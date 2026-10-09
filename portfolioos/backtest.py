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
from portfolioos.policy import policy_history
from portfolioos.regimes import causal_regime, policy_regimes
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
    constrained_baseline: bool = False
    strict_execution_constraints: bool = False
    execution_turnover_reserve: float = 0.0
    execution_sector_reserve: float = 0.0
    execution_te_reserve: float = 0.0
    covariance_method: str = "ledoit_wolf"
    policy_weights: dict | None = None
    regime_source: str | None = None
    regime_asset: str | None = None
    regime_lookback: int = 63
    regime_min_history: int = 252
    regime_te_budgets: dict | None = None
    optimizer: OptimizerConfig = field(default_factory=OptimizerConfig)

    def __post_init__(self):
        if not 0 <= self.execution_turnover_reserve < 1:
            raise ValueError("Invalid execution turnover reserve")
        if (
            self.execution_turnover_reserve > 0
            and self.optimizer.max_turnover is not None
            and (self.execution_turnover_reserve >= self.optimizer.max_turnover)
        ):
            raise ValueError("Execution reserve must be below turnover mandate")
        for reserve, cap in [
            (self.execution_sector_reserve, self.optimizer.max_sector_active_weight),
            (self.execution_te_reserve, self.optimizer.max_tracking_error),
        ]:
            if not 0 <= reserve < 1 or (
                reserve > 0 and cap is not None and reserve >= cap
            ):
                raise ValueError("Invalid execution risk reserve")
        if self.covariance_method not in {"ledoit_wolf", "sample"}:
            raise ValueError("Unknown covariance method")
        if self.regime_source not in {None, "policy"}:
            raise ValueError("Unknown primary regime source")
        if self.regime_source == "policy" and self.policy_weights is None:
            raise ValueError("Policy regimes require policy target weights")
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
            states = (
                {"normal", "high"}
                if self.regime_source == "policy"
                else {"low", "normal", "high"}
            )
            if (self.regime_asset is None and self.regime_source is None) or set(
                self.regime_te_budgets
            ) != states:
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


