from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from portfolioos.backtest import BacktestConfig, run_backtest
from portfolioos.costs import drift_weights, one_way_turnover


def test_future_price_mutation_cannot_change_past_weights(market, config, result):
    p, m = market
    mutated = p.copy()
    cutoff = p.index[110]
    mutated.loc[cutoff:] *= np.linspace(0.5, 2, p.shape[1])
    rerun = run_backtest(mutated, metadata=m, config=config)
    pd.testing.assert_frame_equal(
        result.weights.loc[:cutoff], rerun.weights.loc[:cutoff]
    )
    pd.testing.assert_frame_equal(
        result.signal_scores.loc[:cutoff], rerun.signal_scores.loc[:cutoff]
    )
    pd.testing.assert_frame_equal(
        result.optimization.loc[:cutoff], rerun.optimization.loc[:cutoff]
    )


def test_same_day_return_not_used_even_at_rebalance(market, config, result):
    p, m = market
    date = result.signal_scores.index[2]
    mutated = p.copy()
    mutated.loc[date] *= np.linspace(0.5, 2, p.shape[1])
    # Test the information boundary itself. Later solves after the artificial
    # price crash/rebound are unrelated and can be ill-conditioned on older stacks.
    rerun = run_backtest(
        mutated, metadata=m, config=replace(config, end_date=str(date.date()))
    )
    pd.testing.assert_frame_equal(result.weights.loc[:date], rerun.weights.loc[:date])
    assert result.returns.loc[date, "gross"] != rerun.returns.loc[date, "gross"]


def test_eligibility_and_information_dates(market, result):
    assert result.weights.index[0] == market[0].index[41]
    for date, row in result.optimization.iterrows():
        assert (
            row.information_date == market[0].index[market[0].index.get_loc(date) - 1]
        )


def test_drift_turnover_and_reconciliation(result):
    r = result.returns
    np.testing.assert_allclose(
        (result.weights * result.asset_returns).sum(axis=1), r.gross
    )
    np.testing.assert_allclose(
        (result.benchmark_weights * result.asset_returns).sum(axis=1), r.benchmark
    )
    np.testing.assert_allclose(r.net, r.gross - r.cost)
    np.testing.assert_allclose(r.active, r.net - r.benchmark)
    np.testing.assert_allclose(r.cost, r.turnover * 10 / 10000)
    for i in range(1, len(r)):
        previous = drift_weights(
            result.weights.iloc[i - 1], result.asset_returns.iloc[i - 1]
        )
        if r.rebalance.iloc[i]:
            assert r.turnover.iloc[i] == pytest.approx(
                one_way_turnover(result.weights.iloc[i], previous)
            )
            np.testing.assert_allclose(result.benchmark_weights.iloc[i], 0.1)
        else:
            np.testing.assert_allclose(result.weights.iloc[i], previous)
            assert r.turnover.iloc[i] == 0
            np.testing.assert_allclose(
                result.benchmark_weights.iloc[i],
                drift_weights(
                    result.benchmark_weights.iloc[i - 1],
                    result.asset_returns.iloc[i - 1],
                ),
            )


def test_supplied_benchmark_timing_and_future_mutation(market, config):
    p, m = market
    dates = p.index[[0, 70, 120]]
    b = pd.DataFrame(0.1, index=dates, columns=p.columns)
    b.iloc[1] = [0.2, 0, *([0.1] * 8)]
    first = run_backtest(p, b, m, config=config)
    changed = b.copy()
    changed.iloc[-1] = [0.15, 0.05, *([0.1] * 8)]
    second = run_backtest(p, changed, m, config=config)
    pd.testing.assert_frame_equal(
        first.weights.loc[: dates[-1]], second.weights.loc[: dates[-1]]
    )
    pd.testing.assert_frame_equal(
        first.benchmark_weights.loc[: dates[-1]],
        second.benchmark_weights.loc[: dates[-1]],
    )
    np.testing.assert_allclose(first.benchmark_weights.loc[p.index[71]], b.iloc[1])
    assert not np.allclose(first.benchmark_weights.loc[p.index[70]], b.iloc[1])


def test_external_signals_are_asof(market, config):
    p, m = market
    external = p.copy()
    cfg = replace(config, signal_weights={"external": 1})
    first = run_backtest(p, metadata=m, external_signals=external, config=cfg)
    date = first.signal_scores.index[2]
    external.loc[date:] *= np.linspace(0.5, 2, 10)
    second = run_backtest(p, metadata=m, external_signals=external, config=cfg)
    pd.testing.assert_frame_equal(first.weights.loc[:date], second.weights.loc[:date])


@pytest.mark.parametrize("frequency", ["daily", "weekly"])
def test_alternative_schedules_and_date_range(market, config, frequency):
    p, m = market
    cfg = replace(
        config,
        rebalance_frequency=frequency,
        start_date=str(p.index[60].date()),
        end_date=str(p.index[75].date()),
    )
    result = run_backtest(p, metadata=m, config=cfg)
    assert len(result.weights) == 16
    assert len(result.signal_scores) == (16 if frequency == "daily" else 4)


@pytest.mark.parametrize(
    "problem",
    ["no_dates", "benchmark_late", "external_late", "infeasible", "exhausted"],
)
def test_explicit_failures(market, config, problem):
    p, m = market
    kwargs = {"metadata": m, "config": config}
    error = ValueError
    if problem == "no_dates":
        kwargs["config"] = replace(config, start_date="2100-01-01")
    elif problem == "benchmark_late":
        kwargs["benchmark_weights"] = p.iloc[-1:]
    elif problem == "external_late":
        kwargs["external_signals"] = p.iloc[-1:]
    elif problem == "infeasible":
        kwargs["config"] = replace(
            config, optimizer=replace(config.optimizer, max_position_weight=0.01)
        )
        error = RuntimeError
    else:
        kwargs["config"] = replace(config, transaction_cost_bps=1e9)
    with pytest.raises(error):
        run_backtest(p, **kwargs)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"rebalance_frequency": "yearly"},
        {"momentum_skip": 253},
        {"volatility_lookback": 1},
        {"reversal_lookback": 0},
        {"transaction_cost_bps": -1},
        {"start_date": "2020-01-01", "end_date": "2019-01-01"},
    ],
)
def test_bad_config(kwargs):
    with pytest.raises(ValueError):
        BacktestConfig(**kwargs)
