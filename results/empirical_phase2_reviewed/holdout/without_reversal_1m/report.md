# Historical holdout: without_reversal_1m

Executed sessions: 2023-01-03 to 2026-09-30 (939 observations).

Benchmark: the declared monthly 60/40 policy, reset before the first session return of each month and drifted otherwise. Frictionless policy returns define active metrics; independently cost-adjusted policy returns are also exported. Each period starts endowed in policy holdings.

Decisions use the declared lagged information set; execution-close drift enters turnover and compliance accounting. Closing target fills and additive costs are research approximations.

Ordinary allocation comparisons satisfy their own rules. Active TE, sector, position and turnover mandates apply to optimized strategies at accepted rebalances; subsequent drift and realized risk can exceed target limits.

| Metric | Value |
|---|---|
| cumulative_return | 0.6603630403248626 |
| cagr | 0.14576625734228688 |
| annualized_volatility | 0.10144872217233053 |
| sharpe | 1.3922215446307715 |
| sortino | 2.111521927302522 |
| maximum_drawdown | -0.10099644586434309 |
| benchmark_cumulative_return | 0.5420208243315694 |
| tracking_error | 0.029508267790625455 |
| information_ratio | 0.6795635894140304 |
| annualized_arithmetic_active_return | 0.020052744377187855 |
| annualized_turnover | 1.3231100874833357 |
| total_cost_fraction_sum | 0.004930160206931954 |
| compounded_cost_drag | 0.00820602390356262 |
| average_absolute_active_weight | 0.11321460436895842 |
| maximum_position | 0.3711484415366532 |
| average_estimated_tracking_error | 0.035879386484499766 |
| mean_ic | 0.034882154882154875 |
| median_ic | 0.07878787878787878 |
| ic_std | 0.43192020554092275 |
| ic_information_ratio | 0.08076064614404785 |
| positive_ic_fraction | 0.6 |
| gross_wealth | 1.6685690642284257 |
| net_wealth | 1.6603630403248626 |
| gross_cagr | 0.1472832274815723 |
| average_one_way_turnover | 0.005250436855092602 |
| average_rebalance_turnover | 0.10955911570959895 |
| average_active_share | 0.5660730218447921 |
| execution_constraint_violations | 0 |
| solver_failures | 0 |
| policy_frictionless_cagr | 0.12325378717673874 |
| policy_net_cagr | 0.12315053279029109 |
| net_active_vs_cost_adjusted_policy | 0.020144740110039513 |
| average_signal_capture | 0.8074639109579433 |
| valid_capture_observations | 45 |
| excluded_capture_observations | 0 |

Signal capture is preference expression, not investment skill. IC is evaluated only after construction. No persistent-alpha claim is made. This is independent research, not peer-reviewed research.
