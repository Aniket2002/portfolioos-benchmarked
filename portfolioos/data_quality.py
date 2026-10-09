"""Formal exchange-calendar, price and action checks before model evaluation."""

import json
from importlib.metadata import version
from pathlib import Path

import numpy as np
import pandas as pd

from portfolioos.empirical_protocol import INCEPTION
from portfolioos.historical import file_hash, load_historical_bundle


def exchange_sessions(start, end):
    import pandas_market_calendars as mcal

    return pd.DatetimeIndex(mcal.get_calendar("NYSE").schedule(start, end).index)


def inspect_bundle(directory, assets, start, end, expected_sessions=None):
    """Ingestion diagnostics, without model selection or portfolio performance."""
    root = Path(directory)
    errors, warnings = [], []
    try:
        prices, manifest = load_historical_bundle(root, assets)
    except (ValueError, OSError, KeyError) as exc:
        return {
            "status": "blocked",
            "errors": [str(exc)],
            "warnings": [],
            "model_evaluation_permitted": False,
        }
    expected = (
        exchange_sessions(start, end)
        if expected_sessions is None
        else pd.DatetimeIndex(expected_sessions)
    )
    missing = expected.difference(prices.index)
    unexpected = prices.index.difference(expected)
    if len(missing):
        errors.append(f"{len(missing)} missing NYSE sessions")
    if len(unexpected):
        errors.append(f"{len(unexpected)} unexpected non-session dates")
    actions = pd.read_csv(root / "actions.csv")
    original_prices = root / "original_prices.json"
    if original_prices.exists():
        if manifest["sha256"].get(original_prices.name) != file_hash(original_prices):
            errors.append("Original price response checksum mismatch")
        source = json.loads(original_prices.read_text(encoding="utf-8"))
        try:
            original = pd.DataFrame.from_dict(
                {
                    date: {asset: bars[asset]["Close"] for asset in assets}
                    for date, bars in source.items()
                },
                orient="index",
            ).reindex(columns=assets)
            original.index = pd.DatetimeIndex(original.index)
            if not original.index.equals(prices.index) or not np.allclose(
                original, prices, atol=1e-10, rtol=1e-12
            ):
                errors.append(
                    "Bundle prices differ from original adjusted Close response"
                )
        except (KeyError, TypeError, ValueError):
            errors.append("Malformed original price response")
    action_dates = pd.to_datetime(actions.date)
    if not action_dates.isin(prices.index).all():
        errors.append("Corporate actions outside price-session panel")
    extreme = prices.pct_change(fill_method=None).abs() > 0.20
    events = [
        {
            "date": str(date.date()),
            "asset": asset,
            "absolute_return": float(prices[asset].pct_change().loc[date]),
        }
        for date, asset in zip(*np.where(extreme.to_numpy()))
        for date, asset in [(prices.index[date], prices.columns[asset])]
    ]
    if events:
        errors.append("Daily adjusted returns exceed declared 20% review threshold")
    availability = {}
    for asset in assets:
        series = prices[asset]
        availability[asset] = {
            "first": str(series.first_valid_index().date()),
            "last": str(series.last_valid_index().date()),
            "observations": int(series.count()),
            "inception": INCEPTION.get(asset),
            "distributions": int(
                ((actions.asset == asset) & (actions.type == "distribution")).sum()
            ),
            "splits": int(((actions.asset == asset) & (actions.type == "split")).sum()),
        }
        if asset != "GLD" and not availability[asset]["distributions"]:
            errors.append(
                f"No distribution history supplied for income-paying ETF {asset}"
            )
        if asset in INCEPTION and pd.Timestamp(INCEPTION[asset]) > expected[0]:
            errors.append(f"Asset {asset} did not exist at research start")
    consistency = "not supplied"
    original_path = root / "original_actions.json"
    if original_path.exists():
        if manifest["sha256"].get(original_path.name) != file_hash(original_path):
            errors.append("Original action response checksum mismatch")
        original = json.loads(original_path.read_text(encoding="utf-8"))
        expected_actions = []
        for asset in assets:
            response = original.get(asset, {})
            if "error" in response:
                if asset != "GLD":
                    errors.append(
                        f"Provider action error for {asset}: {response['error']}"
                    )
                continue
            for date, fields in response.items():
                day = pd.Timestamp(date)
                if not pd.Timestamp(start) <= day <= pd.Timestamp(end):
                    continue
                for field, kind in [
                    ("Dividends", "distribution"),
                    ("Stock Splits", "split"),
                ]:
                    value = fields.get(field, 0)
                    if value:
                        expected_actions.append((day, asset, kind, float(value)))
        actual = [
            (pd.Timestamp(row.date), row.asset, row.type, float(row.value))
            for row in actions.itertuples(index=False)
        ]
        expected_actions, actual = sorted(expected_actions), sorted(actual)
        if len(expected_actions) != len(actual) or any(
            x[:3] != y[:3] or not np.isclose(x[3], y[3], atol=1e-10, rtol=1e-9)
            for x, y in zip(expected_actions, actual)
        ):
            errors.append("Price-bar actions differ from independent action endpoint")
        consistency = (
            "two endpoints of same upstream provider; "
            "not independent market verification"
        )
    if not manifest.get("upstream_rights_independently_verified", False):
        warnings.append(
            "No independent upstream redistribution-rights verification; "
            "raw data not distributed"
        )
    warnings.extend(
        [
            "Retrospective adjusted-price vintage may contain later revisions",
            "Fixed surviving ETF universe; no unbiased historical membership claim",
            "Adjustment convention documented by provider; "
            "no independent institutional price validation",
            "GLD holds gold; no cash distributions is consistent with its structure",
        ]
    )
    return {
        "status": "passed" if not errors else "blocked",
        "errors": errors,
        "warnings": warnings,
        "model_evaluation_permitted": not errors,
        "requested_range": [start, end],
        "expected_sessions": len(expected),
        "observed_sessions": len(prices),
        "missing_sessions": [str(x.date()) for x in missing],
        "unexpected_dates": [str(x.date()) for x in unexpected],
        "availability": availability,
        "extreme_returns": events,
        "extreme_threshold": 0.20,
        "actions_endpoint_consistency": consistency,
        "price_response_consistency": (
            "verified against preserved adjusted Close bars"
            if original_prices.exists()
            else "original price response not supplied"
        ),
        "duplicate_timestamps": 0,
        "invalid_prices": 0,
        "adjustment_treatment": (
            "provider auto-adjusted Close used once; actions retained, not reapplied"
        ),
        "prices_sha256": file_hash(root / "prices.csv"),
        "actions_sha256": file_hash(root / "actions.csv"),
        "manifest_sha256": file_hash(root / "manifest.json"),
        "source": manifest["source"],
        "license": manifest["license"],
        "calendar_version": version("pandas_market_calendars")
        if expected_sessions is None
        else "test-fixture",
        "holdout_access": (
            "ingestion/calendar/action diagnostics only; no model performance inspected"
        ),
    }


def write_quality_report(report, output):
    path = Path(output)
    path.mkdir(parents=True, exist_ok=True)
    (path / "data_quality.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    body = [
        "# Historical data-quality report",
        f"\nStatus: **{report['status']}**",
        "\nNo model performance is calculated in this ingestion report.",
    ]
    for label in ["errors", "warnings"]:
        body.append(f"\n## {label.title()}\n")
        body.extend(f"- {item}" for item in report[label])
    if "availability" in report:
        body.append("\n## Instrument availability\n")
        body.append("| ETF | First | Last | Rows | Distributions | Splits |")
        body.append("|---|---|---|---:|---:|---:|")
        for asset, data in report["availability"].items():
            body.append(
                f"| {asset} | {data['first']} | {data['last']} "
                f"| {data['observations']} "
                f"| {data['distributions']} | {data['splits']} |"
            )
    (path / "data_quality.md").write_text("\n".join(body) + "\n", encoding="utf-8")
