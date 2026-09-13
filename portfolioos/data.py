"""Vendor-neutral validation; no backward filling or universe selection."""

import numpy as np
import pandas as pd


def validate_matrix(frame: pd.DataFrame, name: str) -> None:
    if not isinstance(frame.index, pd.DatetimeIndex):
        raise ValueError(f"{name}: require a DatetimeIndex")
    if frame.empty or frame.index.hasnans:
        raise ValueError(f"{name}: empty data or missing dates")
    if not frame.index.is_monotonic_increasing or frame.index.has_duplicates:
        raise ValueError(f"{name}: dates must be sorted and unique")
    if frame.columns.has_duplicates or frame.columns.isna().any():
        raise ValueError(f"{name}: asset identifiers must be unique and nonmissing")
    if not all(isinstance(c, str) and c for c in frame.columns):
        raise ValueError(f"{name}: require nonempty string asset identifiers")


def validate_prices(prices, min_history=2, max_missing_fraction=0.0, fill_limit=0):
    """Reject missing data by default; optional bounded causal forward fill.

    Threshold applies per asset, without dropping assets/dates. Leading gaps and
    gaps exceeding fill_limit are errors. No arbitrary gap bridging is allowed.
    """
    validate_matrix(prices, "prices")
    if min_history < 2 or not 0 <= max_missing_fraction <= 1 or fill_limit < 0:
        raise ValueError("Invalid price validation configuration")
    if len(prices) < min_history:
        raise ValueError("Insufficient price history")
    out = prices.astype(float).copy()
    if np.isinf(out.to_numpy()).any() or (out <= 0).any().any():
        raise ValueError("Prices must be finite and positive")
    if (out.isna().mean() > max_missing_fraction).any():
        raise ValueError("Missing-data threshold exceeded")
    if fill_limit:
        out = out.ffill(limit=fill_limit)
    if out.isna().any().any():
        raise ValueError("Unresolved missing prices; supply a complete panel")
    return out


def align_benchmark(weights, assets):
    """Normalize long-only target snapshots; reject unknown constituents."""
    validate_matrix(weights, "benchmark")
    if set(weights.columns) - set(assets):
        raise ValueError("Benchmark contains unavailable constituents")
    out = weights.reindex(columns=assets, fill_value=0).astype(float)
    if not np.isfinite(out.to_numpy()).all() or (out < 0).any().any():
        raise ValueError("Benchmark weights must be finite and nonnegative")
    if (out.sum(axis=1) <= 0).any():
        raise ValueError("Benchmark rows must have positive total weight")
    return out.div(out.sum(axis=1), axis=0)


def align_sectors(metadata, assets):
    if metadata is None:
        return None
    if metadata.index.has_duplicates or "sector" not in metadata:
        raise ValueError("Metadata needs unique asset index and sector column")
    sectors = metadata.reindex(assets)["sector"]
    if sectors.isna().any():
        raise ValueError("Sector metadata missing for an asset")
    return sectors.astype(str)


def align_external_signals(signals, assets):
    validate_matrix(signals, "external signals")
    if set(signals.columns) != set(assets):
        raise ValueError("External signals must match the price universe")
    out = signals.reindex(columns=assets).astype(float)
    if np.isinf(out.to_numpy()).any():
        raise ValueError("External signals contain infinity")
    return out
