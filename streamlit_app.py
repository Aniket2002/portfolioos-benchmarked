"""Interactive presentation layer for the PortfolioOS research engine."""

import hashlib
import json
import time

import pandas as pd
import streamlit as st

from portfolioos.app_helpers import (
    attribution_frame,
    attribution_tables,
    frame_csv,
    latest_holdings,
    make_app_config,
    performance_tables,
    read_uploaded_csv,
    result_metrics,
    risk_cost_tables,
    safe_metric,
    sector_weights,
    signal_components,
    summary_json,
)
from portfolioos.attribution import signal_ic
from portfolioos.backtest import run_backtest
from portfolioos.reporting import load_config
from portfolioos.synthetic import synthetic_market

st.set_page_config(
    page_title="PortfolioOS Benchmarked",
    page_icon="📈",
    layout="wide",
)


@st.cache_data(show_spinner=False)
def cached_synthetic_market(seed, assets, years):
    """Cache only the deterministic data fixture, never optimization results."""
    return synthetic_market(seed=seed, assets=assets, years=years)


def input_fingerprint(mode, synthetic, controls, uploads):
    payload = json.dumps(
        {"mode": mode, "synthetic": synthetic, "controls": controls},
        sort_keys=True,
    ).encode()
    for upload in uploads:
        payload += upload.getvalue() if upload is not None else b""
    return hashlib.sha256(payload).hexdigest()


def friendly_error(exc):
    message = str(exc)
    lowered = message.lower()
    if "optimization failed" in lowered or "infeasible" in lowered:
        return (
            "Portfolio optimization was infeasible under the selected constraints. "
            "Increase the turnover or tracking-error limit, or reduce concentration "
            "restrictions."
        )
    if "history" in lowered or "eligible evaluation" in lowered:
        return "There is insufficient valid history for the selected lookbacks."
    if "covariance" in lowered:
        return (
            "The trailing covariance estimate failed. Check the price history and "
            "lookback."
        )
    return message


def download(label, data, filename, mime="text/csv"):
    st.download_button(label, data=data, file_name=filename, mime=mime)


_, base_config = load_config("configs/demo.yaml")

st.title("PortfolioOS Benchmarked")
st.markdown(
    "Benchmark-aware systematic portfolio research with transparent signals, "
    "constrained optimisation, transaction costs, walk-forward testing and attribution."
)
st.warning(
    "This application is an educational quantitative-research interface. The default "
    "case study uses synthetic data and is not evidence of real-world alpha or "
    "investment performance."
)

with st.sidebar:
    st.header("Research controls")
    mode = st.radio("Data mode", ["Synthetic demo", "User data"])
    seed, assets, years = 42, 20, 3
    prices_upload = benchmark_upload = metadata_upload = None
    if mode == "Synthetic demo":
        st.caption("SYNTHETIC DEMO · deterministic, offline, no embedded alpha")
        seed = st.number_input("Seed", min_value=0, max_value=1_000_000, value=42)
        assets = st.slider("Number of assets", 15, 60, 20)
        years = st.slider("Years of history", 2, 10, 3)
    else:
        st.caption("CSV inputs stay in memory and are not written to disk.")
        prices_upload = st.file_uploader("Price data (required)", type="csv")
        benchmark_upload = st.file_uploader("Benchmark weights (optional)", type="csv")
        metadata_upload = st.file_uploader("Metadata / sectors (optional)", type="csv")

    st.subheader("Signals")
    momentum_weight = st.slider("12-1 momentum weight", -3.0, 3.0, 1.0, 0.1)
    low_volatility_weight = st.slider("Low-volatility weight", -3.0, 3.0, 1.0, 0.1)
    reversal_weight = st.slider("Short-term reversal weight", -3.0, 3.0, 0.5, 0.1)
    st.caption("These are signal-combination weights, not calibrated expected returns.")

    st.subheader("Risk model")
    covariance_lookback = st.slider("Covariance lookback", 40, 504, 252, 21)
    tracking_error_enabled = st.checkbox("Apply tracking-error cap", value=True)
    max_tracking_error = st.slider("Annual tracking-error cap", 0.01, 0.30, 0.08, 0.01)

    st.subheader("Portfolio constraints")
    max_position_weight = st.slider("Maximum position weight", 0.02, 0.50, 0.08, 0.01)
    sector_cap_enabled = st.checkbox("Apply sector active-weight cap", value=True)
    max_sector_active_weight = st.slider(
        "Maximum sector active weight", 0.01, 0.50, 0.10, 0.01
    )
    turnover_cap_enabled = st.checkbox("Apply turnover cap", value=True)
    max_turnover = st.slider("One-way turnover cap", 0.05, 1.00, 0.30, 0.05)
    if mode == "User data" and metadata_upload is None:
        st.caption("The sector cap is disabled unless sector metadata is supplied.")

    st.subheader("Optimization")
    risk_aversion = st.number_input("Risk-aversion coefficient", 0.0, 1000.0, 10.0, 1.0)
    turnover_penalty = st.number_input(
        "Turnover-penalty coefficient", 0.0, 10.0, 0.1, 0.05
    )
    st.caption("These coefficients express modelling trade-offs.")

    st.subheader("Costs & backtest")
    transaction_cost_bps = st.number_input(
        "Transaction cost (basis points)", 0.0, 100.0, 10.0, 1.0
    )
    rebalance_frequency = st.selectbox(
        "Rebalance frequency", ["monthly", "weekly", "daily"]
    )
    debug = st.checkbox("Developer debug details", value=False)

