# Review diagnostics, 12 October 2026

These analyses were added after the frozen holdout evaluation. The sole new
portfolio specification uses an 8% normal / 3% high-state tracking-error mandate
(7.9% / 2.9% at formation after the existing reserve). It retains the objective,
all other mandates, information lag and rebalance calendar. It is exploratory,
not a new primary model or an untouched holdout test.

| Evidence | Purpose |
|---|---|
| [Diagnostic protocol](diagnostic_protocol.json) | Specification recorded before diagnostic execution; links the original protocol lock |
| [Cap activity](cap_activity.csv) | Actual formation-cap activity at a tolerance of 0.1 basis point of annual TE |
| [Class attribution](asset_class_attribution.csv) | Fixed-risk arithmetic active contributions and mean active weights in all three periods |
| [Security attribution summary](security_attribution_summary.csv) | Period-level contributions by ETF; no individual ETF daily returns |
| [Holdout position context](holdout_position_context.json) and [normalized endpoints](holdout_position_endpoints.csv) | HYG/GLD contributions, exact return window, preceding-close baseline, cumulative returns and fingerprints |
| [Tighter-cap results](tighter_cap_results.json) | Executed performance and paired 21-session circular-block intervals |
| [Table audit](table5_audit.json) | Full-precision low-volatility-omission TE and independent pre-holdout path reproduction |
| [Original evidence hashes](source_evidence_hashes.json) | Original protocol/access records, evaluations and daily portfolio-return ledgers |
| [Public verification record](public_verification.json) | Isolated verification without provider inputs, including rejection of altered tables and fingerprints |

The 8% and 12% caps bind at zero recorded formation decisions. The 5% high-state
mandate binds at 2/7, 5/21 and 2/10 high-state rebalances; 3% binds at 5/7, 11/21
and 7/10. These compare ex-ante formation risk with the reserved formation cap,
not realized full-period TE. The quadratic risk penalty and other constraints
already contain active risk at the larger budgets.
The budgets differ on only 38 decision dates, of which 23 bind at 3%.
The test is underpowered for a general regime-effect claim; narrow intervals on
the original comparison reflect similar paths, not many independent decisions.

In holdout, equities contribute −1.684, fixed income +2.014, gold +1.072 and real
estate +0.063 percentage points/year; trading costs subtract 0.231, reconciling
to +1.233 net active return. Equity is underweight by 5.96 percentage points on
average. HYG contributes +2.210 and GLD +1.072. These are arithmetic holding
contributions, not causal effects, risk-adjusted alpha or a CAGR decomposition.
The holdout gain is largely long high-yield credit and gold: these two positions
contribute +3.28 against +1.23 net and have zero policy weights. GLD's 124.5%
cumulative adjusted-price rise is a likely driver of its contribution in this
window, while HYG has the larger arithmetic contribution. Rank IC covers all ten
assets, whereas positive active P&L is concentrated in these two holdings.

The 124.5% compounds all 939 daily adjusted returns dated January 3, 2023 through
September 30, 2026. It includes January 3's return from the December 30, 2022 close,
consistent with the portfolio-return ledger. A January 3-close-to-September
30-close calculation excludes that first return and gives 122.6%. The public
endpoint ledger uses normalized adjusted closes at the baseline, first return
close and final close; it contains no raw prices or full individual ETF series.
The context JSON records its fingerprint, date convention and original-data hash.

Weekly rebalancing has the highest declared holdout net CAGR (14.99%, +2.38%
arithmetic active), but both earlier paths fail execution checks. There is no
complete development/validation evidence validating a repeatable weekly
advantage. Figure 8 highlights the failed paths and hatches the weekly holdout bar.

The added 3% high-state specification produces holdout active return of +0.886%
and realized TE of 2.578%. Its paired return difference from fixed risk is
−0.347 percentage points/year, with a 95% interval [−1.025, +0.250]. All three
paired intervals include zero.

The two reported 4.989% low-volatility-omission TE entries are a rounding
coincidence: development is 4.988843319% and validation is 4.988632707%.
Independent reruns of both pre-holdout paths match their distinct saved returns.

Run from the repository root with NumPy and pandas installed:

```powershell
python scripts/verify_public_empirical_tables.py --diagnostics results/empirical_review_response
```

This checks all 61 successful original paths, preserves the two failures, and
verifies the new diagnostic results, attribution reconciliation and evidence
hashes, including HYG/GLD endpoint arithmetic and exact holdout dates.
It needs no provider data or optimizer. Daily portfolio returns,
cost/turnover records, optimization, capture and forward-IC ledgers support
verification of table arithmetic. Independent source-price correctness,
class-attribution reconstruction from asset returns, and reconstruction of
portfolio decisions still require the original bundle. Individual ETF daily
returns remain local because upstream redistribution rights are unverified.

With access to the original bundle, independently recompute both cumulative
asset returns from all adjusted daily observations and reconcile the normalized
endpoints to that series:

```powershell
python scripts/verify_public_empirical_tables.py --diagnostics results/empirical_review_response --bundle data/phase2-tigzig-20261008
```

The optional check first requires the frozen price fingerprint. It reads prices
without invoking the optimizer; fresh provider vintages cannot pass as the
original input. Public endpoint arithmetic alone does not establish source-price
correctness.

To regenerate the diagnostics with the original bundle, use a new directory:

```powershell
python scripts/review_empirical_findings.py --results results/empirical_phase2_reviewed --bundle data/phase2-tigzig-20261008 --output results/empirical-review-new
```

The diagnostic runner refuses an existing output directory. Rebuild the revised
presentation from executed evidence without rerunning the original portfolios:

```powershell
python scripts/build_empirical_report.py --results results/empirical_phase2_reviewed --bundle data/phase2-tigzig-20261008 --diagnostics results/empirical_review_response
tectonic -X compile docs/empirical_manuscript.tex --outdir docs
```
