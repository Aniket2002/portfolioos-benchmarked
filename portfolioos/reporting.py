"""Offline research artifacts with explicit provenance and accounting checks."""

import json
import platform
from dataclasses import asdict
from importlib.metadata import version
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml

from portfolioos.attribution import sector_attribution, security_attribution, signal_ic
from portfolioos.backtest import BacktestConfig, run_backtest
from portfolioos.experiments import RESEARCH_QUESTION
from portfolioos.metrics import drawdown, ic_metrics, performance_metrics
from portfolioos.optimizer import OptimizerConfig
from portfolioos.synthetic import synthetic_market


def load_config(path):
    with Path(path).open(encoding="utf-8") as handle:
        settings = yaml.safe_load(handle)
    if not isinstance(settings, dict):
        raise ValueError("Configuration must be a mapping")
    settings = settings.copy()
    synthetic = {k: settings.pop(k) for k in ("seed", "assets", "years")}
    optimizer = OptimizerConfig(**settings.pop("optimizer", {}))
    return synthetic, BacktestConfig(optimizer=optimizer, **settings)


def validate_result(result):
    """Fail before exporting if holdings/accounting invariants are broken."""
    for frame in (result.weights, result.benchmark_weights):
        if not np.isfinite(frame.to_numpy()).all() or (frame < -1e-7).any().any():
            raise ValueError("Invalid output holdings")
        if not np.allclose(frame.sum(axis=1), 1, atol=1e-8):
            raise ValueError("Holdings do not sum to one")
    r = result.returns
    if not np.isfinite(r.to_numpy(dtype=float)).all():
        raise ValueError("Nonfinite return outputs")
    if (r[["cost", "turnover"]] < 0).any().any():
        raise ValueError("Negative costs or turnover")
    checks = [
        (r["gross"] - r["cost"], r["net"]),
        ((result.weights * result.asset_returns).sum(axis=1), r["gross"]),
        ((result.benchmark_weights * result.asset_returns).sum(axis=1), r["benchmark"]),
        (security_attribution(result).sum(axis=1), r["gross_active"]),
    ]
    if result.sectors is not None:
        effects = sector_attribution(result)[["allocation", "selection", "interaction"]]
        checks.append(
            (effects.sum(axis=1).groupby(level="date").sum(), r["gross_active"])
        )
    if any(not np.allclose(a, b, atol=1e-10, rtol=1e-8) for a, b in checks):
        raise ValueError("Return or attribution reconciliation failed")
    cap = result.config.optimizer.max_tracking_error
    if (
        cap is not None
        and (result.optimization.estimated_tracking_error > cap + 1e-7).any()
    ):
        raise ValueError("Rebalance tracking error exceeds constraint")


