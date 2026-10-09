"""Build research tables, figures and manuscript from executed evidence only.

This script does not optimize, tune or rerun any portfolio. Full-panel access for
the reporting-only regime timeline is allowed only after the holdout ledger exists.
"""

# Narrative strings and TeX table rows retain their publication source lines.
# ruff: noqa: E501

import argparse
import json
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


def save_figure(fig, path):
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def build(root, bundle, manuscript):
    root = Path(root)
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
    plt.rcParams.update({"font.size": 9, "axes.grid": True, "grid.alpha": 0.2})

    for name, mode in [("wealth", "wealth"), ("drawdowns", "drawdown")]:
        fig, axes = plt.subplots(1, 3, figsize=(13, 3.8))
        for ax, period in zip(axes, PERIODS):
            for scenario in STRATEGIES:
                if rows[period][scenario]["status"] != "success":
                    continue
                r = frame(root, period, scenario)
                series = (
                    (1 + r.net).cumprod() if mode == "wealth" else drawdown(r.net) * 100
                )
                ax.plot(series.index, series, label=LABELS[scenario], linewidth=1.2)
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
        axes[-1].legend(fontsize=7)
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
            ax.legend()
        axes[0].set_ylabel("Average signal capture")
        axes[1].set_ylabel("Realized net tracking error (%)")
        save_figure(fig, figures / f"{name}.png")

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
    ax.legend()
    save_figure(fig, figures / "cost_sensitivity.png")

    prices, _ = load_historical_bundle(bundle, protocol["assets"])
    if file_hash(Path(bundle) / "prices.csv") != quality["prices_sha256"]:
        raise ValueError("Reporting dataset differs from final evaluation")
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
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.5))
    for ax, period in zip(axes, PERIODS):
        for scenario in ["fixed_risk", "regime_aware"]:
            if rows[period][scenario]["status"] == "success":
                r = frame(root, period, scenario)
                ax.plot(r.index, (1 + r.net).cumprod(), label=LABELS[scenario])
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

    fig, ax = plt.subplots(figsize=(10, 4))
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
        ax.bar(
            ticks + (i - 1) * 0.25,
            np.array(values) * 100,
            width=0.25,
            label=period.title(),
        )
        for j, value in enumerate(values):
            if not np.isfinite(value):
                ax.text(
                    j + (i - 1) * 0.25,
                    0,
                    "failed",
                    rotation=90,
                    fontsize=7,
                    ha="center",
                )
    ax.set_xticks(
        ticks,
        [x.replace("without_", "no ").replace("_", " ") for x in comparisons],
        rotation=25,
        ha="right",
    )
    ax.set_ylabel("Net CAGR (%)")
    ax.legend()
    save_figure(fig, figures / "ablation_robustness.png")

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
        "Tracking-error budgets need not bind: at 8% and 12%, other constraints and the objective can produce virtually identical portfolios. Increased signal capture cannot establish better returns. Cost sensitivities clone identical weights, gross returns and turnover; only net accounting changes. Ablation capture has a different signal-specific reference denominator, so cross-ablation ratios are not cardinal measures of relative skill.",
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
        "See `docs/empirical_phase2.md` for acquisition, validation, freeze, execution and PDF commands. `all_performance.csv` contains every computed primary metric. Undefined metrics are null/NaN and are never replaced by zero. Original evaluations are never overwritten.",
    ]
    (root / "report.md").write_text("\n".join(body) + "\n", encoding="utf-8")
    write_manuscript(manuscript, root, rows, quality, lock, paired)


