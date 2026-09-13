"""Evaluate user-supplied CSV data without downloading or copying raw data."""

import argparse

import pandas as pd

from portfolioos.backtest import run_backtest
from portfolioos.reporting import load_config, write_report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prices", required=True)
    parser.add_argument("--benchmark")
    parser.add_argument("--metadata", help="CSV indexed by ticker with sector column")
    parser.add_argument("--signals")
    parser.add_argument("--config", default="configs/demo.yaml")
    parser.add_argument("--output", default="results/research")
    args = parser.parse_args()

    def matrix(path):
        return pd.read_csv(path, index_col=0, parse_dates=True) if path else None

    _, config = load_config(args.config)
    result = run_backtest(
        matrix(args.prices),
        matrix(args.benchmark),
        pd.read_csv(args.metadata, index_col=0) if args.metadata else None,
        matrix(args.signals),
        config,
    )
    write_report(
        result,
        args.output,
        "USER-SUPPLIED DATA — provenance not independently verified",
    )
    print(f"Research report written to {args.output}")


if __name__ == "__main__":
    main()
