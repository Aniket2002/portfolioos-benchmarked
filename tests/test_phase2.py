import json
from dataclasses import asdict, replace

import numpy as np
import pandas as pd
import pytest

from portfolioos.backtest import ExecutionFailure, run_backtest
from portfolioos.covariance import estimate_covariance
from portfolioos.data_quality import inspect_bundle
from portfolioos.empirical import cost_clone, evaluate_period, read_protocol
from portfolioos.empirical_protocol import ASSETS, POLICY, phase2_protocol
from portfolioos.historical import file_hash
from portfolioos.policy import policy_history
from portfolioos.regimes import policy_regimes
from portfolioos.reporting import validate_result
from portfolioos.uncertainty import block_interval
from tests.test_empirical import make_bundle


def test_monthly_policy_drift_and_costs(market):
    prices, _ = market
    prices = prices.rename(columns=dict(zip(prices.columns, ASSETS)))
    w, ends, records = policy_history(prices, POLICY)
    np.testing.assert_allclose(w.sum(axis=1), 1)
    np.testing.assert_allclose(
        (w * prices.pct_change(fill_method=None)).sum(axis=1), records.gross
    )
    for i in range(1, len(prices)):
        if records.rebalance.iloc[i]:
            np.testing.assert_allclose(w.iloc[i], list(POLICY.values()))
        else:
            pd.testing.assert_series_equal(
                w.iloc[i], ends.iloc[i - 1], check_names=False
            )
    assert records.turnover.sum() > 0
    assert not np.allclose(w.iloc[20], list(POLICY.values()))


def test_primary_regime_uses_prior_75_percentile_and_ties():
    returns = pd.Series(
        np.sin(np.arange(400)) * 0.01, index=pd.date_range("2009-01-01", periods=400)
    )
    result = policy_regimes(returns)
    date = result.index[314]
    previous = returns.rolling(63).std().iloc[:314].dropna() * np.sqrt(252)
    assert len(previous) == 252
    assert result.loc[date, "threshold"] == pytest.approx(previous.quantile(0.75))
    assert result.regime.iloc[:314].isna().all()
    changed = returns.copy()
    changed.iloc[350:] = 100
    pd.testing.assert_frame_equal(result.iloc[:350], policy_regimes(changed).iloc[:350])
    constant = policy_regimes(pd.Series(0.0, index=returns.index))
    assert set(constant.regime.dropna()) == {"normal"}
    assert set(result.regime.dropna()) <= {"normal", "high"}


def test_no_execution_close_prices_enter_target(market, config):
    prices, metadata = market
    cfg = replace(config, information_lag=2)
    first = run_backtest(prices, metadata=metadata, config=cfg)
    date = first.signal_scores.index[2]
    i = prices.index.get_loc(date)
    changed = prices.copy()
    changed.iloc[i - 1] *= np.linspace(0.9, 1.1, len(prices.columns))
    second = run_backtest(
        changed, metadata=metadata, config=replace(cfg, end_date=str(date.date()))
    )
    pd.testing.assert_series_equal(first.weights.loc[date], second.weights.loc[date])
    assert first.returns.loc[date, "turnover"] != second.returns.loc[date, "turnover"]


def test_future_benchmark_snapshot_does_not_enter_lagged_decision(market, config):
    prices, metadata = market
    cfg = replace(config, information_lag=2)
    baseline = run_backtest(prices, metadata=metadata, config=cfg)
    date = baseline.signal_scores.index[2]
    execution = prices.index[prices.index.get_loc(date) - 1]
    b = pd.DataFrame(0.1, index=prices.index[[0]], columns=prices.columns)
    first = run_backtest(
        prices, b, metadata, config=replace(cfg, end_date=str(date.date()))
    )
    b.loc[execution] = [0.2, 0, *([0.1] * 8)]
    second = run_backtest(
        prices, b, metadata, config=replace(cfg, end_date=str(date.date()))
    )
    pd.testing.assert_series_equal(first.weights.loc[date], second.weights.loc[date])


def test_comparisons_are_unconstrained_but_explicit_baseline_can_fail(market, config):
    prices, metadata = market
    cfg = replace(
        config,
        strategy="equal_weight",
        information_lag=2,
        optimizer=replace(
            config.optimizer,
            max_position_weight=0.08,
            max_turnover=0,
            max_tracking_error=0,
        ),
    )
    result = run_backtest(prices, metadata=metadata, config=cfg)
    validate_result(result)
    assert result.optimization.tracking_error_budget.isna().all()
    with pytest.raises(RuntimeError, match="position bounds"):
        run_backtest(
            prices, metadata=metadata, config=replace(cfg, constrained_baseline=True)
        )


