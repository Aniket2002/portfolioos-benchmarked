# Historical holdout: inverse_volatility

Executed sessions: 2023-01-03 to 2026-09-30 (939 observations).

Benchmark: the declared monthly 60/40 policy, reset before the first session return of each month and drifted otherwise. Frictionless policy returns define active metrics; independently cost-adjusted policy returns are also exported. Each period starts endowed in policy holdings.

Decisions use the declared lagged information set; execution-close drift enters turnover and compliance accounting. Closing target fills and additive costs are research approximations.

Ordinary allocation comparisons satisfy their own rules. Active TE, sector, position and turnover mandates apply to optimized strategies at accepted rebalances; subsequent drift and realized risk can exceed target limits.

| Metric | Value |
|---|---|
| cumulative_return | 0.3802560107603803 |
| cagr | 0.09033776714490505 |
| annualized_volatility | 0.07855647648985288 |
| sharpe | 1.1403544213703223 |
| sortino | 1.6927617627014702 |
| maximum_drawdown | -0.08346663611167349 |
| benchmark_cumulative_return | 0.5420208243315694 |
| tracking_error | 0.037455909137957474 |
| information_ratio | -0.8437687868557778 |
| annualized_arithmetic_active_return | -0.03160412701391462 |
| annualized_turnover | 0.539558556349499 |
| total_cost_fraction_sum | 0.0020104979540165858 |
| compounded_cost_drag | 0.002774737766732649 |
| average_absolute_active_weight | 0.07645459223210423 |
| maximum_position | 0.31576013127590685 |
| average_estimated_tracking_error | 0.03630463439334407 |
| mean_ic | -0.018989898989898998 |
| median_ic | 0.0303030303030303 |
| ic_std | 0.43755118479877053 |
| ic_information_ratio | -0.04340040582596626 |
| positive_ic_fraction | 0.5111111111111111 |
| gross_wealth | 1.3830307485271156 |
| net_wealth | 1.3802560107603803 |
| gross_cagr | 0.09092558012923346 |
| average_one_way_turnover | 0.002141105382339282 |
| average_rebalance_turnover | 0.04467773231147968 |
| average_active_share | 0.38227296116052106 |
| execution_constraint_violations | 0 |
| solver_failures | 0 |
| policy_frictionless_cagr | 0.12325378717673874 |
| policy_net_cagr | 0.12315053279029109 |
| net_active_vs_cost_adjusted_policy | -0.03151213128106297 |
| average_signal_capture | undefined |
| valid_capture_observations | 0 |
| excluded_capture_observations | 0 |

Signal capture is preference expression, not investment skill. IC is evaluated only after construction. No persistent-alpha claim is made. This is independent research, not peer-reviewed research.
