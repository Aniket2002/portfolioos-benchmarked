# Historical holdout: equal_weight

Executed sessions: 2023-01-03 to 2026-09-30 (939 observations).

Benchmark: the declared monthly 60/40 policy, reset before the first session return of each month and drifted otherwise. Frictionless policy returns define active metrics; independently cost-adjusted policy returns are also exported. Each period starts endowed in policy holdings.

Decisions use the declared lagged information set; execution-close drift enters turnover and compliance accounting. Closing target fills and additive costs are research approximations.

Ordinary allocation comparisons satisfy their own rules. Active TE, sector, position and turnover mandates apply to optimized strategies at accepted rebalances; subsequent drift and realized risk can exceed target limits.

| Metric | Value |
|---|---|
| cumulative_return | 0.49417332166238426 |
| cagr | 0.11379200544006918 |
| annualized_volatility | 0.09869016450541418 |
| sharpe | 1.1414888992468695 |
| sortino | 1.6873491736086048 |
| maximum_drawdown | -0.0978478490193373 |
| benchmark_cumulative_return | 0.5420208243315694 |
| tracking_error | 0.02840624147725933 |
| information_ratio | -0.3003785300299323 |
| annualized_arithmetic_active_return | -0.00853262505861445 |
| annualized_turnover | 0.22780771274681108 |
| total_cost_fraction_sum | 0.0008488549296399033 |
| compounded_cost_drag | 0.0012655216494219523 |
| average_absolute_active_weight | 0.08005405459845874 |
| maximum_position | 0.11870991800530076 |
| average_estimated_tracking_error | 0.028187348993028827 |
| mean_ic | -0.018989898989898998 |
| median_ic | 0.0303030303030303 |
| ic_std | 0.43755118479877053 |
| ic_information_ratio | -0.04340040582596626 |
| positive_ic_fraction | 0.5111111111111111 |
| gross_wealth | 1.4954388433118053 |
| net_wealth | 1.4941733216623843 |
| gross_cagr | 0.11404509435947885 |
| average_one_way_turnover | 0.0009039988601063933 |
| average_rebalance_turnover | 0.018863442880886743 |
| average_active_share | 0.4002702729922936 |
| execution_constraint_violations | 0 |
| solver_failures | 0 |
| policy_frictionless_cagr | 0.12325378717673874 |
| policy_net_cagr | 0.12315053279029109 |
| net_active_vs_cost_adjusted_policy | -0.008440629325762793 |
| average_signal_capture | undefined |
| valid_capture_observations | 0 |
| excluded_capture_observations | 0 |

Signal capture is preference expression, not investment skill. IC is evaluated only after construction. No persistent-alpha claim is made. This is independent research, not peer-reviewed research.
