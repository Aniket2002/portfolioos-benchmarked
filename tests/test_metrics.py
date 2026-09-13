import numpy as np
import pandas as pd
import pytest

from portfolioos.metrics import drawdown, ic_metrics, performance_metrics


def test_known_cagr_and_volatility():
    r = pd.Series([0.01] * 252)
    out = performance_metrics(r, r)
    assert out["cagr"] == pytest.approx(1.01**252 - 1)
    assert out["annualized_volatility"] == pytest.approx(0, abs=1e-12)
    assert np.isnan(out["sharpe"])
    assert np.isnan(out["information_ratio"])


def test_drawdown_includes_initial_nav():
    r = pd.Series([-0.1, 0, 0.2, -0.25])
    np.testing.assert_allclose(drawdown(r), [-0.1, -0.1, 0, -0.25])


def test_known_risk_metrics():
    r, b = pd.Series([0.02, -0.01, 0.03, -0.02]), pd.Series([0.01, 0, 0.01, 0])
    out = performance_metrics(r, b)
    te = (r - b).std(ddof=1) * np.sqrt(252)
    assert out["annualized_volatility"] == pytest.approx(r.std(ddof=1) * np.sqrt(252))
    assert out["tracking_error"] == pytest.approx(te)
    assert out["information_ratio"] == pytest.approx((r - b).mean() * 252 / te)
    assert out["sortino"] == pytest.approx(
        r.mean() * 252 / (np.sqrt(np.mean(np.minimum(r, 0) ** 2)) * np.sqrt(252))
    )


def test_cost_drag_and_turnover(result):
    r = result.returns
    out = performance_metrics(r.net, r.benchmark, r.turnover, r.cost)
    assert out["total_cost_fraction_sum"] == pytest.approx(r.cost.sum())
    assert out["compounded_cost_drag"] == pytest.approx(
        (1 + r.gross).prod() - (1 + r.net).prod()
    )
    assert out["annualized_turnover"] == pytest.approx(r.turnover.sum() * 252 / len(r))


def test_ic_metrics():
    out = ic_metrics(pd.Series([0.1, -0.1, 0.3, np.nan]))
    assert out["mean_ic"] == pytest.approx(0.1)
    assert out["positive_ic_fraction"] == pytest.approx(2 / 3)
    assert all(np.isnan(v) for v in ic_metrics(pd.Series([np.nan])).values())


@pytest.mark.parametrize(
    "r,b,kwargs",
    [
        ([0], [0], {}),
        ([np.nan, 0], [0, 0], {}),
        ([-1, 0], [0, 0], {}),
        ([0, 0], [0, 0], {"risk_free_rate": -1}),
        ([0, 0], [0, 0], {"annualization": 0}),
        ([0, 0], [0, 0], {"costs": pd.Series([-1, 0])}),
    ],
)
def test_invalid_metrics(r, b, kwargs):
    with pytest.raises(ValueError):
        performance_metrics(r, b, **kwargs)


def test_nonfinite_annualization_rejected():
    with pytest.raises(ValueError, match="annualization"):
        performance_metrics([0, 0], [0, 0], annualization=np.nan)