controls = {
    "momentum_weight": momentum_weight,
    "low_volatility_weight": low_volatility_weight,
    "reversal_weight": reversal_weight,
    "covariance_lookback": covariance_lookback,
    "tracking_error_enabled": tracking_error_enabled,
    "max_tracking_error": max_tracking_error,
    "max_position_weight": max_position_weight,
    "sector_cap_enabled": sector_cap_enabled,
    "max_sector_active_weight": max_sector_active_weight,
    "turnover_cap_enabled": turnover_cap_enabled,
    "max_turnover": max_turnover,
    "risk_aversion": risk_aversion,
    "turnover_penalty": turnover_penalty,
    "transaction_cost_bps": transaction_cost_bps,
    "rebalance_frequency": rebalance_frequency,
}
synthetic_settings = {"seed": seed, "assets": assets, "years": years}
fingerprint = input_fingerprint(
    mode,
    synthetic_settings if mode == "Synthetic demo" else {},
    controls,
    (prices_upload, benchmark_upload, metadata_upload),
)

run_requested = st.button("Run research case study", type="primary")
if run_requested:
    if mode == "User data" and prices_upload is None:
        st.error("Upload a price CSV to run the user-data case study.")
    else:
        try:
            with st.spinner("Running the walk-forward research case study..."):
                started = time.perf_counter()
                if mode == "Synthetic demo":
                    prices, metadata = cached_synthetic_market(**synthetic_settings)
                    benchmark = None
                else:
                    prices = read_uploaded_csv(prices_upload, "prices")
                    benchmark = (
                        read_uploaded_csv(benchmark_upload, "benchmark")
                        if benchmark_upload is not None
                        else None
                    )
                    metadata = (
                        read_uploaded_csv(metadata_upload, "metadata")
                        if metadata_upload is not None
                        else None
                    )
                config = make_app_config(base_config, controls, metadata is not None)
                result = run_backtest(
                    prices,
                    benchmark_weights=benchmark,
                    metadata=metadata,
                    config=config,
                )
                metrics = result_metrics(result)
                runtime = time.perf_counter() - started
            st.session_state["research_run"] = {
                "fingerprint": fingerprint,
                "mode": mode,
                "prices": prices,
                "result": result,
                "metrics": metrics,
                "runtime": runtime,
            }
        except Exception as exc:  # Streamlit boundary: engine errors become UI errors.
            st.error(friendly_error(exc))
            if debug:
                st.exception(exc)

run = st.session_state.get("research_run")
if run is not None and run["fingerprint"] != fingerprint:
    st.info("Controls changed. Run the case study again to view matching results.")
    run = None

if run is None:
    st.caption("Choose the research inputs and run the case study to display results.")
    st.stop()

