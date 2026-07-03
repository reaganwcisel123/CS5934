"""Unit tests for the pure transform logic (normalize, blend, need index)."""

import pandas as pd

from src.transform.metrics import need_index
from src.transform.normalize import blend_domain, normalize_burden


def test_normalize_up_ranks_min_to_25_max_to_100():
    s = pd.Series([1, 2, 3, 4], index=list("abcd"))
    out = normalize_burden(s, "up")
    assert out["a"] == 25.0   # lowest raw -> lowest burden
    assert out["d"] == 100.0  # highest raw -> highest burden


def test_normalize_down_inverts_direction():
    s = pd.Series([1, 2, 3, 4])
    up, down = normalize_burden(s, "up"), normalize_burden(s, "down")
    assert down.iloc[3] == round(100 - up.iloc[3], 1)  # highest raw -> lowest burden
    assert down.iloc[0] == round(100 - up.iloc[0], 1)


def test_normalize_preserves_nan():
    out = normalize_burden(pd.Series([1.0, None, 3.0]), "up")
    assert pd.isna(out.iloc[1])


def test_blend_domain_averages_components():
    out = blend_domain({"a": pd.Series([0, 100]), "b": pd.Series([50, 50])})
    assert list(out) == [25.0, 75.0]


def test_need_index_weighted_average():
    assert need_index({"x": 100, "y": 0}, {"x": 0.5, "y": 0.5}) == 50.0


def test_need_index_renormalizes_over_available_domains():
    dom = {"x": 100, "y": 0, "z": 50}
    weights = {"x": 0.25, "y": 0.25, "z": 0.5}
    # only x and z available: (100*0.25 + 50*0.5) / 0.75 = 66.7
    assert need_index(dom, weights, available={"x", "z"}) == 66.7


def test_need_index_empty_available_falls_back_to_all():
    assert need_index({"x": 100, "y": 0}, {"x": 0.5, "y": 0.5}, available=set()) == 50.0
