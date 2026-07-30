"""US-049: condition x week panel, leakage guard, and county allocation.

Self-contained fixtures; no built atlas or network required.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.model import forecast_config as FC
from src.model import forecast_dataset as fd


def _series(condition: str, weeks: int, start_year: int = 2022, seed: int = 0) -> pd.DataFrame:
    """A continuous weekly series spanning MMWR year boundaries."""
    rng = np.random.default_rng(seed)
    rows, year, week = [], start_year, 1
    for _ in range(weeks):
        rows.append({
            "jurisdiction": "VIRGINIA", "condition": condition,
            "mmwr_year": year, "mmwr_week": week,
            "cases": float(rng.integers(5, 60)),
        })
        week += 1
        if week > 52:
            year, week = year + 1, 1
    return pd.DataFrame(rows)


def test_week_index_is_monotonic_across_year_boundaries():
    df = _series("Pertussis", 60)
    idx = fd.week_index(df)

    assert idx.tolist() == list(range(60))
    assert idx.is_monotonic_increasing


def test_week_index_handles_a_53_week_year():
    # MMWR years run 52 or 53 weeks, so year*52+week would misalign.
    df = pd.DataFrame([
        {"mmwr_year": 2025, "mmwr_week": 52}, {"mmwr_year": 2025, "mmwr_week": 53},
        {"mmwr_year": 2026, "mmwr_week": 1},
    ])

    assert fd.week_index(df).tolist() == [0, 1, 2]


def test_lag_features_are_strictly_past():
    panel = fd.condition_panel(_series("Pertussis", 120), conditions=["Pertussis"])
    g = panel.sort_values("week_idx")

    for lag in FC.LAG_WEEKS:
        assert g[f"lag_{lag}"].equals(g["cases"].shift(lag))


def test_rolling_features_exclude_the_current_week():
    # roll_mean_4 must average the 4 weeks *before* the target, not including it.
    panel = fd.condition_panel(_series("Pertussis", 60), conditions=["Pertussis"])
    g = panel.sort_values("week_idx").reset_index(drop=True)

    expected = g["cases"].shift(1).rolling(4, min_periods=1).mean()
    assert g["roll_mean_4"].equals(expected)


def test_assert_no_leakage_passes_on_a_clean_panel():
    panel = fd.condition_panel(_series("Pertussis", 120), conditions=["Pertussis"])

    fd.assert_no_leakage(panel)


def test_assert_no_leakage_catches_a_shift_zero_slip():
    # The failure this guard exists for: a lag column silently carrying the
    # current week, which just makes the model look excellent.
    panel = fd.condition_panel(_series("Pertussis", 120), conditions=["Pertussis"])
    panel["lag_1"] = panel["cases"]

    with pytest.raises(AssertionError, match="leakage"):
        fd.assert_no_leakage(panel)


def test_seasonal_lag_is_present_and_shifted_a_year():
    panel = fd.condition_panel(_series("Pertussis", 160), conditions=["Pertussis"])
    g = panel.sort_values("week_idx")

    assert g[f"lag_{FC.SEASONAL_LAG_WEEKS}"].equals(g["cases"].shift(FC.SEASONAL_LAG_WEEKS))


def test_week_of_year_is_cyclical():
    # Week 52 and week 1 must be neighbours, not opposite ends of a ramp.
    panel = fd.condition_panel(_series("Pertussis", 104), conditions=["Pertussis"])
    w52 = panel[panel.mmwr_week == 52].iloc[0]
    w1 = panel[panel.mmwr_week == 1].iloc[0]

    distance = np.hypot(w52.woy_sin - w1.woy_sin, w52.woy_cos - w1.woy_cos)
    assert distance < 0.25


def test_panel_covers_multiple_conditions_independently():
    history = pd.concat([_series("Pertussis", 60, seed=1), _series("Shigellosis", 60, seed=2)])
    panel = fd.condition_panel(history, conditions=["Pertussis", "Shigellosis"])

    assert set(panel.condition) == {"Pertussis", "Shigellosis"}
    # Lags must not bleed across conditions.
    first_shig = panel[panel.condition == "Shigellosis"].sort_values("week_idx").iloc[0]
    assert pd.isna(first_shig["lag_1"])


def test_panel_survives_a_filtered_sparse_index():
    # Regression: filtering to a subset leaves a sparse index, and week_index()
    # returns a 0..n-1 Series, so a plain assignment aligned by label into NaN.
    history = pd.concat([
        _series("Pertussis", 60, seed=1),
        _series("Not forecast", 60, seed=2),
    ], ignore_index=True)

    panel = fd.condition_panel(history, conditions=["Pertussis"])

    assert panel["week_idx"].notna().all()
    assert panel["week_idx"].nunique() == 60


def test_usable_conditions_splits_on_the_history_threshold():
    history = pd.concat([
        _series("Chlamydia trachomatis infection", FC.MIN_HISTORY_WEEKS + 10, seed=3),
        _series("Mumps", 20, seed=4),
    ])
    panel = fd.condition_panel(history, conditions=["Chlamydia trachomatis infection", "Mumps"])

    usable, thin = fd.usable_conditions(panel)
    assert usable == ["Chlamydia trachomatis infection"]
    assert thin == ["Mumps"]


def test_feature_columns_all_exist_in_the_panel():
    panel = fd.condition_panel(_series("Pertussis", 120), conditions=["Pertussis"])

    assert set(fd.feature_columns()).issubset(panel.columns)


# --- county allocation -------------------------------------------------------

POPS = {"51001": 30_000.0, "51003": 110_000.0, "51005": 60_000.0}


def test_allocation_splits_by_population_share():
    out = fd.allocate_to_counties(200.0, POPS)

    assert out["allocated_value"].sum() == pytest.approx(200.0)
    biggest = out.loc[out.population_share.idxmax(), "county_fips"]
    assert biggest == "51003"


def test_allocation_tags_every_row_as_derived():
    # The core honesty property: nothing downstream can mistake an allocated
    # figure for an observed county count.
    out = fd.allocate_to_counties(200.0, POPS)

    assert (out["allocation_method"] == FC.ALLOCATION_METHOD).all()
    assert (~out["is_observed"]).all()


def test_allocation_shares_sum_to_one():
    out = fd.allocate_to_counties(1.0, POPS)

    assert out["population_share"].sum() == pytest.approx(1.0)


def test_allocation_rejects_zero_population():
    with pytest.raises(ValueError, match="positive"):
        fd.allocate_to_counties(10.0, {"51001": 0.0})


def test_allocation_propagates_a_missing_state_value():
    out = fd.allocate_to_counties(None, POPS)

    assert out["allocated_value"].isna().all()


def test_load_history_names_the_command_that_produces_it():
    from pathlib import Path

    with pytest.raises(FileNotFoundError, match="src.ingestion.cdc_nndss"):
        fd.load_history(Path("/nonexistent/va_condition_history.csv"))
