# Historical holdout: cost_40bps

Executed sessions: 2023-01-03 to 2026-09-30 (939 observations).

Benchmark: the declared monthly 60/40 policy, reset before the first session return of each month and drifted otherwise. Frictionless policy returns define active metrics; independently cost-adjusted policy returns are also exported. Each period starts endowed in policy holdings.

Decisions use the declared lagged information set; execution-close drift enters turnover and compliance accounting. Closing target fills and additive costs are research approximations.

Ordinary allocation comparisons satisfy their own rules. Active TE, sector, position and turnover mandates apply to optimized strategies at accepted rebalances; subsequent drift and realized risk can exceed target limits.

| Metric | Value |
|---|---|
| cumulative_return | 0.5732046982811858 |
| cagr | 0.12930531701922088 |
| annualized_volatility | 0.09976249894073191 |
| sharpe | 1.2689007684963336 |
| sortino | 1.9334365288222661 |
| maximum_drawdown | -0.11209807648472736 |
| benchmark_cumulative_return | 0.5420208243315694 |
| tracking_error | 0.027923252967078604 |
| information_ratio | 0.1934717016311315 |
| annualized_arithmetic_active_return | 0.005402359266617239 |
| annualized_turnover | 2.3108369222007754 |
| total_cost_fraction_sum | 0.03444247412613537 |
| compounded_cost_drag | 0.05515000843334694 |
| average_absolute_active_weight | 0.10716665244291156 |
| maximum_position | 0.366423400377588 |
| average_estimated_tracking_error | 0.03421182291544698 |
| mean_ic | -0.018989898989898998 |
| median_ic | 0.0303030303030303 |
| ic_std | 0.43755118479877053 |
| ic_information_ratio | -0.04340040582596626 |
| positive_ic_fraction | 0.5111111111111111 |
| gross_wealth | 1.6283547067145339 |
| net_wealth | 1.5732046982811858 |
| gross_cagr | 0.13979621743186943 |
| average_one_way_turnover | 0.009169987786511014 |
| average_rebalance_turnover | 0.1913470784785298 |
| average_active_share | 0.5358332622145578 |
| execution_constraint_violations | 0 |
| solver_failures | 0 |
| policy_frictionless_cagr | 0.12325378717673874 |
| policy_net_cagr | 0.12284082050894973 |
| net_active_vs_cost_adjusted_policy | 0.005770342198023872 |
| average_signal_capture | 0.7296135521870543 |
| valid_capture_observations | 45 |
| excluded_capture_observations | 0 |

Signal capture is preference expression, not investment skill. IC is evaluated only after construction. No persistent-alpha claim is made. This is independent research, not peer-reviewed research.
