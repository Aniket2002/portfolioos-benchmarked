import pandas as pd
import pytest

from portfolioos.synthetic import synthetic_market


def test_deterministic_seed():
    a, metadata = synthetic_market(42, 10, 2)
    b, _ = synthetic_market(42, 10, 2)
    c, _ = synthetic_market(43, 10, 2)
    pd.testing.assert_frame_equal(a, b)
    assert not a.equals(c)
    assert (a > 0).all().all()
    assert metadata.sector.nunique() == 5


@pytest.mark.parametrize("kwargs", [{"assets": 1}, {"years": 1}, {"sectors": 41}])
def test_invalid_generator(kwargs):
    with pytest.raises(ValueError):
        synthetic_market(**kwargs)
