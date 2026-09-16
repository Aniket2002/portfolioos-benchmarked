"""Run the frozen synthetic-seed robustness protocol."""

import argparse

from portfolioos.robustness import load_protocol, run_protocol, write_results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", default="configs/seed_robustness.yaml")
    parser.add_argument("--output", default="results/seed_robustness")
    args = parser.parse_args()
    protocol = load_protocol(args.protocol)
    results = run_protocol(protocol)
    summary = write_results(protocol, results, args.output)
    print(
        f"{summary['classification']} robustness; "
        f"dominant={summary['count_delta_turnover_gt_delta_TE']}/20; "
        f"artifacts in {args.output}"
    )


if __name__ == "__main__":
    main()
