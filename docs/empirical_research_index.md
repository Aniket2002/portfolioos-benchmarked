# Empirical research: reader's guide

Start with the [manuscript PDF](empirical_manuscript.pdf) and
[methodology, provenance and reproduction guide](empirical_phase2.md).
This ten-ETF historical study is independent research and has not been peer reviewed.
The [SSRN preparation note](ssrn_preparation.md) explains the polished working-paper
layout, AI disclosure and author metadata needed before submission.
The separate [synthetic study](../results/research_tradeoffs/report.md) explores
portfolio mechanics on deterministic data.

## Findings and figures

| Read or inspect | Purpose |
|---|---|
| [Results report](../results/empirical_phase2_reviewed/report.md) | Performance, uncertainty, all seven experiment groups and interpretation |
| [All performance rows](../results/empirical_phase2_reviewed/all_performance.csv) | Machine-readable results for every period/scenario, including failed paths |
| [Scenario status](../results/empirical_phase2_reviewed/experiment_status.md) | All 21 scenarios; 61 of 63 period/scenario paths completed |
| [Net wealth](../results/empirical_phase2_reviewed/figures/wealth.png) and [drawdowns](../results/empirical_phase2_reviewed/figures/drawdowns.png) | Primary strategies and allocation comparisons |
| [TE frontier](../results/empirical_phase2_reviewed/figures/te_frontier.png) and [turnover frontier](../results/empirical_phase2_reviewed/figures/turnover_frontier.png) | Sensitivity under the tested settings; the 8%/12% TE limits were largely non-binding |
| [Cost sensitivity](../results/empirical_phase2_reviewed/figures/cost_sensitivity.png) | Fees applied to identical holdings and trades |
| [Fixed versus regime](../results/empirical_phase2_reviewed/figures/fixed_vs_regime.png) and [regime timeline](../results/empirical_phase2_reviewed/figures/regime_timeline.png) | Small, inconclusive regime effects and causal volatility labels |
| [Ablations and robustness](../results/empirical_phase2_reviewed/figures/ablation_robustness.png) | Declared alternatives and visible failures |

The primary model underperformed the policy in development and validation.
Holdout annualized arithmetic active return was 1.23%, with a descriptive
95% block interval of [−1.55%, 3.90%]. Turnover restricted signal expression more
than the tested TE range under this specification; the result does not establish
a general hierarchy of portfolio constraints or persistent alpha.

## Specification and design history

| Record | Purpose |
|---|---|
| [Declared configuration](../configs/empirical_phase2.json) | Universe, model, mandates, periods and scenario groups |
| [Frozen protocol lock](../results/empirical_phase2_reviewed/final_protocol_lock.json) | Frozen model commit, dataset identity, protocol and pre-holdout evidence hashes |
| [Development/validation review](../results/empirical_phase2_reviewed/review.json) | Recorded design revision and review before freezing |
| [Initial development failures](../results/empirical_phase2/development/evaluation.json) and [initial validation failures](../results/empirical_phase2/validation/evaluation.json) | Original zero-reserve execution failures, retained as evidence |
| [Holdout access marker](../results/empirical_phase2_reviewed/holdout_access.json) | Single access after the corrected specification was frozen |

After inspecting development/validation failures, Codex introduced formation
reserves of 2 percentage points for turnover, 1 for sector exposure and 0.1 for
annual TE. Execution mandates stayed unchanged. This was a correction informed
by pre-holdout outcomes, not the untouched initial specification. The corrected
model was frozen before holdout; remaining weekly sector failures in development
and validation were retained without full-period performance.

## Reproducibility and audit trail

The original provider bundle is local and not publicly available. Exact-input
reproduction requires that vintage, the frozen model and compatible dependencies;
numerical equality remains subject to solver tolerances. Dataset hashes establish
identity but cannot supply the missing inputs. Fresh acquisition supports
approximate replication using a newly labelled vintage, whose historical prices
and results may differ. See the [two reproduction routes](empirical_phase2.md#external-reproducibility)
before running commands.

| Audit record | Purpose |
|---|---|
| [Data quality and provenance](../results/empirical_phase2_reviewed/data_quality.md) | Price/action fingerprints, calendar checks and adjustment reconciliation |
| [Pre-holdout verification](../results/empirical_phase2_reviewed/verification.json) | Executed tests and regression evidence used for the freeze |
| [Original-vintage validation check](../results/empirical_phase2_reviewed/reproducibility_verification.json) | Local fixed/regime reproduction; requires the original bundle |
| [Accounting audit](../results/empirical_phase2_reviewed/accounting_audit.json) | Independent reconciliation of all 61 completed saved paths |
| [Artifact fingerprints](../results/empirical_phase2_reviewed/artifact_hashes.json) | File identity for the published evidence and presentation |
| [Complete file inventory](empirical_phase2_files.txt) | Tracked changes relative to the original feature commit |

Detailed ledgers remain in
[`results/empirical_phase2_reviewed`](../results/empirical_phase2_reviewed/), arranged
by development, validation and holdout, then scenario. Each contains status,
returns, optimization diagnostics, capture, uncertainty and summary artifacts.
Stopped paths preserve partial evidence. Full local trade paths and original
provider responses remain local. This guide provides a short reading route while
preserving the complete tracked audit trail.
