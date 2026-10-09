"""Evaluate declared historical scenarios; never silently evaluate the holdout."""

import argparse
import json
from dataclasses import asdict, replace
from pathlib import Path

import pandas as pd

from portfolioos.backtest import BacktestConfig, run_backtest
from portfolioos.historical import file_hash, freeze_protocol, load_historical_bundle
from portfolioos.optimizer import OptimizerConfig
from portfolioos.reporting import write_report


def run(protocol_path, bundle, output, period="validation"):
    protocol = json.loads(Path(protocol_path).read_text(encoding="utf-8"))
    if "experiment_groups" in protocol:
        from portfolioos.empirical import evaluate_period

        return evaluate_period(protocol_path, bundle, output, period)
    assets = protocol["assets"]
    if set(protocol["policy_weights"]) != set(assets):
        raise ValueError("Policy identifiers must match the universe exactly")
    if set(protocol["sectors"]) != set(assets):
        raise ValueError("Sector identifiers must match the universe exactly")
    periods = protocol["periods"]
    previous_end = None
    for name in ("development", "validation", "holdout"):
        start, end = map(pd.Timestamp, periods[name])
        if start > end or (previous_end is not None and start <= previous_end):
            raise ValueError("Research periods must be ordered and disjoint")
        previous_end = end
    policy = pd.Series(protocol["policy_weights"], index=assets, dtype=float)
    if policy.isna().any() or (policy < 0).any() or abs(policy.sum() - 1) > 1e-10:
        raise ValueError("Policy weights must cover universe and sum to one")
    configs = {}
    for name, settings in protocol["scenarios"].items():
        if not name or not all(c.isalnum() or c in "_-" for c in name):
            raise ValueError("Scenario names must be safe directory identifiers")
        settings = settings.copy()
        optimizer = OptimizerConfig(**settings.pop("optimizer"))
        config = BacktestConfig(optimizer=optimizer, **settings)
        if config.information_lag < 2:
            raise ValueError("Empirical scenarios require information_lag >= 2")
        if config.start_date or config.end_date:
            raise ValueError("Scenario dates must come from declared periods")
        configs[name] = config
    if not configs:
        raise ValueError("Declare at least one scenario")
    root = Path(output)
    if (root / period).exists():
        raise ValueError(
            "Evaluation output exists; preserve it and use a new directory"
        )
    # Freeze before loading any market prices, including holdout observations.
    digest = freeze_protocol(protocol, root / "frozen_protocol.json")
    prices, provenance = load_historical_bundle(bundle, assets)
    start, end = map(pd.Timestamp, periods[period])
    if (
        prices.index[-1] < end
        or not ((prices.index >= start) & (prices.index <= end)).any()
    ):
        raise ValueError("Data do not cover requested evaluation period")
    prices = prices.loc[:end]
    # Policy resets monthly independently of each strategy schedule.
    # Availability at preceding session close; target applies next session.
    month_starts = [
        i
        for i in range(1, len(prices))
        if prices.index[i].to_period("M") != prices.index[i - 1].to_period("M")
    ]
    snapshot_dates = [prices.index[0]] + [prices.index[i - 1] for i in month_starts]
    benchmark = pd.DataFrame([policy] * len(snapshot_dates), index=snapshot_dates)
    metadata = pd.DataFrame({"sector": protocol["sectors"]}).reindex(assets)
    rows = []
    for name, config in configs.items():
        config = replace(config, start_date=str(start.date()), end_date=str(end.date()))
        row = {"scenario": name, "configuration": asdict(config)}
        try:
            result = run_backtest(prices, benchmark, metadata, config=config)
            if result.returns.index[0] > prices.index[prices.index >= start][0]:
                raise ValueError(
                    "Insufficient pre-period warmup; evaluation would be shortened"
                )
            summary = write_report(
                result, root / period / name, "HISTORICAL ETF RESEARCH"
            )
            row.update(status="success", metrics=summary["metrics"])
        except (ValueError, RuntimeError) as exc:
            row.update(status="failed", error=str(exc))
        rows.append(row)
    evaluation = {
        "period": period,
        "protocol_sha256": digest,
        "protocol_file_sha256": file_hash(protocol_path),
        "provenance": provenance,
        "scenarios": rows,
        "holdout_access": period == "holdout",
        "limitations": (
            "Provider-adjusted retrospective fixed universe; no alpha inference"
        ),
    }
    target = root / period
    target.mkdir(parents=True, exist_ok=True)
    (target / "evaluation.json").write_text(
        json.dumps(evaluation, indent=2, allow_nan=False), encoding="utf-8"
    )
    return evaluation


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--bundle", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--quality", action="store_true")
    parser.add_argument("--freeze", action="store_true")
    parser.add_argument("--review")
    parser.add_argument("--verification")
    parser.add_argument(
        "--period",
        choices=["development", "validation", "holdout"],
        default="validation",
    )
    args = parser.parse_args()
    if args.quality:
        from portfolioos.data_quality import inspect_bundle, write_quality_report

        protocol = json.loads(Path(args.protocol).read_text(encoding="utf-8"))
        quality = inspect_bundle(
            args.bundle, protocol["assets"], *protocol["data_range"]
        )
        write_quality_report(quality, args.output)
        print(quality["status"], quality["errors"])
    elif args.freeze:
        from portfolioos.empirical import freeze_final

        if not args.review or not args.verification:
            parser.error("--freeze requires --review and --verification")
        freeze_final(
            args.protocol, args.bundle, args.output, args.review, args.verification
        )
    else:
        run(args.protocol, args.bundle, args.output, args.period)
