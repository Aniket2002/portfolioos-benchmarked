import json
from io import BytesIO

import numpy as np
import pandas as pd
import pytest

from portfolioos.app_helpers import (
    attribution_frame,
    attribution_tables,
    frame_csv,
    latest_holdings,
    make_app_config,
    performance_tables,
    read_uploaded_csv,
    result_metrics,
    safe_metric,
    signal_components,
    summary_json,
)
from portfolioos.backtest import run_backtest


@pytest.fixture
def controls():
    return {
        "momentum_weight": 1.2,
        "low_volatility_weight": 0.8,
        "reversal_weight": -0.2,
        "covariance_lookback": 40,
        "tracking_error_enabled": False,
        "max_tracking_error": 0.08,
        "max_position_weight": 0.25,
        "sector_cap_enabled": True,
        "max_sector_active_weight": 0.07,
        "turnover_cap_enabled": False,
        "max_turnover": 0.30,
        "risk_aversion": 12,
        "turnover_penalty": 0.2,
        "transaction_cost_bps": 7,
        "rebalance_frequency": "weekly",
    }


def test_configuration_mapping(config, controls):
    mapped = make_app_config(config, controls, has_sectors=False)
    assert mapped.rebalance_frequency == "weekly"
    assert mapped.signal_weights["momentum_12_1"] == 1.2
    assert mapped.covariance_lookback == 40
    assert mapped.transaction_cost_bps == 7
    assert mapped.optimizer.max_tracking_error is None
    assert mapped.optimizer.max_sector_active_weight is None
    assert mapped.optimizer.max_turnover is None
    assert mapped.optimizer.fallback_to_benchmark is False


def test_safe_formatting_and_serialization(result):
    assert safe_metric(np.nan) == "N/A"
    assert safe_metric(np.inf) == "N/A"
    assert safe_metric(0.1234, "percent") == "12.34%"
    metrics = result_metrics(result)
    payload = json.loads(summary_json(result, metrics, "TEST", 1.25))
    assert payload["provenance"] == "TEST"
    assert payload["runtime_seconds"] == 1.25
    assert payload["metrics"]["evaluation_days"] == len(result.returns)
    assert frame_csv(result.weights).startswith(b"date,")


def test_result_tables_use_result_schema(result, market):
    prices, _ = market
    wealth, relative, drawdowns = performance_tables(result)
    assert list(wealth) == ["Gross", "Net", "Benchmark"]
    assert relative.index.equals(result.returns.index)
    assert list(drawdowns) == ["Gross", "Net", "Benchmark"]
    latest, holdings = latest_holdings(result)
    assert latest == result.weights.index[-1]
    assert np.allclose(holdings.sum()[["Portfolio", "Benchmark"]], 1)
    _, information, components = signal_components(prices, result)
    assert information < result.signal_scores.index[-1]
    assert components["Composite"].equals(
        result.signal_scores.iloc[-1].reindex(components.index)
    )
    security, sector, error = attribution_tables(result)
    assert set(security.index) == set(result.weights.columns)
    assert sector is not None
    assert error < 1e-10
    assert attribution_frame(result).index.names == ["date", "sector"]


def test_in_memory_user_upload_uses_engine_validation(market, config):
    prices, metadata = market
    price_upload = BytesIO(prices.to_csv().encode())
    metadata_upload = BytesIO(metadata.to_csv().encode())
    parsed_prices = read_uploaded_csv(price_upload, "prices")
    parsed_metadata = read_uploaded_csv(metadata_upload, "metadata")
    output = run_backtest(parsed_prices, metadata=parsed_metadata, config=config)
    assert len(output.returns) > 0

    bad_benchmark = pd.DataFrame({"UNKNOWN": [1.0]}, index=[parsed_prices.index[0]])
    parsed_benchmark = read_uploaded_csv(
        BytesIO(bad_benchmark.to_csv().encode()), "benchmark"
    )
    with pytest.raises(ValueError, match="unavailable constituents"):
        run_backtest(
            parsed_prices,
            benchmark_weights=parsed_benchmark,
            metadata=parsed_metadata,
            config=config,
        )


def test_unknown_upload_kind_rejected():
    with pytest.raises(ValueError, match="Unknown uploaded data kind"):
        read_uploaded_csv(BytesIO(b"x\n1\n"), "signals")
