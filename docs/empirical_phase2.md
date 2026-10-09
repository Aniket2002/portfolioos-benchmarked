# PortfolioOS empirical Phase 2

This is independent research, not peer-reviewed research. The existing synthetic
engine, defaults, configurations and committed synthetic outputs are preserved.
The study continues `feature/empirical-research` from
`ab4a7b6daf6fa0cc1c030b8517e070d7b883a076`.

## Audit and methodological corrections

The original feature commit was tested independently in an archived checkout:
163 tests passed. The inherited working implementation passed 178 tests before
this audit's additional changes. New tests cover target causality, execution-close
drift, unconstrained comparisons, benchmark accounting, cost cloning, source
reconciliation, causal percentile ties and holdout tampering.

Ordinary policy, equal-weight and inverse-volatility comparisons now obey their
declared allocation rules and investment accounting. They are not subjected to
the active manager's TE, sector, position or turnover caps. A separately declared
`constrained_baseline` option remains available. Realized risk and costs are
measured for every comparison with the same adjusted asset returns.

The primary two-state regime uses the actual monthly policy portfolio's returns,
not SPY as a proxy. Volatility is the trailing 63-session sample standard deviation
times sqrt(252). Its threshold is the expanding 75th percentile of strictly
earlier rolling values, with at least 252 earlier valid observations. Strict
exceedances are high; ties are normal. Budgets are 8% normal and 5% high; the
fixed-risk model uses 8%. The original three-state asset classifier remains
separately available for exploratory/synthetic compatibility.

For return date t, decisions and signals end at t-2, target fills are modelled
at close t-1, and returns begin after that close. Actual t-1 drift enters cost and
execution compliance checks, but never target formation. Target orders are not
guaranteed executable closing-auction fills. Fees are an additive beginning-NAV
approximation; no exact share/cash ledger is claimed.

The policy rebalances at the close immediately before the first exchange session
return of each month and drifts otherwise. It is independent of weekly strategy
rebalancing. Every period starts endowed in its execution-date policy holdings;
initial active transitions incur fees, the policy endowment does not.

### Preserved failures and declared engineering revision

Original zero-reserve experiments are preserved under `results/empirical_phase2`.
All active scenarios failed at actual execution checks, predominantly turnover;
they were not assigned misleading full-period performance. Ordinary comparisons
completed. An interrupted reserve-run artifact remains locally under
`results/empirical_phase2_final` and is not represented as a completed evaluation.

Before holdout, identical formation reserves were declared across active
scenarios: 2 percentage points turnover, 1 percentage point group exposure and
0.1 percentage point annual TE. Primary formation limits are therefore 28%, 9pp
and 7.9% (4.9% in high states). Execution mandates remain 30%, 10pp and 8%/5%.
Turnover-frontier formation caps are 8/28/48%, corresponding to declared execution
mandates 10/30/50%. This is an explicit engineering feasibility adjustment;
execution violations still stop the path. No further reserve search was performed
after the reviewed runs. Weekly paths still failed sector checks in development
and validation; those failures remain part of experiment G.

## Data provider, adjustment and access conditions

The local bundle is `data/phase2-tigzig-20261008` and contains `prices.csv`,
`actions.csv`, `manifest.json` and both original JSON responses. Retrieval was
2026-10-08T16:36:08.211335+00:00. Raw provider data are ignored by Git and are not
redistributed. Bundle SHA-256:

`5af0b0c65a9b4f8be569090f974c0b5446839a0bac20c3485d2184109cf981ea`

Actions SHA-256:

`c35dc8fc03f714c69e71ea963a81f0773b5233d6f8506be2ef974cafa387752a`

