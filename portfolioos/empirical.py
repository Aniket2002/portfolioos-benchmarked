"""Evidence-led declared study orchestration, with an explicit final holdout gate."""

import json
import subprocess
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from portfolioos.attribution import signal_ic
from portfolioos.backtest import BacktestConfig, ExecutionFailure, run_backtest
from portfolioos.experiments import reference_signal_expression_config, signal_capture
from portfolioos.historical import file_hash, freeze_protocol, load_historical_bundle
from portfolioos.metrics import ic_metrics, performance_metrics
from portfolioos.optimizer import OptimizerConfig
from portfolioos.policy import policy_history
from portfolioos.regimes import policy_regimes
from portfolioos.reporting import validate_result, write_report
from portfolioos.uncertainty import block_interval


def read_protocol(path):
    protocol = json.loads(Path(path).read_text(encoding="utf-8"))
    assets = protocol["assets"]
    if len(assets) != 10 or len(set(assets)) != 10:
        raise ValueError("Declare ten unique assets")
    for name in ["policy_weights", "sectors"]:
        if set(protocol[name]) != set(assets):
            raise ValueError(f"{name} identifiers do not match universe")
    previous = None
    for name in ["development", "validation", "holdout"]:
        start, end = map(pd.Timestamp, protocol["periods"][name])
        if start > end or (previous is not None and start <= previous):
            raise ValueError("Research periods must be ordered and disjoint")
        previous = end
    configs = {}
    for name, settings in protocol["scenarios"].items():
        if not name or not all(c.isalnum() or c in "_-" for c in name):
            raise ValueError("Unsafe scenario name")
        settings = settings.copy()
        optimizer = OptimizerConfig(**settings.pop("optimizer"))
        config = BacktestConfig(optimizer=optimizer, **settings)
        if config.information_lag < 2 or config.start_date or config.end_date:
            raise ValueError("Scenarios require lag >=2 and period-controlled dates")
        if config.policy_weights != protocol["policy_weights"]:
            raise ValueError("Scenarios must use identical declared policy")
        configs[name] = config
    if not configs:
        raise ValueError("No declared scenarios")
    for name, config in configs.items():
        if name.startswith("cost_"):
            comparison = replace(
                config, transaction_cost_bps=configs["fixed_risk"].transaction_cost_bps
            )
            if comparison != configs["fixed_risk"]:
                raise ValueError("Cost scenarios may change accounting cost only")
    return protocol, configs


