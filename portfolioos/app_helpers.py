"""Pure presentation adapters for the optional Streamlit research interface."""

import json
from dataclasses import asdict, replace
from io import BytesIO

import numpy as np
import pandas as pd

from portfolioos.attribution import sector_attribution, security_attribution, signal_ic
from portfolioos.metrics import drawdown, ic_metrics, performance_metrics
from portfolioos.optimizer import OptimizerConfig
from portfolioos.reporting import validate_result
from portfolioos.signals import (
    low_volatility,
    momentum_12_1,
    preprocess,
    reversal_1m,
)


def make_app_config(base, controls, has_sectors=True):
    """Map bounded UI values onto the engine's immutable configuration objects."""
    optimizer = OptimizerConfig(
        risk_aversion=float(controls["risk_aversion"]),
        turnover_penalty=float(controls["turnover_penalty"]),
        max_position_weight=float(controls["max_position_weight"]),
        max_tracking_error=(
            float(controls["max_tracking_error"])
            if controls.get("tracking_error_enabled", True)
            else None
        ),
        max_sector_active_weight=(
            float(controls["max_sector_active_weight"])
            if has_sectors and controls.get("sector_cap_enabled", True)
            else None
        ),
        max_turnover=(
            float(controls["max_turnover"])
            if controls.get("turnover_cap_enabled", True)
            else None
        ),
        fallback_to_benchmark=False,
    )
    return replace(
        base,
        rebalance_frequency=controls["rebalance_frequency"],
        signal_weights={
            "momentum_12_1": float(controls["momentum_weight"]),
            "low_volatility": float(controls["low_volatility_weight"]),
            "reversal_1m": float(controls["reversal_weight"]),
        },
        covariance_lookback=int(controls["covariance_lookback"]),
        transaction_cost_bps=float(controls["transaction_cost_bps"]),
        optimizer=optimizer,
    )


def canonical_synthetic_settings(config_path="configs/demo.yaml"):
    """Return the canonical synthetic inputs from the tracked research config."""
    from portfolioos.reporting import load_config

    synthetic, _ = load_config(config_path)
    return {key: int(synthetic[key]) for key in ("seed", "assets", "years")}


def research_context(current, canonical):
    """Describe the active synthetic case truthfully relative to the canonical one."""
    keys = ("seed", "assets", "years")
    current = {key: int(current[key]) for key in keys}
    canonical = {key: int(canonical[key]) for key in keys}
    return {
        "current": (
            f"Seed {current['seed']} · {current['assets']} assets · "
            f"{current['years']} years"
        ),
        "canonical": (
            f"Seed {canonical['seed']} · {canonical['assets']} assets · "
            f"{canonical['years']} years"
        ),
        "matches_canonical": current == canonical,
    }


def read_uploaded_csv(upload, kind):
    """Read an in-memory upload into the package's documented tabular shape."""
    raw = upload.getvalue() if hasattr(upload, "getvalue") else upload
    if kind == "metadata":
        return pd.read_csv(BytesIO(raw), index_col=0)
    if kind in {"prices", "benchmark"}:
        return pd.read_csv(BytesIO(raw), index_col=0, parse_dates=True)
    raise ValueError(f"Unknown uploaded data kind: {kind}")


def safe_metric(value, style="number"):
    """Format a scalar without exposing NaN or infinity in the UI."""
    if value is None or not np.isfinite(value):
        return "N/A"
    if style == "percent":
        return f"{value:.2%}"
    if style == "integer":
        return f"{int(value):,}"
    return f"{value:.3f}"


def result_metrics(result):
    """Build the app summary exclusively from canonical package metrics/outputs."""
    validate_result(result)
    r = result.returns
    metrics = performance_metrics(r.net, r.benchmark, r.turnover, r.cost)
    ic = signal_ic(result)
    metrics.update(ic_metrics(ic.ic))
    metrics.update(
        {
            "average_absolute_active_weight": float(
                result.active_weights.abs().to_numpy().mean()
            ),
            "average_active_share": float(
                0.5 * result.active_weights.abs().sum(axis=1).mean()
            ),
            "maximum_position": float(result.weights.to_numpy().max()),
            "average_estimated_tracking_error": float(
                result.optimization.estimated_tracking_error.mean()
            ),
            "rebalances": len(result.optimization),
            "evaluation_days": len(r),
            "benchmark_relative_cumulative_result": float(
                (1 + r.net).prod() / (1 + r.benchmark).prod() - 1
            ),
        }
    )
    return metrics