def write_manuscript(destination, root, rows, quality, lock, paired):
    """All numerical tables below are assembled directly from evaluation ledgers."""
    preamble = r"""\documentclass[11pt]{article}
\usepackage[margin=0.8in]{geometry}
\usepackage{amsmath,amssymb,booktabs,longtable,graphicx,hyperref,float}
\hypersetup{colorlinks=true,urlcolor=blue,linkcolor=blue}
\setlength{\emergencystretch}{3em}
\title{Benchmark-Relative Systematic Portfolio Construction:\\An Independent Ten-ETF Historical Study}
\author{Aniket Bhardwaj}
\date{9 October 2026}
\begin{document}
\maketitle
\noindent\textbf{Independent research; not peer reviewed. Retrospective pseudo-out-of-sample evidence.}
\begin{abstract}
This study examines how benchmark-relative tracking-error and turnover limits
compress a fixed composite of momentum, low-volatility and short-term reversal
preferences in a surviving ten-ETF panel. Monthly portfolios are compared with
a monthly 60/40 policy, equal weight and inverse volatility, with a conservative
two-session information lag. Development, validation and final holdout periods
are separated, and the protocol and dataset are frozen before constructed
holdout portfolio performance is examined. Negative outcomes and interrupted
paths remain part of the evidence. Signal capture measures preference expression,
not predictive skill. The results below distinguish arithmetic active returns,
compounded performance and descriptive block-bootstrap uncertainty; they do not
establish persistent alpha or causal effects of volatility regimes.
\end{abstract}
\section{Introduction and research questions}
How do benchmark risk and trading constraints affect signal expression? Does
increased expression improve net historical performance? Can a tighter
tracking-error budget during high policy volatility materially change outcomes?
The policy is a proposed comparison, not a claim of historical optimality.
The original deterministic synthetic study remains unchanged and separate.
\section{Literature review}
Ledoit and Wolf motivate shrinkage risk estimation \cite{lw}; their covariance
result does not establish profitability of this ETF strategy. DeMiguel,
Garlappi and Uppal motivate a transparent equal-weight comparison \cite{dgu}.
Their conclusions concern different universes and estimation problems.
Block resampling recognizes serial dependence rather than treating daily
observations as independent \cite{kunsch}. This study applies those methodological
ideas to portfolio construction without claiming a new asset-pricing discovery.
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

Original development/validation paths without reserves breached execution
turnover limits following unobserved one-session drift; those failures remain
archived. Before holdout, identical formation reserves were declared across
active scenarios: 2 percentage points of turnover, 1 percentage point of group
exposure and 0.1 percentage point of annual TE. Thus primary formation caps are
28\%, 9 percentage points and 7.9\%; the high-state formation TE cap is 4.9\%.
Execution mandates remain 30\%, 10 percentage points and 8\%/5\%, respectively.
Reserves address engineering feasibility, not performance selection, and do
not guarantee that execution constraints remain feasible. A benchmark target
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
95\% percentile intervals for annualized arithmetic active means. Strategy
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
            r"\begin{center}\small\begin{tabular}{lrrrrr}\toprule Strategy & Gross CAGR & Net CAGR & TE & Active & MDD\\\midrule"
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
        sections.append(r"\bottomrule\end{tabular}\end{center}" + "\n")
        fixed = rows[period]["fixed_risk"]
        if fixed["status"] == "success":
            m, interval = fixed["metrics"], fixed["uncertainty"]
            sections.append(
                tex(
                    f"Fixed-risk arithmetic active return is {number(interval['estimate'], True)} "
                    f"with a 95% block interval [{number(interval['lower'], True)}, {number(interval['upper'], True)}]. "
                    f"Mean capture is {number(m['average_signal_capture'])}, with {m['valid_capture_observations']} valid "
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
        r"\begin{center}\small\begin{longtable}{lllrrr}\toprule Period & Strategy & State & Days & Active & TE\\\midrule"
        + "\n"
    )
    for period in PERIODS:
        for scenario in ["fixed_risk", "regime_aware"]:
            for row in rows[period][scenario].get("regime_conditional", []):
                cells = [
                    period,
                    LABELS[scenario],
                    row["regime"],
                    row["observations"],
                    number(row["annualized_mean_active"] * 100),
                    number(row["realized_tracking_error"] * 100),
                ]
                sections.append(" & ".join(map(tex, cells)) + r"\\" + "\n")
    sections.append(r"\bottomrule\end{longtable}\end{center}" + "\n")
    sections.append(r"""