def write_report(result, output, provenance="SYNTHETIC — mechanics demonstration"):
    validate_result(result)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    r = result.returns
    ic = signal_ic(result)
    metrics = performance_metrics(r.net, r.benchmark, r.turnover, r.cost)
    metrics.update(
        {
            "average_absolute_active_weight": float(
                result.active_weights.abs().to_numpy().mean()
            ),
            "maximum_position": float(result.weights.to_numpy().max()),
            "average_estimated_tracking_error": float(
                result.optimization.estimated_tracking_error.mean()
            ),
            **ic_metrics(ic.ic),
        }
    )
    serial_metrics = {k: v if np.isfinite(v) else None for k, v in metrics.items()}
    summary = {
        "software_versions": {
            "python": platform.python_version(),
            **{
                name: version(name)
                for name in (
                    "numpy",
                    "pandas",
                    "scipy",
                    "scikit-learn",
                    "cvxpy",
                    "clarabel",
                    "matplotlib",
                    "PyYAML",
                )
            },
        },
        "provenance": provenance,
        "evaluation_start": str(r.index[0].date()),
        "evaluation_end": str(r.index[-1].date()),
        "observations": len(r),
        "rebalances": len(result.optimization),
        "metrics": serial_metrics,
        "configuration": asdict(result.config),
        "undefined_metrics": [k for k, v in serial_metrics.items() if v is None],
        "notes": [
            "No empirical alpha claim.",
            "Limits apply at rebalances; subsequent drift can exceed target limits.",
            "Attribution is arithmetic daily gross; costs bridge to net active return.",
            "Terminal IC period may be partial; IC ratio is not annualized.",
        ],
    }
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    pd.Series(serial_metrics, name="value").rename_axis("metric").to_csv(
        output / "metrics.csv"
    )
    for name, frame in {
        "weights": result.weights,
        "benchmark_weights": result.benchmark_weights,
        "active_weights": result.active_weights,
        "returns": r,
        "signal_scores": result.signal_scores,
        "optimization": result.optimization,
        "security_attribution": security_attribution(result),
        "signal_ic": ic,
    }.items():
        frame.to_csv(output / f"{name}.csv")
    attribution = (
        sector_attribution(result)
        if result.sectors is not None
        else security_attribution(result)
    )
    attribution.to_csv(output / "attribution.csv")
    charts = {
        "cumulative_returns": (
            (1 + r[["gross", "net", "benchmark"]]).cumprod() - 1,
            "Compounded cumulative return",
        ),
        "cumulative_active_return": (
            ((1 + r.net).cumprod() / (1 + r.benchmark).cumprod() - 1).rename(
                "relative wealth"
            ),
            "Portfolio / benchmark wealth minus one",
        ),
        "drawdown": drawdown(r.net).rename("net portfolio"),
        "rolling_tracking_error": (r.active.rolling(63).std() * np.sqrt(252)).rename(
            "63-day realized TE"
        ),
        "turnover": r.turnover.rename("one-way turnover"),
        "cost_drag": (
            ((1 + r.gross).cumprod() - (1 + r.net).cumprod()).rename(
                "gross minus net wealth"
            )
        ),
        "active_concentration": result.active_weights.abs()
        .max(axis=1)
        .rename("largest absolute active weight"),
        "signal_ic": ic.ic.rename("forward-period Spearman IC"),
    }
    for name, payload in charts.items():
        series, ylabel = (
            payload if isinstance(payload, tuple) else (payload, payload.name)
        )
        fig, ax = plt.subplots(figsize=(9, 4))
        if isinstance(series, pd.DataFrame):
            for column in series:
                ax.plot(series.index, series[column], label=column)
            ax.legend()
        else:
            ax.plot(series.index, series.to_numpy())
        ax.set(
            title=f"{provenance}\n{name.replace('_', ' ').title()}",
            ylabel=ylabel,
            xlabel="Date",
        )
        ax.grid(alpha=0.25)
        fig.tight_layout()
        fig.savefig(output / f"{name}.png", dpi=140)
        plt.close(fig)
    rows = "\n".join(
        f"| {k} | {v:.6f} |" if v is not None else f"| {k} | undefined |"
        for k, v in serial_metrics.items()
    )
    report = f"""# PortfolioOS research report

**{provenance}**

## Research question

{RESEARCH_QUESTION}

The portfolio-construction mechanism runs from signal preference to desired active
positions, constraint compression, turnover-limited transitions, implementation
costs and realized outcomes. This is a controlled sensitivity framework, not causal
inference. Signal capture measures active-weight alignment with a chosen score; it is
not a measure of alpha, skill or future excess return.

This run evaluates mechanics, not persistent real-world alpha. Underperformance
is a valid outcome. No parameter search was used to choose demo defaults.

Evaluation: {summary["evaluation_start"]} to {summary["evaluation_end"]};
{len(r)} daily observations and {len(result.optimization)} rebalances.

| Metric | Value |
| --- | ---: |
{rows}

Signal IC is evaluated after construction and never feeds the strategy.
The final IC window ends at the sample boundary and may be incomplete.
Undefined ratios are null in JSON, not infinity. Rolling TE requires 63 days.

Benchmark: equal-weight at strategy rebalances when no snapshots are supplied;
otherwise supplied target snapshots become effective on the next trading date.
Both portfolio and benchmark drift between their target updates.
Starting capital is endowed in benchmark holdings; the initial active transition
incurs turnover. Benchmark costs are excluded. Costs are the stated additive NAV
approximation, deducted once, with proportional holdings unchanged by the charge.

Security and Brinson-Fachler daily effects reconcile to gross active returns.
Subtract daily cost for net active return. Daily effects must not be described
as compounded multi-period attribution. Rebalance limits are not daily drift limits.

![Cumulative returns](cumulative_returns.png)
![Relative wealth](cumulative_active_return.png)
![Drawdown](drawdown.png)
![Tracking error](rolling_tracking_error.png)
![Turnover](turnover.png)
![Costs](cost_drag.png)
![Concentration](active_concentration.png)
![Signal IC](signal_ic.png)
"""
    (output / "report.md").write_text(report, encoding="utf-8")
    return summary


def run_demo(config_path, output="results/demo", smoke_test=False):
    synthetic, config = load_config(config_path)
    if smoke_test:
        synthetic["years"] = 2
    prices, metadata = synthetic_market(**synthetic)
    result = run_backtest(prices, metadata=metadata, config=config)
    summary = write_report(result, output)
    summary["synthetic_generator"] = synthetic
    (Path(output) / "summary.json").write_text(
        json.dumps(summary, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    return summary
