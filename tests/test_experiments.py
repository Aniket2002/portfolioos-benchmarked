import json
from dataclasses import asdict, replace

import numpy as np
import pandas as pd
import pytest

from portfolioos.backtest import run_backtest
from portfolioos.experiments import (
    EXPERIMENT_COLUMNS,
    RESEARCH_QUESTION,
    SYNTHETIC_DISCLAIMER,
    SYNTHETIC_LABEL,
    active_signal_exposure,
    dataset_fingerprint,
    reference_signal_expression_config,
    run_experiment_suite,
    signal_capture,
    vary_config,
    write_experiment_report,
)


@pytest.fixture(scope="session")
def reference_result(market, config):
    prices, metadata = market
    reference_config = reference_signal_expression_config(config)
    return run_backtest(prices, metadata=metadata, config=reference_config)


@pytest.fixture(scope="session")
def experiment_suite(market, config):
    prices, metadata = market
    return run_experiment_suite(
        prices,
        metadata=metadata,
        base_config=config,
        te_budgets=(0.05, 0.10),
        turnover_limits=(0.20, 0.40),
        cost_bps=(0.0, 20.0),
        grid_te=(0.10,),
        grid_turnover=(0.40,),
    )


def test_active_signal_exposure_and_capture_formula(result, reference_result):
    expected = (
        result.active_weights.loc[result.signal_scores.index] * result.signal_scores
    ).sum(axis=1)
    pd.testing.assert_series_equal(
        active_signal_exposure(result),
        expected.rename("active_signal_exposure"),
    )
    expected_capture = expected / active_signal_exposure(reference_result)
    pd.testing.assert_series_equal(
        signal_capture(result, reference_result),
        expected_capture.rename("signal_capture"),
    )


def test_capture_near_zero_and_misaligned_reference(result, reference_result):
    zero_reference = replace(
        reference_result,
        active_weights=reference_result.active_weights * 0,
    )
    assert signal_capture(result, zero_reference).isna().all()
    misaligned = replace(
        reference_result,
        signal_scores=reference_result.signal_scores.rename(
            columns={"SYN000": "other"}
        ),
    )
    with pytest.raises(ValueError, match="not aligned"):
        signal_capture(result, misaligned)


def test_reference_portfolio_definition(config):
    reference = reference_signal_expression_config(config)
    assert (
        reference.optimizer.max_position_weight
        == config.optimizer.max_position_weight
    )
    assert reference.optimizer.risk_aversion == 0
    assert reference.optimizer.turnover_penalty == 0
    assert reference.optimizer.max_tracking_error is None
    assert reference.optimizer.max_sector_active_weight is None
    assert reference.optimizer.max_turnover is None
    assert reference.transaction_cost_bps == config.transaction_cost_bps
    assert config.optimizer.max_tracking_error == 0.10


@pytest.mark.parametrize(
    ("dimension", "value", "path"),
    [
        ("tracking_error", 0.04, ("optimizer", "max_tracking_error")),
        ("turnover", 0.20, ("optimizer", "max_turnover")),
        ("transaction_cost_bps", 40, ("transaction_cost_bps",)),
    ],
)
def test_frontier_config_changes_only_one_dimension(config, dimension, value, path):
    original = asdict(config)
    varied = asdict(vary_config(config, dimension, value))
    cursor = varied
    for key in path[:-1]:
        cursor = cursor[key]
    original_value = (
        original[path[0]] if len(path) == 1 else original[path[0]][path[1]]
    )
    cursor[path[-1]] = original_value
    assert varied == original
    assert asdict(config) == original


def test_suite_identity_schema_and_cost_invariants(experiment_suite, market):
    prices, metadata = market
    assert experiment_suite.dataset_identity == dataset_fingerprint(
        prices, metadata=metadata
    )
    for table in (
        experiment_suite.te_frontier,
        experiment_suite.turnover_frontier,
        experiment_suite.cost_frontier,
    ):
        assert list(table.columns) == EXPERIMENT_COLUMNS
        assert table.dataset_identity.nunique() == 1
        assert set(table.scenario_status) <= {"success", "infeasible", "failed"}
    costs = experiment_suite.cost_frontier
    assert (costs.scenario_status == "success").all()
    assert costs.average_signal_capture.nunique() == 1
    assert np.allclose(
        costs.gross_annualized_active_return,
        costs.gross_annualized_active_return.iloc[0],
    )
    assert (
        costs.net_annualized_active_return.iloc[-1]
        <= (costs.net_annualized_active_return.iloc[0])
    )


def test_exposure_does_not_use_future_prices(market, config, result):
    prices, metadata = market
    cutoff = prices.index[110]
    mutated = prices.copy()
    mutated.loc[cutoff:] *= np.linspace(0.6, 1.8, prices.shape[1])
    rerun = run_backtest(mutated, metadata=metadata, config=config)
    pd.testing.assert_series_equal(
        active_signal_exposure(result).loc[:cutoff],
        active_signal_exposure(rerun).loc[:cutoff],
    )


def test_saved_experiment_artifacts_and_synthetic_label(experiment_suite, tmp_path):
    write_experiment_report(experiment_suite, tmp_path)
    expected = {
        "te_frontier.csv",
        "turnover_frontier.csv",
        "cost_frontier.csv",
        "te_turnover_grid.csv",
        "experiment_summary.json",
        "report.md",
        "signal_capture_vs_te.png",
        "implementation_frontier.png",
        "signal_capture_vs_turnover.png",
        "gross_vs_net_by_cost.png",
        "information_ratio_vs_te.png",
        "te_turnover_signal_capture_heatmap.png",
    }
    assert expected <= {path.name for path in tmp_path.iterdir()}
    loaded = json.loads((tmp_path / "experiment_summary.json").read_text())
    assert loaded["provenance"] == SYNTHETIC_LABEL
    assert loaded["disclaimer"] == SYNTHETIC_DISCLAIMER
    assert loaded["research_question"] == RESEARCH_QUESTION
    assert (
        "Findings from the synthetic experiment" in (tmp_path / "report.md").read_text()
    )
