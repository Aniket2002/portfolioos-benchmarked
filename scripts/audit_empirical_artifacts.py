"""Independently reconcile saved historical holdings and accounting artifacts.

This reads existing paths, never forms portfolios or reruns the final holdout.
Full local holdings are required; only selected aggregate outputs are committed.
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from portfolioos.empirical import write_json
from portfolioos.historical import file_hash, load_historical_bundle


def audit(root, bundle):
    root = Path(root)
    lock = json.loads((root / "final_protocol_lock.json").read_text())
    protocol = lock["protocol"]
    prices, _ = load_historical_bundle(bundle, protocol["assets"])
    assert file_hash(Path(bundle) / "prices.csv") == lock["quality"]["prices_sha256"]
    asset_returns = prices.pct_change(fill_method=None)
    completed, failures = 0, []
    for period in ["development", "validation", "holdout"]:
        evaluation = json.loads((root / period / "evaluation.json").read_text())
        for row in evaluation["scenarios"]:
            scenario = row["scenario"]
            if row["status"] != "success":
                failures.append(
                    {"period": period, "scenario": scenario, "error": row["error"]}
                )
                continue
            path = root / period / scenario

            def read(name):
                return pd.read_csv(path / f"{name}.csv", index_col=0, parse_dates=True)

            weights, benchmark, returns, decisions = map(
                read, ["weights", "benchmark_weights", "returns", "optimization"]
            )
            cfg = row["configuration"]
            realized = asset_returns.loc[returns.index, weights.columns]
            for holdings in [weights, benchmark]:
                np.testing.assert_allclose(holdings.sum(axis=1), 1, atol=1e-8)
                assert (holdings.to_numpy() >= -1e-7).all()
            np.testing.assert_allclose(
                (weights * realized).sum(axis=1), returns.gross, atol=1e-12
            )
            np.testing.assert_allclose(
                (benchmark * realized).sum(axis=1), returns.benchmark, atol=1e-12
            )
            np.testing.assert_allclose(
                returns.net, returns.gross - returns.cost, atol=1e-12
            )
            np.testing.assert_allclose(
                returns.active, returns.net - returns.benchmark, atol=1e-12
            )
            np.testing.assert_allclose(
                returns.cost,
                returns.turnover * cfg["transaction_cost_bps"] / 10000,
                atol=1e-12,
            )
            drifted = weights.mul(1 + realized).div(1 + returns.gross, axis=0)
            prior = drifted.shift(1)
            prior.iloc[0] = benchmark.iloc[0]
            expected_turnover = (weights - prior).abs().sum(axis=1) / 2
            np.testing.assert_allclose(expected_turnover, returns.turnover, atol=1e-10)
            targets = pd.Series(protocol["policy_weights"]).reindex(weights.columns)
            bench_ends = benchmark.mul(1 + realized).div(1 + returns.benchmark, axis=0)
            for i in range(1, len(returns)):
                monthly = returns.index[i].to_period("M") != returns.index[
                    i - 1
                ].to_period("M")
                expected = targets if monthly else bench_ends.iloc[i - 1]
                np.testing.assert_allclose(benchmark.iloc[i], expected, atol=1e-10)
            expected_bench_turnover = (benchmark - bench_ends.shift(1)).abs().sum(
                axis=1
            ) / 2
            expected_bench_turnover.iloc[0] = 0
            np.testing.assert_allclose(
                expected_bench_turnover, returns.benchmark_turnover, atol=1e-10
            )
            np.testing.assert_allclose(
                returns.benchmark_net,
                returns.benchmark - returns.benchmark_cost,
                atol=1e-12,
            )
            for date, decision in decisions.iterrows():
                i = prices.index.get_loc(date)
                assert (
                    pd.Timestamp(decision.information_date)
                    == prices.index[i - cfg["information_lag"]]
                )
                assert pd.Timestamp(decision.execution_date) == prices.index[i - 1]
                assert cfg["information_lag"] >= 2
            if cfg["strategy"] == "optimized":
                mandate = cfg["optimizer"]
                assert (
                    weights.loc[decisions.index].to_numpy().max()
                    <= mandate["max_position_weight"] + 1e-7
                )
                assert returns.turnover.max() <= mandate["max_turnover"] + 1e-7
                assert (
                    decisions.execution_tracking_error
                    <= decisions.tracking_error_budget + 1e-7
                ).all()
                assert decisions.execution_violations.fillna("").eq("").all()
                for group in set(protocol["sectors"].values()):
                    assets = [
                        x for x in weights.columns if protocol["sectors"][x] == group
                    ]
                    active = (
                        (weights - benchmark).loc[decisions.index, assets].sum(axis=1)
                    )
                    assert (
                        active.abs().max() <= mandate["max_sector_active_weight"] + 1e-7
                    )
            if scenario.startswith("cost_"):
                base = root / period / "fixed_risk"
                original = pd.read_csv(
                    base / "returns.csv", index_col=0, parse_dates=True
                )
                for column in ["gross", "turnover", "benchmark", "rebalance"]:
                    np.testing.assert_allclose(
                        returns[column], original[column], atol=1e-12
                    )
                saved_weights = pd.read_csv(
                    base / "weights.csv", index_col=0, parse_dates=True
                )
                np.testing.assert_allclose(weights, saved_weights, atol=1e-12)
            completed += 1
    record = {
        "passed": True,
        "completed_paths_checked": completed,
        "failed_paths_not_given_full_period_metrics": failures,
        "checks": [
            "asset/portfolio/benchmark returns",
            "holdings drift",
            "actual turnover",
            "costs",
            "monthly benchmark schedule",
            "information lag",
            "execution mandates",
            "identical-trade cost paths",
        ],
        "holdout_reoptimized": False,
    }
    write_json(root / "accounting_audit.json", record)
    return record


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", required=True)
    parser.add_argument("--bundle", required=True)
    args = parser.parse_args()
    print(audit(args.results, args.bundle))
