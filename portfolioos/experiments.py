"""Controlled portfolio-implementation experiments over the canonical backtest."""

import hashlib
import json
import re
from dataclasses import asdict, dataclass, replace
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from portfolioos.backtest import BacktestConfig, run_backtest
from portfolioos.metrics import performance_metrics

RESEARCH_QUESTION = (
    "What is the trade-off between signal capture, benchmark-relative risk and "
    "implementation cost in systematic portfolio construction?"
)
SYNTHETIC_LABEL = "SYNTHETIC RESEARCH EXPERIMENT"
SYNTHETIC_DISCLAIMER = (
    "These experiments demonstrate portfolio-construction mechanics. They are not "
    "evidence that the signals earn persistent real-world alpha."
)
EXPERIMENT_COLUMNS = [
    "experiment",
    "budget",
    "scenario_status",
    "scenario_error",
    "average_signal_capture",
    "median_signal_capture",
    "average_active_signal_exposure",
    "average_active_share",
    "average_ex_ante_tracking_error",
    "realized_tracking_error",
    "average_rebalance_turnover",
    "total_transaction_cost",
    "compounded_cost_drag",
    "gross_annualized_active_return",
    "net_annualized_active_return",
    "information_ratio",
    "maximum_drawdown",
    "maximum_position",
    "infeasible_rebalance_count",
    "evaluation_days",
    "rebalances",
    "dataset_identity",
    "configuration",
]


@dataclass(frozen=True)
class ExperimentSuite:
    """Comparison tables plus the exact configuration and input identity."""

    te_frontier: pd.DataFrame
    turnover_frontier: pd.DataFrame
    cost_frontier: pd.DataFrame
    te_turnover_grid: pd.DataFrame
    base_config: BacktestConfig
    reference_config: BacktestConfig
    dataset_identity: str
    provenance: str


def dataset_fingerprint(prices, benchmark_weights=None, metadata=None):
    """Return a deterministic identity for all tabular inputs to an experiment."""
    digest = hashlib.sha256()
    for name, value in (
        ("prices", prices),
        ("benchmark", benchmark_weights),
        ("metadata", metadata),
    ):
        digest.update(name.encode())
        if value is None:
            digest.update(b"none")
            continue
        digest.update(pd.util.hash_pandas_object(value, index=True).values.tobytes())
        digest.update("|".join(map(str, value.columns)).encode())
    return digest.hexdigest()


def reference_signal_expression_config(config):
    """Keep basic investability while removing implementation compression.

    The reference remains fully invested, long only, and subject to the baseline
    position cap. It maximizes the same score without tracking-error, sector-active,
    turnover constraints, risk aversion, or turnover penalty. Transaction costs stay
    in the configuration but do not enter portfolio formation.
    """
    reference_optimizer = replace(
        config.optimizer,
        risk_aversion=0.0,
        turnover_penalty=0.0,
        max_tracking_error=None,
        max_sector_active_weight=None,
        max_turnover=None,
        fallback_to_benchmark=False,
    )
    return replace(config, optimizer=reference_optimizer)


def active_signal_exposure(result):
    """Compute (target weight - benchmark weight)' standardized score."""
    dates = result.signal_scores.index
    active = result.active_weights.loc[dates, result.signal_scores.columns]
    return (active * result.signal_scores).sum(axis=1).rename("active_signal_exposure")


def signal_capture(result, reference_result, denominator_tolerance=1e-10):
    """Normalize exposure by a same-information reference portfolio exposure."""
    scores = result.signal_scores
    reference_scores = reference_result.signal_scores
    if not scores.index.equals(reference_scores.index) or not scores.columns.equals(
        reference_scores.columns
    ):
        raise ValueError("Scenario and reference scores are not aligned")
    if not np.allclose(scores, reference_scores, atol=1e-12, rtol=1e-10):
        raise ValueError(
            "Scenario and reference must use identical point-in-time scores"
        )
    numerator = active_signal_exposure(result)
    denominator = active_signal_exposure(reference_result)
    capture = numerator.div(denominator)
    capture = capture.mask(denominator.abs() <= denominator_tolerance)
    return capture.rename("signal_capture")


