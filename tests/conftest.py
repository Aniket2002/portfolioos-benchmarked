from dataclasses import replace

import pytest

from portfolioos.backtest import BacktestConfig, run_backtest
from portfolioos.optimizer import OptimizerConfig
from portfolioos.synthetic import synthetic_market


@pytest.fixture(scope="session")
def market():
    prices, metadata = synthetic_market(42, 10, 2)
    return prices.iloc[:160], metadata


@pytest.fixture(scope="session")
def config():
    return BacktestConfig(
        momentum_lookback=40,
        momentum_skip=5,
        volatility_lookback=20,
        reversal_lookback=5,
        covariance_lookback=40,
        optimizer=OptimizerConfig(
            max_position_weight=0.25, max_tracking_error=0.10, max_turnover=0.40
        ),
    )


@pytest.fixture(scope="session")
def result(market, config):
    prices, metadata = market
    return run_backtest(prices, metadata=metadata, config=config)


@pytest.fixture
def unconstrained(config):
    return replace(
        config.optimizer,
        max_position_weight=1,
        max_tracking_error=None,
        max_sector_active_weight=None,
        max_turnover=None,
    )
