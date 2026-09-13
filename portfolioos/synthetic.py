"""Synthetic mechanics fixture, NOT empirical market evidence."""

import numpy as np
import pandas as pd


def synthetic_market(seed=42, assets=40, years=6, sectors=5):
    """Independent factor shocks with heterogeneous loadings and volatilities.

    No predictive signal structure is embedded. A fixed universe and constant
    factor distributions deliberately exclude delistings and regime changes.
    """
    if assets < 2 or years < 2 or not 1 <= sectors <= assets:
        raise ValueError("Require assets >= 2, years >= 2, 1 <= sectors <= assets")
    rng = np.random.default_rng(seed)
    n = int(years * 252)
    groups = np.arange(assets) % sectors
    market = rng.normal(0.00015, 0.008, (n, 1))
    sector = rng.normal(0, 0.005, (n, sectors))
    beta = rng.uniform(0.7, 1.3, assets)
    vol = rng.uniform(0.006, 0.018, assets)
    log_returns = market * beta + sector[:, groups] + rng.normal(size=(n, assets)) * vol
    prices = 100 * np.exp(np.vstack([np.zeros(assets), log_returns.cumsum(axis=0)]))
    tickers = [f"SYN{i:03d}" for i in range(assets)]
    dates = pd.bdate_range("2018-01-01", periods=n + 1)
    return (
        pd.DataFrame(prices, index=dates, columns=tickers),
        pd.DataFrame({"sector": [f"Sector{g}" for g in groups]}, index=tickers),
    )
