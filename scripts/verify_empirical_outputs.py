"""Reproduce selected pre-holdout paths without overwriting study artifacts."""

import argparse
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

from portfolioos.backtest import run_backtest
from portfolioos.empirical import read_protocol, verified_quality, write_json
from portfolioos.historical import load_historical_bundle
from portfolioos.reporting import validate_result


def verify(protocol_path, bundle, output, period="validation"):
    protocol, configs = read_protocol(protocol_path)
    verified_quality(bundle, output)
    if period not in {"development", "validation"}:
        raise ValueError("Only pre-holdout reproduction is allowed in this verifier")
    start, end = protocol["periods"][period]
    prices, _ = load_historical_bundle(bundle, protocol["assets"])
    prices = prices.loc[:end].copy()
    metadata = pd.DataFrame({"sector": protocol["sectors"]}).reindex(prices.columns)
    comparisons = {}
    for scenario in ["fixed_risk", "regime_aware"]:
        result = run_backtest(
            prices,
            metadata=metadata,
            config=replace(configs[scenario], start_date=start, end_date=end),
        )
        validate_result(result)
        comparisons[scenario] = {}
        for label, actual in [("weights", result.weights), ("returns", result.returns)]:
            saved = pd.read_csv(
                Path(output) / period / scenario / f"{label}.csv",
                index_col=0,
                parse_dates=True,
            )
            if not saved.index.equals(actual.index):
                raise ValueError("Reproduction dates differ")
            numeric = actual.select_dtypes("number").columns
            a, b = actual[numeric].to_numpy(), saved[numeric].to_numpy()
            if not np.allclose(a, b, atol=1e-10, rtol=1e-9):
                raise ValueError(f"Reproduction differs: {scenario}/{label}")
            comparisons[scenario][label] = float(np.max(np.abs(a - b)))
    record = {
        "passed": True,
        "period": period,
        "max_absolute_differences": comparisons,
        "holdout_performance_accessed": False,
        "outputs_overwritten": False,
    }
    write_json(Path(output) / "reproducibility_verification.json", record)
    return record


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--bundle", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--period", choices=["development", "validation"], default="validation"
    )
    args = parser.parse_args()
    print(verify(args.protocol, args.bundle, args.output, args.period))