def vary_config(config, dimension, value):
    """Return an independent config changing exactly one experiment dimension."""
    if dimension == "tracking_error":
        return replace(
            config,
            optimizer=replace(config.optimizer, max_tracking_error=float(value)),
        )
    if dimension == "turnover":
        return replace(
            config, optimizer=replace(config.optimizer, max_turnover=float(value))
        )
    if dimension == "transaction_cost_bps":
        return replace(config, transaction_cost_bps=float(value))
    raise ValueError(f"Unknown experiment dimension: {dimension}")


def _successful_row(result, reference, experiment, budget, identity, config):
    returns = result.returns
    net_metrics = performance_metrics(
        returns.net, returns.benchmark, returns.turnover, returns.cost
    )
    gross_metrics = performance_metrics(returns.gross, returns.benchmark)
    capture = signal_capture(result, reference)
    exposure = active_signal_exposure(result)
    rebalances = returns.rebalance.astype(bool)
    return {
        "experiment": experiment,
        "budget": float(budget),
        "scenario_status": "success",
        "scenario_error": "",
        "average_signal_capture": float(capture.mean()),
        "median_signal_capture": float(capture.median()),
        "average_active_signal_exposure": float(exposure.mean()),
        "average_active_share": float(
            0.5 * result.active_weights.abs().sum(axis=1).mean()
        ),
        "average_ex_ante_tracking_error": float(
            result.optimization.estimated_tracking_error.mean()
        ),
        "realized_tracking_error": net_metrics["tracking_error"],
        "average_rebalance_turnover": float(returns.loc[rebalances, "turnover"].mean()),
        "total_transaction_cost": net_metrics["total_cost_fraction_sum"],
        "compounded_cost_drag": net_metrics["compounded_cost_drag"],
        "gross_annualized_active_return": gross_metrics[
            "annualized_arithmetic_active_return"
        ],
        "net_annualized_active_return": net_metrics[
            "annualized_arithmetic_active_return"
        ],
        "information_ratio": net_metrics["information_ratio"],
        "maximum_drawdown": net_metrics["maximum_drawdown"],
        "maximum_position": float(result.weights.to_numpy().max()),
        "infeasible_rebalance_count": 0,
        "evaluation_days": len(returns),
        "rebalances": len(result.optimization),
        "dataset_identity": identity,
        "configuration": json.dumps(asdict(config), sort_keys=True),
    }


def _failed_row(exc, experiment, budget, identity, config):
    row = {column: np.nan for column in EXPERIMENT_COLUMNS}
    optimization_failure = (
        isinstance(exc, RuntimeError)
        and re.match(
            r"^Optimization failed on .*: infeasible(?:_inaccurate)?:", str(exc)
        )
        is not None
    )
    row.update(
        {
            "experiment": experiment,
            "budget": float(budget),
            "scenario_status": "infeasible" if optimization_failure else "failed",
            "scenario_error": str(exc),
            "infeasible_rebalance_count": int(optimization_failure),
            "dataset_identity": identity,
            "configuration": json.dumps(asdict(config), sort_keys=True),
        }
    )
    return row


def validate_experiment_suite_for_smoke(suite):
    """Reject broken research pipelines while allowing isolated infeasibility."""
    problems = []
    tables = {
        "te_frontier": suite.te_frontier,
        "turnover_frontier": suite.turnover_frontier,
        "cost_frontier": suite.cost_frontier,
        "te_turnover_grid": suite.te_turnover_grid,
    }
    for name, table in tables.items():
        failed = int((table.scenario_status == "failed").sum())
        allowed = table.scenario_status.isin({"success", "infeasible", "failed"})
        unknown = int((~allowed).sum())
        if failed:
            problems.append(f"{name}: {failed} failed scenarios")
        if unknown:
            problems.append(f"{name}: {unknown} unknown scenario statuses")
        if not (table.scenario_status == "success").any():
            problems.append(f"{name}: no successful scenario")
    if problems:
        details = "\n".join(f"- {problem}" for problem in problems)
        raise RuntimeError(f"Research smoke validation failed:\n{details}")


