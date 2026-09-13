import numpy as np
import pandas as pd
import pytest

from portfolioos.data import (
    align_benchmark,
    align_external_signals,
    align_sectors,
    validate_prices,
)


def test_valid_prices_are_copied(market):
    prices, _ = market
    pd.testing.assert_frame_equal(prices, validate_prices(prices))
    assert validate_prices(prices) is not prices


@pytest.mark.parametrize(
    "defect",
    [
        "unsorted",
        "duplicate_dates",
        "duplicate_assets",
        "zero",
        "negative",
        "infinity",
        "missing",
        "dates",
        "empty",
        "missing_date",
        "numeric_asset",
    ],
)
def test_bad_prices_rejected(market, defect):
    p = market[0].copy()
    if defect == "unsorted":
        p = p.iloc[::-1]
    elif defect == "duplicate_dates":
        p.index = [p.index[0]] * len(p)
    elif defect == "duplicate_assets":
        p.columns = ["A"] * len(p.columns)
    elif defect in {"zero", "negative", "infinity", "missing"}:
        p.iloc[0, 0] = {
            "zero": 0,
            "negative": -1,
            "infinity": np.inf,
            "missing": np.nan,
        }[defect]
    elif defect == "dates":
        p.index = range(len(p))
    elif defect == "empty":
        p = p.iloc[:0]
    elif defect == "missing_date":
        p.index = pd.DatetimeIndex([pd.NaT, *p.index[1:]])
    else:
        p.columns = range(len(p.columns))
    with pytest.raises(ValueError):
        validate_prices(p)


def test_bounded_fill_is_causal(market):
    p = market[0].copy()
    p.iloc[10, 0] = np.nan
    filled = validate_prices(p, max_missing_fraction=0.02, fill_limit=1)
    assert filled.iloc[10, 0] == p.iloc[9, 0]
    p.iloc[11, 0] = np.nan
    with pytest.raises(ValueError, match="Unresolved"):
        validate_prices(p, max_missing_fraction=0.02, fill_limit=1)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"min_history": 1000},
        {"min_history": 1},
        {"max_missing_fraction": -1},
        {"fill_limit": -1},
    ],
)
def test_bad_validation_settings(market, kwargs):
    with pytest.raises(ValueError):
        validate_prices(market[0], **kwargs)


def test_benchmark_alignment(market):
    p, _ = market
    raw = pd.DataFrame([[2, 3]], index=p.index[:1], columns=p.columns[:2])
    b = align_benchmark(raw, p.columns[::-1])
    assert b.columns.equals(p.columns[::-1])
    assert b.iloc[0][p.columns[0]] == 0.4
    assert b.sum(axis=1).iloc[0] == 1
    assert (b[p.columns[2:]] == 0).all().all()


@pytest.mark.parametrize("values", [[-1, 2], [0, 0], [np.nan, 1], [np.inf, 1]])
def test_invalid_benchmark(market, values):
    p, _ = market
    with pytest.raises(ValueError):
        align_benchmark(
            pd.DataFrame([values], index=p.index[:1], columns=p.columns[:2]), p.columns
        )


def test_unknown_constituents(market):
    p, _ = market
    with pytest.raises(ValueError, match="unavailable"):
        align_benchmark(pd.DataFrame({"UNKNOWN": [1]}, index=p.index[:1]), p.columns)


def test_metadata_and_external_validation(market):
    p, m = market
    assert align_sectors(None, p.columns) is None
    pd.testing.assert_series_equal(align_sectors(m, p.columns), m.sector)
    for bad in (m.iloc[1:], pd.concat([m, m]), m.rename(columns={"sector": "bad"})):
        with pytest.raises(ValueError):
            align_sectors(bad, p.columns)
    pd.testing.assert_frame_equal(align_external_signals(p, p.columns), p)
    with pytest.raises(ValueError):
        align_external_signals(p.iloc[:, 1:], p.columns)
    p = p.copy()
    p.iloc[0, 0] = np.inf
    with pytest.raises(ValueError):
        align_external_signals(p, p.columns)