def test_sample_covariance_matches_numpy(market):
    prices, _ = market
    expected = (
        np.cov(prices.pct_change(fill_method=None).iloc[-40:].to_numpy().T, ddof=1)
        * 252
    )
    actual = estimate_covariance(prices, 40, ridge=0, method="sample")
    np.testing.assert_allclose(actual, expected)
    with pytest.raises(ValueError, match="Unknown"):
        estimate_covariance(prices, 40, method="other")


def test_execution_buffer_keeps_both_turnover_constraints(market, config):
    prices, metadata = market
    cfg = replace(
        config,
        information_lag=2,
        strict_execution_constraints=True,
        execution_turnover_reserve=0.02,
    )
    result = run_backtest(prices, metadata=metadata, config=cfg)
    assert (
        result.optimization.decision_turnover
        <= config.optimizer.max_turnover - 0.02 + 1e-7
    ).all()
    assert result.returns.turnover.max() <= config.optimizer.max_turnover + 1e-7
    validate_result(result)
    with pytest.raises(ValueError, match="reserve"):
        replace(cfg, execution_turnover_reserve=1)


def test_actual_execution_violation_retains_failed_path(market, config):
    from unittest.mock import patch

    import portfolioos.backtest as engine
    from portfolioos.optimizer import OptimizationResult

    prices, metadata = market
    cfg = replace(
        config,
        information_lag=2,
        strict_execution_constraints=True,
        optimizer=replace(
            config.optimizer,
            max_turnover=0.1,
            max_sector_active_weight=None,
            max_tracking_error=None,
        ),
    )
    baseline = run_backtest(
        prices,
        metadata=metadata,
        config=replace(cfg, strict_execution_constraints=False),
    )
    date = baseline.signal_scores.index[1]
    changed = prices.copy()
    changed.iloc[prices.index.get_loc(date) - 1, 2] *= 4

    def target_rule(score, covariance, benchmark, previous, sectors, optimizer):
        target = pd.Series(0.1, index=score.index)
        target.iloc[0] = 0.2
        target.iloc[1] = 0
        return OptimizationResult(target, "optimal", "test predetermined target", 0)

    with patch.object(engine, "optimize", target_rule):
        with pytest.raises(ExecutionFailure) as caught:
            run_backtest(
                changed,
                metadata=metadata,
                config=replace(cfg, end_date=str(date.date())),
            )
    assert caught.value.partial["returns"].shape[0] > 0
    assert "turnover" in caught.value.attempted["violations"]


def test_cost_accounting_reuses_exact_trade_path(result):
    zero, high = cost_clone(result, 0), cost_clone(result, 40)
    pd.testing.assert_frame_equal(zero.weights, high.weights)
    pd.testing.assert_series_equal(zero.returns.gross, high.returns.gross)
    pd.testing.assert_series_equal(zero.returns.turnover, high.returns.turnover)
    np.testing.assert_allclose(
        zero.returns.net - high.returns.net, result.returns.turnover * 0.004
    )


def test_block_bootstrap_is_reproducible_and_paired():
    values = np.sin(np.arange(100)) * 0.01
    first = block_interval(values, resamples=100)
    assert first == block_interval(values, resamples=100)
    assert first["lower"] <= first["upper"]
    zeros = block_interval(np.zeros(100), resamples=100)
    assert zeros["lower"] == zeros["upper"] == zeros["estimate"] == 0
    with pytest.raises(ValueError):
        block_interval([1, np.nan])


def test_protocol_declares_exact_primary_settings():
    p = phase2_protocol()
    assert p["assets"] == ASSETS
    assert sum(POLICY.values()) == pytest.approx(1)
    base = p["scenarios"]["fixed_risk"]
    assert base["optimizer"]["max_position_weight"] == 0.35
    assert base["regime_source"] == "policy"
    assert p["scenarios"]["regime_aware"]["regime_te_budgets"] == {
        "normal": 0.08,
        "high": 0.05,
    }
    assert len(p["experiment_groups"]) == 7


