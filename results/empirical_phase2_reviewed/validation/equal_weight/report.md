# Historical validation: equal_weight

Executed sessions: 2018-01-02 to 2022-12-30 (1259 observations).

Benchmark: the declared monthly 60/40 policy, reset before the first session return of each month and drifted otherwise. Frictionless policy returns define active metrics; independently cost-adjusted policy returns are also exported. Each period starts endowed in policy holdings.

Decisions use the declared lagged information set; execution-close drift enters turnover and compliance accounting. Closing target fills and additive costs are research approximations.

Ordinary allocation comparisons satisfy their own rules. Active TE, sector, position and turnover mandates apply to optimized strategies at accepted rebalances; subsequent drift and realized risk can exceed target limits.

| Metric | Value |
|---|---|
| cumulative_return | 0.1447701696606476 |
| cagr | 0.027431764888455 |
| annualized_volatility | 0.11913523015942575 |
| sharpe | 0.2870062979505295 |
| sortino | 0.3861472227667391 |
| maximum_drawdown | -0.24063788336724024 |
| benchmark_cumulative_return | 0.17521019026801898 |
| tracking_error | 0.0275155320145343 |
| information_ratio | -0.2244542191771253 |
| annualized_arithmetic_active_return | -0.00617597725356549 |
| annualized_turnover | 0.22590599221597665 |
| total_cost_fraction_sum | 0.00112863350872982 |
| compounded_cost_drag | 0.0012907540898146053 |
| average_absolute_active_weight | 0.08006971560157722 |
| maximum_position | 0.12811044400295518 |
| average_estimated_tracking_error | 0.027596711388460152 |
| mean_ic | -0.06020202020202017 |
| median_ic | -0.054545454545454536 |
| ic_std | 0.4925048621663499 |
| ic_information_ratio | -0.12223639770217366 |
| positive_ic_fraction | 0.4666666666666667 |
| gross_wealth | 1.1460609237504622 |
| net_wealth | 1.1447701696606476 |
| gross_cagr | 0.027663534910149945 |
| average_one_way_turnover | 0.0008964523500633993 |
| average_rebalance_turnover | 0.018810558478830335 |
| average_active_share | 0.40034857800788604 |
| execution_constraint_violations | 0 |
| solver_failures | 0 |
| policy_frictionless_cagr | 0.032842851452639765 |
| policy_net_cagr | 0.032705103767938004 |
| net_active_vs_cost_adjusted_policy | -0.006042481239751041 |
| average_signal_capture | undefined |
| valid_capture_observations | 0 |
| excluded_capture_observations | 0 |

Signal capture is preference expression, not investment skill. IC is evaluated only after construction. No persistent-alpha claim is made. This is independent research, not peer-reviewed research.
