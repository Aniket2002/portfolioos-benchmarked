"""Build research tables, figures and manuscript from executed evidence only.

This script does not optimize, tune or rerun any portfolio. Full-panel access for
the reporting-only regime timeline is allowed only after the holdout ledger exists.
"""

# Narrative strings and TeX table rows retain their publication source lines.
# ruff: noqa: E501

import argparse
import json
from os.path import relpath
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from portfolioos.empirical import write_json
from portfolioos.historical import file_hash, load_historical_bundle
from portfolioos.metrics import drawdown
from portfolioos.policy import policy_history
from portfolioos.regimes import policy_regimes
from portfolioos.uncertainty import block_interval

PERIODS = ["development", "validation", "holdout"]
STRATEGIES = [
    "policy",
    "equal_weight",
    "inverse_volatility",
    "fixed_risk",
    "regime_aware",
]
LABELS = {
    "policy": "Policy (net)",
    "equal_weight": "Equal weight",
    "inverse_volatility": "Inverse volatility",
    "fixed_risk": "Fixed risk",
    "regime_aware": "Regime aware",
}
SCENARIO_LABELS = {
    **LABELS,
    "te_4pct": "TE 4%",
    "te_8pct": "TE 8%",
    "te_12pct": "TE 12%",
    "turnover_10pct": "Turnover 10%",
    "turnover_30pct": "Turnover 30%",
    "turnover_50pct": "Turnover 50%",
    "cost_0bps": "Cost 0 bps",
    "cost_10bps": "Cost 10 bps",
    "cost_25bps": "Cost 25 bps",
    "cost_40bps": "Cost 40 bps",
    "without_momentum_12_1": "No momentum",
    "without_low_volatility": "No low-volatility",
    "without_reversal_1m": "No reversal",
    "sample_covariance": "Sample covariance",
    "lag_3": "Three-session lag",
    "weekly": "Weekly rebalance",
}


def tex(value):
    mapping = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
    }
    return "".join(mapping.get(char, char) for char in str(value))


def number(value, percent=False):
    if value is None or not np.isfinite(value):
        return "undefined"
    return f"{value * 100:.2f}%" if percent else f"{value:.3f}"


def markdown_table(columns, rows):
    return "\n".join(
        ["| " + " | ".join(columns) + " |", "|" + "---|" * len(columns)]
        + ["| " + " | ".join(map(str, row)) + " |" for row in rows]
    )


def frame(root, period, scenario):
    return pd.read_csv(
        root / period / scenario / "returns.csv", index_col=0, parse_dates=True
    )


def save_figure(fig, path, rect=None):
    fig.tight_layout(rect=rect)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def load_review(directory, root):
    directory = Path(directory)
    declaration = json.loads((directory / "diagnostic_protocol.json").read_text())
    if declaration["source_lock_sha256"] != file_hash(
        root / "final_protocol_lock.json"
    ):
        raise ValueError("Review diagnostics refer to a different frozen evaluation")
    hashes = json.loads((directory / "source_evidence_hashes.json").read_text())
    if any(file_hash(root / name) != digest for name, digest in hashes.items()):
        raise ValueError("Original evaluation evidence changed after review")
    return {
        "attribution": pd.read_csv(directory / "asset_class_attribution.csv"),
        "securities": pd.read_csv(directory / "security_attribution_summary.csv"),
        "activity": pd.read_csv(directory / "cap_activity.csv"),
        "table5": json.loads((directory / "table5_audit.json").read_text()),
        "tighter": json.loads((directory / "tighter_cap_results.json").read_text()),
    }


def review_markdown(review):
    attribution = review["attribution"].pivot(
        index="component", columns="period", values="annualized_active_contribution"
    )
    lines = [
        "Arithmetic active contributions, in percentage points/year. Each entry is "
        "252 times the daily mean of sum_i (w_i-b_i) r_i for that class; costs bridge gross to net.",
        "",
        markdown_table(
            ["Component", *[p.title() for p in PERIODS]],
            [
                [k, *[number(attribution.loc[k, p] * 100) for p in PERIODS]]
                for k in attribution.index
            ],
        ),
        "",
        "The 8% and 12% caps bind at zero recorded decisions. The original 5% "
        "high-state formation cap (4.9% after reserve) binds at 2/7, 5/21 and 2/10 "
        "high-state rebalances. The risk penalty (lambda=10), together with other "
        "constraints, already limits active risk. Realized TE is not a cap-activity test.",
        "",
        "The comparison has only 38 high-state decision dates (7, 21 and 10), "
        "including 23 binding decisions at 3%. It is underpowered for a general "
        "regime-effect claim; narrow paired intervals on the original comparison "
        "reflect similar paths, not many independent regime decisions.",
        "",
        "The added 8%/3% scenario is post-holdout exploratory evidence, retaining "
        "the same objective, calendar, information lag and reserves. The high-state "
        "formation cap is 2.9%. It is not a replacement primary model.",
        "",
    ]
    for row in review["tighter"]:
        if row["status"] != "success":
            lines += [f"{row['period']}: failed, {row['error']}.", ""]
            continue
        m, interval = row["metrics"], row["paired_vs_fixed"]
        a = review["activity"]
        a = a[(a.period == row["period"]) & (a.scenario == row["scenario"])].iloc[0]
        lines += [
            f"{row['period'].title()}: high-state binding {a.high_binding_rebalances}/"
            f"{a.high_rebalances}; net CAGR {number(m['cagr'], True)}, active "
            f"{number(m['annualized_arithmetic_active_return'], True)}, realized TE "
            f"{number(m['tracking_error'], True)}; paired difference vs fixed "
            f"{number(interval['estimate'], True)} "
            f"[{number(interval['lower'], True)}, {number(interval['upper'], True)}].",
            "",
        ]
    lines += [
        "The holdout gain is largely long high-yield credit and gold in 2023–September "
        "2026. HYG and GLD have zero policy weight and together contribute +3.28 "
        "percentage points/year against +1.23 net. GLD's "
        f"{next(p['cumulative_adjusted_return'] for p in review['positions'] if p['asset'] == 'GLD') * 100:.1f}% "
        "cumulative adjusted return over the executed holdout sessions is a likely "
        "window-specific driver of its contribution; HYG "
        "has the larger arithmetic contribution. IC ranks all ten assets while "
        "positive P&L is concentrated in those two holdings.",
        "",
        "This compounds all 939 holdout sessions, including January 3, 2023's "
        "return from the December 30, 2022 close and ending September 30, 2026. "
        "The normalized endpoints are recorded in holdout_position_endpoints.csv, "
        "with dates and fingerprints in holdout_position_context.json. The public "
        "verifier checks endpoint arithmetic; its optional --bundle check "
        "recomputes the return from the original adjusted series.",
        "",
        "Weekly has the highest declared holdout net CAGR (14.99%, +2.38% arithmetic "
        "active), but both earlier paths fail execution checks. A single completed "
        "holdout window cannot validate a repeatable weekly advantage.",
        "",
        "The low-volatility-omission TE coincidence is rounding, not a copied path. "
        + "; ".join(
            f"{r['period']}: {r['tracking_error'] * 100:.9f}%" for r in review["table5"]
        )
        + ". Both independently rerun pre-holdout paths match the saved returns.",
        "",
        "Verify public table arithmetic without provider data: "
        "python scripts/verify_public_empirical_tables.py --diagnostics results/empirical_review_response",
    ]
    return "\n".join(lines)


