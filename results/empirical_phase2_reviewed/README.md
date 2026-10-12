# Frozen empirical study

Use the [curated research index](../../docs/empirical_research_index.md) to navigate
the [paper](../../docs/empirical_manuscript.pdf),
[methodology and reproduction limits](../../docs/empirical_phase2.md),
[results report](report.md), [performance table](all_performance.csv) and
[scenario status](experiment_status.md).

The `figures/` directory contains the eight publication figures. Detailed
development, validation and holdout directories retain the period/scenario
ledgers and failure evidence for audit. The index explains the pre-holdout reserve
revision and links the frozen protocol and verification records.

The original market-data bundle is local and not publicly available. Exact-input
reproduction requires that bundle; a fresh retrieval supports approximate
replication with potentially revised historical prices. Daily portfolio returns
and decision/capture/IC ledgers also permit independent table-arithmetic checks:

```powershell
python scripts/verify_public_empirical_tables.py --diagnostics results/empirical_review_response
```

The [post-holdout review diagnostics](../empirical_review_response/README.md)
provide asset-class attribution, cap-activity counts, a binding 3% high-state
experiment and the Table 5 precision audit. The original model and evaluation
ledgers are preserved. This study is independent and not peer reviewed.