def run_frontier(
    prices,
    benchmark_weights,
    metadata,
    base_config,
    reference_result,
    dimension,
    values,
    identity,
):
    """Vary one setting, run canonical backtests, and retain explicit failures."""
    rows = []
    for value in values:
        config = vary_config(base_config, dimension, value)
        try:
            result = run_backtest(
                prices,
                benchmark_weights=benchmark_weights,
                metadata=metadata,
                config=config,
            )
            row = _successful_row(
                result, reference_result, dimension, value, identity, config
            )
        except (RuntimeError, ValueError) as exc:
            row = _failed_row(exc, dimension, value, identity, config)
        rows.append(row)
    return pd.DataFrame(rows, columns=EXPERIMENT_COLUMNS)


def run_experiment_suite(
    prices,
    benchmark_weights=None,
    metadata=None,
    base_config=None,
    te_budgets=(0.04, 0.06, 0.08, 0.10, 0.12),
    turnover_limits=(0.10, 0.20, 0.30, 0.40, 0.50),
    cost_bps=(0.0, 5.0, 10.0, 20.0, 40.0),
    grid_te=(0.04, 0.08, 0.12),
    grid_turnover=(0.15, 0.30, 0.50),
    provenance=SYNTHETIC_LABEL,
):
    """Run three one-factor frontiers and a small TE-by-turnover surface."""
    base_config = base_config or BacktestConfig()
    identity = dataset_fingerprint(prices, benchmark_weights, metadata)
    reference_config = reference_signal_expression_config(base_config)
    reference = run_backtest(
        prices,
        benchmark_weights=benchmark_weights,
        metadata=metadata,
        config=reference_config,
    )
    te = run_frontier(
        prices,
        benchmark_weights,
        metadata,
        base_config,
        reference,
        "tracking_error",
        te_budgets,
        identity,
    )
    turnover = run_frontier(
        prices,
        benchmark_weights,
        metadata,
        base_config,
        reference,
        "turnover",
        turnover_limits,
        identity,
    )
    costs = run_frontier(
        prices,
        benchmark_weights,
        metadata,
        base_config,
        reference,
        "transaction_cost_bps",
        cost_bps,
        identity,
    )
    grid_rows = []
    for te_budget in grid_te:
        te_config = vary_config(base_config, "tracking_error", te_budget)
        for turnover_limit in grid_turnover:
            config = vary_config(te_config, "turnover", turnover_limit)
            label = f"te={te_budget:.6g},turnover={turnover_limit:.6g}"
            try:
                result = run_backtest(
                    prices,
                    benchmark_weights=benchmark_weights,
                    metadata=metadata,
                    config=config,
                )
                row = _successful_row(
                    result, reference, "te_turnover_grid", te_budget, identity, config
                )
            except (RuntimeError, ValueError) as exc:
                row = _failed_row(exc, "te_turnover_grid", te_budget, identity, config)
            row["tracking_error_budget"] = float(te_budget)
            row["turnover_limit"] = float(turnover_limit)
            row["scenario"] = label
            grid_rows.append(row)
    grid = pd.DataFrame(grid_rows)
    return ExperimentSuite(
        te,
        turnover,
        costs,
        grid,
        base_config,
        reference_config,
        identity,
        provenance,
    )


def _successful(table):
    return table.loc[table.scenario_status == "success"].sort_values("budget")


