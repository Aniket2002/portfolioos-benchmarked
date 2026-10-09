"""Phase 2 declarations, not fitted parameters or an automated search."""

from dataclasses import asdict, replace

from portfolioos.backtest import BacktestConfig
from portfolioos.optimizer import OptimizerConfig

ASSETS = ["SPY", "IWM", "EFA", "EEM", "IEF", "TLT", "LQD", "HYG", "GLD", "VNQ"]
POLICY = dict(zip(ASSETS, [0.30, 0.05, 0.15, 0.10, 0.20, 0.05, 0.15, 0, 0, 0]))
SECTORS = dict(
    zip(ASSETS, ["equity"] * 4 + ["fixed_income"] * 4 + ["gold", "real_estate"])
)
PERIODS = {
    "development": ["2011-01-03", "2017-12-29"],
    "validation": ["2018-01-02", "2022-12-30"],
    "holdout": ["2023-01-03", "2026-09-30"],
}
INCEPTION = dict(
    zip(
        ASSETS,
        [
            "1993-01-22",
            "2000-05-22",
            "2001-08-14",
            "2003-04-07",
            "2002-07-22",
            "2002-07-22",
            "2002-07-22",
            "2007-04-04",
            "2004-11-18",
            "2004-09-23",
        ],
    )
)


def phase2_protocol():
    base = BacktestConfig(
        information_lag=2,
        policy_weights=POLICY,
        regime_source="policy",
        strict_execution_constraints=True,
        execution_turnover_reserve=0.02,
        execution_sector_reserve=0.01,
        execution_te_reserve=0.001,
        optimizer=OptimizerConfig(max_position_weight=0.35),
    )
    scenarios = {"fixed_risk": base}
    groups = {
        "A_tracking_error": [],
        "B_turnover": [],
        "C_costs": [],
        "D_regimes": ["fixed_risk", "regime_aware"],
        "E_ablations": ["fixed_risk", "regime_aware"],
        "F_strategies": [
            "policy",
            "equal_weight",
            "inverse_volatility",
            "fixed_risk",
            "regime_aware",
        ],
        "G_robustness": ["fixed_risk", "sample_covariance", "lag_3", "weekly"],
    }
    for cap in [0.04, 0.08, 0.12]:
        name = f"te_{cap:.0%}".replace("%", "pct")
        scenarios[name] = replace(
            base, optimizer=replace(base.optimizer, max_tracking_error=cap)
        )
        groups["A_tracking_error"].append(name)
    for cap in [0.10, 0.30, 0.50]:
        name = f"turnover_{cap:.0%}".replace("%", "pct")
        scenarios[name] = replace(
            base, optimizer=replace(base.optimizer, max_turnover=cap)
        )
        groups["B_turnover"].append(name)
    for bps in [0, 10, 25, 40]:
        name = f"cost_{bps}bps"
        scenarios[name] = replace(base, transaction_cost_bps=bps)
        groups["C_costs"].append(name)
    scenarios["regime_aware"] = replace(
        base, regime_te_budgets={"normal": 0.08, "high": 0.05}
    )
    for signal in base.signal_weights:
        name = f"without_{signal}"
        weights = {
            key: value for key, value in base.signal_weights.items() if key != signal
        }
        scenarios[name] = replace(base, signal_weights=weights)
        groups["E_ablations"].append(name)
    for strategy in ["policy", "equal_weight", "inverse_volatility"]:
        scenarios[strategy] = replace(base, strategy=strategy)
    scenarios["sample_covariance"] = replace(base, covariance_method="sample")
    scenarios["lag_3"] = replace(base, information_lag=3)
    scenarios["weekly"] = replace(base, rebalance_frequency="weekly")
    return {
        "study": "Independent ten-ETF historical construction study",
        "assets": ASSETS,
        "policy_weights": POLICY,
        "sectors": SECTORS,
        "periods": PERIODS,
        "data_range": ["2009-01-01", "2026-09-30"],
        "scenarios": {name: asdict(config) for name, config in scenarios.items()},
        "experiment_groups": groups,
        "bootstrap": {
            "seed": 20261008,
            "block_length": 21,
            "resamples": 2000,
            "confidence": 0.95,
            "metric": "annualized_mean_daily_active_return",
        },
        "regime_rule": (
            "63-day policy volatility > prior expanding 75th percentile; "
            "252 earlier values"
        ),
        "initial_endowment": (
            "benchmark holdings at execution close for each independent period"
        ),
        "benchmark_rule": (
            "reset before first trading session return of each month; drift otherwise"
        ),
        "cost_rule": "half-L1 turnover times bps/10000; additive NAV approximation",
        "execution_rule": (
            "decision inputs end t-lag; modeled close t-1 target fill; return t"
        ),
        "execution_mandate": (
            "strict execution check; fail on drift-induced violations, never retarget"
        ),
        "design_revision": (
            "Original development/validation runs failed execution drift checks; "
            "preserved under results/empirical_phase2. Final formation uses 2pp "
            "turnover, 1pp sector and 0.1pp TE reserves, identical across active "
            "scenarios. Execution mandates unchanged; no guarantee against breaches."
        ),
        "holdout_previously_used_for_selection": False,
        "incidental_holdout_quote_exposure": (
            "Inherited source-discovery record reports incidental late-2026 SPY "
            "quotes; no holdout portfolio performance used for selection. Full "
            "panel accessed for ingestion QA only."
        ),
        "multiple_comparisons": (
            "descriptive intervals; no multiplicity-adjusted hypothesis claim"
        ),
    }
