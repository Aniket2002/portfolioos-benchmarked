# Empirical extension: audit, protocol contract, and acceptance record

Status: infrastructure implemented; historical evaluation blocked. The supplied
attachment ends at “The detailed research specification follows below” and contains
no ETF identifiers, policy weights, historical periods, or empirical experiment
grids. No proposed dates or assets have been invented. No historical market data
have been downloaded, and no final historical holdout has been evaluated.

## Repository audit and implementation plan

The existing package already implements CVXPY/CLARABEL allocation, independent
constraint checks, Ledoit–Wolf covariance, three price signals, drift, turnover,
linear costs, attribution, metrics, reports, and synthetic TE/turnover/cost grids.
The scripts, tests, notebook, Streamlit layer, configurations, committed reports,
and GitHub Actions define a working synthetic study. Preserve them and extend the
canonical backtester rather than creating a second portfolio engine.

Gaps: input provenance was caller text only; previous-close information assumed a
same-close fill; no volatility regimes, policy strategy or simple competitors;
no separate empirical protocol freeze. Exact cash/share accounting, historical
point-in-time membership and exchange-calendar verification are still absent.

Implementation sequence: immutable historical bundle validation; opt-in information
lag and timing records; rule-based comparisons; expanding causal regimes; a
separate frozen-protocol scenario runner; integration tests and draft manuscript.
Existing synthetic defaults and tracked results are preserved. Work is on
`feature/empirical-research`.

## Historical bundle contract

Supply an untracked directory containing `prices.csv`, `actions.csv`, and
`manifest.json`. Prices have a session-date first column followed by exactly the
ten declared assets in protocol order. Values must be positive and finite; no
missing dates or assets are filled or silently removed. Leading inception gaps
require a documented research-period change, not backfilling.

Actions have `date,asset,type,value`, where type is `split` or `distribution` and
value is a positive split ratio or cash distribution. Preserve an empty ledger
with these headers only if the provider/source justifies that emptiness. The
validator checks structure, not completeness against an independent provider.
Prices must already be split and distribution adjusted; actions are not applied
a second time. Adjusted close is a total-return proxy with provider conventions,
not an executable price or a cash distribution accounting engine.

The manifest requires nonempty `source`, `source_url`, `retrieved_at` (timezone
included), `license`, `adjustment_convention`, `universe_selection`,
`survivorship_limitations`, `revision_policy`, `calendar`, `timezone`, and `sha256`.
The convention must be `split_and_distribution_adjusted_close`; SHA256 maps
`prices.csv` and `actions.csv` to the hashes of their original bytes. Preserve
retrieval vintage and source files. Hashes detect changes, not false attestations.
The calendar field is an attestation; missing whole exchange sessions are not yet
verified against an exchange calendar. Source licensing must permit the use.

## Protocol and reproduction

Provide JSON with `assets` (ten tickers), `policy_weights` (ticker-to-weight map),
`sectors` (ticker-to-asset-class map), `periods` (ordered, disjoint development,
validation, holdout start/end pairs), and `scenarios` (name-to-BacktestConfig map).
Every scenario must include an explicit `optimizer` map and `information_lag: 2`
or greater. Declare all scenarios before evaluation. The separate runner writes
`frozen_protocol.json` before reading price data, rejects changed protocols at the
same output root, and refuses to overwrite period outputs.

For ten assets, fully invested long-only allocation requires a position cap of
at least 10%; exactly 10% leaves only equal weight. A cap such as 25% permits
active portfolios but is a new research assumption, not the supplied proposal.
Policy weights and sector/TE/turnover constraints can still make a run infeasible.
The engine checks every rule-based target and stops on violation; no cap changes
occur automatically. All scenarios record configuration and failure messages.

Declare TE, turnover and cost scenarios by copying a baseline and varying one
setting. Declare fixed/regime comparisons with identical settings except
`regime_te_budgets`; declare signal ablations by changing `signal_weights` only.
Declare monthly/weekly schedule and covariance-lookback robustness similarly.
Supported competitors are `strategy: policy`, `equal_weight`, and
`inverse_volatility`; optimized allocation is the default. These rule-based
competitors obey the declared constraints rather than silently clipping weights.
The policy comparator is frictionless and resets monthly independent of strategy
schedule. A policy strategy charges its own turnover costs. Each period starts
with a separate benchmark endowment; these are separate evaluations, not one
continuous wealth path across all research periods.

