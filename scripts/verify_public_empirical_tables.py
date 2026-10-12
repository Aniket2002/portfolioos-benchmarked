"""Verify published performance tables using only public portfolio ledgers.

No provider bundle, prices, solver or model execution is required. This validates
table arithmetic, accounting and uncertainty, not original-price correctness.
"""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


def read(path):
    return pd.read_csv(path, index_col=0, parse_dates=True)


def check(actual, expected):
    np.testing.assert_allclose(actual, expected, atol=1e-10, rtol=1e-8)


def circular_interval(values, settings):
    values = np.asarray(values)
    n, length = len(values), settings["block_length"]
    rng = np.random.default_rng(settings["seed"])
    starts = rng.integers(0, n, size=(settings["resamples"], int(np.ceil(n / length))))
    indices = (starts[:, :, None] + np.arange(length)) % n
    samples = values[indices.reshape(settings["resamples"], -1)[:, :n]]
    tail = (1 - settings["confidence"]) / 2
    return np.quantile(samples.mean(axis=1) * 252, [tail, 1 - tail])


def verify_position_context(root, directory, lock, bundle=None):
    """Check public endpoint arithmetic; optionally reconcile original prices."""
    context = json.loads((directory / "holdout_position_context.json").read_text())
    assert {row["asset"] for row in context} == {"HYG", "GLD"}
    returns = read(root / "holdout" / "fixed_risk" / "returns.csv")
    decisions = read(root / "holdout" / "fixed_risk" / "optimization.csv")
    period = [str(returns.index[0].date()), str(returns.index[-1].date())]
    assert period == lock["protocol"]["periods"]["holdout"]
    baseline = str(pd.Timestamp(decisions.execution_date.iloc[0]).date())
    securities = pd.read_csv(directory / "security_attribution_summary.csv")
    securities = securities.query("period == 'holdout'").set_index("asset")
    prices = None
    if bundle:
        path = Path(bundle) / "prices.csv"
        assert (
            hashlib.sha256(path.read_bytes()).hexdigest()
            == lock["quality"]["prices_sha256"]
        )
        prices = read(path)
        assert prices.index.is_unique and prices.index.is_monotonic_increasing
        assert prices.index[prices.index.get_loc(returns.index[0]) - 1] == pd.Timestamp(
            baseline
        )
    cumulative_returns = {}
    for row in context:
        asset = row["asset"]
        assert row["period"] == period
        assert row["baseline_date"] == baseline
        assert row["return_observations"] == len(returns)
        assert row["prices_sha256"] == lock["quality"]["prices_sha256"]
        check(row["policy_weight"], lock["protocol"]["policy_weights"][asset])
        check(
            row["annualized_active_contribution"],
            securities.loc[asset, "annualized_active_contribution"],
        )
        path = directory / row["endpoints_file"]
        assert path.name == "holdout_position_endpoints.csv"
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row["endpoints_sha256"]
        endpoints = pd.read_csv(path)
        endpoints = endpoints[endpoints.asset == asset].set_index("boundary")
        assert len(endpoints) == 3 and endpoints.index.is_unique
        assert set(endpoints.index) == {"baseline", "first_return", "last_return"}
        assert endpoints.loc["baseline", "date"] == baseline
        assert endpoints.loc["first_return", "date"] == period[0]
        assert endpoints.loc["last_return", "date"] == period[1]
        values = endpoints.normalized_adjusted_close
        assert np.isfinite(values).all() and (values > 0).all()
        check(values.loc["baseline"], 1.0)
        check(
            values.loc["last_return"] / values.loc["baseline"] - 1,
            row["cumulative_adjusted_return"],
        )
        cumulative_return = row["cumulative_adjusted_return"]
        if prices is not None:
            source = prices[asset]
            realized = source.pct_change(fill_method=None).loc[returns.index]
            cumulative_return = (1 + realized).prod() - 1
            check(cumulative_return, row["cumulative_adjusted_return"])
            check(
                source.loc[period[1]] / source.loc[baseline] - 1,
                row["cumulative_adjusted_return"],
            )
            for _, endpoint in endpoints.iterrows():
                check(
                    endpoint.normalized_adjusted_close,
                    source.loc[endpoint.date] / source.loc[baseline],
                )
        cumulative_returns[asset] = float(cumulative_return * 100)
    return cumulative_returns


