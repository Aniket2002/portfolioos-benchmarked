"""Post-holdout review diagnostics; never overwrite the frozen evaluation.

Attribution and table checks read executed paths. The one added specification
uses an 8% normal / 3% high-state TE mandate, declared before this script runs.
It is exploratory and cannot restore an untouched holdout.
"""

import argparse
import json
from dataclasses import asdict, replace
from pathlib import Path

import numpy as np
import pandas as pd

from portfolioos.backtest import ExecutionFailure, run_backtest
from portfolioos.empirical import read_protocol, verified_quality, write_json
from portfolioos.historical import file_hash, load_historical_bundle
from portfolioos.metrics import performance_metrics
from portfolioos.reporting import validate_result
from portfolioos.uncertainty import block_interval

PERIODS = ["development", "validation", "holdout"]
BINDING_TOLERANCE = 1e-5  # one tenth of a basis point of annualized TE


def read(path):
    return pd.read_csv(path, index_col=0, parse_dates=True)


def binding_row(period, scenario, decisions, reserve):
    formation_cap = decisions.tracking_error_budget - reserve
    binding = (
        (formation_cap - decisions.estimated_tracking_error).abs().le(BINDING_TOLERANCE)
    )
    high = decisions.regime.eq("high")
    return {
        "period": period,
        "scenario": scenario,
        "rebalances": len(decisions),
        "binding_rebalances": int(binding.sum()),
        "high_rebalances": int(high.sum()),
        "high_binding_rebalances": int((high & binding).sum()),
        "maximum_formation_te": float(decisions.estimated_tracking_error.max()),
        "binding_tolerance": BINDING_TOLERANCE,
    }