class ExecutionFailure(RuntimeError):
    """An attempted target violates the actual execution mandate; retain audit path."""

    def __init__(self, message, date, partial, attempted):
        super().__init__(message)
        self.date = date
        self.partial = partial
        self.attempted = attempted


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
    if config.regime_asset is not None or config.regime_source is not None:
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
    policy = policy_ends = policy_records = regimes = None
    if config.policy_weights is not None:
        if benchmark is not None:
            raise ValueError("Use policy targets or external benchmark, not both")
        policy, policy_ends, policy_records = policy_history(
            prices, config.policy_weights
        )
        if config.regime_source == "policy":
            regimes = policy_regimes(
                policy_records.gross.iloc[1:],
                config.regime_lookback,
                config.regime_min_history,
            )
    start = (
        pd.Timestamp(config.start_date) if config.start_date else prices.index[warmup]
    )
    end = pd.Timestamp(config.end_date) if config.end_date else prices.index[-1]
    holdings, benchmarks, records, scores, statuses, dates = [], [], [], [], [], []
    previous = wb = None
    last_period = None
    last_benchmark_snapshot = None
    known_holdings = {}
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
        if policy is not None:
            wb = policy.loc[date].copy()
        elif benchmark is not None:
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
            # Lagged decisions must not consume execution-close drift or targets.
            decision_previous = previous
            decision_benchmark = wb
            if config.information_lag >= 2:
                if policy is not None:
                    decision_benchmark = policy_ends.loc[asof].copy()
                    if policy_records.loc[date, "rebalance"]:
                        # Fixed monthly target is known before the execution close.
                        decision_benchmark = pd.Series(config.policy_weights).reindex(
                            prices.columns
                        )
                elif benchmark is not None:
                    available_at_decision = benchmark.loc[:asof]
                    if available_at_decision.empty:
                        raise ValueError("No benchmark available at decision date")
                    decision_benchmark = available_at_decision.iloc[-1].copy()
                decision_previous = known_holdings.get(asof, decision_benchmark).copy()
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
            covariance = estimate_covariance(
                history, config.covariance_lookback, method=config.covariance_method
            )
            regime = None
            optimizer = config.optimizer
            if regimes is not None:
                regime = regimes.loc[asof, "regime"]
                if regime is None:
                    raise ValueError("Insufficient causal policy regime history")
                if config.regime_te_budgets is not None:
                    optimizer = replace(
                        optimizer, max_tracking_error=config.regime_te_budgets[regime]
                    )
            elif config.regime_asset is not None:
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
                decision_optimizer = optimizer
                if optimizer.max_turnover is not None:
                    decision_optimizer = replace(
                        optimizer,
                        max_turnover=optimizer.max_turnover
                        - config.execution_turnover_reserve,
                    )
                decision_optimizer = replace(
                    decision_optimizer,
                    max_sector_active_weight=None
                    if optimizer.max_sector_active_weight is None
                    else optimizer.max_sector_active_weight
                    - config.execution_sector_reserve,
                    max_tracking_error=None
                    if optimizer.max_tracking_error is None
                    else optimizer.max_tracking_error - config.execution_te_reserve,
                )
                solution = optimize(
                    score,
                    covariance,
                    decision_benchmark,
                    decision_previous,
                    sectors,
                    decision_optimizer,
                )
            else:
                if config.strategy == "policy":
                    # Follow the benchmark's declared rule; drift needs no order.
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
                baseline_constraints = (
                    optimizer
                    if config.constrained_baseline
                    else replace(
                        optimizer,
                        max_position_weight=1.0,
                        max_tracking_error=None,
                        max_sector_active_weight=None,
                        max_turnover=None,
                    )
                )
                errors, te = constraint_violations(
                    candidate.to_numpy(),
                    decision_benchmark.to_numpy(),
                    decision_previous.to_numpy(),
                    covariance.to_numpy(),
                    None if sectors is None else sectors.to_numpy(),
                    baseline_constraints,
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
            constrained = config.strategy == "optimized" or config.constrained_baseline
            execution_errors, execution_te = constraint_violations(
                target.to_numpy(),
                wb.to_numpy(),
                previous.to_numpy(),
                covariance.to_numpy(),
                None if sectors is None else sectors.to_numpy(),
                optimizer
                if constrained
                else replace(
                    optimizer,
                    max_position_weight=1.0,
                    max_tracking_error=None,
                    max_sector_active_weight=None,
                    max_turnover=None,
                ),
            )
            if constrained and config.strict_execution_constraints and execution_errors:
                raise ExecutionFailure(
                    f"Execution mandate failed on {date.date()}: "
                    + ", ".join(execution_errors),
                    date,
                    {
                        "returns": pd.DataFrame(records, index=dates),
                        "weights": pd.DataFrame(
                            holdings, index=dates, columns=prices.columns
                        ),
                        "benchmark_weights": pd.DataFrame(
                            benchmarks, index=dates, columns=prices.columns
                        ),
                        "optimization": pd.DataFrame(statuses),
                    },
                    {
                        "information_date": str(asof.date()),
                        "execution_date": str(execution_date.date()),
                        "decision_turnover": one_way_turnover(
                            target, decision_previous
                        ),
                        "execution_turnover": turnover,
                        "violations": execution_errors,
                        "target": target.to_dict(),
                    },
                )
            cost = transaction_cost(turnover, config.transaction_cost_bps)
            scores.append(score.rename(date))
            statuses.append(
                {
                    "date": date,
                    "information_date": asof,
                    "execution_date": execution_date,
                    "return_date": date,
                    "regime": regime,
                    "tracking_error_budget": optimizer.max_tracking_error
                    if constrained
                    else None,
                    "decision_turnover": one_way_turnover(target, decision_previous),
                    "decision_turnover_budget": (
                        None
                        if optimizer.max_turnover is None
                        else optimizer.max_turnover - config.execution_turnover_reserve
                    )
                    if constrained
                    else None,
                    "execution_tracking_error": execution_te,
                    "execution_violations": ", ".join(execution_errors),
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
        if policy_records is not None:
            # Each independent period starts endowed at the benchmark close;
            # subsequent policy orders use their own monthly calendar.
            benchmark_turnover = (
                0.0 if len(dates) == 1 else float(policy_records.loc[date, "turnover"])
            )
            benchmark_cost = transaction_cost(
                benchmark_turnover, config.transaction_cost_bps
            )
            records[-1].update(
                benchmark_turnover=benchmark_turnover,
                benchmark_cost=benchmark_cost,
                benchmark_net=bench - benchmark_cost,
            )
        previous = pd.Series(drift_weights(target, realized), index=prices.columns)
        known_holdings[date] = previous.copy()
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