@pytest.fixture
def study(tmp_path, market, config):
    prices, metadata = market
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    make_bundle(bundle, prices)
    weights = dict.fromkeys(prices.columns, 0.1)
    cfg = replace(config, information_lag=2, policy_weights=weights)
    p = {
        "assets": list(prices.columns),
        "policy_weights": weights,
        "sectors": metadata.sector.to_dict(),
        "periods": {
            "development": [str(prices.index[42].date()), str(prices.index[90].date())],
            "validation": [str(prices.index[91].date()), str(prices.index[120].date())],
            "holdout": [str(prices.index[121].date()), str(prices.index[-1].date())],
        },
        "scenarios": {
            "fixed_risk": asdict(cfg),
            "cost_0bps": asdict(replace(cfg, transaction_cost_bps=0)),
            "policy": asdict(replace(cfg, strategy="policy")),
        },
        "experiment_groups": {"A": ["fixed_risk"]},
        "bootstrap": {
            "block_length": 5,
            "resamples": 50,
            "seed": 1,
            "confidence": 0.95,
            "metric": "annualized_mean_daily_active_return",
        },
    }
    path = tmp_path / "protocol.json"
    path.write_text(json.dumps(p))
    output = tmp_path / "output"
    output.mkdir()
    quality = {
        "status": "passed",
        "model_evaluation_permitted": True,
        "prices_sha256": file_hash(bundle / "prices.csv"),
        "actions_sha256": file_hash(bundle / "actions.csv"),
        "manifest_sha256": file_hash(bundle / "manifest.json"),
    }
    (output / "data_quality.json").write_text(json.dumps(quality))
    return path, bundle, output, prices


def test_declared_runner_never_passes_future_period_to_models(study, monkeypatch):
    path, bundle, output, prices = study
    import portfolioos.empirical as empirical

    real_run = empirical.run_backtest
    cutoffs = []

    def checked_run(panel, *args, **kwargs):
        cutoffs.append(panel.index[-1])
        return real_run(panel, *args, **kwargs)

    monkeypatch.setattr(empirical, "run_backtest", checked_run)
    evaluation = evaluate_period(path, bundle, output, "development")
    assert all(x == prices.index[90] for x in cutoffs)
    assert len(cutoffs) == 3  # baseline, reference, policy; cost clone has no solve
    assert all(row["status"] == "success" for row in evaluation["scenarios"])
    assert not evaluation["holdout_performance_accessed"]
    with pytest.raises(ValueError, match="already exist"):
        evaluate_period(path, bundle, output, "development")
    with pytest.raises(FileNotFoundError):
        evaluate_period(path, bundle, output, "holdout")
    assert not (output / "holdout").exists()


def test_runner_rejects_changed_quality_inputs(study):
    path, bundle, output, _ = study
    with (bundle / "prices.csv").open("a") as handle:
        handle.write("\n")
    with pytest.raises(ValueError, match="changed"):
        evaluate_period(path, bundle, output, "development")


def test_quality_calendar_extremes_and_real_actions(study):
    _, bundle, _, prices = study
    # Income distribution check is expected to reject empty synthetic action
    # ledgers; no synthetic fixture is certified as an empirical dataset.
    q = inspect_bundle(
        bundle,
        list(prices.columns),
        str(prices.index[0].date()),
        str(prices.index[-1].date()),
        expected_sessions=prices.index,
    )
    assert q["status"] == "blocked"
    assert any("No distribution" in e for e in q["errors"])
    extra = pd.DatetimeIndex([prices.index[-1] + pd.Timedelta(days=1)])
    q = inspect_bundle(
        bundle,
        list(prices.columns),
        str(prices.index[0].date()),
        str(extra[-1].date()),
        expected_sessions=prices.index.append(extra),
    )
    assert any("missing NYSE" in e for e in q["errors"])


def test_read_protocol_rejects_bad_identifiers_and_lag(study):
    path, _, _, _ = study
    protocol = json.loads(path.read_text())
    protocol["scenarios"]["fixed_risk"]["information_lag"] = 1
    path.write_text(json.dumps(protocol))
    with pytest.raises(ValueError, match="lag"):
        read_protocol(path)