def review_tex(review):
    attribution = review["attribution"].pivot(
        index="component", columns="period", values="annualized_active_contribution"
    )
    labels = {
        "equity": "Equity",
        "fixed_income": "Fixed income",
        "gold": "Gold",
        "real_estate": "Real estate",
        "costs": "Trading costs",
    }
    parts = [
        r"\begin{center}\begin{minipage}{\textwidth}\small",
        r"\captionof{table}{Fixed-risk arithmetic active-return attribution.}\label{tab-attribution}",
        r"\begin{tabular*}{\textwidth}{@{\extracolsep{\fill}}lrrr@{}}\toprule",
        r"Component & Development & Validation & Holdout\\\midrule",
    ]
    for component in labels:
        cells = [labels[component]] + [
            number(attribution.loc[component, period] * 100) for period in PERIODS
        ]
        parts.append(" & ".join(cells) + r"\\")
    parts.append(
        "Net active return & "
        + " & ".join(number(attribution[p].sum() * 100) for p in PERIODS)
        + r"\\"
    )
    parts += [
        r"\bottomrule\end{tabular*}\par\vspace{4pt}\footnotesize",
        r"Notes: Percentage points/year, computed as $252$ times mean daily "
        r"$\sum_{i\in g}(w_{i,t}-b_{i,t})r_{i,t}$. Costs are a separate negative "
        r"component. These are additive arithmetic contributions, not a CAGR decomposition.",
        r"\end{minipage}\end{center}",
    ]
    holdout = review["attribution"].query("period == 'holdout'").set_index("component")
    assets = review["securities"].query("period == 'holdout'").set_index("asset")
    positions = {row["asset"]: row for row in review["positions"]}
    parts += [
        tex(
            f"In holdout, equity exposure averages {abs(holdout.loc['equity', 'mean_active_weight']) * 100:.2f} "
            f"percentage points below the policy and detracts "
            f"{abs(attribution.loc['equity', 'holdout']) * 100:.2f} percentage points/year. "
            f"SPY and IWM contribute {assets.loc['SPY', 'annualized_active_contribution'] * 100:.2f} "
            f"and {assets.loc['IWM', 'annualized_active_contribution'] * 100:.2f}."
        ),
        "",
        tex(
            f"The holdout gain is largely long high-yield credit and gold during "
            f"2023--September 2026. The policy assigns zero weight to both HYG and "
            f"GLD; their contributions are "
            f"+{positions['HYG']['annualized_active_contribution'] * 100:.2f} and "
            f"+{positions['GLD']['annualized_active_contribution'] * 100:.2f} "
            f"percentage points/year, totaling "
            f"+{sum(p['annualized_active_contribution'] for p in positions.values()) * 100:.2f} "
            f"against {attribution['holdout'].sum() * 100:.2f} net active return. "
            f"Losses elsewhere and trading costs absorb the difference. GLD's "
            f"{positions['GLD']['cumulative_adjusted_return'] * 100:.1f}% cumulative "
            f"adjusted return over the executed holdout sessions is a likely driver of its "
            f"contribution; HYG is the larger arithmetic contributor."
        ),
        r"\footnote{Compounds all 939 daily returns dated January 3, 2023--September "
        r"30, 2026, including the first return from the December 30, 2022 close; "
        r"see the endpoint ledger in Appendix~\ref{app-reproduction}.}",
        "",
        "Mean forward IC ranks all ten assets, whereas the positive active P\\&L "
        "is concentrated in these two positions. That concentration, together "
        "with the different weighting and horizons of rank IC and daily "
        "holdings-based returns, explains why negative average IC can coexist "
        "with positive active return. These window-specific credit and gold "
        "exposures do not establish broad predictive skill or risk-adjusted alpha.",
    ]
    regime = [
        r"\subsection{Constraint activity and a binding-cap diagnostic}",
        r"The original regime comparison is partly mechanical. Fixed-risk realized "
        r"TE is about 2.8\%--3.7\%, below the 5\% high-state mandate, although "
        r"realized TE alone cannot determine whether an ex-ante limit binds. "
        r"At formation, after the 0.1-percentage-point reserve, the 4.9\% cap "
        r"binds at only 2/7, 5/21 and 2/10 high-state rebalances in development, "
        r"validation and holdout. The budgets differ only on high-state rebalance "
        r"dates, and the risk penalty already limits many desired deviations.",
        r"Binding means estimated formation TE is within $10^{-5}$ of the "
        r"formation cap (0.1 basis point of annual TE); this is a numerical activity "
        r"diagnostic, not a dual-value or realized-risk test.",
        r"We therefore add one separately labelled post-holdout diagnostic with "
        r"8\% normal and 3\% high-state mandates, keeping all other settings fixed. "
        r"The 2.9\% high-state formation cap binds appreciably more often. "
        r"This experiment was requested after holdout review and is exploratory; "
        r"it does not alter the frozen specification or its reported performance.",
        r"\begin{center}\begin{minipage}{\textwidth}\small",
        r"\captionof{table}{Post-holdout 8\%/3\% regime diagnostic.}\label{tab-tight-regime}",
        r"\begin{tabular*}{\textwidth}{@{\extracolsep{\fill}}lrrrrr@{}}\toprule",
        r"Period & High binding & Net CAGR & Active & TE & $\Delta$ vs fixed\\\midrule",
    ]
    for row in review["tighter"]:
        if row["status"] != "success":
            regime.append(tex(f"{row['period']}: {row['error']}"))
            continue
        a = review["activity"]
        a = a[(a.period == row["period"]) & (a.scenario == row["scenario"])].iloc[0]
        m = row["metrics"]
        cells = [
            row["period"].title(),
            f"{a.high_binding_rebalances}/{a.high_rebalances}",
            number(m["cagr"] * 100),
            number(m["annualized_arithmetic_active_return"] * 100),
            number(m["tracking_error"] * 100),
            number(row["paired_vs_fixed"]["estimate"] * 100),
        ]
        regime.append(" & ".join(cells) + r"\\")
    regime += [
        r"\bottomrule\end{tabular*}\par\vspace{4pt}\footnotesize",
        r"Notes: Returns and TE are percentages. High binding is binding/high-state "
        r"rebalance counts. $\Delta$ is annualized mean daily net-return difference "
        r"from fixed 8\% risk, in percentage points/year.",
        r"\end{minipage}\end{center}",
    ]
    for row in review["tighter"]:
        if row["status"] == "success":
            ci = row["paired_vs_fixed"]
            regime.append(
                tex(
                    f"{row['period'].title()} paired 95% circular-block interval for "
                    f"the difference: [{ci['lower'] * 100:.3f}, {ci['upper'] * 100:.3f}] "
                    "percentage points/year."
                )
            )
    regime.append(
        "All paired intervals include zero. A binding cap changes allocations and "
        "reduces realized TE, but this diagnostic does not establish a return "
        "benefit from the classifier."
    )
    tighter_activity = review["activity"].query("scenario == 'regime_high_3pct'")
    regime.append("")
    regime.append(
        tex(
            f"Only {int(tighter_activity.high_rebalances.sum())} high-state decision "
            f"dates distinguish budgets (7, 21 and 10; "
            f"{int(tighter_activity.high_binding_rebalances.sum())} binding at 3%). "
            "This regime test is underpowered: the narrow original paired "
            "intervals reflect similar return paths and few decisions, not "
            "strong evidence about a general regime effect."
        )
    )
    table_check = (
        r"The two low-volatility-omission TE entries in Table~\ref{allresults} "
        r"both round to 4.989\%. Recomputing from distinct daily return ledgers gives "
        + " and ".join(
            f"{r['tracking_error'] * 100:.9f}\\% ({r['period']})"
            for r in review["table5"]
        )
        + ". Independent pre-holdout reruns reproduce both paths within solver "
        "tolerances; this is a rounding coincidence, not a copied value."
    )
    return "\n".join(parts), "\n".join(regime), table_check


