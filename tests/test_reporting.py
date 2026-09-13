import json
from dataclasses import replace

import pytest

from portfolioos.reporting import load_config, validate_result, write_report


def test_exported_artifacts(result, tmp_path):
    summary = write_report(result, tmp_path)
    assert summary["provenance"].startswith("SYNTHETIC")
    assert len(list(tmp_path.glob("*.png"))) == 8
    assert json.loads((tmp_path / "summary.json").read_text())["observations"] == len(
        result.weights
    )
    assert (tmp_path / "attribution.csv").exists()
    assert "not persistent real-world alpha" in (tmp_path / "report.md").read_text(
        encoding="utf-8"
    )


@pytest.mark.parametrize(
    "defect", ["weights", "sum", "nan", "cost", "reconciliation", "te"]
)
def test_invalid_results_rejected(result, defect):
    w, r, o = result.weights.copy(), result.returns.copy(), result.optimization.copy()
    if defect == "weights":
        w.iloc[0, 0] = -1
    elif defect == "sum":
        w.iloc[0] *= 0.5
    elif defect == "nan":
        r.iloc[0, 0] = float("nan")
    elif defect == "cost":
        r.loc[r.index[0], "cost"] = -1
    elif defect == "reconciliation":
        r.loc[r.index[0], "net"] += 1
    else:
        o.iloc[0, o.columns.get_loc("estimated_tracking_error")] = 10
    with pytest.raises(ValueError):
        validate_result(replace(result, weights=w, returns=r, optimization=o))


def test_configuration(tmp_path):
    synthetic, config = load_config("configs/demo.yaml")
    assert synthetic == {"seed": 42, "assets": 40, "years": 6}
    assert config.optimizer.max_turnover == 0.3
    path = tmp_path / "bad.yaml"
    path.write_text("- invalid")
    with pytest.raises(ValueError):
        load_config(path)
