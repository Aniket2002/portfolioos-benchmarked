# Historical validation: cost_25bps

Executed sessions: 2018-01-02 to 2022-12-30 (1259 observations).

Benchmark: the declared monthly 60/40 policy, reset before the first session return of each month and drifted otherwise. Frictionless policy returns define active metrics; independently cost-adjusted policy returns are also exported. Each period starts endowed in policy holdings.

Decisions use the declared lagged information set; execution-close drift enters turnover and compliance accounting. Closing target fills and additive costs are research approximations.

Ordinary allocation comparisons satisfy their own rules. Active TE, sector, position and turnover mandates apply to optimized strategies at accepted rebalances; subsequent drift and realized risk can exceed target limits.

| Metric | Value |
|---|---|
| cumulative_return | 0.08567555716576858 |
| cagr | 0.016589648676889723 |
| annualized_volatility | 0.13212189566130292 |
| sharpe | 0.19086200848003163 |
| sortino | 0.2582466928100775 |
| maximum_drawdown | -0.25326487017224997 |
| benchmark_cumulative_return | 0.17521019026801898 |
| tracking_error | 0.03301386318372313 |
| information_ratio | -0.45894320706070013 |
| annualized_arithmetic_active_return | -0.01515148824700107 |
| annualized_turnover | 2.449759605599592 |
| total_cost_fraction_sum | 0.030597691899304433 |
| compounded_cost_drag | 0.0336918137857285 |
| average_absolute_active_weight | 0.08323760978447074 |
| maximum_position | 0.37558142779603637 |
| average_estimated_tracking_error | 0.03112483308673942 |
| mean_ic | -0.06020202020202017 |
| median_ic | -0.054545454545454536 |
| ic_std | 0.4925048621663499 |
| ic_information_ratio | -0.12223639770217366 |
| positive_ic_fraction | 0.4666666666666667 |
| gross_wealth | 1.1193673709514955 |
| net_wealth | 1.0856755571657686 |
| gross_cagr | 0.02282729321928878 |
| average_one_way_turnover | 0.009721268276188858 |
| average_rebalance_turnover | 0.20398461266202958 |
| average_active_share | 0.4161880489223537 |
| execution_constraint_violations | 0 |
| solver_failures | 0 |
| policy_frictionless_cagr | 0.032842851452639765 |
| policy_net_cagr | 0.03249851277170146 |
| net_active_vs_cost_adjusted_policy | -0.014817748212464944 |
| average_signal_capture | 0.5479622475517847 |
| valid_capture_observations | 60 |
| excluded_capture_observations | 0 |

Signal capture is preference expression, not investment skill. IC is evaluated only after construction. No persistent-alpha claim is made. This is independent research, not peer-reviewed research.
