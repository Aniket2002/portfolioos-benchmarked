import numpy as np
import pandas as pd
import pytest

from portfolioos.signals import (
    composite_score,
    low_volatility,
    momentum_12_1,
    preprocess,
    reversal_1m,
)


def test_momentum_window_and_exclusion(market):
    p = market[0].copy()
    expected = p.iloc[-6] / p.iloc[-41] - 1
    pd.testing.assert_series_equal(momentum_12_1(p, 40, 5), expected)
    p.iloc[-5:] *= 4
    pd.testing.assert_series_equal(momentum_12_1(p, 40, 5), expected)


def test_orientation():
    p = pd.DataFrame(
        {
            "steady": np.exp(np.arange(70) * 0.001),
            "volatile": np.exp(np.arange(70) * 0.003 + np.sin(np.arange(70)) * 0.1),
        }
    )
    assert low_volatility(p)["steady"] > low_volatility(p)["volatile"]
    assert reversal_1m(p)["steady"] < 0
    pd.testing.assert_series_equal(reversal_1m(p), -(p.iloc[-1] / p.iloc[-22] - 1))


def test_preprocessing():
    score = preprocess(pd.Series([1, 2, 3, 1000, np.nan]))
    assert abs(score.mean()) < 1e-12
    assert score.iloc[-1] == 0
    assert np.isclose(score.iloc[:-1].std(ddof=0), 1)
    assert (preprocess(pd.Series([4, 4, 4])) == 0).all()
    assert (preprocess(pd.Series([np.nan, np.inf])) == 0).all()
    with pytest.raises(ValueError):
        preprocess(pd.Series([1, 2]), 0.5)


@pytest.mark.parametrize(
    "function,kwargs",
    [
        (momentum_12_1, {}),
        (low_volatility, {"lookback": 200}),
        (reversal_1m, {"lookback": 200}),
    ],
)
def test_insufficient_history(market, function, kwargs):
    with pytest.raises(ValueError):
        function(market[0], **kwargs)


def test_composite_is_explicit_weighted_sum(market):
    p = market[0]
    lookbacks = {"momentum": 40, "skip": 5, "volatility": 20, "reversal": 5}
    weights = {"momentum_12_1": 1, "low_volatility": 2, "reversal_1m": 0.5}
    expected = (
        preprocess(momentum_12_1(p, 40, 5))
        + 2 * preprocess(low_volatility(p, 20))
        + 0.5 * preprocess(reversal_1m(p, 5))
    )
    pd.testing.assert_series_equal(composite_score(p, weights, lookbacks), expected)
    external = pd.Series(np.arange(10), index=p.columns)
    pd.testing.assert_series_equal(
        composite_score(p, {"external": 1}, lookbacks, external), preprocess(external)
    )
    for bad in ({"unknown": 1}, {"external": 1}, {}, {"momentum_12_1": np.nan}):
        with pytest.raises(ValueError):
            composite_score(p, bad, lookbacks)
