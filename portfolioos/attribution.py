"""Single-day arithmetic attribution; costs are a separate residual."""

import numpy as np
import pandas as pd


def security_attribution(result):
    return result.active_weights * result.asset_returns


def sector_attribution(result):
    """Brinson-Fachler with explicit zero-weight sector return convention.

    For an absent side, its sector return is zero. Allocation, selection and
    interaction still reconcile algebraically; standalone effects for such a
    sector are convention-dependent. Summed daily effects are NOT compounded.
    """
    if result.sectors is None:
        raise ValueError("Sector attribution requires metadata")
    rows = []
    for sector in sorted(result.sectors.unique()):
        assets = result.sectors.index[result.sectors == sector]
        pw = result.weights[assets].sum(axis=1)
        bw = result.benchmark_weights[assets].sum(axis=1)
        pc = (result.weights[assets] * result.asset_returns[assets]).sum(axis=1)
        bc = (result.benchmark_weights[assets] * result.asset_returns[assets]).sum(
            axis=1
        )
        pr = pc.div(pw.replace(0, np.nan)).fillna(0)
        br = bc.div(bw.replace(0, np.nan)).fillna(0)
        rows.append(
            pd.DataFrame(
                {
                    "sector": sector,
                    "portfolio_weight": pw,
                    "benchmark_weight": bw,
                    "portfolio_sector_return": pr,
                    "benchmark_sector_return": br,
                    "allocation": (pw - bw) * (br - result.returns["benchmark"]),
                    "selection": bw * (pr - br),
                    "interaction": (pw - bw) * (pr - br),
                }
            )
        )
    return (
        pd.concat(rows).rename_axis("date").reset_index().set_index(["date", "sector"])
    )


def signal_ic(result):
    """Evaluate each score against subsequent buy-and-hold period asset returns."""
    dates = result.signal_scores.index
    rows = []
    for i, date in enumerate(dates):
        end = dates[i + 1] if i + 1 < len(dates) else None
        period = result.asset_returns.loc[date:]
        if end is not None:
            period = period.loc[period.index < end]
        forward = (1 + period).prod() - 1
        score = result.signal_scores.loc[date]
        ic = (
            score.corr(forward, method="spearman")
            if (score.nunique() > 1 and forward.nunique() > 1)
            else np.nan
        )
        rows.append(
            {
                "date": date,
                "period_end": period.index[-1],
                "observations": len(period),
                "ic": ic,
                "terminal_period": end is None,
            }
        )
    return pd.DataFrame(rows).set_index("date")
