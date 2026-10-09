# Historical holdout: lag_3

Executed sessions: 2023-01-03 to 2026-09-30 (939 observations).

Benchmark: the declared monthly 60/40 policy, reset before the first session return of each month and drifted otherwise. Frictionless policy returns define active metrics; independently cost-adjusted policy returns are also exported. Each period starts endowed in policy holdings.

Decisions use the declared lagged information set; execution-close drift enters turnover and compliance accounting. Closing target fills and additive costs are research approximations.

Ordinary allocation comparisons satisfy their own rules. Active TE, sector, position and turnover mandates apply to optimized strategies at accepted rebalances; subsequent drift and realized risk can exceed target limits.

| Metric | Value |
|---|---|
| cumulative_return | 0.6103645307242209 |
| cagr | 0.1364030016788631 |
| annualized_volatility | 0.09705008924661762 |
| sharpe | 1.3662138190625792 |
| sortino | 2.0925003403694156 |
| maximum_drawdown | -0.11241778087507126 |
| benchmark_cumulative_return | 0.5420208243315694 |
| tracking_error | 0.027773860814433945 |
| information_ratio | 0.41063145090964204 |
| annualized_arithmetic_active_return | 0.011404820763593462 |
| annualized_turnover | 2.3174512632319355 |
| total_cost_fraction_sum | 0.008635264826090425 |
| compounded_cost_drag | 0.01396477725543721 |
| average_absolute_active_weight | 0.10551087637570557 |
| maximum_position | 0.3654940241369738 |
| average_estimated_tracking_error | 0.033367928678135136 |
| mean_ic | -0.02599326599326601 |
| median_ic | 0.01818181818181818 |
| ic_std | 0.4369383692575689 |
| ic_information_ratio | -0.05948954777634406 |
| positive_ic_fraction | 0.5111111111111111 |
| gross_wealth | 1.624329307979658 |
| net_wealth | 1.610364530724221 |
| gross_cagr | 0.1390393580906284 |
| average_one_way_turnover | 0.009196235171555298 |
| average_rebalance_turnover | 0.19189477391312057 |
| average_active_share | 0.5275543818785279 |
| execution_constraint_violations | 0 |
| solver_failures | 0 |
| policy_frictionless_cagr | 0.12325378717673874 |
| policy_net_cagr | 0.12315053279029109 |
| net_active_vs_cost_adjusted_policy | 0.011496816496445116 |
| average_signal_capture | 0.7381805837753326 |
| valid_capture_observations | 45 |
| excluded_capture_observations | 0 |

Signal capture is preference expression, not investment skill. IC is evaluated only after construction. No persistent-alpha claim is made. This is independent research, not peer-reviewed research.
