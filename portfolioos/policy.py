"""Predeclared monthly policy targets with close-to-close holdings drift."""

import numpy as np
import pandas as pd

from portfolioos.costs import drift_weights, one_way_turnover


def policy_history(prices, targets):
    """Reset before first session's return each month, at preceding close.

    The first supplied price is an endowment mark, not an earned return. Monthly
    reset dates are known calendar rules; price levels never determine them.
    Return weights are beginning-of-period; end_weights include that day's drift.
    """
    target = pd.Series(targets, dtype=float).reindex(prices.columns)
    if (
        set(targets) != set(prices.columns)
        or not np.isfinite(target).all()
        or (target < 0).any()
        or abs(target.sum() - 1) > 1e-10
    ):
        raise ValueError("Invalid policy targets")
    returns = prices.pct_change(fill_method=None)
    previous = target.copy()
    starts, ends, records = [], [], []
    for i, date in enumerate(prices.index):
        reset = i > 0 and date.to_period("M") != prices.index[i - 1].to_period("M")
        w = target.copy() if reset else previous.copy()
        turnover = one_way_turnover(w, previous) if reset else 0.0
        r = returns.iloc[i].fillna(0.0) if i == 0 else returns.iloc[i]
        gross = float(w @ r)
        previous = pd.Series(drift_weights(w, r), index=prices.columns)
        starts.append(w.to_numpy())
        ends.append(previous.to_numpy())
        records.append({"gross": gross, "turnover": turnover, "rebalance": reset})
    return (
        pd.DataFrame(starts, index=prices.index, columns=prices.columns),
        pd.DataFrame(ends, index=prices.index, columns=prices.columns),
        pd.DataFrame(records, index=prices.index),
    )
