"""Expanding historical volatility thresholds; no full-sample labels."""

import numpy as np


def causal_regime(history, lookback=63, min_history=252):
    """Classify latest volatility against strictly earlier rolling estimates.

    Cutoffs are the expanding 1/3 and 2/3 quantiles. Call with an information-
    truncated price series. Ties are normal; insufficient history is an error.
    """
    if lookback < 2 or min_history < 2:
        raise ValueError("Invalid regime lookbacks")
    volatility = history.pct_change(fill_method=None).rolling(lookback).std().dropna()
    past = volatility.iloc[:-1]
    if len(past) < min_history or not np.isfinite(volatility).all():
        raise ValueError("Insufficient finite regime history")
    low, high = past.quantile([1 / 3, 2 / 3])
    current = volatility.iloc[-1]
    return "low" if current < low else "high" if current > high else "normal"
