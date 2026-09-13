from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from portfolioos.attribution import sector_attribution, security_attribution, signal_ic


def test_security_and_sector_reconcile(result):
    np.testing.assert_allclose(
        security_attribution(result).sum(axis=1),
        result.returns.gross_active,
        atol=1e-14,
    )
    sector = sector_attribution(result)
    daily = (
        sector[["allocation", "selection", "interaction"]]
        .sum(axis=1)
        .groupby(level="date")
        .sum()
    )
    np.testing.assert_allclose(daily, result.returns.gross_active, atol=1e-14)
    np.testing.assert_allclose(
        daily - result.returns.cost, result.returns.active, atol=1e-14
    )


def test_zero_sector_weights_reconcile(result):
    w, b = result.weights.copy(), result.benchmark_weights.copy()
    assets = result.sectors.index[result.sectors == result.sectors.iloc[0]]
    w.loc[:, assets] = 0
    w = w.div(w.sum(axis=1), axis=0)
    other = result.sectors.index[result.sectors == result.sectors.iloc[1]]
    b.loc[:, other] = 0
    b = b.div(b.sum(axis=1), axis=0)
    r = result.returns.copy()
    r["gross"] = (w * result.asset_returns).sum(axis=1)
    r["benchmark"] = (b * result.asset_returns).sum(axis=1)
    modified = replace(result, weights=w, benchmark_weights=b, returns=r)
    effects = sector_attribution(modified)[["allocation", "selection", "interaction"]]
    assert np.isfinite(effects.to_numpy()).all()
    np.testing.assert_allclose(
        effects.sum(axis=1).groupby(level="date").sum(),
        r.gross - r.benchmark,
        atol=1e-14,
    )


def test_no_metadata(result):
    with pytest.raises(ValueError):
        sector_attribution(replace(result, sectors=None))


def test_ic_forward_window(result):
    ic = signal_ic(result)
    start, end = result.signal_scores.index[:2]
    forward = (
        1 + result.asset_returns.loc[start:].loc[lambda x: x.index < end]
    ).prod() - 1
    expected = result.signal_scores.loc[start].corr(forward, method="spearman")
    assert ic.loc[start, "ic"] == pytest.approx(expected)
    assert ic.iloc[-1].terminal_period
    constant = replace(
        result,
        signal_scores=pd.DataFrame(
            0.0, index=result.signal_scores.index, columns=result.weights.columns
        ),
    )
    assert signal_ic(constant).ic.isna().all()
