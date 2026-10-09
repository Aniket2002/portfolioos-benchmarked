# Historical holdout: regime_aware

Executed sessions: 2023-01-03 to 2026-09-30 (939 observations).

Benchmark: the declared monthly 60/40 policy, reset before the first session return of each month and drifted otherwise. Frictionless policy returns define active metrics; independently cost-adjusted policy returns are also exported. Each period starts endowed in policy holdings.

Decisions use the declared lagged information set; execution-close drift enters turnover and compliance accounting. Closing target fills and additive costs are research approximations.

Ordinary allocation comparisons satisfy their own rules. Active TE, sector, position and turnover mandates apply to optimized strategies at accepted rebalances; subsequent drift and realized risk can exceed target limits.

| Metric | Value |
|---|---|
| cumulative_return | 0.6135107583951322 |
| cagr | 0.13699842126547646 |
| annualized_volatility | 0.09962808774284836 |
| sharpe | 1.3386562169511813 |
| sortino | 2.046255899704214 |
| maximum_drawdown | -0.11088867140404135 |
| benchmark_cumulative_return | 0.5420208243315694 |
| tracking_error | 0.02772869027911789 |
| information_ratio | 0.4393069636867506 |
| annualized_arithmetic_active_return | 0.012181406733529597 |
| annualized_turnover | 2.3185306638073326 |
| total_cost_fraction_sum | 0.008639286878234464 |
| compounded_cost_drag | 0.014000098612112044 |
| average_absolute_active_weight | 0.10677833558460936 |
| maximum_position | 0.3664234003775937 |
| average_estimated_tracking_error | 0.03396577603483189 |
| mean_ic | -0.018989898989898998 |
| median_ic | 0.0303030303030303 |
| ic_std | 0.43755118479877053 |
| ic_information_ratio | -0.04340040582596626 |
| positive_ic_fraction | 0.5111111111111111 |
| gross_wealth | 1.6275108570072447 |
| net_wealth | 1.6135107583951322 |
| gross_cagr | 0.13963766949406398 |
| average_one_way_turnover | 0.009200518507171955 |
| average_rebalance_turnover | 0.19198415284965473 |
| average_active_share | 0.5338916779230468 |
| execution_constraint_violations | 0 |
| solver_failures | 0 |
| policy_frictionless_cagr | 0.12325378717673874 |
| policy_net_cagr | 0.12315053279029109 |
| net_active_vs_cost_adjusted_policy | 0.012273402466381254 |
| average_signal_capture | 0.7291194016978679 |
| valid_capture_observations | 45 |
| excluded_capture_observations | 0 |

Signal capture is preference expression, not investment skill. IC is evaluated only after construction. No persistent-alpha claim is made. This is independent research, not peer-reviewed research.