def verify(results, diagnostics=None, bundle=None):
    root = Path(results)
    table = pd.read_csv(root / "all_performance.csv")
    lock = json.loads((root / "final_protocol_lock.json").read_text())
    completed, failed = 0, 0
    for _, row in table.iterrows():
        path = root / row.period / row.scenario
        if row.status != "success":
            failed += 1
            assert row[["cagr", "tracking_error"]].isna().all()
            assert (
                json.loads((path / "scenario_status.json").read_text())["status"]
                != "success"
            )
            continue
        r = read(path / "returns.csv")
        assert r.index.is_unique and r.index.is_monotonic_increasing
        assert np.isfinite(r.select_dtypes("number")).all().all()
        check(r.gross - r.cost, r.net)
        check(r.net - r.benchmark, r.active)
        cfg = lock["protocol"]["scenarios"][row.scenario]
        check(r.turnover * cfg["transaction_cost_bps"] / 10000, r.cost)
        n = len(r)
        wealth = (1 + r.net).cumprod()
        metrics = {
            "cagr": wealth.iloc[-1] ** (252 / n) - 1,
            "gross_cagr": (1 + r.gross).prod() ** (252 / n) - 1,
            "tracking_error": r.active.std(ddof=1) * np.sqrt(252),
            "annualized_arithmetic_active_return": r.active.mean() * 252,
            "maximum_drawdown": (wealth / wealth.cummax().clip(lower=1) - 1).min(),
            "average_rebalance_turnover": r.loc[r.rebalance, "turnover"].mean(),
        }
        for key, value in metrics.items():
            check(value, row[key])
        if pd.notna(row.average_signal_capture):
            capture = read(path / "signal_capture.csv").signal_capture
            check(capture.mean(), row.average_signal_capture)
            check(capture.notna().sum(), row.valid_capture_observations)
            check(capture.isna().sum(), row.excluded_capture_observations)
        ic_path = path / "signal_ic.csv"
        if pd.notna(row.mean_ic):
            check(read(ic_path).ic.mean(), row.mean_ic)
        interval = json.loads((path / "uncertainty.json").read_text())
        check(r.active.mean() * 252, interval["estimate"])
        check(
            circular_interval(r.active, lock["protocol"]["bootstrap"]),
            [interval["lower"], interval["upper"]],
        )
        completed += 1
    positions = {}
    if diagnostics:
        directory = Path(diagnostics)
        positions = verify_position_context(root, directory, lock, bundle)
        hashes = json.loads((directory / "source_evidence_hashes.json").read_text())
        for name, digest in hashes.items():
            assert hashlib.sha256((root / name).read_bytes()).hexdigest() == digest, (
                name
            )
        attribution = pd.read_csv(directory / "asset_class_attribution.csv")
        for period, group in attribution.groupby("period"):
            primary = table[(table.period == period) & (table.scenario == "fixed_risk")]
            check(
                group.annualized_active_contribution.sum(),
                primary.iloc[0].annualized_arithmetic_active_return,
            )
        activity = pd.read_csv(directory / "cap_activity.csv")
        for _, row in activity.iterrows():
            original = row.scenario != "regime_high_3pct"
            path = (root if original else directory) / row.period / row.scenario
            o = read(path / "optimization.csv")
            reserve = lock["protocol"]["scenarios"]["fixed_risk"][
                "execution_te_reserve"
            ]
            binding = (
                (o.tracking_error_budget - reserve - o.estimated_tracking_error)
                .abs()
                .le(row.binding_tolerance)
            )
            check(len(o), row.rebalances)
            check(o.regime.eq("high").sum(), row.high_rebalances)
            check(o.estimated_tracking_error.max(), row.maximum_formation_te)
            check(binding.sum(), row.binding_rebalances)
            check((binding & o.regime.eq("high")).sum(), row.high_binding_rebalances)
        for row in json.loads((directory / "table5_audit.json").read_text()):
            r = read(root / row["period"] / "without_low_volatility" / "returns.csv")
            check(r.active.std(ddof=1) * np.sqrt(252), row["tracking_error"])
        for row in json.loads((directory / "tighter_cap_results.json").read_text()):
            if row["status"] != "success":
                continue
            r = read(directory / row["period"] / row["scenario"] / "returns.csv")
            b = read(root / row["period"] / "fixed_risk" / "returns.csv")
            check(
                r.active.mean() * 252,
                row["metrics"]["annualized_arithmetic_active_return"],
            )
            check(r.active.std(ddof=1) * np.sqrt(252), row["metrics"]["tracking_error"])
            check((1 + r.net).prod() ** (252 / len(r)) - 1, row["metrics"]["cagr"])
            check(
                circular_interval(r.net - b.net, lock["protocol"]["bootstrap"]),
                [row["paired_vs_fixed"]["lower"], row["paired_vs_fixed"]["upper"]],
            )
    return {
        "passed": True,
        "completed_paths": completed,
        "preserved_failures": failed,
        "provider_bundle_required": False,
        "model_rerun": False,
        "holdout_positions_verified": len(positions),
        "holdout_cumulative_adjusted_return_percent": positions,
        "original_adjusted_series_checked": bundle is not None,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", default="results/empirical_phase2_reviewed")
    parser.add_argument("--diagnostics")
    parser.add_argument(
        "--bundle", help="Optional original-bundle check of HYG/GLD returns"
    )
    args = parser.parse_args()
    if args.bundle and not args.diagnostics:
        parser.error("--bundle requires --diagnostics")
    print(json.dumps(verify(args.results, args.diagnostics, args.bundle), indent=2))
