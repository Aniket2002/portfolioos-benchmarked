# Historical validation: sample_covariance

Executed sessions: 2018-01-02 to 2022-12-30 (1259 observations).

Benchmark: the declared monthly 60/40 policy, reset before the first session return of each month and drifted otherwise. Frictionless policy returns define active metrics; independently cost-adjusted policy returns are also exported. Each period starts endowed in policy holdings.

Decisions use the declared lagged information set; execution-close drift enters turnover and compliance accounting. Closing target fills and additive costs are research approximations.

Ordinary allocation comparisons satisfy their own rules. Active TE, sector, position and turnover mandates apply to optimized strategies at accepted rebalances; subsequent drift and realized risk can exceed target limits.

| Metric | Value |
|---|---|
| cumulative_return | 0.10574501188270213 |
| cagr | 0.020323601607289632 |
| annualized_volatility | 0.13212275114832472 |
| sharpe | 0.21861241140854454 |
| sortino | 0.29608008855107115 |
| maximum_drawdown | -0.2531516179600668 |
| benchmark_cumulative_return | 0.17521019026801898 |
| tracking_error | 0.03293098816624167 |
| information_ratio | -0.3487555650824234 |
| annualized_arithmetic_active_return | -0.01148486538664021 |
| annualized_turnover | 2.4468859442379496 |
| total_cost_fraction_sum | 0.01222471985633166 |
| compounded_cost_drag | 0.013581698703356793 |
| average_absolute_active_weight | 0.08343828973499332 |
| maximum_position | 0.37558142779295944 |
| average_estimated_tracking_error | 0.029791472419144056 |
| mean_ic | -0.06020202020202017 |
| median_ic | -0.054545454545454536 |
| ic_std | 0.4925048621663499 |
| ic_information_ratio | -0.12223639770217366 |
| positive_ic_fraction | 0.4666666666666667 |
| gross_wealth | 1.119326710586059 |
| net_wealth | 1.1057450118827021 |
| gross_cagr | 0.022819856488464962 |
| average_one_way_turnover | 0.009709864858087102 |
| average_rebalance_turnover | 0.20374533093886102 |
| average_active_share | 0.41719144867496655 |
| execution_constraint_violations | 0 |
| solver_failures | 0 |
| policy_frictionless_cagr | 0.032842851452639765 |
| policy_net_cagr | 0.032705103767938004 |
| net_active_vs_cost_adjusted_policy | -0.01135136937282576 |
| average_signal_capture | 0.547953477226813 |
| valid_capture_observations | 60 |
| excluded_capture_observations | 0 |

Signal capture is preference expression, not investment skill. IC is evaluated only after construction. No persistent-alpha claim is made. This is independent research, not peer-reviewed research.