def clean_json(value):
    if isinstance(value, dict):
        return {k: clean_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [clean_json(v) for v in value]
    if isinstance(value, (float, np.floating)) and not np.isfinite(value):
        return None
    if isinstance(value, np.generic):
        return value.item()
    return value


def write_json(path, value):
    Path(path).write_text(
        json.dumps(clean_json(value), indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def verified_quality(bundle, output):
    report = json.loads(
        (Path(output) / "data_quality.json").read_text(encoding="utf-8")
    )
    if not report["model_evaluation_permitted"] or report["status"] != "passed":
        raise ValueError("Data quality blocks evaluation")
    for filename, key in [
        ("prices.csv", "prices_sha256"),
        ("actions.csv", "actions_sha256"),
        ("manifest.json", "manifest_sha256"),
    ]:
        if file_hash(Path(bundle) / filename) != report[key]:
            raise ValueError("Data changed since quality checks")
    return report


def freeze_final(protocol_path, bundle, output, review_path, verification_path):
    """Freeze only after pre-holdout evidence and verification are available."""
    protocol, _ = read_protocol(protocol_path)
    root = Path(output)
    quality = verified_quality(bundle, root)
    review = json.loads(Path(review_path).read_text(encoding="utf-8"))
    tests = json.loads(Path(verification_path).read_text(encoding="utf-8"))
    if not review.get("development_validation_reviewed") or not tests.get("passed"):
        raise ValueError("Review and executed verification must pass before freezing")
    if protocol.get("holdout_previously_used_for_selection"):
        raise ValueError(
            "Holdout used for selection cannot be labelled untouched confirmatory"
        )
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    status = subprocess.check_output(["git", "status", "--porcelain"], text=True)
    if status.strip():
        raise ValueError("Commit research code/configuration before freezing holdout")
    evidence = {
        name: file_hash(root / name / "evaluation.json")
        for name in ["development", "validation"]
    }
    lock = {
        "protocol": protocol,
        "quality": quality,
        "code_commit": commit,
        "preholdout_evidence": evidence,
        "review_sha256": file_hash(review_path),
        "verification_sha256": file_hash(verification_path),
        "holdout_opened": False,
        "frozen_at": datetime.now(timezone.utc).isoformat(),
    }
    freeze_protocol(lock, root / "final_protocol_lock.json")
    return lock


def cost_clone(result, bps):
    """Reuse exact holdings and trade path; cost sensitivity never calls the solver."""
    r = result.returns.copy()
    r["cost"] = r.turnover * bps / 10000
    r["net"] = r.gross - r.cost
    r["active"] = r.net - r.benchmark
    if "benchmark_turnover" in r:
        r["benchmark_cost"] = r.benchmark_turnover * bps / 10000
        r["benchmark_net"] = r.benchmark - r.benchmark_cost
    clone = replace(
        result, returns=r, config=replace(result.config, transaction_cost_bps=bps)
    )
    validate_result(clone)
    return clone


def evaluate_period(protocol_path, bundle, output, period):
    protocol, configs = read_protocol(protocol_path)
    root = Path(output)
    quality = verified_quality(bundle, root)
    if period not in protocol["periods"]:
        raise ValueError("Unknown evaluation period")
    if (root / period).exists():
        raise ValueError("Period outputs already exist; never overwrite an evaluation")
    declaration = freeze_protocol(protocol, root / "declared_protocol.json")
    if period == "holdout":
        lock_path = root / "final_protocol_lock.json"
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        if lock["protocol"] != protocol or lock["quality"] != quality:
            raise ValueError("Final freeze differs from current inputs")
        current_commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip()
        dirty = subprocess.check_output(["git", "status", "--porcelain"], text=True)
        if current_commit != lock["code_commit"] or dirty.strip():
            raise ValueError("Code changed since final freeze")
        for name, digest in lock["preholdout_evidence"].items():
            if file_hash(root / name / "evaluation.json") != digest:
                raise ValueError("Preholdout evidence changed after freezing")
        # Exclusive access marker is written BEFORE any holdout model use.
        with (root / "holdout_access.json").open("x", encoding="utf-8") as handle:
            json.dump(
                {
                    "code_commit": lock["code_commit"],
                    "protocol_lock_sha256": file_hash(lock_path),
                    "purpose": "single declared final evaluation",
                    "opened_at": datetime.now(timezone.utc).isoformat(),
                },
                handle,
            )
    target = root / period
    target.mkdir(parents=True)
    prices, provenance = load_historical_bundle(bundle, protocol["assets"])
    start, end = map(pd.Timestamp, protocol["periods"][period])
    # Full panel access above is ingestion only. Every model/reference gets this
    # physical slice, so development/validation cannot consume holdout observations.
    prices = prices.loc[:end].copy()
    expected = prices.index[(prices.index >= start) & (prices.index <= end)]
    if expected.empty:
        raise ValueError("No evaluation sessions")
    metadata = pd.DataFrame({"sector": protocol["sectors"]}).reindex(prices.columns)
    rows, results, failures, references = [], {}, {}, {}
    for name, original in configs.items():
        config = replace(
            original, start_date=str(start.date()), end_date=str(end.date())
        )
        row = {"scenario": name, "configuration": asdict(config)}
        try:
            if name.startswith("cost_"):
                if "fixed_risk" not in results:
                    raise RuntimeError(
                        "Identical-trade-path base did not complete: "
                        + failures.get("fixed_risk", "missing base")
                    )
                result = cost_clone(results["fixed_risk"], config.transaction_cost_bps)
            else:
                result = run_backtest(prices, metadata=metadata, config=config)
            if not result.returns.index.equals(expected):
                raise ValueError("Evaluation dates shortened by inadequate warmup")
            validate_result(result)
            summary = write_report(
                result,
                target / name,
                "HISTORICAL ETF RESEARCH (public educational API)",
                make_charts=False,
            )
            metrics = summary["metrics"]
            r = result.returns
            metrics.update(
                {
                    "gross_wealth": float((1 + r.gross).prod()),
                    "net_wealth": float((1 + r.net).prod()),
                    "gross_cagr": performance_metrics(r.gross, r.benchmark)["cagr"],
                    "average_one_way_turnover": float(r.turnover.mean()),
                    "average_rebalance_turnover": float(
                        r.loc[r.rebalance, "turnover"].mean()
                    ),
                    "average_active_share": float(
                        0.5 * result.active_weights.abs().sum(axis=1).mean()
                    ),
                    "execution_constraint_violations": int(
                        result.optimization.execution_violations.ne("").sum()
                    ),
                    "solver_failures": int(
                        (
                            ~result.optimization.status.isin(["optimal", "rule_based"])
                        ).sum()
                    ),
                    **ic_metrics(signal_ic(result).ic),
                }
            )
            if "benchmark_net" in r:
                metrics.update(
                    policy_frictionless_cagr=performance_metrics(
                        r.benchmark, r.benchmark
                    )["cagr"],
                    policy_net_cagr=performance_metrics(r.benchmark_net, r.benchmark)[
                        "cagr"
                    ],
                    net_active_vs_cost_adjusted_policy=float(
                        (r.net - r.benchmark_net).mean() * 252
                    ),
                )
            if config.strategy == "optimized":
                ref_cfg = reference_signal_expression_config(
                    replace(config, regime_te_budgets=None)
                )
                # Cost does not enter formation; cache across identical cost paths.
                ref_cfg = replace(ref_cfg, transaction_cost_bps=0)
                key = json.dumps(asdict(ref_cfg), sort_keys=True)
                if key not in references:
                    references[key] = run_backtest(
                        prices, metadata=metadata, config=ref_cfg
                    )
                capture = signal_capture(result, references[key])
                capture.to_csv(target / name / "signal_capture.csv")
                metrics.update(
                    average_signal_capture=float(capture.mean()),
                    valid_capture_observations=int(capture.notna().sum()),
                    excluded_capture_observations=int(capture.isna().sum()),
                )
            else:
                metrics.update(
                    average_signal_capture=None,
                    valid_capture_observations=0,
                    excluded_capture_observations=0,
                )
            bootstrap = protocol["bootstrap"].copy()
            bootstrap.pop("metric")
            interval = block_interval(r.active, **bootstrap)
            write_json(target / name / "uncertainty.json", interval)
            # Conditional arithmetic means/volatility only; no artificial CAGR
            # compounded from a discontinuous subsequence of regime-labelled days.
            _, _, policy = policy_history(prices, config.policy_weights)
            regimes = policy_regimes(policy.gross.iloc[1:])
            labels = pd.Series(
                {
                    date: regimes.loc[
                        prices.index[
                            prices.index.get_loc(date) - config.information_lag
                        ],
                        "regime",
                    ]
                    for date in r.index
                }
            )
            conditional = []
            for state in ["normal", "high"]:
                selected = r.loc[labels == state]
                conditional.append(
                    {
                        "regime": state,
                        "observations": len(selected),
                        "annualized_mean_active": float(selected.active.mean() * 252),
                        "realized_tracking_error": float(
                            selected.active.std() * np.sqrt(252)
                        ),
                        "average_turnover": float(selected.turnover.mean()),
                    }
                )
            write_json(target / name / "regime_conditional.json", conditional)
            row.update(
                status="success",
                metrics=metrics,
                uncertainty=interval,
                evaluation_start=str(expected[0].date()),
                evaluation_end=str(expected[-1].date()),
                observations=len(r),
                regime_conditional=conditional,
            )
            results[name] = result
        except (RuntimeError, ValueError) as exc:
            failures[name] = str(exc)
            row.update(status="failed", error=str(exc), observations=0)
            row.update(
                solver_failures=int("Optimization failed" in str(exc)),
                execution_failures=int(isinstance(exc, ExecutionFailure)),
                dependent_path_unavailable=name.startswith("cost_"),
            )
            if isinstance(exc, ExecutionFailure):
                partial = target / name
                partial.mkdir(exist_ok=True)
                for label, frame in exc.partial.items():
                    frame.to_csv(partial / f"partial_{label}.csv")
                row.update(
                    failure_date=str(exc.date.date()),
                    attempted=exc.attempted,
                    completed_days=len(exc.partial["returns"]),
                )
        rows.append(row)
        scenario_dir = target / name
        scenario_dir.mkdir(exist_ok=True)
        write_json(scenario_dir / "scenario_status.json", row)
        print(f"{period}: {name}: {row['status']}", flush=True)
    evaluation = {
        "period": period,
        "protocol_sha256": declaration,
        "quality_sha256": file_hash(root / "data_quality.json"),
        "dataset_identity": quality["prices_sha256"],
        "provenance": provenance,
        "scenarios": rows,
        "groups": protocol["experiment_groups"],
        "holdout_performance_accessed": period == "holdout",
    }
    write_json(target / "evaluation.json", evaluation)
    flat = [
        {
            "scenario": row["scenario"],
            "status": row["status"],
            "error": row.get("error", ""),
            **row.get("metrics", {}),
        }
        for row in rows
    ]
    pd.DataFrame(flat).to_csv(target / "performance.csv", index=False)
    return evaluation
