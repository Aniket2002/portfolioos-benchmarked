"""Predeclared multi-seed robustness study using the canonical experiment engine."""

import hashlib
import json
from dataclasses import asdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml

from portfolioos.backtest import run_backtest
from portfolioos.experiments import (
    reference_signal_expression_config,
    run_frontier,
)
from portfolioos.reporting import load_config
from portfolioos.synthetic import synthetic_market

EXPECTED_SEEDS = tuple(range(40, 60))
RESULT_COLUMNS = [
    "seed",
    "capture_TE_4",
    "capture_TE_12",
    "delta_TE",
    "capture_turnover_10",
    "capture_turnover_50",
    "delta_turnover",
    "dominance_delta",
    "realized_turnover_at_10",
    "realized_turnover_at_50",
    "scenario_status",
    "scenario_error",
    "dataset_identity",
    "configuration_fingerprint",
    "fixed_settings_fingerprint",
]


def _fingerprint(value):
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def load_protocol(path="configs/seed_robustness.yaml"):
    """Load and validate the immutable public protocol."""
    path = Path(path)
    protocol = yaml.safe_load(path.read_text(encoding="utf-8"))
    seeds = tuple(protocol["predeclared_seeds"])
    if seeds != EXPECTED_SEEDS:
        raise ValueError(f"Protocol seeds must be exactly {list(EXPECTED_SEEDS)}")
    protocol["protocol_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    return protocol


def _endpoint(table, budget, column):
    rows = table.loc[np.isclose(table["budget"], budget)]
    if len(rows) != 1:
        raise ValueError(f"Expected exactly one scenario for budget {budget}")
    row = rows.iloc[0]
    if row.scenario_status != "success":
        return np.nan
    return float(row[column])


def run_seed(protocol, seed):
    """Run the declared TE and turnover frontiers for one synthetic seed."""
    synthetic, base_config = load_config(protocol["base_config"])
    synthetic["seed"] = int(seed)
    fixed_synthetic = {key: value for key, value in synthetic.items() if key != "seed"}
    fixed_settings = {
        "synthetic": fixed_synthetic,
        "backtest": asdict(base_config),
        "tracking_error_budgets": protocol["tracking_error_budgets"],
        "turnover_limits": protocol["turnover_limits"],
    }
    run_configuration = {**fixed_settings, "seed": int(seed)}
    prices, metadata = synthetic_market(**synthetic)
    from portfolioos.experiments import dataset_fingerprint

    identity = dataset_fingerprint(prices, None, metadata)
    reference = run_backtest(
        prices,
        metadata=metadata,
        config=reference_signal_expression_config(base_config),
    )
    te = run_frontier(
        prices,
        None,
        metadata,
        base_config,
        reference,
        "tracking_error",
        protocol["tracking_error_budgets"],
        identity,
    )
    turnover = run_frontier(
        prices,
        None,
        metadata,
        base_config,
        reference,
        "turnover",
        protocol["turnover_limits"],
        identity,
    )
    endpoints = protocol["endpoints"]
    capture_te_low = _endpoint(
        te, endpoints["tracking_error_low"], "average_signal_capture"
    )
    capture_te_high = _endpoint(
        te, endpoints["tracking_error_high"], "average_signal_capture"
    )
    capture_turnover_low = _endpoint(
        turnover, endpoints["turnover_low"], "average_signal_capture"
    )
    capture_turnover_high = _endpoint(
        turnover, endpoints["turnover_high"], "average_signal_capture"
    )
    delta_te = capture_te_high - capture_te_low
    delta_turnover = capture_turnover_high - capture_turnover_low
    failed = pd.concat([te, turnover]).loc[
        lambda frame: frame.scenario_status != "success"
    ]
    return {
        "seed": int(seed),
        "capture_TE_4": capture_te_low,
        "capture_TE_12": capture_te_high,
        "delta_TE": delta_te,
        "capture_turnover_10": capture_turnover_low,
        "capture_turnover_50": capture_turnover_high,
        "delta_turnover": delta_turnover,
        "dominance_delta": delta_turnover - delta_te,
        "realized_turnover_at_10": _endpoint(
            turnover, endpoints["turnover_low"], "average_rebalance_turnover"
        ),
        "realized_turnover_at_50": _endpoint(
            turnover, endpoints["turnover_high"], "average_rebalance_turnover"
        ),
        "scenario_status": "success" if failed.empty else "incomplete",
        "scenario_error": " | ".join(failed.scenario_error.astype(str)),
        "dataset_identity": identity,
        "configuration_fingerprint": _fingerprint(run_configuration),
        "fixed_settings_fingerprint": _fingerprint(fixed_settings),
    }


def summarize_results(results):
    """Create the predeclared descriptive summaries and classification."""
    if tuple(results.seed) != EXPECTED_SEEDS or len(results) != len(EXPECTED_SEEDS):
        raise ValueError("Every predeclared seed must be retained in order")
    summaries = {}
    for column in ("delta_TE", "delta_turnover", "dominance_delta"):
        values = results[column]
        summaries[column] = {
            "n": int(values.count()),
            "mean": float(values.mean()),
            "median": float(values.median()),
            "standard_deviation": float(values.std(ddof=1)),
            "minimum": float(values.min()),
            "maximum": float(values.max()),
            "25th_percentile": float(values.quantile(0.25)),
            "75th_percentile": float(values.quantile(0.75)),
        }
    complete = bool((results.scenario_status == "success").all())
    dominant = int((results.delta_turnover > results.delta_TE).sum())
    median = summaries["dominance_delta"]["median"]
    if dominant >= 16 and median > 0:
        classification = "STRONG"
    elif dominant >= 12 and median > 0:
        classification = "MIXED"
    else:
        classification = "NOT ROBUST"
    return {
        "descriptive_only": True,
        "seed_count": len(results),
        "summaries": summaries,
        "count_delta_turnover_gt_delta_TE": dominant,
        "fraction_delta_turnover_gt_delta_TE": dominant / len(results),
        "count_delta_turnover_gt_zero": int((results.delta_turnover > 0).sum()),
        "count_delta_TE_gt_zero": int((results.delta_TE > 0).sum()),
        "all_scenarios_complete": complete,
        "classification": classification,
    }


def write_results(protocol, results, output="results/seed_robustness"):
    """Write tables, two honest figures, summary, and a restrained report."""
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    results = results.loc[:, RESULT_COLUMNS]
    results.to_csv(output / "seed_results.csv", index=False)
    frozen_protocol = dict(protocol)
    (output / "protocol.json").write_text(
        json.dumps(frozen_protocol, indent=2) + "\n", encoding="utf-8"
    )
    summary = summarize_results(results)
    summary["protocol_sha256"] = protocol["protocol_sha256"]
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(results.seed, results.delta_TE, "o-", label="TE: 4% to 12%")
    ax.plot(results.seed, results.delta_turnover, "o-", label="Turnover: 10% to 50%")
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set(
        title=(
            "Synthetic descriptive robustness: change in signal capture\n"
            "Missing TE markers: 4% TE did not complete for seeds 46 and 53"
        ),
        xlabel="Predeclared synthetic seed",
        ylabel="Change in average signal capture",
        xticks=list(EXPECTED_SEEDS),
    )
    ax.tick_params(axis="x", rotation=45)
    ax.grid(alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(output / "paired_seed_deltas.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 5))
    colors = np.where(results.dominance_delta > 0, "#2a6fbb", "#ba3a3a")
    ax.bar(results.seed.astype(str), results.dominance_delta, color=colors)
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set(
        title=(
            "Synthetic descriptive robustness: turnover delta minus TE delta\n"
            "Blank bars: 4% TE did not complete for seeds 46 and 53"
        ),
        xlabel="Predeclared synthetic seed",
        ylabel="Dominance delta",
    )
    ax.tick_params(axis="x", rotation=45)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(output / "dominance_delta_by_seed.png", dpi=160)
    plt.close(fig)

    count = summary["count_delta_turnover_gt_delta_TE"]
    fraction = summary["fraction_delta_turnover_gt_delta_TE"]
    median = summary["summaries"]["dominance_delta"]["median"]
    classification = summary["classification"]
    if classification == "STRONG":
        wording = (
            "Across 20 predeclared synthetic seeds, turnover generally constrained "
            "signal expression more than the tested tracking-error range."
        )
    elif classification == "MIXED":
        wording = (
            "In the canonical seed-42 study, turnover had a larger effect on signal "
            "capture than the tested tracking-error range, but the ordering was "
            "mixed across synthetic seeds."
        )
    else:
        wording = (
            "In the canonical seed-42 synthetic study, turnover had a larger effect "
            "on signal capture than the tested tracking-error range; the ranking of "
            "constraint effects was realization-dependent across seeds."
        )
    summary_rows = []
    for name in ("delta_TE", "delta_turnover", "dominance_delta"):
        stats = summary["summaries"][name]
        values = [
            stats["n"],
            stats["mean"],
            stats["median"],
            stats["standard_deviation"],
            stats["minimum"],
            stats["25th_percentile"],
            stats["75th_percentile"],
            stats["maximum"],
        ]
        formatted = [str(values[0]), *(f"{value:.6f}" for value in values[1:])]
        summary_rows.append(f"| {name} | " + " | ".join(formatted) + " |")
    summary_table = "\n".join(summary_rows)
    report = f"""# Predeclared synthetic-seed robustness study

**SYNTHETIC DESCRIPTIVE ROBUSTNESS — NOT EMPIRICAL MARKET VALIDATION**

This study used all 20 predeclared seeds, 40–59, with every non-seed setting fixed.
It is not a sampling distribution of market outcomes and provides no statistical
significance, persistent-alpha, causal, or real-market-performance evidence.

## Result

- Classification: **{classification}**
- `delta_turnover > delta_TE`: {count}/20 ({fraction:.0%})
- Median dominance delta: {median:.6f}
- All scenarios complete: {summary["all_scenarios_complete"]}

| Measure | n | Mean | Median | Std. dev. | Min | 25th pct. | 75th pct. | Max |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
{summary_table}

Both incomplete seeds are retained. Their unavailable TE comparisons count against
the 20-seed dominance fraction. All 20 turnover deltas were positive; all 18
completed TE deltas were positive. No p-values or confidence intervals are used.

Allowed interpretation: {wording}

Seed 42 remains the canonical illustrative case. Signal capture measures alignment
with the chosen synthetic signal, not alpha, forecast accuracy, return, skill, or
predictive power. Per-seed values and reversals are retained in `seed_results.csv`.
"""
    (output / "report.md").write_text(report, encoding="utf-8")
    return summary


def run_protocol(protocol):
    """Run every declared seed without selection or omission."""
    rows = [run_seed(protocol, seed) for seed in protocol["predeclared_seeds"]]
    return pd.DataFrame(rows, columns=RESULT_COLUMNS)
