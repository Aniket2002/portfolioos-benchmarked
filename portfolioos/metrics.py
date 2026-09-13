"""Metrics use 252 observations/year and arithmetic daily active returns."""

import numpy as np
import pandas as pd


def drawdown(returns):
    wealth = (1 + returns).cumprod()
    return wealth / wealth.cummax().clip(lower=1.0) - 1


def safe_ratio(numerator, denominator):
    return float(numerator / denominator) if denominator > 1e-15 else np.nan


def performance_metrics(
    returns, benchmark, turnover=None, costs=None, risk_free_rate=0.0, annualization=252
):
    r, b = pd.Series(returns, dtype=float), pd.Series(benchmark, dtype=float)
    if len(r) < 2 or not r.index.equals(b.index):
        raise ValueError("Require at least two aligned return observations")
    if (
        not np.isfinite(r).all()
        or not np.isfinite(b).all()
        or (r <= -1).any()
        or (b <= -1).any()
    ):
        raise ValueError("Returns must be finite and greater than -1")
    if (
        not np.isfinite([annualization, risk_free_rate]).all()
        or annualization <= 0
        or risk_free_rate <= -1
    ):
        raise ValueError("Invalid risk-free rate or annualization")
    active = r - b
    daily_rf = (1 + risk_free_rate) ** (1 / annualization) - 1
    excess = r - daily_rf
    vol = r.std(ddof=1) * np.sqrt(annualization)
    te = active.std(ddof=1) * np.sqrt(annualization)
    downside = np.sqrt(np.mean(np.minimum(excess, 0) ** 2)) * np.sqrt(annualization)
    cumulative = (1 + r).prod() - 1
    out = {
        "cumulative_return": float(cumulative),
        "cagr": float((1 + cumulative) ** (annualization / len(r)) - 1),
        "annualized_volatility": float(vol),
        "sharpe": safe_ratio(excess.mean() * annualization, vol),
        "sortino": safe_ratio(excess.mean() * annualization, downside),
        "maximum_drawdown": float(drawdown(r).min()),
        "benchmark_cumulative_return": float((1 + b).prod() - 1),
        "tracking_error": float(te),
        "information_ratio": safe_ratio(active.mean() * annualization, te),
        "annualized_arithmetic_active_return": float(active.mean() * annualization),
    }
    for name, series in (("turnover", turnover), ("costs", costs)):
        if series is not None:
            if (
                not series.index.equals(r.index)
                or not np.isfinite(series).all()
                or (series < 0).any()
            ):
                raise ValueError(f"Invalid {name} series")
    if turnover is not None:
        out["annualized_turnover"] = float(turnover.sum() * annualization / len(r))
    if costs is not None:
        out["total_cost_fraction_sum"] = float(costs.sum())
        out["compounded_cost_drag"] = float((1 + r + costs).prod() - (1 + r).prod())
    return out


def ic_metrics(ic):
    valid = ic.dropna()
    if valid.empty:
        return {
            k: np.nan
            for k in (
                "mean_ic",
                "median_ic",
                "ic_std",
                "ic_information_ratio",
                "positive_ic_fraction",
            )
        }
    std = valid.std(ddof=1)
    return {
        "mean_ic": float(valid.mean()),
        "median_ic": float(valid.median()),
        "ic_std": float(std),
        "ic_information_ratio": safe_ratio(valid.mean(), std),
        "positive_ic_fraction": float((valid > 0).mean()),
    }