def build(root, bundle, manuscript, diagnostics=None):
    root = Path(root)
    review = load_review(diagnostics, root) if diagnostics else None
    if not (root / "holdout_access.json").exists():
        raise ValueError("Report requires the recorded final holdout evaluation")
    evaluations = {
        period: json.loads((root / period / "evaluation.json").read_text())
        for period in PERIODS
    }
    lock = json.loads((root / "final_protocol_lock.json").read_text())
    protocol = lock["protocol"]
    quality = json.loads((root / "data_quality.json").read_text())
    if quality != lock["quality"]:
        raise ValueError("Data quality differs from the final freeze")
    rows = {
        period: {row["scenario"]: row for row in evaluation["scenarios"]}
        for period, evaluation in evaluations.items()
    }
    figures = root / "figures"
    figures.mkdir(exist_ok=True)
    plt.rcParams.update({"font.size": 12, "axes.grid": True, "grid.alpha": 0.2})

    for name, mode in [("wealth", "wealth"), ("drawdowns", "drawdown")]:
        fig, axes = plt.subplots(1, 3, figsize=(10, 4))
        for ax, period in zip(axes, PERIODS):
            for scenario in STRATEGIES:
                if rows[period][scenario]["status"] != "success":
                    continue
                r = frame(root, period, scenario)
                series = (
                    (1 + r.net).cumprod() if mode == "wealth" else drawdown(r.net) * 100
                )
                ax.plot(
                    series.index,
                    series,
                    label=LABELS[scenario],
                    linewidth=1.2,
                    linestyle="--" if scenario == "fixed_risk" else "-",
                    zorder=4 if scenario == "fixed_risk" else 2,
                )
            benchmark = frame(root, period, "policy").benchmark
            series = (
                (1 + benchmark).cumprod()
                if mode == "wealth"
                else drawdown(benchmark) * 100
            )
            ax.plot(
                series.index, series, "k--", label="Policy (frictionless)", linewidth=1
            )
            ax.set_title(period.title())
            ax.tick_params(axis="x", rotation=30)
            ax.set_ylabel(
                "Wealth (initial NAV = 1)" if mode == "wealth" else "Drawdown (%)"
            )
        axes[-1].legend(fontsize=9)
        save_figure(fig, figures / f"{name}.png")

    for name, group, cap, label in [
        (
            "te_frontier",
            "A_tracking_error",
            "max_tracking_error",
            "Declared TE cap (%)",
        ),
        (
            "turnover_frontier",
            "B_turnover",
            "max_turnover",
            "Declared one-way turnover cap (%)",
        ),
    ]:
        fig, axes = plt.subplots(1, 2, figsize=(9, 3.5))
        for period in PERIODS:
            selected = [rows[period][x] for x in protocol["experiment_groups"][group]]
            selected = [x for x in selected if x["status"] == "success"]
            x = [100 * r["configuration"]["optimizer"][cap] for r in selected]
            y = [r["metrics"]["average_signal_capture"] for r in selected]
            risk = [100 * r["metrics"]["tracking_error"] for r in selected]
            axes[0].plot(x, y, "o-", label=period.title())
            axes[1].plot(x, risk, "o-", label=period.title())
        for ax in axes:
            ax.set_xlabel(label)
        handles, labels = axes[0].get_legend_handles_labels()
        fig.legend(handles, labels, loc="upper center", ncol=3, frameon=False)
        axes[0].set_ylabel("Average signal capture")
        axes[1].set_ylabel("Realized net tracking error (%)")
        save_figure(fig, figures / f"{name}.png", rect=(0, 0, 1, 0.86))

    fig, ax = plt.subplots(figsize=(7, 3.5))
    for period in PERIODS:
        selected = [rows[period][x] for x in protocol["experiment_groups"]["C_costs"]]
        selected = [x for x in selected if x["status"] == "success"]
        ax.plot(
            [x["configuration"]["transaction_cost_bps"] for x in selected],
            [x["metrics"]["cagr"] * 100 for x in selected],
            "o-",
            label=period.title(),
        )
    ax.set_xlabel("Cost per unit of one-way turnover (bps)")
    ax.set_ylabel("Net CAGR (%)")
    fig.legend(
        *ax.get_legend_handles_labels(), loc="upper center", ncol=3, frameon=False
    )
    save_figure(fig, figures / "cost_sensitivity.png", rect=(0, 0, 1, 0.86))

    prices, _ = load_historical_bundle(bundle, protocol["assets"])
    if file_hash(Path(bundle) / "prices.csv") != quality["prices_sha256"]:
        raise ValueError("Reporting dataset differs from final evaluation")
    if review:
        dates = frame(root, "holdout", "fixed_risk").index
        if [str(dates[0].date()), str(dates[-1].date())] != protocol["periods"][
            "holdout"
        ]:
            raise ValueError(
                "Position context requires the exact executed holdout dates"
            )
        baseline = prices.index[prices.index.get_loc(dates[0]) - 1]
        realized = prices.pct_change(fill_method=None).loc[dates]
        securities = (
            review["securities"].query("period == 'holdout'").set_index("asset")
        )
        endpoint_rows = [
            {
                "asset": asset,
                "boundary": boundary,
                "date": str(date.date()),
                "normalized_adjusted_close": float(
                    prices.loc[date, asset] / prices.loc[baseline, asset]
                ),
            }
            for asset in ["HYG", "GLD"]
            for boundary, date in [
                ("baseline", baseline),
                ("first_return", dates[0]),
                ("last_return", dates[-1]),
            ]
        ]
        endpoint_path = Path(diagnostics) / "holdout_position_endpoints.csv"
        pd.DataFrame(endpoint_rows).to_csv(endpoint_path, index=False)
        review["positions"] = [
            {
                "asset": asset,
                "policy_weight": protocol["policy_weights"][asset],
                "cumulative_adjusted_return": float((1 + realized[asset]).prod() - 1),
                "annualized_active_contribution": float(
                    securities.loc[asset, "annualized_active_contribution"]
                ),
                "mean_active_weight": float(
                    securities.loc[asset, "mean_active_weight"]
                ),
                "period": protocol["periods"]["holdout"],
                "baseline_date": str(baseline.date()),
                "return_observations": len(dates),
                "return_convention": "Compound daily adjusted returns on every executed holdout session, including the first return from the preceding session close",
                "endpoints_file": endpoint_path.name,
                "endpoints_sha256": file_hash(endpoint_path),
                "prices_sha256": quality["prices_sha256"],
                "analysis": "reporting-only context from the frozen data vintage",
            }
            for asset in ["HYG", "GLD"]
        ]
        for row in review["positions"]:
            endpoint_return = (
                prices.loc[dates[-1], row["asset"]] / prices.loc[baseline, row["asset"]]
                - 1
            )
            if not np.isclose(
                row["cumulative_adjusted_return"], endpoint_return, atol=1e-12
            ):
                raise ValueError(
                    "Daily compounding and adjusted-price endpoints disagree"
                )
        write_json(
            Path(diagnostics) / "holdout_position_context.json", review["positions"]
        )
    _, _, policy = policy_history(prices, protocol["policy_weights"])
    regimes = policy_regimes(policy.gross.iloc[1:])
    regimes.to_csv(root / "regime_timeline.csv")
    selected = regimes.loc["2011-01-01":]
    fig, ax = plt.subplots(figsize=(10, 3.5))
    ax.plot(
        selected.index,
        selected.volatility * 100,
        label="Trailing 63-session policy volatility",
    )
    ax.plot(
        selected.index,
        selected.threshold * 100,
        label="Strictly earlier expanding 75th percentile",
    )
    high = selected.regime.eq("high")
    ax.fill_between(
        selected.index,
        0,
        selected.volatility * 100,
        where=high,
        alpha=0.2,
        color="crimson",
        label="High volatility (label available after close)",
    )
    ax.set_ylabel("Annualized volatility (%)")
    ax.legend(fontsize=8)
    save_figure(fig, figures / "regime_timeline.png")

    paired = {}
    fig, axes = plt.subplots(1, 3, figsize=(10, 4))
    for ax, period in zip(axes, PERIODS):
        for scenario in ["fixed_risk", "regime_aware"]:
            if rows[period][scenario]["status"] == "success":
                r = frame(root, period, scenario)
                ax.plot(
                    r.index,
                    (1 + r.net).cumprod(),
                    label=LABELS[scenario],
                    linestyle="--" if scenario == "fixed_risk" else "-",
                    zorder=4 if scenario == "fixed_risk" else 2,
                )
        ax.set_title(period.title())
        ax.set_ylabel("Net wealth (initial NAV = 1)")
        ax.tick_params(axis="x", rotation=30)
        ax.legend(fontsize=8)
        if all(
            rows[period][s]["status"] == "success"
            for s in ["fixed_risk", "regime_aware"]
        ):
            delta = (
                frame(root, period, "regime_aware").net
                - frame(root, period, "fixed_risk").net
            )
            bootstrap = protocol["bootstrap"].copy()
            bootstrap.pop("metric")
            paired[period] = block_interval(delta, **bootstrap)
    write_json(root / "paired_regime_uncertainty.json", paired)
    save_figure(fig, figures / "fixed_vs_regime.png")

    fig, ax = plt.subplots(figsize=(10, 4.7))
    comparisons = [
        "fixed_risk",
        "without_momentum_12_1",
        "without_low_volatility",
        "without_reversal_1m",
        "regime_aware",
        "sample_covariance",
        "lag_3",
        "weekly",
    ]
    ticks = np.arange(len(comparisons))
    for i, period in enumerate(PERIODS):
        values = [
            rows[period][x].get("metrics", {}).get("cagr", np.nan) for x in comparisons
        ]
        bars = ax.bar(
            ticks + (i - 1) * 0.25,
            np.array(values) * 100,
            width=0.25,
            label=period.title(),
        )
        if period == "holdout":
            bars[-1].set_hatch("//")
        for j, value in enumerate(values):
            if not np.isfinite(value):
                ax.text(
                    j + (i - 1) * 0.25,
                    0.3,
                    "FAILED",
                    rotation=90,
                    fontsize=11,
                    fontweight="bold",
                    color=bars[j].get_facecolor(),
                    ha="center",
                    va="bottom",
                )
    ax.set_xticks(
        ticks,
        [SCENARIO_LABELS[x] for x in comparisons],
        rotation=20,
        ha="right",
    )
    ax.set_ylabel("Net CAGR (%)")
    fig.legend(
        *ax.get_legend_handles_labels(), loc="upper center", ncol=3, frameon=False
    )
    fig.text(
        0.5,
        0.87,
        "Weekly completes only in holdout; earlier paths fail execution checks.",
        ha="center",
        fontsize=11,
    )
    save_figure(fig, figures / "ablation_robustness.png", rect=(0, 0, 1, 0.82))

    flat = []
    for period in PERIODS:
        for row in rows[period].values():
            flat.append(
                {
                    "period": period,
                    "scenario": row["scenario"],
                    "status": row["status"],
                    "error": row.get("error", ""),
                    **row.get("metrics", {}),
                }
            )
            if row["status"] == "success":
                # Replace the legacy synthetic report's default-benchmark prose
                # with the executed historical policy contract; no model rerun.
                notes = [
                    f"# Historical {period}: {row['scenario']}",
                    "",
                    f"Executed sessions: {row['evaluation_start']} to {row['evaluation_end']} ({row['observations']} observations).",
                    "",
                    "Benchmark: the declared monthly 60/40 policy, reset before the first session return of each month and drifted otherwise. Frictionless policy returns define active metrics; independently cost-adjusted policy returns are also exported. Each period starts endowed in policy holdings.",
                    "",
                    "Decisions use the declared lagged information set; execution-close drift enters turnover and compliance accounting. Closing target fills and additive costs are research approximations.",
                    "",
                    "Ordinary allocation comparisons satisfy their own rules. Active TE, sector, position and turnover mandates apply to optimized strategies at accepted rebalances; subsequent drift and realized risk can exceed target limits.",
                    "",
                    markdown_table(
                        ["Metric", "Value"],
                        [
                            [key, "undefined" if value is None else str(value)]
                            for key, value in row["metrics"].items()
                        ],
                    ),
                    "",
                    "Signal capture is preference expression, not investment skill. IC is evaluated only after construction. No persistent-alpha claim is made. This is independent research, not peer-reviewed research.",
                ]
                (root / period / row["scenario"] / "report.md").write_text(
                    "\n".join(notes) + "\n", encoding="utf-8"
                )
    pd.DataFrame(flat).to_csv(root / "all_performance.csv", index=False)

    status_rows = [
        [scenario]
        + [
            rows[p][scenario]["status"]
            + (
                ": " + rows[p][scenario]["error"]
                if rows[p][scenario]["status"] != "success"
                else ""
            )
            for p in PERIODS
        ]
        for scenario in protocol["scenarios"]
    ]
    status = markdown_table(["Scenario"] + PERIODS, status_rows)
    (root / "experiment_status.md").write_text(status + "\n", encoding="utf-8")
    body = [
        "# Independent historical ETF research",
        "",
        "This is independent research, not peer-reviewed research. No persistent-alpha or causal-regime claim is made.",
        "",
        f"Frozen code commit: `{lock['code_commit']}`. Dataset SHA-256: `{quality['prices_sha256']}`.",
        "",
        "Reader's guide: [paper](../../docs/empirical_manuscript.pdf), [methodology](../../docs/empirical_phase2.md), and [curated research index](../../docs/empirical_research_index.md). Detailed ledgers are retained for audit.",
        "",
        "**Pre-holdout design revision:** after inspecting development/validation execution failures, Codex introduced formation reserves of 2 percentage points for turnover, 1 for sector exposure and 0.1 for annual TE. Execution mandates stayed unchanged. The corrected specification was frozen before the single holdout evaluation; the published results use that corrected specification.",
        "",
        "## Historical periods",
        "",
        "Warmup: 2009-01-02 to 2010-12-31. All evaluation boundaries follow the user proposal; periods start endowed in policy holdings and are evaluated independently.",
        "",
        "## Experiment status",
        "",
        status,
        "",
        "Original zero-reserve failures remain in `results/empirical_phase2`. An interrupted reserve run remains locally in `results/empirical_phase2_final`. Reviewed runs are not replacements for those failure records.",
        "",
        "## Primary performance and uncertainty",
        "",
        "Returns below are net of 10 bps per unit of half-L1 turnover. Benchmark-relative metrics use the frictionless monthly policy; the independently cost-adjusted policy is also reported. Sharpe and Sortino use a declared zero risk-free rate. Percentages are annualized except drawdown and rebalance turnover.",
        "",
    ]
    for period in PERIODS:
        body += [f"### {period.title()}", ""]
        performance = []
        for scenario in STRATEGIES:
            row = rows[period][scenario]
            if row["status"] != "success":
                continue
            m, interval = row["metrics"], row["uncertainty"]
            performance.append(
                [
                    scenario,
                    number(m["gross_cagr"], True),
                    number(m["cagr"], True),
                    number(m["tracking_error"], True),
                    number(m["annualized_arithmetic_active_return"], True),
                    f"[{number(interval['lower'], True)}, {number(interval['upper'], True)}]",
                    number(m["maximum_drawdown"], True),
                ]
            )
        body += [
            markdown_table(
                [
                    "Strategy",
                    "Gross CAGR",
                    "Net CAGR",
                    "Realized TE",
                    "Arithmetic active",
                    "95% block interval",
                    "Max drawdown",
                ],
                performance,
            ),
            "",
        ]
        fixed = rows[period]["fixed_risk"]
        if fixed["status"] == "success":
            m = fixed["metrics"]
            body += [
                f"Fixed-risk signal capture: {number(m['average_signal_capture'])}; valid/excluded observations: {m['valid_capture_observations']}/{m['excluded_capture_observations']}; mean forward Spearman IC: {number(m['mean_ic'])}. Policy frictionless/net CAGR: {number(m['policy_frictionless_cagr'], True)}/{number(m['policy_net_cagr'], True)}.",
                "",
            ]

    body += ["## Constraint sensitivity, ablations and robustness", ""]
    for group, scenarios in protocol["experiment_groups"].items():
        body += [f"### {group}", ""]
        table = []
        for period in PERIODS:
            for scenario in scenarios:
                row = rows[period][scenario]
                m = row.get("metrics", {})
                table.append(
                    [
                        period,
                        scenario,
                        row["status"],
                        number(m.get("cagr"), True),
                        number(m.get("average_signal_capture")),
                        number(m.get("average_estimated_tracking_error"), True),
                        number(m.get("average_rebalance_turnover"), True),
                        number(m.get("average_active_share"), True),
                    ]
                )
        body += [
            markdown_table(
                [
                    "Period",
                    "Scenario",
                    "Status",
                    "Net CAGR",
                    "Capture",
                    "Ex-ante TE",
                    "Rebalance turnover",
                    "Active share",
                ],
                table,
            ),
            "",
        ]

    body += [
        "## Regime comparisons",
        "",
        "Conditional summaries use daily information-date labels, rather than the state held since the last rebalance. The 8%/5% budget changes only at scheduled rebalances. Conditional arithmetic means are descriptive; no discontinuous-subsequence CAGR or causal inference is reported.",
        "",
    ]
    conditional = []
    for period in PERIODS:
        for scenario in ["fixed_risk", "regime_aware"]:
            for row in rows[period][scenario].get("regime_conditional", []):
                conditional.append(
                    [
                        period,
                        scenario,
                        row["regime"],
                        row["observations"],
                        number(row["annualized_mean_active"], True),
                        number(row["realized_tracking_error"], True),
                    ]
                )
    body += [
        markdown_table(
            ["Period", "Strategy", "State", "Days", "Arithmetic active", "Realized TE"],
            conditional,
        ),
        "",
    ]
    for period, interval in paired.items():
        body += [
            f"{period.title()} regime-aware minus fixed-risk annualized arithmetic return: {number(interval['estimate'], True)}, paired 95% block interval [{number(interval['lower'], True)}, {number(interval['upper'], True)}].",
            "",
        ]
    body += [
        "## Interpretation and limitations",
        "",
        "The 8% and 12% TE configurations have essentially identical performance, consistent with largely non-binding TE caps at those settings. Turnover restricted signal expression more than the tested 4%–12% TE range under this model, objective, universe and other constraints. This conditional sensitivity result does not establish that turnover is generally more important than tracking error in portfolio management. Increased signal capture cannot establish better returns. Cost sensitivities clone identical weights, gross returns and turnover; only net accounting changes. Ablation capture has a different signal-specific reference denominator, so cross-ablation ratios are not cardinal measures of relative skill.",
        "",
        "Weekly failures are execution-mandate violations; no full-period performance is assigned to interrupted paths. The safety margins are not execution guarantees. No constraints were relaxed, and no better-performing ablation was promoted to the primary model.",
        "",
        "Circular blocks of 21 sessions, 2,000 resamples and seed 20261008 provide descriptive percentile intervals for annualized arithmetic paired active returns. Approximate within-period stationarity and within-block dependence are assumed. Structural breaks, regime persistence, limited holdout length, a fixed block length and multiple comparisons limit interpretation; no independent-daily significance test is used.",
        "",
        "The fixed surviving ETF universe is retrospectively selected. Prices use a latest retrieval vintage, not contemporaneous adjustment vintages. Yahoo-derived non-institutional data lack independent institutional price validation. The operator offers an open educational API; upstream redistribution rights are not independently verified. Raw data remain outside Git. ETF expenses are embedded in prices; taxes, impact, borrow/funding, share lots and settlement are omitted. Weight-target fills at the previous close are research approximations, not guaranteed executable trades. Zero-rate Sharpe is not excess over historical Treasury-bill returns.",
        "",
        "Source verification exposed incidental issuer quotes/performance panels in the holdout era; the full panel was loaded for ingestion QA. No constructed holdout portfolio performance was used for parameter selection. This is retrospective pseudo-out-of-sample research, not prospective preregistration.",
        "",
        "## Figures",
        "",
    ]
    for path in sorted(figures.glob("*.png")):
        body += [f"![{path.stem}]({path.relative_to(root).as_posix()})", ""]
    body += [
        "## Reproduction",
        "",
        "The original market-data bundle is retained locally and is not publicly available. Exact-input reproduction requires that bundle, the frozen model/protocol and compatible recorded dependencies, with solver tolerances allowed. Fingerprints establish identity but cannot supply the missing inputs. A fresh provider retrieval supports approximate replication using a new labelled vintage; revised historical prices may change results. Public ledgers permit evidence inspection, not independent reconstruction from source prices. See [the reproduction routes and commands](../../docs/empirical_phase2.md#external-reproducibility). `all_performance.csv` contains every computed primary metric. Undefined metrics are null/NaN and are never replaced by zero. Original evaluations are never overwritten.",
    ]
    (root / "report.md").write_text("\n".join(body) + "\n", encoding="utf-8")
    if diagnostics:
        body += [
            "",
            "## Review diagnostics (post-holdout)",
            "",
            review_markdown(review),
            "",
        ]
        (root / "report.md").write_text("\n".join(body) + "\n", encoding="utf-8")
    else:
        review = None
    write_manuscript(manuscript, root, rows, quality, lock, paired, review)


