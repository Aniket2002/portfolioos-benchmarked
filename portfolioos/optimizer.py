"""Convex benchmark-relative allocation with explicit failure outcomes."""

from dataclasses import dataclass

import cvxpy as cp
import numpy as np
import pandas as pd

from portfolioos.costs import one_way_turnover


@dataclass(frozen=True)
class OptimizerConfig:
    risk_aversion: float = 10.0
    turnover_penalty: float = 0.1
    max_position_weight: float = 0.08
    max_tracking_error: float | None = 0.08
    max_sector_active_weight: float | None = 0.10
    max_turnover: float | None = 0.30
    fallback_to_benchmark: bool = False

    def __post_init__(self):
        for name in ("risk_aversion", "turnover_penalty", "max_position_weight"):
            if getattr(self, name) is None:
                raise ValueError(f"Required optimizer setting cannot be null: {name}")
        for name in (
            "risk_aversion",
            "turnover_penalty",
            "max_position_weight",
            "max_tracking_error",
            "max_sector_active_weight",
            "max_turnover",
        ):
            value = getattr(self, name)
            if value is not None and (not np.isfinite(value) or value < 0):
                raise ValueError(f"Invalid optimizer setting: {name}")
        if not 0 < self.max_position_weight <= 1:
            raise ValueError("max_position_weight must be in (0, 1]")


@dataclass
class OptimizationResult:
    weights: pd.Series | None
    status: str
    message: str
    tracking_error: float | None = None


def constraint_violations(w, wb, previous, covariance, sectors, config, tol=1e-7):
    """Independently check returned holdings, including configured fallbacks."""
    errors = []
    if not np.isfinite(w).all() or abs(w.sum() - 1) > tol:
        errors.append("nonfinite or not fully invested")
    if w.min() < -tol or w.max() > config.max_position_weight + tol:
        errors.append("position bounds")
    active = w - wb
    te = np.sqrt(max(0.0, float(active @ covariance @ active)))
    if config.max_tracking_error is not None and te > config.max_tracking_error + tol:
        errors.append("tracking error")
    if config.max_turnover is not None:
        if one_way_turnover(w, previous) > config.max_turnover + tol:
            errors.append("turnover")
    if config.max_sector_active_weight is not None and sectors is not None:
        for sector in np.unique(sectors):
            if (
                abs(active[sectors == sector].sum())
                > config.max_sector_active_weight + tol
            ):
                errors.append("sector active weight")
    return errors, te


def optimize(score, covariance, benchmark, previous, sectors=None, config=None):
    config = config or OptimizerConfig()
    assets = score.index
    if assets.has_duplicates or len(assets) < 2:
        raise ValueError("Require at least two unique assets")
    for vector in (benchmark, previous):
        if not vector.index.equals(assets):
            raise ValueError("Optimizer vectors must have identical asset order")
    if not covariance.index.equals(assets) or not covariance.columns.equals(assets):
        raise ValueError("Covariance universe/order mismatch")
    s, wb, prev, cov = map(np.asarray, (score, benchmark, previous, covariance))
    if not all(np.isfinite(x).all() for x in (s, wb, prev, cov)):
        raise ValueError("Optimizer inputs must be finite")
    if (
        not np.allclose(cov, cov.T, atol=1e-10, rtol=0)
        or np.linalg.eigvalsh(cov).min() < -1e-10
    ):
        raise ValueError("Covariance must be symmetric positive semidefinite")
    if any(x.min() < 0 or not np.isclose(x.sum(), 1) for x in (wb, prev)):
        raise ValueError(
            "Benchmark and previous weights must be long-only and sum to one"
        )
    sector_array = None
    if sectors is not None:
        if not sectors.index.equals(assets) or sectors.isna().any():
            raise ValueError("Invalid sector alignment")
        sector_array = sectors.to_numpy()
    elif config.max_sector_active_weight is not None:
        raise ValueError("Sector constraint requires sector metadata")

    w = cp.Variable(len(s))
    active = w - wb
    active_variance = cp.quad_form(active, cp.psd_wrap(cov))
    constraints = [cp.sum(w) == 1, w >= 0, w <= config.max_position_weight]
    if config.max_tracking_error is not None:
        eigenvalues, eigenvectors = np.linalg.eigh(cov)
        covariance_factor = np.sqrt(np.maximum(eigenvalues, 0))[:, None] * (
            eigenvectors.T
        )
        constraints.append(
            cp.norm(covariance_factor @ active, 2) <= config.max_tracking_error
        )
    if config.max_turnover is not None:
        constraints.append(0.5 * cp.norm1(w - prev) <= config.max_turnover)
    if config.max_sector_active_weight is not None:
        for sector in np.unique(sector_array):
            constraints.append(
                cp.abs(cp.sum(active[sector_array == sector]))
                <= config.max_sector_active_weight
            )
    objective = cp.Maximize(
        s @ w
        - config.risk_aversion * active_variance
        - config.turnover_penalty * cp.norm1(w - prev)
    )
    problem = cp.Problem(objective, constraints)
    message = ""
    try:
        problem.solve(
            solver="CLARABEL",
            tol_gap_abs=1e-9,
            tol_feas=1e-9,
            tol_gap_rel=1e-9,
            max_iter=300,
        )
        status = str(problem.status)
    except cp.error.SolverError as exc:
        status, message = "solver_error", str(exc)
    if status == "optimal" and w.value is not None:
        # Remove only numerical negative dust, then verify every constraint again.
        candidate = np.maximum(w.value, 0)
        candidate /= candidate.sum()
        errors, te = constraint_violations(
            candidate, wb, prev, cov, sector_array, config
        )
        if not errors:
            return OptimizationResult(
                pd.Series(candidate, index=assets), status, "", te
            )
        status, message = "constraint_violation", ", ".join(errors)
    if not message:
        message = "No accepted optimum; constraints were not relaxed"
        if len(s) * config.max_position_weight < 1:
            message += "; aggregate position capacity is below 100%"
    if config.fallback_to_benchmark:
        errors, te = constraint_violations(wb, wb, prev, cov, sector_array, config)
        if not errors:
            return OptimizationResult(
                benchmark.copy(), f"fallback:{status}", message, te
            )
        message += "; benchmark fallback violates " + ", ".join(errors)
    return OptimizationResult(None, status, message)
