# PortfolioOS Benchmarked

[![CI](https://github.com/Aniket2002/portfolioos-benchmarked/actions/workflows/ci.yml/badge.svg)](https://github.com/Aniket2002/portfolioos-benchmarked/actions/workflows/ci.yml)

A reproducible Python research framework for benchmark-aware systematic
portfolio construction, connecting transparent cross-sectional signals with
active-risk constraints, turnover, transaction costs, walk-forward backtesting
and performance attribution.

**Research question:** Can transparent cross-sectional signals retain useful
benchmark-relative performance after active-risk constraints, turnover limits
and transaction costs are imposed?

The included results are **SYNTHETIC**, not evidence of persistent real-world
alpha. A negative result is valid; the framework remains useful when it
underperforms. This is an educational research implementation, not a live
execution platform. No empirical performance claim is made.

## Quick start

Python 3.10–3.12 is tested in CI. From the repository root:

```sh
python -m venv .venv
# Activate .venv using your shell's activation command.
python -m pip install -e '.[dev]'
python scripts/run_demo.py --config configs/demo.yaml
python -m pytest -q --cov=portfolioos --cov-report=term-missing --cov-fail-under=80
python -m ruff check .
python -m ruff format --check .
```

Dependency installation and GitHub Actions provisioning need network access.
**Tests, package execution and the demo require no internet or API credentials.**
The short CI demo uses `--smoke-test` and writes `results/smoke/`; the full run
writes [results/demo/report.md](results/demo/report.md). Seeds are deterministic;
solver outputs may differ slightly across platforms or dependency versions.
Supported dependency ranges are in `pyproject.toml`.

## Architecture

```mermaid
flowchart LR
    P[Prices through t-1] --> S[Cross-sectional signals]
    P --> C[Trailing covariance]
    B[Benchmark known through t-1] --> O[Constrained optimizer]
    S --> O
    C --> O
    W[Drifted pre-trade holdings] --> O
    O --> T[Turnover and costs]
    T --> R[Prospective returns and drift]
    R --> A[Metrics, IC and attribution]
```

| Modules | Responsibility |
| --- | --- |
| `data`, `synthetic` | Validation and deterministic market fixtures |
| `signals`, `covariance` | Transparent scores and trailing risk estimation |
| `optimizer` | CVXPY allocation and independent constraint validation |
| `backtest`, `costs` | Walk-forward timing, drift, turnover and costs |
| `metrics`, `attribution` | Performance, forward IC, security/sector effects |
| `reporting` | Configurations, reconciliation and research artifacts |

The notebook is a presentation layer calling these modules.
Install `python -m pip install -e '.[notebook]'` for a notebook kernel and execution
dependencies, then select that environment in your notebook editor.

## Data and timing contract

Adjusted prices are a `DatetimeIndex × asset identifier` DataFrame. Dates must
be chronological and unique; identifiers must be unique nonempty strings.
Prices must be positive and finite. Missing data is rejected by default.
Optional `max_missing_fraction` applies per asset and `fill_limit` permits only
bounded **causal forward filling**. Leading or unresolved gaps fail. No backward
fill or automatic asset/date dropping occurs. Filling creates stale marks and
changes measured returns/volatility; the researcher must justify it.

The universe is fixed per run. Real research must establish point-in-time
membership, delisting treatment, corporate actions and historical adjustment
vintages. Retrospectively adjusted prices can themselves contain revisions.

For holdings earning close-to-close return on date **t**:

1. The exclusive slice `prices.iloc[:i]` ends at **t−1** for signals/covariance.
2. Benchmark and external-signal snapshots must be dated ≤ t−1.
3. Targets and costs are set before return t is observed.
4. Return t is applied, then holdings drift to the next pre-trade state.

This assumes idealized execution at the previous close after observing its
close. Real auction deadlines, processing time and slippage require an extra
lag or intraday data. The structural guarantee is no use of return t in weights
earning return t, not a claim that these closing fills are executable.
Adversarial tests mutate same-day/future prices, benchmark rows and external
signals and verify earlier weights are identical.

Default warmup is 253 prices (252 returns). Evaluation begins on the next
eligible date, even mid-month. Subsequent monthly rebalances use the first
observed trading day of a new month. Weekly/daily schedules are supported.
Start/end dates restrict evaluation while retaining earlier training history.

## Price-based signals

Let **s = t−1** denote the information date; offsets count observed trading days.

| Signal | Definition | Default |
| --- | --- | --- |
| 12−1 momentum | `P[s−21] / P[s−252] − 1` | Excludes latest 21 days |
| Low volatility | Negative trailing sample daily-return standard deviation | 63 returns |
| Short-term reversal | `−(P[s] / P[s−21] − 1)` | 21 days |

These are price signals, not fundamental value or quality factors. Each is
winsorized at its cross-sectional 5th/95th quantiles, then z-scored with population
standard deviation. Missing scores become neutral zero; constant or entirely
missing cross sections become zero. Normalization uses no future dates.

`score[i] = Σ beta[k] × z[k,i]`. Defaults are 1, 1 and 0.5, fixed in advance and
not normalized to sum to one. No evaluation-sample fitting of signal weights
occurs. An external signal is preprocessed identically; explicitly add an
`external` coefficient to use it. Its timestamps must represent availability,
not merely the underlying accounting period. Last known snapshots persist until
updated; the caller is responsible for assessing staleness.

## Covariance and portfolio optimization

[Ledoit–Wolf shrinkage](https://scikit-learn.org/stable/modules/generated/sklearn.covariance.LedoitWolf.html)
uses trailing 252 daily returns ending at s. The estimator demeans returns;
a daily diagonal ridge of `1e-10` supplies numerical stability. The matrix is
symmetric and positive semidefinite. `Σannual = 252 × Σdaily`.

```text
maximize    score' w − λrisk (w − wb)' Σannual (w − wb)
                    − λturnover ||w − wpretrade||₁

subject to  Σ w = 1
            0 ≤ wi ≤ position cap
            sqrt((w − wb)' Σannual (w − wb)) ≤ annual TE cap       [optional]
            |Σsector (w − wb)| ≤ sector active cap                [optional]
            0.5 ||w − wpretrade||₁ ≤ one-way turnover cap          [optional]
```

Scores are dimensionless preferences, **not annual expected-return forecasts**.
Risk and turnover coefficients are modelling tradeoffs, not calibrated utility.
The objective penalizes full L1; reported turnover and its cap use half L1.
Default coefficients are 10 and 0.1; caps are 8% position, 8% annual estimated TE,
10 percentage points sector active weight and 30% one-way turnover. Defaults
were chosen for transparent mechanics, not optimized synthetic performance.

[CLARABEL through CVXPY](https://www.cvxpy.org/tutorial/solvers/index.html)
requires no proprietary solver. Only an `optimal` solution passing independent
constraint checks is accepted. Numerical negative dust is clipped and holdings
normalized, then every constraint is rechecked with `1e-7` tolerance. Failures
are explicit and stop the backtest with date/status/reason. Configured benchmark
fallback (off by default) is allowed only if all constraints, including turnover,
remain satisfied. Constraints are never silently relaxed.

Caps apply at **rebalances**; drift may exceed position/sector limits and realized
TE may exceed estimated TE. Risk estimates are stored at rebalances, not
re-estimated daily. If metadata is omitted, explicitly set
`max_sector_active_weight: null`.

## Benchmark, drift, turnover and costs

Supplied benchmark rows are nonnegative target snapshots normalized to one.
Missing price assets receive zero weight; unknown constituents are rejected,
including unknown zero-weight columns. Rows take effect on the next observed
trading date. A repeated row supplied daily means daily target rebalancing.
Between updates, benchmark holdings drift. The latest known snapshot initializes
the evaluation period.

Without snapshots, the benchmark resets to **equal weight** at strategy rebalances
and drifts between them. It is not the S&P 500 or another named index. Benchmark
costs are excluded, as with a frictionless index comparison.

Both portfolios drift using `wnew[i] = w[i] × (1+r[i]) / (1+w'r)`.
Initial capital is endowed in benchmark holdings; the initial active transition
incurs turnover. Later turnover uses drifted pre-trade holdings:

```text
one_way_turnover = 0.5 × Σ |target − pretrade|
cost_fraction   = one_way_turnover × transaction_cost_bps / 10,000
net_return      = gross_return − cost_fraction
active_return   = net_return − benchmark_return
```

10 bps means 0.10% of starting NAV for a complete switch (turnover 1), not a
separate 10 bps charge on each buy/sell leg. Cost is deducted once using an
additive return approximation. A proportional fee leaves relative holdings
unchanged; drift uses gross asset returns. Exact cash/share execution accounting,
impact, taxes, funding, settlement, lot sizes and liquidity are outside v1.

## Metrics, IC and attribution

Annualizations use 252 observations/year; CAGR is `wealth^(252/n)−1`.
Volatility and realized TE use sample standard deviation. Sharpe uses mean daily
excess return ×252 / annual volatility; risk-free rate defaults to zero, with
an optional annual rate geometrically converted to daily. Sortino uses root mean
squared negative excess returns over **all days**. Drawdown includes starting
NAV 1. Undefined ratios are NaN in memory and JSON null in reports.

Active returns are arithmetic daily differences; information ratio is their mean
×252 / annual TE. The relative-wealth chart is portfolio wealth / benchmark
wealth −1, not compounded daily active returns. Annual turnover is total ×252/n.
Summed daily cost fractions and compounded gross-minus-net wealth drag are
reported separately. Average absolute active weight averages all securities/dates;
maximum position includes drift; average estimated TE uses rebalances only.

Forward signal IC is Spearman correlation between rebalance scores and asset
buy-and-hold returns from that effective date through the day before the next
rebalance. It is computed **after** simulation and never used in construction.
The terminal window may be partial and is flagged. Reports include mean, median,
standard deviation, fraction positive and mean/std (not annualized). No claim
of statistical significance or independent IC observations is made.

Security contribution is exactly `(w−wb) × asset_return` using beginning-of-day
holdings, summing to gross active return. Subtract daily cost for net active.
For sector weights Wp/Wb, within-sector returns Rp/Rb and total benchmark RB,
Brinson–Fachler effects are:

```text
allocation  = (Wp − Wb) × (Rb − RB)
selection   = Wb × (Rp − Rb)
interaction = (Wp − Wb) × (Rp − Rb)
```

Daily effects reconcile to gross active return. An absent side's sector return
is defined as zero; individual effects then depend on the convention, but the
total still reconciles. Daily effects are not linked into compounded multi-period
attribution; summing them is an arithmetic summary only.

## Synthetic case study and external data

The default generator uses 40 assets, five sectors, six 252-day years and seed 42.
Independent market/sector/idiosyncratic log-return shocks have heterogeneous
loadings and volatilities. **No predictive signal structure is embedded.**
There are no delistings, membership changes or factor-distribution regimes.
The business-day index is illustrative, not an exchange calendar.

See the [notebook](notebooks/research_case_study.ipynb) and
[synthetic report](results/demo/report.md). Outputs include JSON, metrics,
holdings, active holdings, returns, optimization statuses, scores, IC,
security/sector attribution and eight PNG charts. The summary records config/seed.
Only synthetic demo artifacts are tracked; other results and local data are ignored.

```python
import pandas as pd
from portfolioos import run_backtest
from portfolioos.reporting import load_config, write_report

prices = pd.read_csv("data/prices.csv", index_col=0, parse_dates=True)
benchmark = pd.read_csv("data/benchmark.csv", index_col=0, parse_dates=True)
metadata = pd.read_csv("data/metadata.csv", index_col=0)
_, config = load_config("configs/demo.yaml")
result = run_backtest(prices, benchmark, metadata, config=config)
write_report(result, "results/research", provenance="USER-SUPPLIED historical data")
```

Equivalent CLI:

```sh
python scripts/run_research.py --prices data/prices.csv \
  --benchmark data/benchmark.csv --metadata data/metadata.csv
```

Price/benchmark/signal CSVs have a date first column and asset columns. Metadata
has a ticker first column and `sector`. Optional `--signals` accepts publication-
dated snapshots. Nothing downloads data. Users must establish licenses, point-in-
time provenance, corporate-action handling, availability and defensible universes.
Provider inputs are never automatically copied or committed.

## Validation and limitations

CI runs Ruff, pytest with an **80% minimum coverage gate**, and an offline demo
on Python 3.10, 3.11 and 3.12. Tests cover known examples, solver failures,
constraints, timing mutations, drift, costs and attribution. See the
[adversarial review](docs/adversarial_review.md).

Coverage supports mechanics, not economic validity. Real research still needs
survivorship controls, realistic execution, cost sensitivity, changing universes,
regime analysis, independent holdouts and proper inference. No production
readiness, market calibration or institutional validation is claimed.

## Suggested CV wording

“Developed a benchmark-aware systematic portfolio research framework combining
cross-sectional signals with constrained optimisation, tracking-error controls,
turnover and transaction-cost modelling, walk-forward backtesting and
performance attribution.”

MIT licensed. Implementation is original to this repository.
