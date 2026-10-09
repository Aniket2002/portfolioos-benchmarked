"""Immutable vendor-neutral historical input bundles and provenance checks."""

import hashlib
import json
from pathlib import Path

import pandas as pd

from portfolioos.data import validate_prices


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_historical_bundle(directory, assets):
    """Load a complete adjusted-close panel without filling or dropping rows.

    manifest.json attests provider conventions; validation does not independently
    establish their truth. actions.csv preserves the supplied corporate-action
    ledger; adjusted prices must already incorporate actions, never adjust twice.
    """
    root = Path(directory)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    required = (
        "source",
        "source_url",
        "retrieved_at",
        "license",
        "adjustment_convention",
        "universe_selection",
        "survivorship_limitations",
        "revision_policy",
        "calendar",
        "timezone",
        "sha256",
    )
    if any(not manifest.get(key) for key in required):
        raise ValueError("Incomplete historical provenance manifest")
    if manifest["adjustment_convention"] != "split_and_distribution_adjusted_close":
        raise ValueError("Require explicitly split and distribution adjusted close")
    if pd.Timestamp(manifest["retrieved_at"]).tzinfo is None:
        raise ValueError("Retrieval timestamp must include timezone")
    if len(assets) != 10 or len(set(assets)) != 10:
        raise ValueError("Empirical universe must declare ten unique assets")
    for name in ("prices.csv", "actions.csv"):
        if manifest["sha256"].get(name) != file_hash(root / name):
            raise ValueError(f"Historical input checksum mismatch: {name}")
    prices = pd.read_csv(root / "prices.csv", index_col=0, parse_dates=True)
    if list(prices.columns) != list(assets):
        raise ValueError("Historical universe/order differs from protocol")
    prices = validate_prices(prices)
    if prices.index.tz is not None or not prices.index.equals(prices.index.normalize()):
        raise ValueError("Prices require timezone-naive session dates")
    actions = pd.read_csv(root / "actions.csv")
    if set(actions.columns) != {"date", "asset", "type", "value"}:
        raise ValueError("Corporate actions require date, asset, type, value")
    if not actions.empty:
        dates = pd.to_datetime(actions.date, errors="raise")
        values = pd.to_numeric(actions.value, errors="raise")
        if (
            not actions.asset.isin(assets).all()
            or not actions.type.isin(["split", "distribution"]).all()
            or dates.isna().any()
            or (values <= 0).any()
            or not values.map(lambda x: 0 < x < float("inf")).all()
            or actions.duplicated(["date", "asset", "type"]).any()
        ):
            raise ValueError("Invalid corporate-action ledger")
    return prices, manifest


def freeze_protocol(protocol, destination):
    """Write once; identical retries allowed, alterations rejected."""
    payload = json.dumps(protocol, sort_keys=True, indent=2, allow_nan=False) + "\n"
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
    except FileExistsError:
        if path.read_text(encoding="utf-8") != payload:
            raise ValueError("Frozen protocol differs; use a separately labelled study")
    return hashlib.sha256(payload.encode()).hexdigest()
