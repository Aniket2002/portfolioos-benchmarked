"""Trailing Ledoit-Wolf risk estimate, annualized with 252 trading days."""

import numpy as np
import pandas as pd
from sklearn.covariance import LedoitWolf


def estimate_covariance(history, lookback=252, annualization=252, ridge=1e-10):
    if lookback < 2 or len(history) <= lookback:
        raise ValueError("Insufficient covariance history or invalid lookback")
    if not np.isfinite([annualization, ridge]).all() or annualization <= 0 or ridge < 0:
        raise ValueError("Invalid annualization or ridge")
    returns = history.pct_change(fill_method=None).iloc[-lookback:]
    if not np.isfinite(returns.to_numpy()).all():
        raise ValueError("Covariance returns must be finite")
    daily = LedoitWolf().fit(returns.to_numpy()).covariance_
    daily = (daily + daily.T) / 2 + np.eye(len(daily)) * ridge
    return pd.DataFrame(
        daily * annualization, index=history.columns, columns=history.columns
    )
