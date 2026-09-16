# Predeclared synthetic-seed robustness study

**SYNTHETIC DESCRIPTIVE ROBUSTNESS — NOT EMPIRICAL MARKET VALIDATION**

This study used all 20 predeclared seeds, 40–59, with every non-seed setting fixed.
It is not a sampling distribution of market outcomes and provides no statistical
significance, persistent-alpha, causal, or real-market-performance evidence.

## Result

- Classification: **STRONG**
- `delta_turnover > delta_TE`: 18/20 (90%)
- Median dominance delta: 0.136174
- All scenarios complete: False

| Measure | n | Mean | Median | Std. dev. | Min | 25th pct. | 75th pct. | Max |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| delta_TE | 18 | 0.010429 | 0.008402 | 0.005634 | 0.003290 | 0.006800 | 0.013573 | 0.021290 |
| delta_turnover | 20 | 0.147857 | 0.143373 | 0.016945 | 0.125271 | 0.136281 | 0.155715 | 0.192077 |
| dominance_delta | 18 | 0.134827 | 0.136174 | 0.015492 | 0.104423 | 0.121461 | 0.144640 | 0.161785 |

Both incomplete seeds are retained. Their unavailable TE comparisons count against
the 20-seed dominance fraction. All 20 turnover deltas were positive; all 18
completed TE deltas were positive. No p-values or confidence intervals are used.

Allowed interpretation: Across 20 predeclared synthetic seeds, turnover generally constrained signal expression more than the tested tracking-error range.

Seed 42 remains the canonical illustrative case. Signal capture measures alignment
with the chosen synthetic signal, not alpha, forecast accuracy, return, skill, or
predictive power. Per-seed values and reversals are retained in `seed_results.csv`.
