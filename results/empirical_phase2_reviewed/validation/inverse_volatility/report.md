# Historical validation: inverse_volatility

Executed sessions: 2018-01-02 to 2022-12-30 (1259 observations).

Benchmark: the declared monthly 60/40 policy, reset before the first session return of each month and drifted otherwise. Frictionless policy returns define active metrics; independently cost-adjusted policy returns are also exported. Each period starts endowed in policy holdings.

Decisions use the declared lagged information set; execution-close drift enters turnover and compliance accounting. Closing target fills and additive costs are research approximations.

Ordinary allocation comparisons satisfy their own rules. Active TE, sector, position and turnover mandates apply to optimized strategies at accepted rebalances; subsequent drift and realized risk can exceed target limits.

| Metric | Value |
|---|---|
| cumulative_return | 0.0719143535089164 |
| cagr | 0.01399732289731026 |
| annualized_volatility | 0.09137816861777845 |
| sharpe | 0.19793169145333836 |
| sortino | 0.2665314314374283 |
| maximum_drawdown | -0.22547465552663826 |
| benchmark_cumulative_return | 0.17521019026801898 |
| tracking_error | 0.054360999552892766 |
| information_ratio | -0.4098876643907402 |
| annualized_arithmetic_active_return | -0.02228190314068129 |
| annualized_turnover | 0.6083195339090911 |
| total_cost_fraction_sum | 0.0030391837031410545 |
| compounded_cost_drag | 0.0032611009247112133 |
| average_absolute_active_weight | 0.07891020906967577 |
| maximum_position | 0.3502740542675068 |
| average_estimated_tracking_error | 0.05172850094937407 |
| mean_ic | -0.06020202020202017 |
| median_ic | -0.054545454545454536 |
| ic_std | 0.4925048621663499 |
| ic_information_ratio | -0.12223639770217366 |
| positive_ic_fraction | 0.4666666666666667 |
| gross_wealth | 1.0751754544336276 |
| net_wealth | 1.0719143535089164 |
| gross_cagr | 0.014614042872010291 |
| average_one_way_turnover | 0.002413966404401155 |
| average_rebalance_turnover | 0.05065306171901758 |
| average_active_share | 0.3945510453483789 |
| execution_constraint_violations | 0 |
| solver_failures | 0 |
| policy_frictionless_cagr | 0.032842851452639765 |
| policy_net_cagr | 0.032705103767938004 |
| net_active_vs_cost_adjusted_policy | -0.02214840712686683 |
| average_signal_capture | undefined |
| valid_capture_observations | 0 |
| excluded_capture_observations | 0 |

Signal capture is preference expression, not investment skill. IC is evaluated only after construction. No persistent-alpha claim is made. This is independent research, not peer-reviewed research.
