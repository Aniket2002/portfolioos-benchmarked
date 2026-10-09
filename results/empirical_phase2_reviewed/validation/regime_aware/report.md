# Historical validation: regime_aware

Executed sessions: 2018-01-02 to 2022-12-30 (1259 observations).

Benchmark: the declared monthly 60/40 policy, reset before the first session return of each month and drifted otherwise. Frictionless policy returns define active metrics; independently cost-adjusted policy returns are also exported. Each period starts endowed in policy holdings.

Decisions use the declared lagged information set; execution-close drift enters turnover and compliance accounting. Closing target fills and additive costs are research approximations.

Ordinary allocation comparisons satisfy their own rules. Active TE, sector, position and turnover mandates apply to optimized strategies at accepted rebalances; subsequent drift and realized risk can exceed target limits.

| Metric | Value |
|---|---|
| cumulative_return | 0.10865026356636887 |
| cagr | 0.020859627361549338 |
| annualized_volatility | 0.1323348570422546 |
| sharpe | 0.222444042246645 |
| sortino | 0.3012996757246269 |
| maximum_drawdown | -0.25315161796556285 |
| benchmark_cumulative_return | 0.17521019026801898 |
| tracking_error | 0.03250427275042325 |
| information_ratio | -0.33630772700038924 |
| annualized_arithmetic_active_return | -0.010931438086495535 |
| annualized_turnover | 2.394410146601189 |
| total_cost_fraction_sum | 0.011962549105440066 |
| compounded_cost_drag | 0.013324177490764644 |
| average_absolute_active_weight | 0.08201212313513652 |
| maximum_position | 0.37558142779603626 |
| average_estimated_tracking_error | 0.029816514988038837 |
| mean_ic | -0.06020202020202017 |
| median_ic | -0.054545454545454536 |
| ic_std | 0.4925048621663499 |
| ic_information_ratio | -0.12223639770217366 |
| positive_ic_fraction | 0.4666666666666667 |
| gross_wealth | 1.121974441057134 |
| net_wealth | 1.1086502635663689 |
| gross_cagr | 0.02330367269653255 |
| average_one_way_turnover | 0.009501627565877736 |
| average_rebalance_turnover | 0.19937581842400115 |
| average_active_share | 0.41006061567568264 |
| execution_constraint_violations | 0 |
| solver_failures | 0 |
| policy_frictionless_cagr | 0.032842851452639765 |
| policy_net_cagr | 0.032705103767938004 |
| net_active_vs_cost_adjusted_policy | -0.010797942072681085 |
| average_signal_capture | 0.546012599659319 |
| valid_capture_observations | 60 |
| excluded_capture_observations | 0 |

Signal capture is preference expression, not investment skill. IC is evaluated only after construction. No persistent-alpha claim is made. This is independent research, not peer-reviewed research.
