# Historical holdout: without_low_volatility

Executed sessions: 2023-01-03 to 2026-09-30 (939 observations).

Benchmark: the declared monthly 60/40 policy, reset before the first session return of each month and drifted otherwise. Frictionless policy returns define active metrics; independently cost-adjusted policy returns are also exported. Each period starts endowed in policy holdings.

Decisions use the declared lagged information set; execution-close drift enters turnover and compliance accounting. Closing target fills and additive costs are research approximations.

Ordinary allocation comparisons satisfy their own rules. Active TE, sector, position and turnover mandates apply to optimized strategies at accepted rebalances; subsequent drift and realized risk can exceed target limits.

| Metric | Value |
|---|---|
| cumulative_return | 0.640224635287268 |
| cagr | 0.14202007244990544 |
| annualized_volatility | 0.12069337601328228 |
| sharpe | 1.1608014705428866 |
| sortino | 1.7005654029250095 |
| maximum_drawdown | -0.13563799088456996 |
| benchmark_cumulative_return | 0.5420208243315694 |
| tracking_error | 0.04250151162280981 |
| information_ratio | 0.4450358430183526 |
| annualized_arithmetic_active_return | 0.018914696054611473 |
| annualized_turnover | 2.531136760292964 |
| total_cost_fraction_sum | 0.00943149769013926 |
| compounded_cost_drag | 0.015535487160322603 |
| average_absolute_active_weight | 0.12240525758478278 |
| maximum_position | 0.37154693417592305 |
| average_estimated_tracking_error | 0.0426536951568014 |
| mean_ic | 0.0962962962962963 |
| median_ic | 0.1515151515151515 |
| ic_std | 0.4156754495307044 |
| ic_information_ratio | 0.23166221725390412 |
| positive_ic_fraction | 0.6222222222222222 |
| gross_wealth | 1.655760122447591 |
| net_wealth | 1.640224635287268 |
| gross_cagr | 0.1449129567310501 |
| average_one_way_turnover | 0.010044193493226048 |
| average_rebalance_turnover | 0.20958883755865026 |
| average_active_share | 0.612026287923914 |
| execution_constraint_violations | 0 |
| solver_failures | 0 |
| policy_frictionless_cagr | 0.12325378717673874 |
| policy_net_cagr | 0.12315053279029109 |
| net_active_vs_cost_adjusted_policy | 0.019006691787463132 |
| average_signal_capture | 0.5941489670947496 |
| valid_capture_observations | 45 |
| excluded_capture_observations | 0 |

Signal capture is preference expression, not investment skill. IC is evaluated only after construction. No persistent-alpha claim is made. This is independent research, not peer-reviewed research.
