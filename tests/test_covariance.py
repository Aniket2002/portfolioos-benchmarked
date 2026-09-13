import numpy as np
import pandas as pd
import pytest

from portfolioos.covariance import estimate_covariance


def test_psd_symmetric_annualized(market):
    p = market[0]
    daily = estimate_covariance(p, 40, annualization=1)
    annual = estimate_covariance(p, 40)
    np.testing.assert_allclose(annual, daily * 252)
    np.testing.assert_allclose(annual, annual.T, atol=1e-14)
    assert np.linalg.eigvalsh(annual).min() >= -1e-12


def test_trailing_window_only(market):
    p = market[0].copy()
    before = estimate_covariance(p, 40)
    p.iloc[:-41] *= 3
    pd.testing.assert_frame_equal(before, estimate_covariance(p, 40))


@pytest.mark.parametrize(
    "kwargs", [{"lookback": 999}, {"lookback": 1}, {"annualization": 0}, {"ridge": -1}]
)
def test_invalid_settings(market, kwargs):
    with pytest.raises(ValueError):
        estimate_covariance(market[0], lookback=kwargs.pop("lookback", 40), **kwargs)


def test_missing_returns_rejected(market):
    p = market[0].copy()
    p.iloc[-2, 0] = np.nan
    with pytest.raises(ValueError):
        estimate_covariance(p, 40)


@pytest.mark.parametrize("kwargs", [{"ridge": np.nan}, {"annualization": np.inf}])
def test_nonfinite_scaling_rejected(market, kwargs):
    with pytest.raises(ValueError, match="annualization or ridge"):
        estimate_covariance(market[0], 40, **kwargs)