def review(results, bundle, output):
    root, destination = Path(results), Path(output)
    if root.resolve() == destination.resolve() or destination.exists():
        raise ValueError("Use a new directory for post-holdout diagnostics")
    quality = verified_quality(bundle, root)
    lock = json.loads((root / "final_protocol_lock.json").read_text())
    protocol, configs = read_protocol(root / "declared_protocol.json")
    if protocol != lock["protocol"] or quality != lock["quality"]:
        raise ValueError("Inputs differ from frozen evaluation")
    destination.mkdir(parents=True)
    tighter = replace(
        configs["regime_aware"], regime_te_budgets={"normal": 0.08, "high": 0.03}
    )
    write_json(
        destination / "diagnostic_protocol.json",
        {
            "purpose": "post-holdout exploratory review; not model selection",
            "source_lock_sha256": file_hash(root / "final_protocol_lock.json"),
            "configuration": asdict(tighter),
            "periods": protocol["periods"],
            "bootstrap": protocol["bootstrap"],
            "binding_tolerance": BINDING_TOLERANCE,
        },
    )
    prices, _ = load_historical_bundle(bundle, protocol["assets"])
    metadata = pd.DataFrame({"sector": protocol["sectors"]})
    attribution, securities, bindings, table_check, tighter_rows = [], [], [], [], []
    for period in PERIODS:
        primary = root / period / "fixed_risk"
        returns = read(primary / "returns.csv")
        weights = read(primary / "weights.csv")
        benchmark = read(primary / "benchmark_weights.csv")
        realized = prices.pct_change(fill_method=None).loc[returns.index]
        contributions = (weights - benchmark) * realized
        np.testing.assert_allclose(
            contributions.sum(axis=1) - returns.cost, returns.active, atol=1e-12
        )
        for sector in sorted(set(protocol["sectors"].values())):
            assets = [a for a in weights if protocol["sectors"][a] == sector]
            attribution.append(
                {
                    "period": period,
                    "component": sector,
                    "annualized_active_contribution": float(
                        contributions[assets].sum(axis=1).mean() * 252
                    ),
                    "mean_active_weight": float(
                        (weights[assets] - benchmark[assets]).sum(axis=1).mean()
                    ),
                }
            )
        attribution.append(
            {
                "period": period,
                "component": "costs",
                "annualized_active_contribution": float(-returns.cost.mean() * 252),
                "mean_active_weight": None,
            }
        )
        for asset in weights:
            securities.append(
                {
                    "period": period,
                    "asset": asset,
                    "annualized_active_contribution": float(
                        contributions[asset].mean() * 252
                    ),
                    "mean_active_weight": float(
                        (weights[asset] - benchmark[asset]).mean()
                    ),
                }
            )
        for scenario in ["fixed_risk", "regime_aware", "te_8pct", "te_12pct"]:
            bindings.append(
                binding_row(
                    period,
                    scenario,
                    read(root / period / scenario / "optimization.csv"),
                    configs[scenario].execution_te_reserve,
                )
            )
        start, end = protocol["periods"][period]
        if period != "holdout":
            scenario = "without_low_volatility"
            saved = read(root / period / scenario / "returns.csv")
            replicated = run_backtest(
                prices.loc[:end].copy(),
                metadata=metadata,
                config=replace(configs[scenario], start_date=start, end_date=end),
            )
            validate_result(replicated)
            np.testing.assert_allclose(saved.net, replicated.returns.net, atol=1e-12)
            te = float((saved.net - saved.benchmark).std(ddof=1) * np.sqrt(252))
            evaluation = json.loads((root / period / "evaluation.json").read_text())
            reported = next(
                x["metrics"]["tracking_error"]
                for x in evaluation["scenarios"]
                if x["scenario"] == scenario
            )
            np.testing.assert_allclose(te, reported, atol=1e-12)
            table_check.append(
                {
                    "period": period,
                    "tracking_error": te,
                    "table_percent_3dp": f"{te * 100:.3f}",
                    "maximum_replication_difference": float(
                        (saved.net - replicated.returns.net).abs().max()
                    ),
                    "returns_sha256": file_hash(
                        root / period / scenario / "returns.csv"
                    ),
                }
            )
        target = destination / period / "regime_high_3pct"
        target.mkdir(parents=True)
        row = {"period": period, "scenario": "regime_high_3pct"}
        try:
            result = run_backtest(
                prices.loc[:end].copy(),
                metadata=metadata,
                config=replace(tighter, start_date=start, end_date=end),
            )
            validate_result(result)
            result.returns.to_csv(target / "returns.csv")
            result.optimization.to_csv(target / "optimization.csv")
            m = performance_metrics(result.returns.net, result.returns.benchmark)
            bindings.append(
                binding_row(
                    period,
                    row["scenario"],
                    result.optimization,
                    tighter.execution_te_reserve,
                )
            )
            bootstrap = protocol["bootstrap"].copy()
            bootstrap.pop("metric")
            paired = block_interval(result.returns.net - returns.net, **bootstrap)
            row.update(status="success", metrics=m, paired_vs_fixed=paired)
        except ExecutionFailure as error:
            row.update(status="failed", error=str(error), attempted=error.attempted)
            for name, partial in error.partial.items():
                partial.to_csv(target / f"partial_{name}.csv")
        write_json(target / "scenario_status.json", row)
        tighter_rows.append(row)
        print(f"{period}: tighter cap {row['status']}", flush=True)
    pd.DataFrame(attribution).to_csv(
        destination / "asset_class_attribution.csv", index=False
    )
    pd.DataFrame(securities).to_csv(
        destination / "security_attribution_summary.csv", index=False
    )
    pd.DataFrame(bindings).to_csv(destination / "cap_activity.csv", index=False)
    write_json(destination / "table5_audit.json", table_check)
    write_json(destination / "tighter_cap_results.json", tighter_rows)
    # Identity record for the source evidence, excluding reporting-only files.
    paths = [root / "final_protocol_lock.json", root / "holdout_access.json"]
    paths += [root / p / "evaluation.json" for p in PERIODS]
    paths += list(root.glob("*/*/returns.csv"))
    write_json(
        destination / "source_evidence_hashes.json",
        {p.relative_to(root).as_posix(): file_hash(p) for p in paths},
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", required=True)
    parser.add_argument("--bundle", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    review(args.results, args.bundle, args.output)