def write_manuscript(destination, root, rows, quality, lock, paired, review=None):
    """All numerical tables below are assembled directly from evaluation ledgers."""
    preamble = r"""\documentclass[11pt,a4paper]{article}
\usepackage[a4paper,margin=1in,headheight=14pt,headsep=16pt]{geometry}
\usepackage[T1]{fontenc}
\usepackage{amsmath}
\usepackage{newtxtext,newtxmath}
\usepackage{microtype,booktabs,longtable,graphicx,xcolor}
\usepackage{setspace,titlesec,fancyhdr,caption,needspace}
\usepackage{hyperref}
\usepackage{xurl}
\AtBeginDocument{\ifdefined\XeTeXtracingfonts\XeTeXtracingfonts=0\fi}
\definecolor{ink}{HTML}{23364A}
\definecolor{muted}{HTML}{59616A}
\hypersetup{
  colorlinks=true,urlcolor=ink,linkcolor=ink,citecolor=ink,
  hypertexnames=false,bookmarksnumbered=true,
  pdftitle={Benchmark-Relative Systematic Portfolio Construction: Evidence from a Ten-ETF Historical Study},
  pdfauthor={Aniket Bhardwaj},
  pdfsubject={Benchmark-relative portfolio construction},
  pdfkeywords={portfolio construction, tracking error, turnover, ETFs, backtesting},
  pdflang={en-US}
}
\urlstyle{same}
\setstretch{1.10}
\setlength{\parindent}{1.2em}
\setlength{\parskip}{3pt}
\setlength{\emergencystretch}{3em}
\setlength{\tabcolsep}{7pt}
\renewcommand{\arraystretch}{1.12}
\captionsetup{font=small,labelfont=bf,labelsep=period,justification=raggedright,singlelinecheck=false,skip=8pt,hypcap=false}
\titleformat{\section}{\large\bfseries}{\thesection}{0.65em}{}
\titleformat{\subsection}{\normalsize\bfseries}{\thesubsection}{0.65em}{}
\titlespacing*{\section}{0pt}{18pt plus 3pt minus 2pt}{7pt}
\titlespacing*{\subsection}{0pt}{12pt plus 2pt minus 1pt}{5pt}
\pagestyle{fancy}
\fancyhf{}
\fancyhead[L]{\footnotesize\color{muted}Benchmark-Relative Portfolio Construction}
\fancyfoot[C]{\small\thepage}
\renewcommand{\headrulewidth}{0pt}
\renewcommand{\footrulewidth}{0pt}
\raggedbottom
\widowpenalty=10000
\clubpenalty=10000
\renewenvironment{abstract}{\par\vspace{12pt}\noindent\textbf{Abstract}\par\vspace{4pt}\small\setstretch{1.08}}{\par\normalsize\vspace{10pt}}
\begin{document}
\begin{titlepage}
\thispagestyle{empty}
\begin{center}
\vspace*{8mm}
{\fontsize{22}{26}\selectfont\bfseries Benchmark-Relative Systematic\\[3pt]Portfolio Construction}\par
\vspace{4mm}
{\large Evidence from a Ten-ETF Historical Study}\par
\vspace{9mm}
{\large Aniket Bhardwaj}\par
\vspace{2mm}
{\small Independent researcher}\par
\vspace{4mm}
{\small 12 October 2026}\par
\end{center}
\vspace{5mm}
\begin{abstract}
We study how tracking-error and turnover limits shape monthly long-only
portfolios in a surviving ten-ETF panel. Momentum, low-volatility and reversal
preferences are evaluated against a monthly 60/40 policy in development
(2011--2017), validation (2018--2022) and holdout (2023--September 2026).
Formation reserves introduced after pre-holdout execution failures were frozen
before holdout evaluation. Turnover limits restrict preference expression,
while the objective's risk penalty and other constraints leave the 8\% and
12\% tracking-error caps inactive. The 5\% high-state cap binds infrequently,
limiting the original regime comparison's ability to distinguish allocations.
The primary model has negative active-return point estimates in development
and validation; both block intervals include zero.
% HOLDOUT FINDING
% REVIEW ABSTRACT
This retrospective study separates portfolio construction from investment
skill. Public daily portfolio ledgers support table verification; rebuilding
allocations requires the original data vintage or a labelled fresh download.
\end{abstract}
\noindent{\small\textbf{Keywords:} Portfolio construction; tracking error; turnover; exchange-traded funds; walk-forward backtesting.}\par
\vfill
\noindent{\footnotesize\color{muted}Code, protocol and evidence: \href{https://github.com/Aniket2002/portfolioos-benchmarked/tree/feature/empirical-research}{PortfolioOS research repository}.}\par
\end{titlepage}
\setcounter{page}{1}
\section{Introduction and research questions}
Benchmark-relative managers must translate investment preferences into holdings
while controlling deviations from a policy portfolio and the cost of changing
positions. A hard tracking-error limit can appear unimportant if a quadratic risk
penalty already keeps the optimizer within that limit. Conversely, a turnover
limit may prevent a desired allocation even when the risk budget has headroom.
Separating these mechanisms matters when interpreting a flat constraint frontier
or a small difference between fixed and state-dependent risk budgets.

We ask how risk and trading limits affect signal expression, whether greater
expression improves net historical performance, and whether a tighter risk budget
during high policy volatility changes allocations. The contribution is an
auditable comparison in a transparent multi-asset ETF setting: declared
constraint frontiers, independently costed comparison portfolios, preserved
execution failures, and separate development, validation and holdout evidence.
We measure constraint activity directly and reconcile active return by asset
class, so construction effects can be distinguished from predictive skill.
A separately labelled 3\% high-state diagnostic was added after holdout review.
The monthly 60/40 policy is a proposed comparison; the deterministic synthetic
study remains a separate exercise.
\section{Literature review}
Roll's analysis of tracking error \cite{roll} establishes the distinction between
optimization relative to a benchmark and conventional mean--variance efficiency.
Jorion \cite{jorion} derives the geometry of tracking-error-constrained portfolios
and shows why controlling relative risk alone can leave total portfolio risk
inefficient. Our objective penalizes active variance and also imposes a hard TE
cap; realized total volatility and drawdown are reported alongside relative risk.
We do not add a total-volatility mandate.

Clarke, de Silva and Thorley \cite{cdt} extend the fundamental law of active
management with a transfer coefficient describing how constraints impede the
translation of forecasts into active holdings. Our \textit{signal capture} diagnostic
addresses that same implementation question, but is a score-expression ratio
against a feasible reference, rather than their risk-adjusted cross-sectional
correlation. Its inputs are preferences, not calibrated residual-return forecasts,
so it is neither the classical transfer coefficient nor an estimate of expected
information ratio.

Ledoit and Wolf motivate shrinkage covariance estimation \cite{lw}; DeMiguel,
Garlappi and Uppal motivate the equal-weight comparison \cite{dgu}.
K\"unsch \cite{kunsch} provides the moving-block foundation for dependent-data
resampling. Our fixed-length blocks wrap around the sample endpoints, following
the circular procedure of Politis and Romano \cite{pr}, rather than an
unwrapped moving-block bootstrap.
Momentum research documents winner--loser persistence in individual stocks
\cite{jt}; volatility-return research studies stock-level aggregate and
idiosyncratic risk \cite{ang}; reversal research considers short-horizon
contrarian stock returns \cite{lehmann}. These findings motivate preferences,
not calibrated ETF expected returns. Total ETF volatility is not idiosyncratic
stock volatility, and a 21-session reversal score is not a replication of a
weekly stock-reversal study. Economic portability is an empirical question.
\section{Historical dataset and data quality}
The ordered universe is SPY, IWM, EFA, EEM, IEF, TLT, LQD, HYG, GLD and VNQ.
Equity covers the first four; fixed income covers IEF, TLT, LQD and HYG;
gold and real estate are separate constraint groups. VNQ is treated as a separate
real-estate allocation despite its equity-like risk. Funds were selected
retrospectively and survived to retrieval: this is not an unbiased historical
investable universe. Every fund existed before January 2009; issuer inception
and first-listing sources are recorded in the provenance appendix document.
GLD's November 18, 2004 availability date is its first trading date, distinct
from the trust's November 12 formation date.

The TigZig public API supplies Yahoo Finance data via yfinance. Its documented
auto-adjusted Close incorporates splits and distributions \cite{tigzig}.
The action ledger is preserved without a second adjustment. The operator's
terms describe educational/demonstration use and disclaim accuracy \cite{terms};
an institutional licence and upstream redistribution permission are not claimed.
Raw responses remain outside Git. Adjusted returns approximate total returns
with provider reinvestment conventions; tax and exact distribution reinvestment
execution are not modelled. Latest-vintage revisions can differ from historical
information available at each date.

Validation checks hashes, strict timestamp order, duplicates, positive finite
prices, common NYSE sessions, per-fund availability, distributions/splits,
20\% absolute daily-return review thresholds, original-response Close values,
and actions from a second endpoint of the same provider. The second endpoint
is not an independent market-data validation.
"""
    primary = rows["holdout"]["fixed_risk"]
    if primary["status"] == "success":
        interval = primary["uncertainty"]
        finding = tex(
            f"Holdout annualized arithmetic active return is "
            f"{number(interval['estimate'], True)} with a descriptive 95% "
            f"block interval [{number(interval['lower'], True)}, "
            f"{number(interval['upper'], True)}]."
        )
        preamble = preamble.replace("% HOLDOUT FINDING", finding)
    preamble = preamble.replace(
        "% REVIEW ABSTRACT",
        "Class attribution traces holdout gains to high-yield credit and gold, despite "
        "negative holdout mean IC. A post-holdout 3\\% high-state diagnostic binds "
        "more often but provides no conclusive return benefit."
        if review
        else "",
    )
    sections = [preamble]
    sections.append(
        f"The panel contains {quality['observed_sessions']:,} common sessions from "
        "January 2, 2009 to September 30, 2026, with "
        f"{len(quality['missing_sessions'])} missing sessions and "
        f"{len(quality['extreme_returns'])} threshold exceedances. "
        f"The ledger contains {sum(x['distributions'] for x in quality['availability'].values()):,} "
        "distributions and no splits in this window; GLD has no cash distributions.\n"
    )
    sections.append(r"""
\section{Mathematical model}
With score $s$, benchmark $b$, annual covariance $\Sigma$ and known lagged
holdings $w^{\rm known}$, the existing convex program solves
\[
\max_w\ s^\top w-10(w-b)^\top\Sigma(w-b)
       -0.1\lVert w-w^{\rm known}\rVert_1.
\]
Fully invested long-only portfolios satisfy $\mathbf{1}^\top w=1$ and
$0\leq w_i\leq0.35$. At execution, annual estimated TE is at most 8\%
(5\% in the high-state alternative), absolute active group exposure is at most
10 percentage points, and $T=\tfrac12\lVert w-w^{\rm pretrade}\rVert_1\leq0.30$.
Every accepted solution is independently checked. Infeasible or inaccurate
solver outcomes stop a path rather than silently relaxing constraints.

At return date $t$, signal and decision information end at $t-2$; target weights
are formed then, modelled at close $t-1$, and earn returns after that close.
Execution-close drift changes actual turnover but does not change target
formation. Holdings drift as
\[
w_{i,t}^{\rm end}=\frac{w_{i,t}(1+r_{i,t})}{1+w_t^\top r_t},\qquad
R_t^{\rm net}=w_t^\top r_t-\frac{c}{10000}T_t.
\]
The additive fee convention is a declared NAV approximation; this does not
prove closing prices were executable. Exact share/cash accounting is omitted.
\section{Signals and covariance methodology}
For information date $u$, raw momentum is $P_{u-21}/P_{u-252}-1$;
low volatility is the negative sample standard deviation of the last 63 daily
returns; reversal is $-(P_u/P_{u-21}-1)$. Cross-sectional 5th/95th winsorization
and population-standard-deviation standardization precede the composite
$s=z_{\rm momentum}+z_{\rm lowvol}+0.5z_{\rm reversal}$.
Coefficients are fixed preferences, not calibrated expected returns.
With ten complete observations and linear quantile interpolation, 5th/95th
winsorization clips only the minimum and maximum of each raw score, leaving eight
values unchanged before standardization. This is limited tail treatment in a
small cross-section, not strong protection against outliers; an isolated extreme
can still be reduced materially. Standardizing equities, bonds, gold and real
estate together mixes distinct risk and return distributions and can encode
asset-class preferences rather than within-class predictive information.
Covariance uses 252 trailing returns, Ledoit--Wolf shrinkage, a $10^{-10}$
daily diagonal ridge and annualization 252. Sample covariance is a declared
robustness alternative. Forward IC is Spearman correlation with subsequent
asset returns through the next rebalance; the terminal period can be partial.

Signal capture is $(w-b)^\top s$ divided by the expression of a same-score,
same-information long-only reference with the 35\% position cap but without
TE, group, turnover constraints or penalties. Exposure is measured against
the realized execution benchmark for both paths. Absolute reference exposure
at most $10^{-10}$ yields an undefined observation. Different ablations have
different reference scores, so their capture ratios are not cardinal skill
comparisons. High capture does not imply superior returns.
This diagnostic is related to the transfer-coefficient literature \cite{cdt},
but its normalization is an attainable score exposure, not a risk-adjusted
correlation.
\section{Policy benchmark and constraints}
The policy weights, in universe order, are
$(0.30,0.05,0.15,0.10,0.20,0.05,0.15,0,0,0)$.
It resets at the close immediately before the first observed session return
of each month and drifts between resets. The schedule is independently
represented when the active strategy rebalances weekly. Ordinary policy,
equal-weight and inverse-volatility comparisons satisfy their own rules and
portfolio accounting; active-manager TE, sector and turnover mandates are
not imposed on them. Both frictionless and independently cost-adjusted
policy returns are exported. Each independent period starts endowed at
its execution-date policy holdings; the active transition is charged and
the initial policy endowment is not charged.

\subsection{Pre-holdout design revision after execution failures}
Original development/validation active paths without reserves failed execution
checks, predominantly turnover limits following unobserved one-session drift;
those failures remain archived. After inspecting these development/validation
outcomes, we introduced identical formation reserves across
active scenarios: 2 percentage points of turnover, 1 percentage point of group
exposure and 0.1 percentage point of annual TE. Thus primary formation caps are
28\%, 9 percentage points and 7.9\%; the high-state formation TE cap is 4.9\%.
Execution mandates remain 30\%, 10 percentage points and 8\%/5\%, respectively.
This is an outcome-informed engineering correction to the initial specification.
The corrected specification was reviewed and frozen before constructed holdout
portfolio performance was examined; published results use that corrected model.
Reserves address engineering feasibility and do not guarantee that execution
constraints remain feasible. Remaining weekly sector failures in development
and validation were retained. A benchmark target
fits the 35\% cap; transition constraints can still be infeasible.
\section{Experiment design and holdout protocol}
Warmup is January 2009--December 2010; development is January 3, 2011--December
29, 2017; validation is January 2, 2018--December 30, 2022; final holdout is
January 3, 2023--September 30, 2026. Models receive physical price slices
ending at each period boundary. Before holdout, data checks, tests,
development/validation review and the configuration were frozen with dataset
hashes and a code commit. An exclusive access ledger was written before
the single final evaluation. No favourable ablation was substituted for
the primary model. Inherited source discovery and issuer verification exposed
incidental holdout-era quotes/performance panels, and full prices were ingested
for quality checks; constructed holdout performance was not used for selection.
The historical split is retrospective, not prospective preregistration.

Experiments A--G cover TE caps 4/8/12\%; turnover caps 10/30/50\%; identical-trade
cost sensitivities 0/10/25/40 bps; fixed 8\% versus normal 8\%/high 5\% TE;
three signal omissions plus regime awareness; the five portfolio strategies;
and sample covariance, three-session information delay and weekly rebalancing.
The full ledgers retain failures. Cost assumptions do not reoptimize holdings.
Metrics use 252 observations/year and sample return standard deviations;
Sharpe/Sortino assume zero risk-free return. Undefined metrics are explicit.

Uncertainty uses circular 21-session blocks, 2,000 resamples, seed 20261008 and
95\% percentile intervals for annualized arithmetic active means \cite{pr}. Strategy
differences are paired on the same dates. Approximate within-period stationarity
and dependence within blocks are assumed; structural breaks, longer regime
persistence and multiple comparisons are not resolved. No naive independent-day
significance tests or persistent-alpha conclusions are made.
\section{Empirical performance results}
All returns below are computed from executed paths. CAGR, annualized arithmetic
active return and TE are distinct quantities. Active returns use the frictionless
policy; a cost-adjusted policy comparison is included in the machine-readable
tables. Percent figures are expressed in percentage points.
""")
    for period in PERIODS:
        sections.append(f"\\subsection{{{period.title()}}}\n")
        sections.append(
            r"\begin{center}\begin{minipage}{\textwidth}\small"
            + f"\n\\captionof{{table}}{{{period.title()}-period performance.}}\\label{{tab-{period}}}\n"
            + r"\begin{tabular*}{\textwidth}{@{\extracolsep{\fill}}lrrrrr@{}}\toprule Strategy & Gross CAGR & Net CAGR & TE & Active & Max. DD\\\midrule"
            + "\n"
        )
        for scenario in STRATEGIES:
            row = rows[period][scenario]
            if row["status"] != "success":
                continue
            m = row["metrics"]
            cells = [LABELS[scenario]] + [
                number(m[k] * 100)
                for k in [
                    "gross_cagr",
                    "cagr",
                    "tracking_error",
                    "annualized_arithmetic_active_return",
                    "maximum_drawdown",
                ]
            ]
            sections.append(" & ".join(map(tex, cells)) + r"\\" + "\n")
        sections.append(
            r"\bottomrule\end{tabular*}\par\vspace{4pt}"
            r"\footnotesize\noindent Notes: All values are percentages. Active denotes annualized arithmetic return relative to the frictionless policy; TE is realized tracking error. Max. DD is maximum drawdown. Net returns include 10 bps per unit of one-way turnover."
            r"\end{minipage}\end{center}" + "\n"
        )
        fixed = rows[period]["fixed_risk"]
        if fixed["status"] == "success":
            m, interval = fixed["metrics"], fixed["uncertainty"]
            sections.append(
                tex(
                    f"Fixed-risk arithmetic active return: {number(interval['estimate'], True)}; "
                    f"95% block interval [{number(interval['lower'], True)}, {number(interval['upper'], True)}]. "
                    f"Mean capture: {number(m['average_signal_capture'])}, with {m['valid_capture_observations']} valid "
                    f"and {m['excluded_capture_observations']} excluded rebalance observations. "
                    f"Mean forward IC is {number(m['mean_ic'])}. "
                    f"Frictionless policy CAGR is {number(m['policy_frictionless_cagr'], True)}; "
                    f"independently cost-adjusted policy CAGR is {number(m['policy_net_cagr'], True)}."
                )
                + "\n"
            )
    sections.append(r"""
\section{Constraint sensitivity findings}
Table \ref{allresults} reports every declared scenario. Relaxing a risk cap need
not change an allocation when another constraint or the objective dominates.
The 8\% and 12\% TE configurations have essentially identical performance,
because those caps are inactive at every recorded formation decision.
The $\lambda=10$ quadratic active-risk penalty already discourages large risk
deviations, together with the group, position and turnover constraints; expanding
the hard cap from 8\% to 12\% therefore adds headroom the optimizer does not use.
The cap comparison alone does not isolate the risk penalty's marginal effect.
Turnover restricted
signal expression more than the tested 4\%--12\% TE range under this model,
objective, universe and other constraints. This conditional sensitivity does not
establish that turnover is generally more important than tracking error in
portfolio management. Higher capture does not establish better returns.
Capture and turnover frontiers describe construction mechanics rather than
investment skill. Formation reserves apply identically across frontier scenarios;
10/30/50\% turnover mandates imply 8/28/48\% formation caps.
\section{Volatility-regime comparison}
The classifier uses the monthly-policy return history: trailing 63-session
sample volatility times $\sqrt{252}$, compared with the expanding 75th percentile
of strictly earlier valid rolling observations, requiring 252 earlier values.
Only strict exceedances are high; ties are normal. Labels used in allocation are
dated at the lagged information close and budgets change at rebalances.
The timeline shows observation-date labels, whose availability is after that
close. Conditional results use daily lagged labels and arithmetic summaries;
they do not compound discontinuous subsequences or imply regime causality.
""")
    for period, interval in paired.items():
        sections.append(
            tex(
                f"{period.title()}: regime-aware minus fixed annualized arithmetic return "
                f"{number(interval['estimate'], True)}; paired 95% block interval "
                f"[{number(interval['lower'], True)}, {number(interval['upper'], True)}]."
            )
            + "\n\n"
        )
    sections.append(
        r"\begin{center}\small\begin{longtable}{@{}lllrrr@{}}"
        r"\caption{Conditional performance by lagged volatility state.}\label{tab-regimes}\\"
        r"\toprule Period & Strategy & State & Days & Active & TE\\\midrule\endfirsthead"
        r"\toprule Period & Strategy & State & Days & Active & TE\\\midrule\endhead"
        + "\n"
    )
    for period in PERIODS:
        for scenario in ["fixed_risk", "regime_aware"]:
            for row in rows[period][scenario].get("regime_conditional", []):
                cells = [
                    period.title(),
                    LABELS[scenario],
                    row["regime"],
                    row["observations"],
                    number(row["annualized_mean_active"] * 100),
                    number(row["realized_tracking_error"] * 100),
                ]
                sections.append(" & ".join(map(tex, cells)) + r"\\" + "\n")
    sections.append(r"\bottomrule\end{longtable}\end{center}" + "\n")
    sections.append("% REGIME REVIEW\n")
    sections.append(r"""
\section{Robustness and ablation results}
% TABLE5 AUDIT
The alternative covariance, delayed-information and signal-omission experiments
remain separately labelled. They are descriptive checks, not an uncontrolled
parameter search. Weekly paths that breach execution constraints receive no
full-period CAGR or fabricated continuation. The omission plots preserve the
full original model rather than selecting the best historical omission.

% WEEKLY CAUTION
\section{Economic interpretation}
Executed holdings explain the active-return contributions below, with trading
costs deducted separately. Standardized preference scores need not predict
portfolio returns.
% ATTRIBUTION REVIEW
No regression-based risk-adjusted alpha,
causal regime effect or investable closing-auction advantage is established.
\section{Limitations}
The surviving universe, latest adjustment vintage and Yahoo-derived data are
material selection and measurement limitations. ETF prices embed fund expenses;
taxes, share-lot/cash execution, market impact, liquidity, funding and settlement
are omitted. Turnover is half-L1 and fees are additive fractions of beginning NAV.
Constraints hold at accepted rebalances; drift can violate limits between them,
and realized TE can exceed ex-ante caps. Fixed risk reserves cannot guarantee
future mandate compliance. The modest fixed panel and multiple comparisons limit
generalization; block intervals do not solve structural-break uncertainty.
Zero-rate Sharpe is not a comparison with historical cash yields. The split is
retrospective and independently reproduced source prices can change vintage.
The original market-data bundle is retained locally and is not publicly
available. Fingerprints establish identity but cannot supply those inputs;
exact reconstruction of allocations is therefore conditional on original-bundle access.
Public daily portfolio returns and decision ledgers support independent
recomputation of the performance tables without provider data.
Fresh downloads can support method replication while changing numerical findings.
\section{Conclusion}
Under the tested objective and mandates, turnover restricts signal expression
while the 8\% and 12\% TE caps remain inactive. Holdout active return concentrates
in HYG and GLD, despite negative holdout mean IC. Formation reserves were an
outcome-informed correction frozen before holdout. The regime comparison offers limited
decision evidence and inconclusive return differences. These findings describe
construction mechanics and window-specific exposures; they establish neither
a general constraint ranking nor persistent alpha.
""")
    captions = {
        "wealth": "Executed cumulative net wealth with the frictionless policy shown separately. Each period is independently endowed at NAV 1.",
        "drawdowns": "Executed net drawdowns, including initial NAV 1 in the running high-water mark.",
        "te_frontier": "Declared TE mandates versus average signal capture and realized net TE; all other primary settings fixed.",
        "turnover_frontier": "Declared turnover mandates versus capture and realized net TE; the identical two-percentage-point formation reserve applies throughout.",
        "cost_sensitivity": "Net CAGR under accounting-only cost changes with identical gross returns, holdings and trades.",
        "regime_timeline": "Policy volatility and its strictly earlier expanding threshold. Red shading marks observation-date high-state labels, available only after that close.",
        "fixed_vs_regime": "Executed fixed-risk and regime-aware net wealth; small visual differences need not indicate meaningful skill.",
        "ablation_robustness": "Executed ablations and robustness comparisons. FAILED denotes an interrupted path with no full-period return bar. The hatched weekly holdout bar has no completed development or validation counterpart.",
    }
    sections.append(
        r"\clearpage\section*{Research figures}\addcontentsline{toc}{section}{Research figures}"
        + "\n"
    )
    for position, (name, caption) in enumerate(captions.items()):
        path = Path(
            relpath(root / "figures" / f"{name}.png", Path(destination).parent)
        ).as_posix()
        sections.append(
            r"\begin{center}\begin{minipage}{\textwidth}\centering"
            + "\n"
            + f"\\includegraphics[width=\\textwidth]{{{path}}}\n\\captionof{{figure}}{{{caption}}}\\label{{fig-{name}}}\n"
            + r"\end{minipage}\end{center}\vfill"
            + "\n"
        )
        if position % 2 == 1:
            sections.append(r"\clearpage" + "\n")
    sections.append(r"""
\clearpage
\begin{thebibliography}{99}
\raggedright
\bibitem{roll} Roll, R. (1992). A mean/variance analysis of tracking error.
\emph{Journal of Portfolio Management} 18(4), 13--22.
\url{https://doi.org/10.3905/jpm.1992.701922}.
\bibitem{jorion} Jorion, P. (2003). Portfolio optimization with tracking-error
constraints. \emph{Financial Analysts Journal} 59(5), 70--82.
\url{https://doi.org/10.2469/faj.v59.n5.2565}.
\bibitem{cdt} Clarke, R., de Silva, H., and Thorley, S. (2002). Portfolio
constraints and the fundamental law of active management.
\emph{Financial Analysts Journal} 58(5), 48--66.
\url{https://doi.org/10.2469/faj.v58.n5.2468}.
\bibitem{lw} Ledoit, O., and Wolf, M. (2004). A well-conditioned estimator for
large-dimensional covariance matrices. \emph{Journal of Multivariate Analysis}
88(2), 365--411. \url{https://doi.org/10.1016/S0047-259X(03)00096-4}.
\bibitem{dgu} DeMiguel, V., Garlappi, L., and Uppal, R. (2009). Optimal versus
naive diversification: How inefficient is the 1/N portfolio strategy?
\emph{Review of Financial Studies} 22(5), 1915--1953.
\url{https://doi.org/10.1093/rfs/hhm075}.
\bibitem{kunsch} K\"unsch, H. R. (1989). The jackknife and the bootstrap for
general stationary observations. \emph{Annals of Statistics} 17(3), 1217--1241.
\url{https://doi.org/10.1214/aos/1176347265}.
\bibitem{pr} Politis, D. N., and Romano, J. P. (1992).
A circular block-resampling procedure for stationary data.
In R. LePage and L. Billard (eds.), \emph{Exploring the Limits of Bootstrap},
263--270. Wiley, New York.
\url{https://purl.stanford.edu/xh812zd4638}
(Stanford technical-report version, 1991).
\bibitem{jt} Jegadeesh, N., and Titman, S. (1993). Returns to buying winners
and selling losers: Implications for stock market efficiency.
\emph{Journal of Finance} 48(1), 65--91.
\url{https://doi.org/10.1111/j.1540-6261.1993.tb04702.x}.
\bibitem{ang} Ang, A., Hodrick, R. J., Xing, Y., and Zhang, X. (2006).
The cross-section of volatility and expected returns.
\emph{Journal of Finance} 61(1), 259--299.
\url{https://doi.org/10.1111/j.1540-6261.2006.00836.x}.
\bibitem{lehmann} Lehmann, B. N. (1990). Fads, martingales, and market efficiency.
\emph{Quarterly Journal of Economics} 105(1), 1--28.
\url{https://doi.org/10.2307/2937816}.
\bibitem{tigzig} TigZig (2026). Yahoo Finance Data API documentation.
\url{https://www.tigzig.com/apis/yahoo-finance}. Accessed October 9, 2026.
\bibitem{terms} TigZig (2026). Terms of Use (August 2026 revision).
\url{https://www.tigzig.com/terms}. Accessed October 9, 2026.
\end{thebibliography}
\clearpage\appendix
\section{All declared scenario results}
Table values are percentages for CAGR, active return, TE and turnover;
capture is unitless. A dash denotes an unavailable full-period metric.
Complete Sharpe, Sortino, volatility, drawdown, information ratio, wealth,
cost drag, active share, IC and constraint diagnostics are in
\texttt{all\_performance.csv} and the per-scenario ledgers.
\begin{center}\footnotesize
\setlength{\tabcolsep}{4pt}
\renewcommand{\arraystretch}{1.06}
\begin{longtable}{@{}llrrrrr@{}}
\caption{All executed scenarios; failures are retained.}\label{allresults}\\
\toprule Period & Scenario & Net CAGR & Active & TE & Capture & Turnover\\\midrule\endfirsthead
\caption[]{All executed scenarios (continued).}\\
\toprule Period & Scenario & Net CAGR & Active & TE & Capture & Turnover\\\midrule\endhead
""")
    for period in PERIODS:
        if period == "holdout":
            sections.append(r"\pagebreak" + "\n")
        for scenario, row in rows[period].items():
            m = row.get("metrics", {})
            cells = [period.title(), SCENARIO_LABELS.get(scenario, scenario)] + [
                number(m[k] * (1 if k == "average_signal_capture" else 100))
                if m.get(k) is not None
                else "--"
                for k in [
                    "cagr",
                    "annualized_arithmetic_active_return",
                    "tracking_error",
                    "average_signal_capture",
                    "average_rebalance_turnover",
                ]
            ]
            sections.append(" & ".join(map(tex, cells)) + r"\\" + "\n")
    sections.append(r"\bottomrule\end{longtable}\end{center}" + "\n")
    sections.append(
        r"\noindent Scenario labels correspond to the identifiers in the declared protocol and \texttt{all\_performance.csv}. The complete model is retained in every signal-omission comparison; no alternative is promoted to the primary specification."
        + "\n"
    )
    for period in PERIODS:
        for scenario, row in rows[period].items():
            if row["status"] != "success":
                sections.append(
                    tex(f"Failure: {period}, {scenario}: {row['error']}.") + "\n\n"
                )
    sections.append(
        r"\clearpage\section{Reproduction appendix}\label{app-reproduction}" + "\n"
    )
    sections.append("Frozen code commit: \\path{" + lock["code_commit"] + "}.\n\n")
    sections.append(
        "Dataset SHA-256:\\par\\noindent{\\small\\path{"
        + quality["prices_sha256"]
        + "}}.\n\n"
    )
    sections.append(r"""
See \texttt{docs/empirical\_phase2.md} for the data-provider and issuer sources,
environment versions, original failures, exact commands and verification record.
\paragraph{Exact-input reproduction.}
The original bundle (original responses, prices, actions and manifest) is local
and not publicly distributed. Exact-input reproduction requires access to that
bundle, matching recorded fingerprints, the frozen model commit and protocol,
and compatible recorded dependencies. Numerical agreement is subject to solver
tolerances; byte-for-byte equality across environments is not promised.
The local validation reproduction and accounting audit used the original bundle;
they do not establish that an external reader can retrieve the same vintage.
Dataset hashes identify the inputs but cannot provide them.

\paragraph{Approximate replication with a new vintage.}
The acquisition commands retrieve fresh provider data, whose historical adjusted
prices or actions may have changed. This replicates the method, not necessarily
the published numerical results. Preserve a new manifest and fingerprints and
use a new explicitly labelled output directory. The original frozen holdout
output must not be overwritten or retuned.

\paragraph{Table verification without provider data.}
The public evidence includes daily portfolio gross/net returns, frictionless and
cost-adjusted policy returns, turnover/cost accounting, optimization diagnostics,
capture ledgers and forward-IC ledgers. Use the verifier:\par
\noindent\mbox{\texttt{scripts/verify\_public\_empirical\_tables.py}}\par
It recomputes CAGR, active means,
TE, drawdown, turnover, capture and block intervals from those outputs.
The separate \path{results/empirical_review_response} directory contains
reconciled class attribution, full-precision Table~\ref{allresults} checks,
cap-activity counts and the exploratory 3\% high-state paths.
The \mbox{\texttt{holdout\_position\_endpoints.csv}} ledger records normalized
adjusted-price endpoints for HYG and GLD. Its hash, exact return window,
preceding-close baseline and observation count are recorded in
\mbox{\texttt{holdout\_position\_context.json}}. The public verifier checks
endpoint arithmetic and dates. Supplying \texttt{--bundle} additionally recomputes
the compounded daily return from the original adjusted series after verifying
its frozen fingerprint.
The directory also preserves hashes of the original evaluation evidence. These artifacts verify
table arithmetic, not input-price accuracy or independent optimizer reconstruction.
Individual ETF daily return series are not redistributed because upstream
redistribution rights remain unverified.
The reporting script reads executed
ledgers and never calls the optimizer. The manuscript compiles from the
repository root using the documented Tectonic command.
\end{document}
""")
    manuscript = "\n".join(sections)
    if review:
        attribution, regime, table_check = review_tex(review)
    else:
        attribution, regime, table_check = "", "", ""
    manuscript = manuscript.replace("% ATTRIBUTION REVIEW", attribution)
    manuscript = manuscript.replace("% REGIME REVIEW", regime)
    manuscript = manuscript.replace("% TABLE5 AUDIT", table_check)
    weekly = rows["holdout"]["weekly"]
    if weekly["status"] == "success":
        m = weekly["metrics"]
        caution = tex(
            f"Weekly has the highest declared holdout net CAGR "
            f"({number(m['cagr'], True)}) and "
            f"{number(m['annualized_arithmetic_active_return'], True)} arithmetic "
            "active return. Both earlier paths failed execution checks, leaving "
            "no full-period development or validation evidence. The tall holdout "
            "bar in Figure 8 therefore does not validate a repeatable weekly advantage."
        )
    else:
        caution = ""
    manuscript = manuscript.replace("% WEEKLY CAUTION", caution)
    Path(destination).write_text(manuscript, encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", required=True)
    parser.add_argument("--bundle", required=True)
    parser.add_argument("--manuscript", default="docs/empirical_manuscript.tex")
    parser.add_argument(
        "--diagnostics", help="Separately labeled post-holdout evidence"
    )
    args = parser.parse_args()
    build(args.results, args.bundle, args.manuscript, args.diagnostics)