```sh
python scripts/run_empirical.py --protocol configs/my_empirical_protocol.json --bundle data/my_market_bundle --output results/my_empirical_study --period development
python scripts/run_empirical.py --protocol configs/my_empirical_protocol.json --bundle data/my_market_bundle --output results/my_empirical_study --period validation
# Run once only after protocol review; this explicitly opens the final holdout.
python scripts/run_empirical.py --protocol configs/my_empirical_protocol.json --bundle data/my_market_bundle --output results/my_empirical_study --period holdout
```

The runner exports computed metrics, returns, holdings, optimization records,
eight figures per successful scenario, provenance, and `evaluation.json` with
all successes/failures. It makes no inference of statistical significance.
Protocol freezing is local write protection, not an independently registered
preregistration or proof that the researcher never viewed the holdout elsewhere.
Any earlier access must be disclosed; subsequent analyses are exploratory.

## Timing, regimes, and remaining execution limitations

For return date t and `information_lag: 2`, signals, external signals and covariance
end at t−2, execution is modeled at the close of t−1, and return accrues from t−1
to t. Lag 1 retains the legacy synthetic convention. Optimization records contain
information, execution, and return dates plus the effective TE budget and regime.

The allocation is still a weight-target simulation: sizing and turnover use actual
drifted execution-close holdings; policy snapshots are available through that
close. This is an idealized close-targeting approximation, not predetermined
share orders executable at a guaranteed closing price. Cash is implicitly zero;
costs use the existing additive NAV convention. Exact cash/share execution,
auction cutoffs, spreads, slippage, settlement, taxes, and corporate-action cash
flows remain out of scope and must precede trading-realism claims.

Regimes use the declared asset's trailing sample volatility (63 returns by
default), compared with the expanding 1/3 and 2/3 quantiles of strictly earlier
rolling volatilities (at least 252). Ties are normal. Only information-truncated
history is supplied. No HMM or full-sample percentiles are used. Fixed thresholds
and state-dependent TE caps are proposed mechanics, not demonstrated improvements.

## Verification and acceptance

Baseline before edits: 153 tests passed. New tests exercise byte tampering,
universe order, immutable freezes, execution-close signal mutations, regime
warmup/ties, varying TE compliance, rule-based accounting, explicit constraint
failure, and an end-to-end frozen-runner fixture. Fixture prices are synthetic
and cannot establish empirical market validity.

Final execution on local Python 3.14: 163 tests passed; package coverage 89.96%
(80% gate passed). Ruff lint and formatting checks passed. Synthetic demo smoke:
252 evaluation days, 13 rebalances. Synthetic frontier smoke: ten declared
scenarios (two TE, two turnover, two cost, four joint-grid), zero failures,
dataset fingerprint prefix `4eb06ae31278`. Artifacts are in the two scratch
directories named below. This local run does not substitute for executing the
GitHub Actions Python 3.10–3.12 matrix. LaTeX compilation was not performed.

Full synthetic regression run: 1,260 days and 59 rebalances, exported to
`results/empirical-extension-synthetic-regression`. Returns, strategy weights,
benchmark weights, and scores match the original HEAD backtester exactly when
both engines are executed in the current environment. An initial comparison
against committed CSVs at `atol=1e-9, rtol=1e-7` failed on tiny return differences
(maximum violating difference about 3.68e-8); the same-environment original-engine
comparison resolves this as a numerical environment difference rather than a
change in synthetic behavior. Committed results/configurations/CI are untouched.

Files added: `portfolioos/historical.py`, `portfolioos/regimes.py`,
`scripts/run_empirical.py`, `tests/test_empirical.py`, this document,
`docs/empirical_manuscript.tex`. Files changed: `portfolioos/backtest.py`,
`portfolioos/reporting.py`, and `README.md`. Existing CI checks are retained.

Run package validation and synthetic smoke experiments without overwriting the
canonical outputs:

```sh
python -m pytest -q --cov=portfolioos --cov-report=term-missing --cov-fail-under=80
python -m ruff check .
python -m ruff format --check .
python scripts/run_demo.py --config configs/demo.yaml --smoke-test --output results/empirical-extension-synthetic-smoke
python scripts/run_experiments.py --config configs/demo.yaml --smoke-test --output results/empirical-extension-frontier-smoke
```

No empirical frontiers, regime comparison, signal ablations or robustness results
are available. Required next inputs are the detailed proposal and a licensed,
complete historical bundle. The manuscript is an explicitly incomplete draft.