\section{Robustness and ablation results}
The alternative covariance, delayed-information and signal-omission experiments
remain separately labelled. They are descriptive checks, not an uncontrolled
parameter search. Weekly paths that breach execution constraints receive no
full-period CAGR or fabricated continuation. The omission plots preserve the
full original model rather than selecting the best historical omission.
\section{Economic interpretation}
Costs mechanically reduce net wealth on an unchanged trade path. A stronger
preference alignment can coexist with underperformance, because standardized
signal scores are not expected-return forecasts. Changes in relative performance
across historical periods can reflect asset-class composition, macroeconomic
exposures, estimator error and noise. No regression-based risk-adjusted alpha,
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
\section{Conclusion}
The empirical workflow provides auditable evidence of portfolio-construction
tradeoffs under declared benchmark risk, trading and cost conventions. It also
preserves failed transitions and inconclusive uncertainty. Signal expression is
a construction diagnostic; these historical results do not establish persistent
alpha. Prospective evaluation and independently licensed institutional data would
strengthen further research.
""")
    captions = {
        "wealth": "Executed cumulative net wealth with the frictionless policy shown separately. Each period is independently endowed at NAV 1.",
        "drawdowns": "Executed net drawdowns, including initial NAV 1 in the running high-water mark.",
        "te_frontier": "Declared TE mandates versus average signal capture and realized net TE; all other primary settings fixed.",
        "turnover_frontier": "Declared turnover mandates versus capture and realized net TE; the identical two-percentage-point formation reserve applies throughout.",
        "cost_sensitivity": "Net CAGR under accounting-only cost changes with identical gross returns, holdings and trades.",
        "regime_timeline": "Policy volatility and its strictly earlier expanding threshold. Red shading marks observation-date high-state labels, available only after that close.",
        "fixed_vs_regime": "Executed fixed-risk and regime-aware net wealth; small visual differences need not indicate meaningful skill.",
        "ablation_robustness": "Executed ablations and robustness comparisons. Failed full-period paths have no return bar.",
    }
    sections.append(r"\clearpage\section*{Research figures}" + "\n")
    for name, caption in captions.items():
        path = (root / "figures" / f"{name}.png").as_posix()
        sections.append(
            r"\begin{figure}[htbp]\centering"
            + "\n"
            + f"\\includegraphics[width=\\textwidth]{{{path}}}\n\\caption{{{caption}}}\n"
            + r"\end{figure}"
            + "\n"
        )
    sections.append(r"""
\clearpage
\begin{thebibliography}{9}
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
\bibitem{tigzig} TigZig (2026). Yahoo Finance Data API documentation.
\url{https://www.tigzig.com/apis/yahoo-finance}. Accessed October 9, 2026.
\bibitem{terms} TigZig (2026). Terms of Use (August 2026 revision).
\url{https://www.tigzig.com/terms}. Accessed October 9, 2026.
\end{thebibliography}
\appendix
\section{All declared scenario results}
Table values are percentages for CAGR, active return, TE and turnover;
capture is unitless. A dash denotes an unavailable full-period metric.
Complete Sharpe, Sortino, volatility, drawdown, information ratio, wealth,
cost drag, active share, IC and constraint diagnostics are in
\texttt{all\_performance.csv} and the per-scenario ledgers.
\begin{center}\scriptsize
\begin{longtable}{llrrrrr}
\caption{All executed scenarios; failures are retained.}\label{allresults}\\
\toprule Period & Scenario & Net CAGR & Active & TE & Capture & Turnover\\\midrule\endfirsthead
\toprule Period & Scenario & Net CAGR & Active & TE & Capture & Turnover\\\midrule\endhead
""")
    for period in PERIODS:
        for scenario, row in rows[period].items():
            m = row.get("metrics", {})
            cells = [period, scenario] + [
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
    for period in PERIODS:
        for scenario, row in rows[period].items():
            if row["status"] != "success":
                sections.append(
                    tex(f"Failure: {period}, {scenario}: {row['error']}.") + "\n\n"
                )
    sections.append(r"\section{Reproduction appendix}" + "\n")
    sections.append(
        "Frozen code commit: \\texttt{" + tex(lock["code_commit"]) + "}.\n\n"
    )
    sections.append("Dataset SHA-256: \\path{" + quality["prices_sha256"] + "}.\n\n")
    sections.append(r"""
See \texttt{docs/empirical\_phase2.md} for the data-provider and issuer sources,
environment versions, original failures, exact commands and verification record.
The original frozen holdout output must not be overwritten or retuned.
A reproduction uses a new explicitly labelled output directory; changed
historical vintages receive new hashes. The reporting script reads executed
ledgers and never calls the optimizer. The manuscript compiles from the
repository root using the documented Tectonic command.
\end{document}
""")
    Path(destination).write_text("\n".join(sections), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", required=True)
    parser.add_argument("--bundle", required=True)
    parser.add_argument("--manuscript", default="docs/empirical_manuscript.tex")
    args = parser.parse_args()
    build(args.results, args.bundle, args.manuscript)
