import numpy as np
import pytest

from portfolioos.costs import drift_weights, one_way_turnover, transaction_cost


def test_turnover_invariants():
    assert one_way_turnover([0.3, 0.7], [0.3, 0.7]) == 0
    assert one_way_turnover([1, 0], [0, 1]) == 1
    assert one_way_turnover([0.2, 0.8], [0.8, 0.2]) == pytest.approx(0.6)


def test_cost_convention():
    assert transaction_cost(0, 100) == 0
    assert transaction_cost(0.4, 10) == pytest.approx(0.0004)
    assert transaction_cost(0.4, 20) > transaction_cost(0.4, 10)


def test_drift():
    np.testing.assert_allclose(drift_weights([0.5, 0.5], [0.1, -0.1]), [0.55, 0.45])
    np.testing.assert_allclose(drift_weights([0.5, 0.5], [0.1, 0.1]), [0.5, 0.5])


@pytest.mark.parametrize("args", [([1], [1, 0]), ([np.nan], [1])])
def test_invalid_turnover(args):
    with pytest.raises(ValueError):
        one_way_turnover(*args)


@pytest.mark.parametrize("args", [(-1, 10), (1, -10), (np.inf, 10)])
def test_invalid_cost(args):
    with pytest.raises(ValueError):
        transaction_cost(*args)


@pytest.mark.parametrize(
    "args", [([1], [0, 0]), ([1], [-1]), ([0.2, 0.2], [0, 0]), ([-1, 2], [0, 0])]
)
def test_invalid_drift(args):
    with pytest.raises(ValueError):
        drift_weights(*args)
