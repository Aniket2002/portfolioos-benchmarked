"""Expanding historical volatility thresholds; no full-sample labels."""

import numpy as np
import pandas as pd


def policy_regimes(returns, lookback=63, min_history=252):
    """Two-state policy-return volatility, strictly earlier expanding 75% cutoff.

    Labels are available only after their dated close. Consumers must slice at
    the declared information date. Annualization changes scale, not labels.
    """
    if lookback < 2 or min_history < 2 or not np.isfinite(returns).all():
        raise ValueError("Invalid policy regime inputs")
    vol = returns.rolling(lookback, min_periods=lookback).std(ddof=1) * np.sqrt(252)
    threshold = vol.shift(1).expanding(min_periods=min_history).quantile(0.75)
    labels = pd.Series(None, index=returns.index, dtype=object)
    eligible = vol.notna() & threshold.notna()
    labels.loc[eligible] = np.where(
        vol.loc[eligible] > threshold.loc[eligible], "high", "normal"
    )
    return pd.DataFrame({"volatility": vol, "threshold": threshold, "regime": labels})


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
