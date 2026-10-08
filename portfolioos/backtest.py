"""Walk-forward simulation with a structurally truncated information set."""

from dataclasses import dataclass, field, replace

import pandas as pd

from portfolioos.costs import drift_weights, one_way_turnover, transaction_cost
from portfolioos.covariance import estimate_covariance
from portfolioos.data import (
    align_benchmark,
    align_external_signals,
    align_sectors,
    validate_prices,
)
from portfolioos.optimizer import (
    OptimizationResult,
    OptimizerConfig,
    constraint_violations,
    optimize,
)
from portfolioos.regimes import causal_regime
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
    information_lag: int = 1
    strategy: str = "optimized"
    regime_asset: str | None = None
    regime_lookback: int = 63
    regime_min_history: int = 252
    regime_te_budgets: dict | None = None
    optimizer: OptimizerConfig = field(default_factory=OptimizerConfig)

    def __post_init__(self):
        if self.strategy not in {
            "optimized",
            "policy",
            "equal_weight",
            "inverse_volatility",
        }:
            raise ValueError("Unknown strategy")
        if not isinstance(self.information_lag, int) or self.information_lag < 1:
            raise ValueError("information_lag must be a positive integer")
        if self.regime_lookback < 2 or self.regime_min_history < 2:
            raise ValueError("Invalid regime history")
        if self.regime_te_budgets is not None:
            if self.regime_asset is None or set(self.regime_te_budgets) != {
                "low",
                "normal",
                "high",
            }:
                raise ValueError("Regime budgets require an asset and all three states")
            for budget in self.regime_te_budgets.values():
                replace(self.optimizer, max_tracking_error=budget)
                if budget is None:
                    raise ValueError("Regime budgets must be finite")
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
    if config.regime_asset is not None:
        warmup = max(warmup, config.regime_lookback + config.regime_min_history + 1)
    warmup += config.information_lag - 1
    prices = validate_prices(
        prices, warmup + 1, config.max_missing_fraction, config.fill_limit
    )
    if config.regime_asset is not None and config.regime_asset not in prices.columns:
        raise ValueError("Regime asset is outside the price universe")
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
        history = prices.iloc[: i - config.information_lag + 1]
        asof = history.index[-1]
        execution_date = prices.index[i - 1]
        period = (
            date.to_period("M")
            if config.rebalance_frequency == "monthly"
            else date.to_period("W-FRI")
            if config.rebalance_frequency == "weekly"
            else date
        )
        rebalance = previous is None or period != last_period
        if benchmark is not None:
            available = benchmark.loc[:execution_date]
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
            regime = None
            optimizer = config.optimizer
            if config.regime_asset is not None:
                regime = causal_regime(
                    history[config.regime_asset],
                    config.regime_lookback,
                    config.regime_min_history,
                )
                if config.regime_te_budgets is not None:
                    optimizer = replace(
                        optimizer, max_tracking_error=config.regime_te_budgets[regime]
                    )
            if config.strategy == "optimized":
                solution = optimize(score, covariance, wb, previous, sectors, optimizer)
            else:
                if config.strategy == "policy":
                    candidate = wb.copy()
                elif config.strategy == "equal_weight":
                    candidate = pd.Series(1 / len(wb), index=wb.index)
                else:
                    vol = (
                        history.pct_change(fill_method=None)
                        .iloc[-config.volatility_lookback :]
                        .std()
                    )
                    if (vol <= 0).any():
                        raise ValueError(
                            "Inverse volatility requires positive volatility"
                        )
                    candidate = (1 / vol) / (1 / vol).sum()
                errors, te = constraint_violations(
                    candidate.to_numpy(),
                    wb.to_numpy(),
                    previous.to_numpy(),
                    covariance.to_numpy(),
                    None if sectors is None else sectors.to_numpy(),
                    optimizer,
                )
                solution = OptimizationResult(
                    None if errors else candidate,
                    "constraint_violation" if errors else "rule_based",
                    ", ".join(errors),
                    te,
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
                    "execution_date": execution_date,
                    "return_date": date,
                    "regime": regime,
                    "tracking_error_budget": optimizer.max_tracking_error,
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