result = run["result"]
prices = run["prices"]
metrics = run["metrics"]
provenance = (
    "SYNTHETIC DEMO · Synthetic research demonstration"
    if run["mode"] == "Synthetic demo"
    else "USER-SUPPLIED DATA · Research output"
)
st.subheader(provenance)
st.caption(
    f"Evaluation: {result.returns.index[0].date()} to "
    f"{result.returns.index[-1].date()} · Runtime: {run['runtime']:.2f}s"
)

kpi_specs = [
    ("CAGR", "cagr", "percent"),
    ("Annualized volatility", "annualized_volatility", "percent"),
    ("Sharpe ratio", "sharpe", "number"),
    ("Maximum drawdown", "maximum_drawdown", "percent"),
    ("Tracking error", "tracking_error", "percent"),
    ("Information ratio", "information_ratio", "number"),
]
for column, (label, key, style) in zip(st.columns(6), kpi_specs):
    column.metric(label, safe_metric(metrics.get(key), style))

secondary = [
    ("Avg one-way turnover", result.returns.turnover.mean(), "percent"),
    ("Compounded cost drag", metrics.get("compounded_cost_drag"), "percent"),
    ("Average active share", metrics.get("average_active_share"), "percent"),
    ("Rebalances", metrics.get("rebalances"), "integer"),
    ("Evaluation days", metrics.get("evaluation_days"), "integer"),
    (
        "Benchmark-relative result",
        metrics.get("benchmark_relative_cumulative_result"),
        "percent",
    ),
]
for column, (label, value, style) in zip(st.columns(6), secondary):
    column.metric(label, safe_metric(value, style))

performance_tab, portfolio_tab, signals_tab, risk_tab, attribution_tab, method_tab = (
    st.tabs(
        [
            "Performance",
            "Portfolio",
            "Signals",
            "Risk & Costs",
            "Attribution",
            "Methodology",
        ]
    )
)

with performance_tab:
    st.caption(provenance)
    wealth, relative, drawdowns = performance_tables(result)
    st.markdown("#### Growth of $1")
    st.line_chart(wealth)
    st.markdown("#### Net benchmark-relative wealth")
    st.line_chart(relative)
    st.markdown("#### Drawdown")
    st.line_chart(drawdowns)
    summary = pd.Series(metrics, name="Value").rename_axis("Metric").to_frame()
    st.dataframe(summary, width="stretch")

with portfolio_tab:
    st.caption(provenance)
    st.info(
        "Portfolio constraints are enforced at rebalance dates. Holdings may drift "
        "beyond target limits between rebalances."
    )
    latest_date, holdings = latest_holdings(result)
    st.markdown(f"#### Holdings on {latest_date.date()}")
    st.dataframe(holdings.style.format("{:.2%}"), width="stretch")
    left, right = st.columns(2)
    left.markdown("#### Top overweight positions")
    left.dataframe(holdings.head(10).style.format("{:.2%}"))
    right.markdown("#### Top underweight positions")
    right.dataframe(holdings.tail(10).sort_values("Active").style.format("{:.2%}"))
    sectors = sector_weights(result)
    if sectors is not None:
        st.markdown("#### Latest sector weights")
        st.dataframe(sectors.style.format("{:.2%}"), width="stretch")
    else:
        st.info("No sector metadata was supplied; sector weights are unavailable.")
    behavior = pd.DataFrame(
        {
            "Maximum position": result.weights.max(axis=1),
            "Largest absolute active weight": result.active_weights.abs().max(axis=1),
            "Active share": 0.5 * result.active_weights.abs().sum(axis=1),
        }
    )
    st.markdown("#### Concentration through time")
    st.line_chart(behavior)
    st.markdown("#### Estimated tracking error at rebalances")
    st.line_chart(result.optimization[["estimated_tracking_error"]])

with signals_tab:
    st.caption(provenance)
    effective, information, components = signal_components(prices, result)
    st.caption(
        f"Latest rebalance: {effective.date()} · "
        f"Information through: {information.date()}"
    )
    st.markdown("#### Latest composite score distribution")
    st.bar_chart(components["Composite"].sort_values())
    st.markdown("#### Latest signal rankings and standardized components")
    st.dataframe(components, width="stretch")
    ic = signal_ic(result)
    st.markdown("#### Forward signal IC through time")
    st.line_chart(ic[["ic"]])
    ic_cols = st.columns(3)
    ic_cols[0].metric("Mean IC", safe_metric(metrics.get("mean_ic")))
    ic_cols[1].metric("Median IC", safe_metric(metrics.get("median_ic")))
    ic_cols[2].metric(
        "Positive-IC fraction",
        safe_metric(metrics.get("positive_ic_fraction"), "percent"),
    )
    st.info(
        "Signal IC is calculated after portfolio simulation and is not used by the "
        "optimizer."
    )

