# Historical validation: lag_3

Executed sessions: 2018-01-02 to 2022-12-30 (1259 observations).

Benchmark: the declared monthly 60/40 policy, reset before the first session return of each month and drifted otherwise. Frictionless policy returns define active metrics; independently cost-adjusted policy returns are also exported. Each period starts endowed in policy holdings.

Decisions use the declared lagged information set; execution-close drift enters turnover and compliance accounting. Closing target fills and additive costs are research approximations.

Ordinary allocation comparisons satisfy their own rules. Active TE, sector, position and turnover mandates apply to optimized strategies at accepted rebalances; subsequent drift and realized risk can exceed target limits.

| Metric | Value |
|---|---|
| cumulative_return | 0.12926838142374053 |
| cagr | 0.02463177766190716 |
| annualized_volatility | 0.13080062510107685 |
| sharpe | 0.2516799390772021 |
| sortino | 0.34160839623621275 |
| maximum_drawdown | -0.24700348718222243 |
| benchmark_cumulative_return | 0.17521019026801898 |
| tracking_error | 0.0327569861683741 |
| information_ratio | -0.22739104330663398 |
| annualized_arithmetic_active_return | -0.007448645260407566 |
| annualized_turnover | 2.5504807503052715 |
| total_cost_fraction_sum | 0.012742282796168 |
| compounded_cost_drag | 0.014456337638667272 |
| average_absolute_active_weight | 0.08408208354556093 |
| maximum_position | 0.37242614051237843 |
| average_estimated_tracking_error | 0.03107748022305175 |
| mean_ic | -0.06929292929292927 |
| median_ic | -0.07272727272727272 |
| ic_std | 0.4931547950237984 |
| ic_information_ratio | -0.14050949112151565 |
| positive_ic_fraction | 0.4166666666666667 |
| gross_wealth | 1.143724719062407 |
| net_wealth | 1.1292683814237405 |
| gross_cagr | 0.027243888724908905 |
| average_one_way_turnover | 0.010120955358354252 |
| average_rebalance_turnover | 0.21237137993613336 |
| average_active_share | 0.42041041772780463 |
| execution_constraint_violations | 0 |
| solver_failures | 0 |
| policy_frictionless_cagr | 0.032842851452639765 |
| policy_net_cagr | 0.032705103767938004 |
| net_active_vs_cost_adjusted_policy | -0.007315149246593116 |
| average_signal_capture | 0.5340239492256612 |
| valid_capture_observations | 60 |
| excluded_capture_observations | 0 |

Signal capture is preference expression, not investment skill. IC is evaluated only after construction. No persistent-alpha claim is made. This is independent research, not peer-reviewed research.
