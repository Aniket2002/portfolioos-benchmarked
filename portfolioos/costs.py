"""One-way turnover and linear costs as fractions of portfolio NAV."""

import numpy as np


def one_way_turnover(target, pretrade):
    target, pretrade = np.asarray(target, float), np.asarray(pretrade, float)
    if target.shape != pretrade.shape or target.ndim != 1:
        raise ValueError("Weights must be matching vectors")
    if not np.isfinite(target).all() or not np.isfinite(pretrade).all():
        raise ValueError("Weights must be finite")
    return float(0.5 * np.abs(target - pretrade).sum())


def transaction_cost(turnover, bps):
    if not np.isfinite([turnover, bps]).all() or turnover < 0 or bps < 0:
        raise ValueError("Turnover and bps must be finite and nonnegative")
    return float(turnover * bps / 10_000)


def drift_weights(weights, returns):
    w, r = np.asarray(weights, float), np.asarray(returns, float)
    if w.shape != r.shape or w.ndim != 1:
        raise ValueError("Weights and returns must be matching vectors")
    if not np.isfinite(w).all() or not np.isfinite(r).all() or (r <= -1).any():
        raise ValueError("Invalid weights or returns")
    if (w < -1e-8).any() or not np.isclose(w.sum(), 1, atol=1e-8):
        raise ValueError("Require fully invested long-only weights")
    return w * (1 + r) / (1 + w @ r)