The [TigZig API documentation](https://www.tigzig.com/apis/yahoo-finance)
describes a public no-auth API over Yahoo Finance via yfinance. Its all-prices
endpoint provides auto-adjusted Close incorporating splits and dividends;
distributions and splits appear on event dates. Prices are used once; the actions
ledger is retained without double adjustment. [Operator terms](https://www.tigzig.com/terms)
describe educational/demonstration use and disclaim warranties. Public technical
access is not proof of institutional licensing or upstream redistribution rights.
Neither upstream redistribution permission nor a vendor accuracy attestation is
claimed. Reproduction requires a source whose conditions permit the intended use.
No authenticated premium provider or institutional entitlement was found locally.

Yahoo's [adjusted-close explanation](https://help.yahoo.com/kb/adjusted-close-sln28256.html)
is referenced in the source manifest; it was not reliably retrievable during this
audit. The adjustment claim relies on the operator's directly inspected
documentation, not a fabricated independent Yahoo attestation.

Formal [data quality](../results/empirical_phase2_reviewed/data_quality.md)
checks price/action hashes, original Close reconciliation, monotone unique
timestamps, positive finite prices, common NYSE sessions, per-asset availability,
20% extreme-return review thresholds and two-endpoint action consistency.
There are 4,463 common sessions, no missing/unexpected dates, 1,133 distributions,
no splits and no threshold exceedances. Endpoints share the upstream provider;
their consistency is not independent institutional validation. The NYSE calendar
includes exceptional closures and is not an artificial business-day calendar.
Latest adjusted-price vintages may contain revisions and are not point-in-time
corporate-action adjustment vintages.

### Instrument availability

Every fund predates January 2009. Availability was verified against issuer
documentation; the panel itself covers 2009-01-02 through 2026-09-30 for all ten.
No inception history was fabricated or filled.

| ETF | Inception / availability date | Issuer evidence |
|---|---|---|
| SPY | 1993-01-22 | [State Street](https://www.ssga.com/us/en/institutional/etfs/state-street-spdr-sp-500-etf-trust-spy) |
| IWM | 2000-05-22 | [BlackRock fund list](https://www.blackrock.com/us/individual/products/investment-funds) |
| EFA | 2001-08-14 | [iShares EFA](https://www.ishares.com/us/products/239623/ishares-msci-eafe-etf) |
| EEM | 2003-04-07 | [iShares EEM](https://www.ishares.com/us/products/239637/ishares-core-msci-emerging-markets-etf) |
| IEF | 2002-07-22 | [iShares fund list](https://www.ishares.com/us/products/etf-investments) |
| TLT | 2002-07-22 | [iShares fund list](https://www.ishares.com/us/products/etf-investments) |
| LQD | 2002-07-22 | [iShares fund list](https://www.ishares.com/us/products/etf-investments) |
| HYG | 2007-04-04 | [iShares fund list](https://www.ishares.com/us/products/etf-investments) |
| GLD | First trading 2004-11-18; trust formed 2004-11-12 | [Issuer annual report](https://www.spdrgoldshares.com/media/GLD/file/10-K_11_22_10.pdf) |
| VNQ | 2004-09-23 | [Vanguard fact sheet](https://workplace.vanguard.com/assets/corp/fund_communications/pdf_publish/us-products/fact-sheet/F0986.pdf) |

The universe was retrospectively selected from surviving funds and is explicitly
not an unbiased historical investable universe. VNQ is a separate real-estate
constraint group, despite equity-like economic exposure; HYG belongs to fixed
income. The fixed policy is a proposed comparison, not historically optimal.

## Periods and holdout protocol

| Period | Actual boundaries | Purpose |
|---|---|---|
| Warmup | 2009-01-02–2010-12-31 | Pre-estimation history |
| Development | 2011-01-03–2017-12-29 | Engineering and preliminary experiments |
| Validation | 2018-01-02–2022-12-30 | Configuration review |
| Holdout | 2023-01-03–2026-09-30 | Single frozen pseudo-out-of-sample evaluation |

The full bundle was accessed for ingestion/calendar/corporate-action checks.
Models and reference portfolios receive physical slices ending at the selected
period boundary. Incidental holdout-era SPY quotes were inherited from source
discovery; issuer verification in this audit also exposed issuer quote and
performance panels. Constructed holdout portfolio performance was not inspected
for selection. This is retrospective pseudo-out-of-sample research, not a claim
of prospective preregistration or ignorance of known market history.

The final freeze requires successful QA, executed tests, explicit review of both
pre-holdout ledgers, a clean committed code/configuration tree and matching input
hashes. `final_protocol_lock.json` records code commit, protocol, dataset identity,
evidence hashes, review hash, verification hash and freeze time. The exclusive
`holdout_access.json` marker is created before any holdout model evaluation.
Existing outputs cannot be overwritten. Additional analyses must use separately
labelled directories and must not erase the original final evaluation.

## Executed outputs and uncertainty

The final evaluation completed 61 of 63 period/scenario paths. The two stopped
paths are weekly sector-limit breaches in development (2012-06-04) and validation
(2020-03-16). All 21 holdout scenarios completed. The model was not retuned after
the holdout was opened.

| Primary comparison | Development | Validation | Holdout |
|---|---:|---:|---:|
| Fixed-risk net CAGR | 7.50% | 2.03% | 13.72% |
| Frictionless policy CAGR | 7.99% | 3.28% | 12.33% |
| Annualized arithmetic active return | −0.38% | −1.15% | 1.23% |
| 95% block-bootstrap interval | [−3.14%, 2.08%] | [−3.67%, 1.36%] | [−1.55%, 3.90%] |

The primary model underperformed in both pre-holdout periods. Holdout excess
performance is statistically inconclusive under the declared uncertainty method.
Regime awareness made little difference: its holdout arithmetic return difference
versus fixed risk is −0.015 percentage points/year, with a paired interval
[−0.098, 0.048] percentage points/year. No interval establishes persistent alpha.
The primary holdout forward IC is −0.019, despite positive portfolio active
return; preference alignment and cross-sectional prediction are distinct.

The reviewed study is under `results/empirical_phase2_reviewed`. Its
`all_performance.csv`, `experiment_status.md`, `report.md`, eight figures,
period/scenario ledgers and paired regime intervals are produced by executed
models and the reporting script. Full local trade paths are retained for audit;
Git records aggregate portfolio returns/diagnostics and summaries, not raw ETF
prices or corporate-action responses.

The [finished manuscript PDF](empirical_manuscript.pdf) has 12 pages and all eight
requested figures. Every page was rendered and visually inspected; fonts are
embedded, all eight images are present, and there are no unresolved references,
overfull/underfull boxes or out-of-page content blocks. Tectonic emitted a local
Fontconfig configuration diagnostic but successfully used embedded bundled fonts.
The final compile log has no LaTeX formatting warnings. Reporting-only path and
layout corrections followed the holdout; model code/configuration and original
holdout returns were not changed or rerun.

An [independent artifact audit](../results/empirical_phase2_reviewed/accounting_audit.json)
reconciles all 61 completed paths: asset-to-portfolio and benchmark returns,
holdings drift, actual turnover, policy calendar/cost accounting, information
dates, execution mandates and identical-trade cost comparisons. Stopped weekly
paths retain explicit failure records without full-period metrics.

### Verification results

| Check | Result |
|---|---|
| Original feature commit | 163 tests passed in archived checkout |
| Inherited worktree before additional audit changes | 178 tests passed |
| Python 3.10.22 | 186 tests passed; 87.20% package coverage |
| Python 3.11.3 | 186 tests passed; 87.20% package coverage |
| Python 3.12.15 | 186 tests passed; 87.20% package coverage; one dependency deprecation warning |
| Ruff lint and formatting | Passed |
| Synthetic full demo | 1,260 days / 59 rebalances; differences at most 4.25e-8, within 1e-7 solver tolerance |
| Synthetic full frontiers | Dataset identities/statuses identical; numeric tables exactly equal |
| Primary/regime validation reproduction | Maximum numeric differences below 1e-16; outputs not overwritten |
| Notebook validation | One tracked notebook validated; not executed |
| Source/wheel build and external wheel import | Passed |
| Streamlit health and root | HTTP 200 |
| PDF | 12 pages, eight embedded figures; inspected |

The [verification record](../results/empirical_phase2_reviewed/verification.json)
captures the executed local checks **before holdout freezing**. It does not attest
to a remote GitHub Actions run; remote status must be checked for the published
final commit. Environment snapshots are alongside it. Research artifacts use
`.gitattributes` to preserve exact bytes for evidence hashes across Git checkouts.

Sharpe/Sortino use an explicitly declared zero risk-free rate. CAGR uses
252 observations/year. TE and annualized arithmetic active return compare net
strategy returns with the frictionless policy. Independently cost-adjusted policy
returns and arithmetic active comparison are also exported. Signal capture uses
a same-score, same-date investable reference; near-zero denominators (absolute
exposure at most 1e-10) are excluded and counted. Undefined metrics remain
null/NaN. Ablations have signal-specific references, so capture ratios cannot be
interpreted as a common cardinal skill scale across ablations.

Circular block bootstrap uses 21-session blocks, 2,000 resamples, seed 20261008 and
95% percentile intervals for arithmetic active means. Regime-aware minus fixed
differences are paired on the same dates. Approximate within-period stationarity
and within-block dependence are assumptions, not established facts. Regime
persistence, structural breaks, multiple comparisons and limited holdout length
are limitations. Conditional regimes use daily lagged labels, while allocation
budgets update only at rebalances; neither implies causal effects.

## Reproduction commands

Use Python 3.10, 3.11 or 3.12. A complete dependency snapshot accompanies the
verification record; bounded installation ranges remain in `pyproject.toml`.
Commands below are PowerShell-compatible after activating the intended venv.
For a fresh reproduction use a new output path and preserve the original final
evaluation. A fresh retrieval can have a different adjustment vintage/hash.

```powershell
python -m pip install -e '.[dev,empirical]'
python scripts/acquire_market_data.py --output data/reproduction-bundle
$bundle = 'data/reproduction-bundle'
$output = 'results/empirical-reproduction'
$protocol = 'configs/empirical_phase2.json'
python scripts/run_empirical.py --protocol $protocol --bundle $bundle --output $output --quality
python -m ruff check .
python -m ruff format --check .
python -m pytest -q --cov=portfolioos --cov-fail-under=80
python scripts/run_empirical.py --protocol $protocol --bundle $bundle --output $output --period development
python scripts/run_empirical.py --protocol $protocol --bundle $bundle --output $output --period validation
```

Inspect both evaluations, record an honest `review.json` containing
`development_validation_reviewed: true`, and a `verification.json` containing
`passed: true` with the actual executed check results. Keep those generated records
under the ignored output directory. Commit code/configuration before freezing.
For this study the review and verification records are committed beside the
result summaries. Never fabricate the two gate attestations to bypass review.

```powershell
python scripts/run_empirical.py --protocol $protocol --bundle $bundle --output $output --freeze --review "$output/review.json" --verification "$output/verification.json"
python scripts/run_empirical.py --protocol $protocol --bundle $bundle --output $output --period holdout
python scripts/build_empirical_report.py --results $output --bundle $bundle
tectonic -X compile docs/empirical_manuscript.tex --outdir docs
```

The manuscript's image paths are repository-relative, so compile from the root
with Tectonic's `--keep-logs` option for formatting diagnostics. The local executable
used here is `.cache/tectonic/tectonic.exe` (Tectonic 0.17.0). It is a local tool,
not a downloaded market-data script. PDF inspection uses PyMuPDF, an optional
inspection dependency, not a portfolio-engine dependency.

Existing synthetic regression commands write separately:

```powershell
python scripts/run_demo.py --config configs/demo.yaml --output results/phase2-synthetic-regression
python scripts/run_experiments.py --config configs/demo.yaml --output results/phase2-synthetic-frontiers
python scripts/verify_empirical_outputs.py --protocol configs/empirical_phase2.json --bundle data/phase2-tigzig-20261008 --output results/empirical_phase2_reviewed
python scripts/audit_empirical_artifacts.py --results results/empirical_phase2_reviewed --bundle data/phase2-tigzig-20261008
```

GitHub CI keeps its Python 3.10/3.11/3.12 matrix, tests, lint/format, package,
notebook, Streamlit and research smoke jobs. Feature-branch pushes and manual
dispatch are enabled. Local verification does not imply a remote Actions run;
no merge to `main` is performed.

## Bibliography verification

Ledoit and Wolf (2004), *Journal of Multivariate Analysis* 88(2), 365–411,
[author bibliography](https://www.ledoit.net/), DOI
10.1016/S0047-259X(03)00096-4.
DeMiguel, Garlappi and Uppal (2009), *Review of Financial Studies* 22(5),
1915–1953, DOI [10.1093/rfs/hhm075](https://doi.org/10.1093/rfs/hhm075),
also confirmed in the [LBS author research paper bibliography](https://lbsresearch.london.edu/id/eprint/1755/1/OptimalPortfolioDiversific.pdf).
Künsch (1989), *Annals of Statistics* 17(3), 1217–1241,
[author bibliography](https://people.math.ethz.ch/~hkuensch/papers/), DOI
10.1214/aos/1176347265. Publication details were checked; these citations motivate
methods and comparisons, not this strategy's economic validity.

The signal discussion also cites Jegadeesh and Titman (1993), *Journal of Finance*
48(1), 65–91, [publisher record](https://onlinelibrary.wiley.com/doi/10.1111/j.1540-6261.1993.tb04702.x);
Ang, Hodrick, Xing and Zhang (2006), *Journal of Finance* 61(1), 259–299,
[NBER publication record](https://www.nber.org/papers/w10852); and Lehmann (1990),
*Quarterly Journal of Economics* 105(1), 1–28,
[publisher record](https://doi.org/10.2307/2937816). Their stock-level evidence is
not represented as a replication or calibrated ETF expected-return model.

## Remaining limitations

Surviving fixed universe, retrospective adjustment vintage, non-institutional
provider quality, upstream rights not independently verified, approximate
weight-target execution and costs, omitted taxes/impact/liquidity/funding/share
lots, drift between rebalances, potentially infeasible transitions, a zero
risk-free-rate assumption, short final period, multiple comparisons and limited
bootstrap stationarity are material. No empirical result is changed to satisfy
a positive-return target. The work is not peer reviewed.
