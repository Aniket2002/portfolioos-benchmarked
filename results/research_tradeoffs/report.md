# Portfolio implementation trade-off research

**SYNTHETIC RESEARCH EXPERIMENT**

These experiments demonstrate portfolio-construction mechanics. They are not evidence that the signals earn persistent real-world alpha.

## Research question

What is the trade-off between signal capture, benchmark-relative risk and implementation cost in systematic portfolio construction?

Signal capture is the active signal exposure `(w - b)'s` divided by exposure in
the signal-expression reference portfolio. The reference retains full investment,
long-only weights, and the baseline position cap, while removing risk/sector/turnover
compression. It uses the same scores and information dates. It is a measurement
portfolio, not an optimal alpha portfolio or a claim about investability.

## Findings from the synthetic experiment

- Changing the annual TE cap from 4% to 12% changed average signal capture from 0.955 to 0.964 and average active share from 62.35% to 64.36%.
- Changing the one-way turnover limit from 10% to 50% changed average signal capture from 0.846 to 0.974; realized average rebalance turnover changed from 10.00% to 28.86%.
- Raising the cost assumption from 0 to 40 bps left annualized gross active return at -0.83% and changed annualized net active return from -0.83% to -2.05%.
- Across the tested TE budgets, the descriptive correlation between average signal capture and realized net active return was positive (1.000). This synthetic sensitivity is not evidence of skill, alpha, causality, or statistical significance.
- 0 tested scenarios failed before completion.

These comparisons are controlled sensitivities. They do not establish causality or
statistical significance. High signal capture can coexist with poor realized returns.
Negative active results remain part of the evidence shown in the CSV tables.
