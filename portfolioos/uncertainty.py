"""Declared paired circular block bootstrap for arithmetic active returns."""

import numpy as np


def block_interval(
    active_returns, block_length=21, resamples=2000, seed=20261008, confidence=0.95
):
    values = np.asarray(active_returns, dtype=float)
    if (
        values.ndim != 1
        or len(values) < block_length
        or block_length < 1
        or resamples < 2
        or not np.isfinite(values).all()
        or not 0 < confidence < 1
    ):
        raise ValueError("Invalid block bootstrap inputs")
    rng = np.random.default_rng(seed)
    blocks = int(np.ceil(len(values) / block_length))
    starts = rng.integers(0, len(values), size=(resamples, blocks))
    indices = (starts[:, :, None] + np.arange(block_length)) % len(values)
    samples = values[indices.reshape(resamples, -1)[:, : len(values)]]
    means = samples.mean(axis=1) * 252
    lower, upper = np.quantile(means, [(1 - confidence) / 2, (1 + confidence) / 2])
    return {
        "estimate": float(values.mean() * 252),
        "lower": float(lower),
        "upper": float(upper),
        "confidence": confidence,
        "seed": seed,
        "block_length": block_length,
        "resamples": resamples,
        "assumption": (
            "approximate within-period stationarity, dependence within blocks"
        ),
        "limitations": (
            "structural breaks, overlapping regimes and multiple tests not resolved"
        ),
    }
