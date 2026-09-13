"""PortfolioOS: reproducible benchmark-aware portfolio research."""

from portfolioos.backtest import BacktestConfig, BacktestResult, run_backtest
from portfolioos.synthetic import synthetic_market

__all__ = ["BacktestConfig", "BacktestResult", "run_backtest", "synthetic_market"]
