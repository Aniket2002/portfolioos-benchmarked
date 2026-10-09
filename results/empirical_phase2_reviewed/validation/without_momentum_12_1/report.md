# Historical validation: without_momentum_12_1

Executed sessions: 2018-01-02 to 2022-12-30 (1259 observations).

Benchmark: the declared monthly 60/40 policy, reset before the first session return of each month and drifted otherwise. Frictionless policy returns define active metrics; independently cost-adjusted policy returns are also exported. Each period starts endowed in policy holdings.

Decisions use the declared lagged information set; execution-close drift enters turnover and compliance accounting. Closing target fills and additive costs are research approximations.

Ordinary allocation comparisons satisfy their own rules. Active TE, sector, position and turnover mandates apply to optimized strategies at accepted rebalances; subsequent drift and realized risk can exceed target limits.

| Metric | Value |
|---|---|
| cumulative_return | 0.1117415631731209 |
| cagr | 0.021428747067973264 |
| annualized_volatility | 0.12683068140996456 |
| sharpe | 0.23095693426983138 |
| sortino | 0.3117965457551091 |
| maximum_drawdown | -0.2673975708166626 |
| benchmark_cumulative_return | 0.17521019026801898 |
| tracking_error | 0.03547382305652271 |
| information_ratio | -0.31223342490205064 |
| annualized_arithmetic_active_return | -0.011076113267307416 |
| annualized_turnover | 2.3789933554942917 |
| total_cost_fraction_sum | 0.011885526327648069 |
| compounded_cost_drag | 0.0132929851144028 |
| average_absolute_active_weight | 0.08666842410194715 |
| maximum_position | 0.37741570636199123 |
| average_estimated_tracking_error | 0.029653844945033193 |
| mean_ic | -0.04040404040404041 |
| median_ic | -0.09696969696969696 |
| ic_std | 0.482842107855157 |
| ic_information_ratio | -0.08367961233439236 |
| positive_ic_fraction | 0.45 |
| gross_wealth | 1.1250345482875246 |
| net_wealth | 1.111741563173121 |
| gross_cagr | 0.02386170563160661 |
| average_one_way_turnover | 0.009440449823390047 |
| average_rebalance_turnover | 0.19809210546080117 |
| average_active_share | 0.4333421205097358 |
| execution_constraint_violations | 0 |
| solver_failures | 0 |
| policy_frictionless_cagr | 0.032842851452639765 |
| policy_net_cagr | 0.032705103767938004 |
| net_active_vs_cost_adjusted_policy | -0.010942617253492966 |
| average_signal_capture | 0.3845059968995782 |
| valid_capture_observations | 60 |
| excluded_capture_observations | 0 |

Signal capture is preference expression, not investment skill. IC is evaluated only after construction. No persistent-alpha claim is made. This is independent research, not peer-reviewed research.