def performance_tables(result):
    r = result.returns
    wealth = (1 + r[["gross", "net", "benchmark"]]).cumprod()
    wealth.columns = ["Gross", "Net", "Benchmark"]
    relative = (wealth["Net"] / wealth["Benchmark"] - 1).rename(
        "Net portfolio / benchmark wealth - 1"
    )
    drawdowns = pd.concat(
        {
            "Gross": drawdown(r.gross),
            "Net": drawdown(r.net),
            "Benchmark": drawdown(r.benchmark),
        },
        axis=1,
    )
    return wealth, relative, drawdowns


def latest_holdings(result):
    latest = result.weights.index[-1]
    table = pd.DataFrame(
        {
            "Portfolio": result.weights.loc[latest],
            "Benchmark": result.benchmark_weights.loc[latest],
            "Active": result.active_weights.loc[latest],
        }
    )
    table = table.rename_axis("Asset")
    return latest, table.sort_values("Active", ascending=False)


def sector_weights(result):
    if result.sectors is None:
        return None
    _, holdings = latest_holdings(result)
    grouped = holdings.assign(Sector=result.sectors).groupby("Sector").sum()
    return grouped.sort_values("Active", ascending=False)


def signal_components(prices, result):
    """Evaluate existing signal functions at the latest rebalance information date."""
    effective_date = result.signal_scores.index[-1]
    information_date = pd.Timestamp(
        result.optimization.loc[effective_date, "information_date"]
    )
    history = prices.loc[:information_date]
    config = result.config
    components = pd.DataFrame(
        {
            "12-1 momentum": preprocess(
                momentum_12_1(history, config.momentum_lookback, config.momentum_skip)
            ),
            "Low volatility": preprocess(
                low_volatility(history, config.volatility_lookback)
            ),
            "Short-term reversal": preprocess(
                reversal_1m(history, config.reversal_lookback)
            ),
            "Composite": result.signal_scores.loc[effective_date],
        }
    )
    components = components.rename_axis("Asset")
    return (
        effective_date,
        information_date,
        components.sort_values("Composite", ascending=False),
    )


def risk_cost_tables(result):
    r = result.returns
    risk = pd.DataFrame(
        {
            "63-day realized tracking error": r.active.rolling(63).std() * np.sqrt(252),
            "Active share": 0.5 * result.active_weights.abs().sum(axis=1),
        }
    )
    trading = pd.DataFrame(
        {
            "One-way turnover": r.turnover,
            "Transaction cost": r.cost,
            "Cumulative cost fraction": r.cost.cumsum(),
            "Compounded gross minus net wealth": (1 + r.gross).cumprod()
            - (1 + r.net).cumprod(),
        }
    )
    return risk, trading


def attribution_tables(result):
    security = security_attribution(result)
    aggregate_security = (
        security.sum()
        .sort_values(ascending=False)
        .rename("Aggregate arithmetic active contribution")
    )
    if result.sectors is None:
        return aggregate_security, None, None
    sector = sector_attribution(result)
    effects = sector[["allocation", "selection", "interaction"]]
    aggregate_sector = effects.groupby(level="sector").sum()
    daily_total = effects.sum(axis=1).groupby(level="date").sum()
    error = float((daily_total - result.returns.gross_active).abs().max())
    return aggregate_security, aggregate_sector, error


def attribution_frame(result):
    """Return the canonical daily attribution output used by package reporting."""
    if result.sectors is not None:
        return sector_attribution(result)
    return security_attribution(result)


def frame_csv(frame):
    if isinstance(frame, pd.Series):
        frame = frame.to_frame()
    return frame.to_csv().encode("utf-8")


def summary_json(result, metrics, provenance, runtime_seconds):
    serial = {
        key: (float(value) if np.isfinite(value) else None)
        for key, value in metrics.items()
    }
    payload = {
        "provenance": provenance,
        "evaluation_start": str(result.returns.index[0].date()),
        "evaluation_end": str(result.returns.index[-1].date()),
        "runtime_seconds": runtime_seconds,
        "metrics": serial,
        "configuration": asdict(result.config),
    }
    return (json.dumps(payload, indent=2, allow_nan=False) + "\n").encode("utf-8")
