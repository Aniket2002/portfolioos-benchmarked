from dataclasses import replace

import cvxpy as cp
import numpy as np
import pandas as pd
import pytest

from portfolioos.optimizer import OptimizerConfig, constraint_violations, optimize


def test_independent_constraint_checker_rejects_bad_holdings(inputs):
    _, covariance, benchmark, previous, sectors = inputs
    cfg = OptimizerConfig(
        max_position_weight=0.3,
        max_tracking_error=0.01,
        max_sector_active_weight=0.01,
        max_turnover=0.01,
    )
    errors, _ = constraint_violations(
        np.array([0.9, 0.2, 0, 0]),
        benchmark.to_numpy(),
        previous.to_numpy(),
        covariance.to_numpy(),
        sectors.to_numpy(),
        cfg,
    )
    assert set(errors) == {
        "nonfinite or not fully invested",
        "position bounds",
        "tracking error",
        "turnover",
        "sector active weight",
    }


def test_reject_solver_optimal_status_with_bad_weights(
    inputs, unconstrained, monkeypatch
):
    def false_optimum(problem, **kwargs):
        problem.variables()[0].value = np.array([1.0, 0, 0, 0])
        problem._status = "optimal"

    monkeypatch.setattr(cp.Problem, "solve", false_optimum)
    out = optimize(*inputs, config=replace(unconstrained, max_position_weight=0.3))
    assert out.weights is None and out.status == "constraint_violation"


@pytest.mark.parametrize(
    "name", ["risk_aversion", "turnover_penalty", "max_position_weight"]
)
def test_required_settings_cannot_be_null(name):
    with pytest.raises(ValueError, match="cannot be null"):
        OptimizerConfig(**{name: None})


@pytest.fixture
def inputs():
    assets = pd.Index(["A", "B", "C", "D"])
    return (
        pd.Series([2.0, 1, -1, -2], index=assets),
        pd.DataFrame(np.eye(4) * 0.04, index=assets, columns=assets),
        pd.Series(0.25, index=assets),
        pd.Series(0.25, index=assets),
        pd.Series(["X", "X", "Y", "Y"], index=assets),
    )


def test_all_constraints(inputs):
    cfg = OptimizerConfig(
        max_position_weight=0.4,
        max_tracking_error=0.03,
        max_sector_active_weight=0.05,
        max_turnover=0.12,
    )
    out = optimize(*inputs, config=cfg)
    w, b = out.weights, inputs[2]
    assert out.status == "optimal"
    assert w.sum() == pytest.approx(1)
    assert w.min() >= 0
    assert w.max() <= 0.4 + 1e-7
    assert out.tracking_error <= 0.03 + 1e-7
    assert 0.5 * (w - b).abs().sum() <= 0.12 + 1e-7
    assert (w - b).groupby(inputs[4]).sum().abs().max() <= 0.05 + 1e-7


def test_stronger_signal_increases_allocation(inputs, unconstrained):
    cfg = replace(unconstrained, risk_aversion=100, turnover_penalty=0)
    baseline = optimize(*inputs, config=cfg).weights
    score = inputs[0].copy()
    score.iloc[0] += 1
    stronger = optimize(score, *inputs[1:], config=cfg).weights
    assert stronger.iloc[0] > baseline.iloc[0]


def test_infeasible_no_silent_fallback(inputs, unconstrained):
    cfg = replace(unconstrained, max_position_weight=0.2)
    out = optimize(*inputs, config=cfg)
    assert out.weights is None
    assert out.status == "infeasible"
    assert "capacity" in out.message
    out = optimize(*inputs, config=replace(cfg, fallback_to_benchmark=True))
    assert out.weights is None
    assert "fallback violates" in out.message


def test_solver_failure_and_configured_fallback(inputs, unconstrained, monkeypatch):
    def fail(*args, **kwargs):
        raise cp.error.SolverError("test solver failure")

    monkeypatch.setattr(cp.Problem, "solve", fail)
    out = optimize(*inputs, config=unconstrained)
    assert out.status == "solver_error" and out.weights is None
    out = optimize(*inputs, config=replace(unconstrained, fallback_to_benchmark=True))
    assert out.status == "fallback:solver_error"
    pd.testing.assert_series_equal(out.weights, inputs[2])


@pytest.mark.parametrize(
    "defect",
    [
        "order",
        "cov_order",
        "nan",
        "asymmetric",
        "indefinite",
        "weights",
        "sectors",
        "no_sectors",
        "one_asset",
    ],
)
def test_invalid_inputs(inputs, unconstrained, defect):
    s, c, b, p, sectors = (x.copy() for x in inputs)
    cfg = unconstrained
    if defect == "order":
        b = b.iloc[::-1]
    elif defect == "cov_order":
        c = c.iloc[::-1]
    elif defect == "nan":
        s.iloc[0] = np.nan
    elif defect == "asymmetric":
        c.iloc[0, 1] = 0.5
    elif defect == "indefinite":
        c.iloc[0, 0] = -1
    elif defect == "weights":
        p.iloc[0] = 0.5
    elif defect == "sectors":
        sectors = sectors.iloc[::-1]
    elif defect == "no_sectors":
        sectors = None
        cfg = replace(cfg, max_sector_active_weight=0.1)
    else:
        s = s.iloc[:1]
    with pytest.raises(ValueError):
        optimize(s, c, b, p, sectors, cfg)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"risk_aversion": -1},
        {"max_turnover": np.nan},
        {"max_position_weight": 0},
        {"max_position_weight": 2},
    ],
)
def test_invalid_config(kwargs):
    with pytest.raises(ValueError):
        OptimizerConfig(**kwargs)