def experiment_findings(suite):
    """Generate restrained descriptive findings from calculated table values."""
    findings = []
    te = _successful(suite.te_frontier)
    if len(te) >= 2:
        tight, loose = te.iloc[0], te.iloc[-1]
        findings.append(
            f"Changing the annual TE cap from {tight.budget:.0%} to "
            f"{loose.budget:.0%} changed average signal capture from "
            f"{tight.average_signal_capture:.3f} to "
            f"{loose.average_signal_capture:.3f} and average active share from "
            f"{tight.average_active_share:.2%} to {loose.average_active_share:.2%}."
        )
    turnover = _successful(suite.turnover_frontier)
    if len(turnover) >= 2:
        tight, loose = turnover.iloc[0], turnover.iloc[-1]
        findings.append(
            f"Changing the one-way turnover limit from {tight.budget:.0%} to "
            f"{loose.budget:.0%} changed average signal capture from "
            f"{tight.average_signal_capture:.3f} to "
            f"{loose.average_signal_capture:.3f}; realized average rebalance "
            f"turnover changed from {tight.average_rebalance_turnover:.2%} to "
            f"{loose.average_rebalance_turnover:.2%}."
        )
    costs = _successful(suite.cost_frontier)
    if len(costs) >= 2:
        low, high = costs.iloc[0], costs.iloc[-1]
        findings.append(
            f"Raising the cost assumption from {low.budget:.0f} to "
            f"{high.budget:.0f} bps left annualized gross active return at "
            f"{high.gross_annualized_active_return:.2%} and changed annualized net "
            f"active return from {low.net_annualized_active_return:.2%} to "
            f"{high.net_annualized_active_return:.2%}."
        )
    if len(te) >= 2:
        correlation = te.average_signal_capture.corr(te.net_annualized_active_return)
        if np.isfinite(correlation):
            direction = "positive" if correlation > 0 else "negative"
            findings.append(
                "Across the tested TE budgets, the descriptive correlation between "
                "average signal capture and realized net active return was "
                f"{direction} "
                f"({correlation:.3f}). This synthetic sensitivity is not evidence of "
                "skill, alpha, causality, or statistical significance."
            )
    failures = sum(
        int((table.scenario_status != "success").sum())
        for table in (
            suite.te_frontier,
            suite.turnover_frontier,
            suite.cost_frontier,
            suite.te_turnover_grid,
        )
    )
    findings.append(f"{failures} tested scenarios failed before completion.")
    return findings


def _plot_line(table, x, ys, ylabel, title, output):
    successful = table.loc[table.scenario_status == "success"]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for column, label in ys.items():
        ax.plot(successful[x], successful[column], marker="o", label=label)
    ax.set(
        title=f"{SYNTHETIC_LABEL}\n{title}",
        xlabel=x.replace("_", " "),
        ylabel=ylabel,
    )
    ax.grid(alpha=0.25)
    if len(ys) > 1:
        ax.legend()
    fig.tight_layout()
    fig.savefig(output, dpi=140)
    plt.close(fig)


