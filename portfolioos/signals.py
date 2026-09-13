"""Price signals take only the already-truncated information set."""

import numpy as np
import pandas as pd


def momentum_12_1(history, lookback=252, skip=21):
    if not 0 < skip < lookback or len(history) <= lookback:
        raise ValueError("Insufficient momentum history or invalid lookbacks")
    return history.iloc[-skip - 1] / history.iloc[-lookback - 1] - 1


def low_volatility(history, lookback=63):
    if lookback < 2 or len(history) <= lookback:
        raise ValueError("Insufficient volatility history or invalid lookback")
    return -history.pct_change(fill_method=None).iloc[-lookback:].std(ddof=1)


def reversal_1m(history, lookback=21):
    if lookback < 1 or len(history) <= lookback:
        raise ValueError("Insufficient reversal history or invalid lookback")
    return -(history.iloc[-1] / history.iloc[-lookback - 1] - 1)


def preprocess(signal, clip_quantile=0.05):
    """Winsorize valid cross section; z-score (ddof=0); missing -> neutral 0."""
    if not 0 <= clip_quantile < 0.5:
        raise ValueError("clip_quantile must be in [0, 0.5)")
    clean = signal.astype(float).replace([np.inf, -np.inf], np.nan)
    valid = clean.dropna()
    if valid.empty:
        return pd.Series(0.0, index=signal.index)
    clipped = clean.clip(
        valid.quantile(clip_quantile), valid.quantile(1 - clip_quantile)
    )
    scale = clipped.std(ddof=0)
    if not np.isfinite(scale) or scale < 1e-12:
        return pd.Series(0.0, index=signal.index)
    return ((clipped - clipped.mean()) / scale).fillna(0.0)


def composite_score(history, weights, lookbacks=None, external=None):
    lookbacks = lookbacks or {}
    raw = {
        "momentum_12_1": momentum_12_1(
            history, lookbacks.get("momentum", 252), lookbacks.get("skip", 21)
        ),
        "low_volatility": low_volatility(history, lookbacks.get("volatility", 63)),
        "reversal_1m": reversal_1m(history, lookbacks.get("reversal", 21)),
    }
    if external is not None:
        raw["external"] = external.reindex(history.columns)
    if not weights or set(weights) - set(raw):
        raise ValueError("Unknown or unavailable signal in weights")
    if not np.isfinite(list(weights.values())).all():
        raise ValueError("Signal weights must be finite")
    return sum((float(beta) * preprocess(raw[name]) for name, beta in weights.items()))
