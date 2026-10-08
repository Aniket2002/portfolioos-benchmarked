import json
from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from portfolioos.backtest import run_backtest
from portfolioos.historical import file_hash, freeze_protocol, load_historical_bundle
from portfolioos.regimes import causal_regime
from portfolioos.reporting import validate_result
from scripts.run_empirical import run


def make_bundle(tmp_path, prices):
    prices.to_csv(tmp_path / "prices.csv")
    pd.DataFrame(columns=["date", "asset", "type", "value"]).to_csv(
        tmp_path / "actions.csv", index=False
    )
    manifest = {
        key: "SYNTHETIC TEST FIXTURE"
        for key in (
            "source",
            "source_url",
            "license",
            "universe_selection",
            "survivorship_limitations",
            "revision_policy",
            "calendar",
            "timezone",
        )
    }
    manifest.update(
        retrieved_at="2026-10-08T00:00:00Z",
        adjustment_convention="split_and_distribution_adjusted_close",
        sha256={
            name: file_hash(tmp_path / name) for name in ("prices.csv", "actions.csv")
        },
    )
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))


def test_bundle_integrity_and_universe(tmp_path, market):
    prices, _ = market
    make_bundle(tmp_path, prices)
    loaded, manifest = load_historical_bundle(tmp_path, list(prices.columns))
    np.testing.assert_allclose(loaded, prices)
    assert manifest["source"] == "SYNTHETIC TEST FIXTURE"
    with pytest.raises(ValueError, match="universe"):
        load_historical_bundle(tmp_path, list(reversed(prices.columns)))
    with (tmp_path / "prices.csv").open("a") as handle:
        handle.write("\n")
    with pytest.raises(ValueError, match="checksum"):
        load_historical_bundle(tmp_path, list(prices.columns))


def test_freeze_cannot_be_changed(tmp_path):
    path = tmp_path / "protocol.json"
    identity = freeze_protocol({"x": 1}, path)
    assert freeze_protocol({"x": 1}, path) == identity
    with pytest.raises(ValueError, match="Frozen"):
        freeze_protocol({"x": 2}, path)


def test_lag_blocks_execution_close_signals(market, config):
    prices, metadata = market
    cfg = replace(config, information_lag=2)
    first = run_backtest(prices, metadata=metadata, config=cfg)
    date = first.signal_scores.index[2]
    i = prices.index.get_loc(date)
    changed = prices.copy()
    changed.iloc[i - 1] *= np.linspace(0.8, 1.2, 10)
    second = run_backtest(
        changed, metadata=metadata, config=replace(cfg, end_date=str(date.date()))
    )
    pd.testing.assert_series_equal(
        first.signal_scores.loc[date], second.signal_scores.loc[date]
    )
    assert first.optimization.loc[date, "information_date"] == prices.index[i - 2]
    assert first.optimization.loc[date, "execution_date"] == prices.index[i - 1]
    # Sizing/turnover uses actual drift at the execution close, so holdings may differ.
    validate_result(first)


def test_regime_only_uses_supplied_past(market):
    prices, _ = market
    series = prices.iloc[:, 0]
    expected = causal_regime(series.iloc[:100], 10, 20)
    changed = series.copy()
    changed.iloc[100:] *= 100
    assert causal_regime(changed.iloc[:100], 10, 20) == expected
    with pytest.raises(ValueError, match="Insufficient"):
        causal_regime(series.iloc[:20], 10, 20)
    constant = pd.Series(1.0, index=pd.date_range("2020-01-01", periods=50))
    assert causal_regime(constant, 10, 20) == "normal"


@pytest.mark.parametrize("strategy", ["policy", "equal_weight", "inverse_volatility"])
def test_competing_accounting(market, config, strategy):
    prices, metadata = market
    result = run_backtest(
        prices,
        metadata=metadata,
        config=replace(
            config,
            strategy=strategy,
            information_lag=2,
            optimizer=replace(config.optimizer, max_sector_active_weight=0.2),
        ),
    )
    validate_result(result)
    if strategy == "policy":
        np.testing.assert_allclose(result.returns.gross_active, 0, atol=1e-15)


def test_competing_strategy_does_not_relax_constraints(market, config):
    prices, metadata = market
    with pytest.raises(RuntimeError, match="sector active weight"):
        run_backtest(
            prices,
            metadata=metadata,
            config=replace(config, strategy="inverse_volatility", information_lag=2),
        )


def test_regime_budget_is_recorded_and_checked(market, config):
    prices, metadata = market
    cfg = replace(
        config,
        regime_asset=prices.columns[0],
        regime_lookback=10,
        regime_min_history=20,
        regime_te_budgets={"low": 0.1, "normal": 0.08, "high": 0.06},
    )
    result = run_backtest(prices, metadata=metadata, config=cfg)
    validate_result(result)
    assert set(result.optimization.regime) <= {"low", "normal", "high"}
    assert (
        result.optimization.estimated_tracking_error
        <= result.optimization.tracking_error_budget + 1e-7
    ).all()


def test_runner_freezes_and_preserves_results(tmp_path, market, config):
    from dataclasses import asdict

    prices, metadata = market
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    make_bundle(bundle, prices)
    settings = asdict(replace(config, information_lag=2, strategy="policy"))
    protocol = {
        "assets": list(prices.columns),
        "policy_weights": dict.fromkeys(prices.columns, 0.1),
        "sectors": metadata.sector.to_dict(),
        "periods": {
            "development": [str(prices.index[45].date()), str(prices.index[60].date())],
            "validation": [str(prices.index[61].date()), str(prices.index[90].date())],
            "holdout": [str(prices.index[91].date()), str(prices.index[-1].date())],
        },
        "scenarios": {"policy": settings},
    }
    path = tmp_path / "protocol.json"
    path.write_text(json.dumps(protocol))
    output = tmp_path / "output"
    evaluation = run(path, bundle, output)
    assert not evaluation["holdout_access"]
    assert evaluation["scenarios"][0]["status"] == "success"
    with pytest.raises(ValueError, match="exists"):
        run(path, bundle, output)
