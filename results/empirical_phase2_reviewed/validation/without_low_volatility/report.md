# Historical validation: without_low_volatility

Executed sessions: 2018-01-02 to 2022-12-30 (1259 observations).

Benchmark: the declared monthly 60/40 policy, reset before the first session return of each month and drifted otherwise. Frictionless policy returns define active metrics; independently cost-adjusted policy returns are also exported. Each period starts endowed in policy holdings.

Decisions use the declared lagged information set; execution-close drift enters turnover and compliance accounting. Closing target fills and additive costs are research approximations.

Ordinary allocation comparisons satisfy their own rules. Active TE, sector, position and turnover mandates apply to optimized strategies at accepted rebalances; subsequent drift and realized risk can exceed target limits.

| Metric | Value |
|---|---|
| cumulative_return | 0.06729511861466864 |
| cagr | 0.013121187287385983 |
| annualized_volatility | 0.13888540551108858 |
| sharpe | 0.1635625932957234 |
| sortino | 0.22026508198537514 |
| maximum_drawdown | -0.26341293163723956 |
| benchmark_cumulative_return | 0.17521019026801898 |
| tracking_error | 0.04988632706858772 |
| information_ratio | -0.35384608485036856 |
| annualized_arithmetic_active_return | -0.017652081520784728 |
| annualized_turnover | 2.478177604583063 |
| total_cost_fraction_sum | 0.012381053984801887 |
| compounded_cost_drag | 0.013253378112379144 |
| average_absolute_active_weight | 0.11246725689260961 |
| maximum_position | 0.3806183068221671 |
| average_estimated_tracking_error | 0.04772071812115169 |
| mean_ic | -0.03555555555555555 |
| median_ic | -0.030303030303030297 |
| ic_std | 0.5238279180660921 |
| ic_information_ratio | -0.06787640431006858 |
| positive_ic_fraction | 0.45 |
| gross_wealth | 1.080548496727048 |
| net_wealth | 1.0672951186146686 |
| gross_cagr | 0.01562690508444753 |
| average_one_way_turnover | 0.009834038113424851 |
| average_rebalance_turnover | 0.20635089974669807 |
| average_active_share | 0.5623362844630481 |
| execution_constraint_violations | 0 |
| solver_failures | 0 |
| policy_frictionless_cagr | 0.032842851452639765 |
| policy_net_cagr | 0.032705103767938004 |
| net_active_vs_cost_adjusted_policy | -0.017518585506970278 |
| average_signal_capture | 0.5758959526965103 |
| valid_capture_observations | 60 |
| excluded_capture_observations | 0 |

Signal capture is preference expression, not investment skill. IC is evaluated only after construction. No persistent-alpha claim is made. This is independent research, not peer-reviewed research.
