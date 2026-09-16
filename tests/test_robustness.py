import hashlib
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from portfolioos.reporting import load_config
from portfolioos.robustness import (
    EXPECTED_SEEDS,
    load_protocol,
    run_seed,
    summarize_results,
)


def test_protocol_has_exact_predeclared_seed_list():
    protocol = load_protocol()
    assert tuple(protocol["predeclared_seeds"]) == tuple(range(40, 60))
    assert len(set(protocol["predeclared_seeds"])) == 20


def test_only_seed_varies_in_declared_runs():
    protocol = load_protocol()
    synthetic, config = load_config(protocol["base_config"])
    baseline = {key: value for key, value in synthetic.items() if key != "seed"}
    for seed in protocol["predeclared_seeds"]:
        candidate = dict(synthetic, seed=seed)
        assert {
            key: value for key, value in candidate.items() if key != "seed"
        } == baseline
        assert asdict(config) == asdict(load_config(protocol["base_config"])[1])


def _fake_results():
    delta_te = np.linspace(0.01, 0.02, 20)
    delta_turnover = np.linspace(0.03, 0.04, 20)
    return pd.DataFrame(
        {
            "seed": EXPECTED_SEEDS,
            "delta_TE": delta_te,
            "delta_turnover": delta_turnover,
            "dominance_delta": delta_turnover - delta_te,
            "scenario_status": "success",
        }
    )


def test_summary_calculations_and_all_seeds_retained():
    results = _fake_results()
    summary = summarize_results(results)
    assert summary["seed_count"] == 20
    assert summary["count_delta_turnover_gt_delta_TE"] == 20
    assert summary["fraction_delta_turnover_gt_delta_TE"] == 1
    assert summary["count_delta_turnover_gt_zero"] == 20
    assert summary["count_delta_TE_gt_zero"] == 20
    assert summary["classification"] == "STRONG"
    assert summary["summaries"]["dominance_delta"]["median"] == pytest.approx(0.02)


def test_no_seed_may_be_silently_dropped():
    with pytest.raises(ValueError, match="Every predeclared seed"):
        summarize_results(_fake_results().iloc[:-1])


def test_failed_scenarios_count_against_predeclared_dominance_gate():
    results = _fake_results()
    results.loc[:1, ["delta_TE", "dominance_delta"]] = np.nan
    results.loc[:1, "scenario_status"] = "incomplete"
    summary = summarize_results(results)
    assert summary["count_delta_turnover_gt_delta_TE"] == 18
    assert not summary["all_scenarios_complete"]
    assert summary["classification"] == "STRONG"


def test_seed_run_is_deterministic_and_fingerprinted():
    protocol = load_protocol()
    first = run_seed(protocol, 42)
    second = run_seed(protocol, 42)
    for key in ("delta_TE", "delta_turnover", "dominance_delta"):
        assert first[key] == pytest.approx(second[key], abs=1e-12)
    assert first["configuration_fingerprint"] == second["configuration_fingerprint"]
    assert first["fixed_settings_fingerprint"] == second["fixed_settings_fingerprint"]
    assert first["dominance_delta"] == pytest.approx(
        first["delta_turnover"] - first["delta_TE"]
    )


def test_canonical_seed_42_artifacts_remain_unchanged():
    expected = {
        "te_frontier.csv": (
            "5e6e852b9978a447b471795c22c501d9bdac78fb44599bdce1e825c6281d2b8c"
        ),
        "turnover_frontier.csv": (
            "98d800980182c0f93ba5167a60665dbfcf5bf5c6fb7a034423c939e34298fb6a"
        ),
        "cost_frontier.csv": (
            "fc9e1000b0ff071d091e12293a860c7f9bae42046c11d9d6c234e5db763d4026"
        ),
        "te_turnover_grid.csv": (
            "f9f828ce34313d3182fea9b73bd10ae6b66c85abbec826616386b435cb18541a"
        ),
        "experiment_summary.json": (
            "2645ac256bbcd17c971f11c1a3933f1b5018a2f37b4dec4dbd046cecb127386d"
        ),
    }
    root = Path("results/research_tradeoffs")
    actual = {
        name: hashlib.sha256((root / name).read_bytes()).hexdigest()
        for name in expected
    }
    assert actual == expected
