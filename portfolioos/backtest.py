"""Walk-forward simulation with a structurally truncated information set."""

from dataclasses import dataclass, field

import pandas as pd

from portfolioos.costs import drift_weights, one_way_turnover, transaction_cost
from portfolioos.covariance import estimate_covariance
from portfolioos.data import (
    align_benchmark,
    align_external_signals,
    align_sectors,
    validate_prices,
)
from portfolioos.optimizer import OptimizerConfig, optimize
from portfolioos.signals import composite_score


@dataclass(frozen=True)
class BacktestConfig:
    start_date: str | None = None
    end_date: str | None = None
    rebalance_frequency: str = "monthly"
    signal_weights: dict = field(
        default_factory=lambda: {
            "momentum_12_1": 1.0,
            "low_volatility": 1.0,
            "reversal_1m": 0.5,
        }
    )
    momentum_lookback: int = 252
    momentum_skip: int = 21
    volatility_lookback: int = 63
    reversal_lookback: int = 21
    covariance_lookback: int = 252
    transaction_cost_bps: float = 10.0
    max_missing_fraction: float = 0.0
    fill_limit: int = 0
    optimizer: OptimizerConfig = field(default_factory=OptimizerConfig)

    def __post_init__(self):
        if self.rebalance_frequency not in {"monthly", "weekly", "daily"}:
            raise ValueError("Rebalance frequency must be monthly, weekly or daily")
        if not 0 < self.momentum_skip < self.momentum_lookback:
            raise ValueError("Invalid momentum lookbacks")
        if min(self.volatility_lookback, self.covariance_lookback) < 2:
            raise ValueError("Risk lookbacks must be at least 2")
        if self.reversal_lookback < 1:
            raise ValueError("Reversal lookback must be positive")
        transaction_cost(0, self.transaction_cost_bps)
        if self.start_date and self.end_date:
            if pd.Timestamp(self.start_date) > pd.Timestamp(self.end_date):
                raise ValueError("start_date exceeds end_date")


@dataclass
class BacktestResult:
    weights: pd.DataFrame
    benchmark_weights: pd.DataFrame
    active_weights: pd.DataFrame
    signal_scores: pd.DataFrame
    returns: pd.DataFrame
    asset_returns: pd.DataFrame
    optimization: pd.DataFrame
    sectors: pd.Series | None
    config: BacktestConfig


def run_backtest(
    prices, benchmark_weights=None, metadata=None, external_signals=None, config=None
):
    config = config or BacktestConfig()
    warmup = (
        max(
            config.momentum_lookback,
            config.volatility_lookback,
            config.reversal_lookback,
            config.covariance_lookback,
        )
        + 1
    )
    prices = validate_prices(
        prices, warmup + 1, config.max_missing_fraction, config.fill_limit
    )
    sectors = align_sectors(metadata, prices.columns)
    benchmark = (
        None
        if benchmark_weights is None
        else align_benchmark(benchmark_weights, prices.columns)
    )
    external = (
        None
        if external_signals is None
        else align_external_signals(external_signals, prices.columns)
    )
    returns = prices.pct_change(fill_method=None)
    start = (
        pd.Timestamp(config.start_date) if config.start_date else prices.index[warmup]
    )
    end = pd.Timestamp(config.end_date) if config.end_date else prices.index[-1]
    holdings, benchmarks, records, scores, statuses, dates = [], [], [], [], [], []
    previous = wb = None
    last_period = None
    last_benchmark_snapshot = None
    for i in range(warmup, len(prices)):
        date = prices.index[i]
        if date < start or date > end:
            continue
        # Exclusive slice: the realized return for date is inaccessible to models.
        history = prices.iloc[:i]
        asof = history.index[-1]
        period = (
            date.to_period("M")
            if config.rebalance_frequency == "monthly"
            else date.to_period("W-FRI")
            if config.rebalance_frequency == "weekly"
            else date
        )
        rebalance = previous is None or period != last_period
        if benchmark is not None:
            available = benchmark.loc[:asof]
            if available.empty:
                raise ValueError(f"No benchmark snapshot known by {asof.date()}")
            snapshot = available.index[-1]
            # Supplied rows are target updates, effective on the next price date.
            if snapshot != last_benchmark_snapshot:
                wb = available.iloc[-1].copy()
                last_benchmark_snapshot = snapshot
        elif rebalance:
            wb = pd.Series(1 / len(prices.columns), index=prices.columns)
        if previous is None:
            # Initial endowment is benchmark holdings; charge active transition.
            previous = wb.copy()
        turnover = cost = 0.0
        if rebalance:
            ext = None
            if external is not None:
                known = external.loc[:asof]
                if known.empty:
                    raise ValueError(f"No external signal known by {asof.date()}")
                ext = known.iloc[-1]
            score = composite_score(
                history,
                config.signal_weights,
                {
                    "momentum": config.momentum_lookback,
                    "skip": config.momentum_skip,
                    "volatility": config.volatility_lookback,
                    "reversal": config.reversal_lookback,
                },
                ext,
            )
            covariance = estimate_covariance(history, config.covariance_lookback)
            solution = optimize(
                score, covariance, wb, previous, sectors, config.optimizer
            )
            if solution.weights is None:
                raise RuntimeError(
                    f"Optimization failed on {date.date()}: "
                    f"{solution.status}: {solution.message}"
                )
            target = solution.weights
            turnover = one_way_turnover(target, previous)
            cost = transaction_cost(turnover, config.transaction_cost_bps)
            scores.append(score.rename(date))
            statuses.append(
                {
                    "date": date,
                    "information_date": asof,
                    "status": solution.status,
                    "message": solution.message,
                    "estimated_tracking_error": solution.tracking_error,
                }
            )
        else:
            target = previous
        realized = returns.iloc[i]
        gross, bench = float(target @ realized), float(wb @ realized)
        net = gross - cost
        if net <= -1:
            raise ValueError("Costs and returns exhaust portfolio NAV")
        dates.append(date)
        holdings.append(target.to_numpy().copy())
        benchmarks.append(wb.to_numpy().copy())
        records.append(
            {
                "gross": gross,
                "net": net,
                "benchmark": bench,
                "active": net - bench,
                "gross_active": gross - bench,
                "turnover": turnover,
                "cost": cost,
                "rebalance": rebalance,
            }
        )
        previous = pd.Series(drift_weights(target, realized), index=prices.columns)
        wb = pd.Series(drift_weights(wb, realized), index=prices.columns)
        last_period = period
    if not dates:
        raise ValueError("No eligible evaluation dates after warmup")
    index = pd.DatetimeIndex(dates, name="date")
    w = pd.DataFrame(holdings, index=index, columns=prices.columns)
    b = pd.DataFrame(benchmarks, index=index, columns=prices.columns)
    return BacktestResult(
        w,
        b,
        w - b,
        pd.DataFrame(scores),
        pd.DataFrame(records, index=index),
        returns.loc[index],
        pd.DataFrame(statuses).set_index("date"),
        sectors,
        config,
    )
