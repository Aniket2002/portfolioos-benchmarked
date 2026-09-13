"""Generate a synthetic offline research report."""

import argparse

from portfolioos.reporting import run_demo


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/demo.yaml")
    parser.add_argument("--output", default=None)
    parser.add_argument("--smoke-test", action="store_true")
    args = parser.parse_args()
    output = args.output or ("results/smoke" if args.smoke_test else "results/demo")
    summary = run_demo(args.config, output, args.smoke_test)
    print(
        f"SYNTHETIC demo passed: {summary['observations']} days, "
        f"{summary['rebalances']} rebalances; artifacts in {output}"
    )


if __name__ == "__main__":
    main()