with risk_tab:
    st.caption(provenance)
    risk, trading = risk_cost_tables(result)
    st.markdown("#### Estimated tracking error at rebalance dates")
    st.line_chart(result.optimization[["estimated_tracking_error"]])
    st.markdown("#### Realized risk and active share")
    st.line_chart(risk)
    st.markdown("#### Turnover and transaction costs")
    st.line_chart(trading)
    st.code(
        "one-way turnover = 0.5 × Σ |target − pre-trade|\n"
        "cost = turnover × transaction_cost_bps / 10,000"
    )

with attribution_tab:
    st.caption(provenance)
    security, sector, reconciliation_error = attribution_tables(result)
    positive, negative = st.columns(2)
    positive.markdown("#### Top positive security contributors")
    positive.dataframe(security.head(10).to_frame())
    negative.markdown("#### Top negative security contributors")
    negative.dataframe(security.tail(10).sort_values().to_frame())
    if sector is None:
        st.info("No sector metadata was supplied; sector attribution is unavailable.")
    else:
        st.markdown("#### Aggregate daily arithmetic Brinson-Fachler effects")
        st.dataframe(sector, width="stretch")
        st.caption(f"Attribution reconciliation error: {reconciliation_error:.3e}")
    st.caption(
        "Security and sector effects are daily arithmetic gross attribution. Summed "
        "effects are an arithmetic summary, not compounded multi-period attribution; "
        "transaction costs bridge gross to net active return."
    )

with method_tab:
    st.caption(provenance)
    st.markdown(
        """
#### Research question
Can transparent cross-sectional signals retain useful benchmark-relative performance
after active-risk constraints, turnover limits and transaction costs are imposed?

#### Signals and timing
The model combines 12-1 momentum, low volatility and short-term reversal. Weights
earning return at *t* use information available only through *t−1*. Signal weights
are dimensionless preferences rather than calibrated expected returns.

#### Covariance and optimization
Risk uses a trailing Ledoit-Wolf covariance estimate. The optimizer solves:

```text
maximize score' w
         - lambda_risk (w-wb)' Sigma (w-wb)
         - lambda_turnover ||w-wpretrade||_1
```

subject to the configured long-only, fully invested, position, tracking-error,
sector-active and one-way turnover constraints. Risk and turnover coefficients are
modelling trade-offs.

#### Benchmark, costs and attribution
Supplied benchmark snapshots become effective on the next observed trading date.
Without snapshots, the comparison is an illustrative equal-weight benchmark reset at
strategy rebalances. One-way turnover is half the absolute target-to-pre-trade change;
linear cost is turnover times basis points divided by 10,000. Security active
contribution and daily arithmetic Brinson-Fachler sector effects reconcile to gross
active return.

#### Limitations
- Fixed universe and synthetic default data.
- Idealized previous-close execution and simplified linear transaction costs.
- Static sector metadata.
- Constraints apply at rebalances; holdings can drift afterward.
- Daily arithmetic attribution is not compounded multi-period attribution.
- No claim of real-world alpha or investment performance.
"""
    )

st.markdown("### Download research outputs")
dcols = st.columns(6)
with dcols[0]:
    download(
        "Summary JSON",
        summary_json(result, metrics, provenance, run["runtime"]),
        "summary.json",
        "application/json",
    )
with dcols[1]:
    download("Portfolio weights CSV", frame_csv(result.weights), "weights.csv")
with dcols[2]:
    download(
        "Active weights CSV", frame_csv(result.active_weights), "active_weights.csv"
    )
with dcols[3]:
    download("Returns CSV", frame_csv(result.returns), "returns.csv")
with dcols[4]:
    download("Signal scores CSV", frame_csv(result.signal_scores), "signal_scores.csv")
with dcols[5]:
    download(
        "Attribution CSV",
        frame_csv(attribution_frame(result)),
        "attribution.csv",
    )
