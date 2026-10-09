# Historical holdout: sample_covariance

Executed sessions: 2023-01-03 to 2026-09-30 (939 observations).

Benchmark: the declared monthly 60/40 policy, reset before the first session return of each month and drifted otherwise. Frictionless policy returns define active metrics; independently cost-adjusted policy returns are also exported. Each period starts endowed in policy holdings.

Decisions use the declared lagged information set; execution-close drift enters turnover and compliance accounting. Closing target fills and additive costs are research approximations.

Ordinary allocation comparisons satisfy their own rules. Active TE, sector, position and turnover mandates apply to optimized strategies at accepted rebalances; subsequent drift and realized risk can exceed target limits.

| Metric | Value |
|---|---|
| cumulative_return | 0.6167783209525008 |
| cagr | 0.13761590479480845 |
| annualized_volatility | 0.09970557742545309 |
| sharpe | 1.3431407325819698 |
| sortino | 2.053782973319305 |
| maximum_drawdown | -0.11088867140552561 |
| benchmark_cumulative_return | 0.5420208243315694 |
| tracking_error | 0.027846996011630865 |
| information_ratio | 0.45722238743530214 |
| annualized_arithmetic_active_return | 0.0127322699993392 |
| annualized_turnover | 2.3116859312434817 |
| total_cost_fraction_sum | 0.008613782100942975 |
| compounded_cost_drag | 0.01398673329063116 |
| average_absolute_active_weight | 0.10794534486370337 |
| maximum_position | 0.3664233989731065 |
| average_estimated_tracking_error | 0.031121388858676005 |
| mean_ic | -0.018989898989898998 |
| median_ic | 0.0303030303030303 |
| ic_std | 0.43755118479877053 |
| ic_information_ratio | -0.04340040582596626 |
| positive_ic_fraction | 0.5111111111111111 |
| gross_wealth | 1.630765054243133 |
| net_wealth | 1.6167783209525008 |
| gross_cagr | 0.1402487582741887 |
| average_one_way_turnover | 0.009173356870013817 |
| average_rebalance_turnover | 0.19141738002095496 |
| average_active_share | 0.5397267243185168 |
| execution_constraint_violations | 0 |
| solver_failures | 0 |
| policy_frictionless_cagr | 0.12325378717673874 |
| policy_net_cagr | 0.12315053279029109 |
| net_active_vs_cost_adjusted_policy | 0.012824265732190863 |
| average_signal_capture | 0.7300229808332569 |
| valid_capture_observations | 45 |
| excluded_capture_observations | 0 |

Signal capture is preference expression, not investment skill. IC is evaluated only after construction. No persistent-alpha claim is made. This is independent research, not peer-reviewed research.