def write_experiment_report(suite, output="results/research_tradeoffs"):
    """Write reproducible tables, charts, configuration, and calculated findings."""
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    tables = {
        "te_frontier": suite.te_frontier,
        "turnover_frontier": suite.turnover_frontier,
        "cost_frontier": suite.cost_frontier,
        "te_turnover_grid": suite.te_turnover_grid,
    }
    for name, table in tables.items():
        table.to_csv(output / f"{name}.csv", index=False)

    _plot_line(
        suite.te_frontier,
        "budget",
        {"average_signal_capture": "Average signal capture"},
        "Average signal capture",
        "Signal capture vs tracking-error budget",
        output / "signal_capture_vs_te.png",
    )
    _plot_line(
        suite.te_frontier,
        "average_ex_ante_tracking_error",
        {"average_signal_capture": "Average signal capture"},
        "Average signal capture",
        "Implementation frontier",
        output / "implementation_frontier.png",
    )
    _plot_line(
        suite.turnover_frontier,
        "budget",
        {"average_signal_capture": "Average signal capture"},
        "Average signal capture",
        "Signal capture vs one-way turnover limit",
        output / "signal_capture_vs_turnover.png",
    )
    _plot_line(
        suite.cost_frontier,
        "budget",
        {
            "gross_annualized_active_return": "Gross active return",
            "net_annualized_active_return": "Net active return",
        },
        "Annualized arithmetic active return",
        "Gross and net active return by cost assumption",
        output / "gross_vs_net_by_cost.png",
    )
    _plot_line(
        suite.te_frontier,
        "budget",
        {"information_ratio": "Information ratio"},
        "Information ratio",
        "Information ratio vs tracking-error budget",
        output / "information_ratio_vs_te.png",
    )

    heatmap = suite.te_turnover_grid.pivot(
        index="turnover_limit",
        columns="tracking_error_budget",
        values="average_signal_capture",
    )
    fig, ax = plt.subplots(figsize=(7, 4.5))
    image = ax.imshow(heatmap, aspect="auto", origin="lower")
    ax.set_xticks(range(len(heatmap.columns)), [f"{x:.0%}" for x in heatmap.columns])
    ax.set_yticks(range(len(heatmap.index)), [f"{x:.0%}" for x in heatmap.index])
    ax.set(
        title=f"{SYNTHETIC_LABEL}\nAverage signal capture",
        xlabel="Annual tracking-error cap",
        ylabel="One-way turnover limit",
    )
    fig.colorbar(image, ax=ax, label="Average signal capture")
    fig.tight_layout()
    fig.savefig(output / "te_turnover_signal_capture_heatmap.png", dpi=140)
    plt.close(fig)

    findings = experiment_findings(suite)
    summary = {
        "provenance": suite.provenance,
        "disclaimer": SYNTHETIC_DISCLAIMER,
        "research_question": RESEARCH_QUESTION,
        "dataset_identity": suite.dataset_identity,
        "base_configuration": asdict(suite.base_config),
        "reference_configuration": asdict(suite.reference_config),
        "tested_values": {
            "tracking_error_budgets": suite.te_frontier.budget.tolist(),
            "turnover_limits": suite.turnover_frontier.budget.tolist(),
            "transaction_cost_bps": suite.cost_frontier.budget.tolist(),
            "te_turnover_grid": suite.te_turnover_grid[
                ["tracking_error_budget", "turnover_limit"]
            ].to_dict("records"),
        },
        "findings": findings,
        "notes": [
            "Signal capture measures alignment with a chosen signal, not alpha or "
            "skill.",
            "The reference is a measurement portfolio, not a more realistic portfolio.",
            "Transaction costs affect net returns, not signals, asset returns, or "
            "weights.",
            "The optimizer penalizes turnover but does not ingest an expected-cost "
            "model.",
            "Scenario failures stop at the first failed rebalance; constraints are "
            "not relaxed.",
        ],
    }
    (output / "experiment_summary.json").write_text(
        json.dumps(summary, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    finding_lines = "\n".join(f"- {finding}" for finding in findings)
    report = f"""# Portfolio implementation trade-off research

**{suite.provenance}**

{SYNTHETIC_DISCLAIMER}

## Research question

{RESEARCH_QUESTION}

Signal capture is the active signal exposure `(w - b)'s` divided by exposure in
the signal-expression reference portfolio. The reference retains full investment,
long-only weights, and the baseline position cap, while removing risk/sector/turnover
compression. It uses the same scores and information dates. It is a measurement
portfolio, not an optimal alpha portfolio or a claim about investability.

## Findings from the synthetic experiment

{finding_lines}

These comparisons are controlled sensitivities. They do not establish causality or
statistical significance. High signal capture can coexist with poor realized returns.
Negative active results remain part of the evidence shown in the CSV tables.
"""
    (output / "report.md").write_text(report, encoding="utf-8")
    return summary
