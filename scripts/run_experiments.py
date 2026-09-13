"""Run controlled synthetic portfolio-implementation trade-off experiments."""

import argparse

from portfolioos.experiments import run_experiment_suite, write_experiment_report
from portfolioos.reporting import load_config
from portfolioos.synthetic import synthetic_market


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/demo.yaml")
    parser.add_argument("--output", default="results/research_tradeoffs")
    parser.add_argument("--smoke-test", action="store_true")
    args = parser.parse_args()

    synthetic, config = load_config(args.config)
    kwargs = {}
    if args.smoke_test:
        synthetic["years"] = 2
        kwargs = {
            "te_budgets": (0.04, 0.08),
            "turnover_limits": (0.15, 0.30),
            "cost_bps": (0.0, 10.0),
            "grid_te": (0.04, 0.08),
            "grid_turnover": (0.15, 0.30),
        }
    prices, metadata = synthetic_market(**synthetic)
    suite = run_experiment_suite(
        prices, metadata=metadata, base_config=config, **kwargs
    )
    summary = write_experiment_report(suite, args.output)
    failures = sum(
        int((table.scenario_status != "success").sum())
        for table in (
            suite.te_frontier,
            suite.turnover_frontier,
            suite.cost_frontier,
            suite.te_turnover_grid,
        )
    )
    identity = summary["dataset_identity"][:12]
    print(
        f"{summary['provenance']} complete; dataset={identity}; "
        f"failure_summary={failures}; artifacts in {args.output}"
    )


if __name__ == "__main__":
    main()