def test_weekly_active_schedule_keeps_monthly_policy_accounting(market, config):
    prices, metadata = market
    cfg = replace(
        config,
        policy_weights=dict.fromkeys(prices.columns, 0.1),
        information_lag=2,
        rebalance_frequency="weekly",
        strategy="equal_weight",
    )
    result = run_backtest(prices, metadata=metadata, config=cfg)
    validate_result(result)
    _, _, policy = policy_history(prices, cfg.policy_weights)
    np.testing.assert_allclose(
        result.returns.benchmark, policy.gross.loc[result.returns.index]
    )
    monthly_orders = policy.rebalance.loc[result.returns.index].copy()
    monthly_orders.iloc[0] = False  # endowment, not a fee-bearing policy order
    assert (result.returns.benchmark_turnover > 0).equals(monthly_orders)
    assert result.returns.rebalance.sum() > monthly_orders.sum()
    np.testing.assert_allclose(
        result.returns.benchmark_cost,
        result.returns.benchmark_turnover * cfg.transaction_cost_bps / 10000,
    )
    high = cost_clone(result, 40)
    validate_result(high)
    np.testing.assert_allclose(
        high.returns.benchmark_net,
        result.returns.benchmark - result.returns.benchmark_turnover * 0.004,
    )


def test_policy_strategy_matches_independent_net_benchmark(market, config):
    prices, metadata = market
    result = run_backtest(
        prices,
        metadata=metadata,
        config=replace(
            config,
            information_lag=2,
            strategy="policy",
            policy_weights=dict.fromkeys(prices.columns, 0.1),
        ),
    )
    np.testing.assert_allclose(result.returns.net, result.returns.benchmark_net)
    np.testing.assert_allclose(
        result.returns.turnover, result.returns.benchmark_turnover
    )


def test_original_source_response_must_reconcile_with_bundle(study):
    _, bundle, _, prices = study
    source = {
        str(date.date()): {asset: {"Close": 100} for asset in prices.columns}
        for date in prices.index
    }
    path = bundle / "original_prices.json"
    path.write_text(json.dumps(source))
    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["sha256"][path.name] = file_hash(path)
    manifest_path.write_text(json.dumps(manifest))
    report = inspect_bundle(
        bundle,
        list(prices.columns),
        str(prices.index[0].date()),
        str(prices.index[-1].date()),
        expected_sessions=prices.index,
    )
    assert any("Bundle prices differ" in error for error in report["errors"])


def test_final_freeze_and_single_holdout_access(study, monkeypatch, tmp_path):
    import portfolioos.empirical as empirical

    path, bundle, output, _ = study
    evaluate_period(path, bundle, output, "development")
    evaluate_period(path, bundle, output, "validation")
    review = tmp_path / "review.json"
    verification = tmp_path / "verification.json"
    review.write_text(json.dumps({"development_validation_reviewed": True}))
    verification.write_text(json.dumps({"passed": True}))

    def git_state(args, **kwargs):
        return "" if args[1] == "status" else "test-code-commit\n"

    monkeypatch.setattr(empirical.subprocess, "check_output", git_state)
    lock = empirical.freeze_final(path, bundle, output, review, verification)
    assert lock["code_commit"] == "test-code-commit"
    evaluation = evaluate_period(path, bundle, output, "holdout")
    assert evaluation["holdout_performance_accessed"]
    assert (output / "holdout_access.json").exists()
    with pytest.raises(ValueError, match="already exist"):
        evaluate_period(path, bundle, output, "holdout")


@pytest.mark.parametrize("tamper", ["code", "quality", "evidence", "protocol"])
def test_holdout_gate_rejects_tampered_freeze(study, monkeypatch, tmp_path, tamper):
    import portfolioos.empirical as empirical

    path, bundle, output, _ = study
    evaluate_period(path, bundle, output, "development")
    evaluate_period(path, bundle, output, "validation")
    review, verification = tmp_path / "review.json", tmp_path / "tests.json"
    review.write_text(json.dumps({"development_validation_reviewed": True}))
    verification.write_text(json.dumps({"passed": True}))
    monkeypatch.setattr(
        empirical.subprocess,
        "check_output",
        lambda args, **kwargs: "" if args[1] == "status" else "commit\n",
    )
    empirical.freeze_final(path, bundle, output, review, verification)
    if tamper == "code":
        monkeypatch.setattr(
            empirical.subprocess,
            "check_output",
            lambda args, **kwargs: "" if args[1] == "status" else "new-commit\n",
        )
    elif tamper == "evidence":
        with (output / "development" / "evaluation.json").open("a") as handle:
            handle.write("\n")
    elif tamper == "quality":
        quality = json.loads((output / "data_quality.json").read_text())
        quality["additional_review"] = True
        (output / "data_quality.json").write_text(json.dumps(quality))
    else:
        protocol = json.loads(path.read_text())
        protocol["study"] = "changed after freeze"
        path.write_text(json.dumps(protocol))
    with pytest.raises(ValueError):
        evaluate_period(path, bundle, output, "holdout")
    assert not (output / "holdout_access.json").exists()
