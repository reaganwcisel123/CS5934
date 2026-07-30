"""US-056: seasonal-anomaly threat ranking with regional corroboration."""

from __future__ import annotations

import pandas as pd
import pytest

from src.model import threat_ranking as tr


def _rows(jurisdiction, condition, year, weeks, cases):
    """Weekly rows for one jurisdiction/condition/year."""
    if not isinstance(cases, (list, tuple)):
        cases = [cases] * len(weeks)
    return [{"jurisdiction": jurisdiction, "condition": condition,
             "mmwr_year": year, "mmwr_week": w, "cases": c}
            for w, c in zip(weeks, cases)]


CURRENT, WEEKS = 2026, list(range(22, 30))     # 8 weeks, W22-W29
PRIOR = [2022, 2023, 2024, 2025]


def _frame(current_va, baseline_va, condition="Cyclosporiasis", neighbors=None):
    rows = _rows("VIRGINIA", condition, CURRENT, WEEKS, current_va)
    for y in PRIOR:
        rows += _rows("VIRGINIA", condition, y, WEEKS, baseline_va)
    for name, (cur, base) in (neighbors or {}).items():
        rows += _rows(name, condition, CURRENT, WEEKS, cur)
        for y in PRIOR:
            rows += _rows(name, condition, y, WEEKS, base)
    return pd.DataFrame(rows)


# --- window and baseline -----------------------------------------------------

def test_latest_week_is_the_newest_reported_week():
    df = _frame(10.0, 5.0)

    assert tr.latest_week(df) == (2026, 29)


def test_latest_week_ignores_weeks_with_no_reported_value():
    df = _frame(10.0, 5.0)
    df = pd.concat([df, pd.DataFrame(_rows("VIRGINIA", "X", 2026, [40], [None]))])

    assert tr.latest_week(df) == (2026, 29)


def test_latest_week_raises_on_an_empty_history():
    empty = pd.DataFrame({"mmwr_year": [], "mmwr_week": [], "cases": []})

    with pytest.raises(ValueError, match="no reported cases"):
        tr.latest_week(empty)


def test_baseline_uses_the_same_weeks_in_prior_years():
    # The whole point: a July rise is compared against previous Julys, not
    # against the preceding spring.
    df = _frame(20.0, 5.0)
    stats = tr.condition_stats(df, "VIRGINIA", 2026, 22, 29)

    assert stats.loc["Cyclosporiasis", "recent"] == pytest.approx(20.0)
    assert stats.loc["Cyclosporiasis", "seasonal_base"] == pytest.approx(5.0)


def test_a_purely_seasonal_rise_scores_near_one():
    # Same level as every prior year in these weeks: not a threat.
    df = _frame(12.0, 12.0)
    stats = tr.condition_stats(df, "VIRGINIA", 2026, 22, 29)

    assert stats.loc["Cyclosporiasis", "ratio"] == pytest.approx(1.0)


def test_condition_absent_in_prior_years_gets_a_zero_baseline():
    rows = _rows("VIRGINIA", "Measles", CURRENT, WEEKS, 9.0)
    stats = tr.condition_stats(pd.DataFrame(rows), "VIRGINIA", 2026, 22, 29)

    assert stats.loc["Measles", "seasonal_base"] == 0.0


# --- smoothing ---------------------------------------------------------------

def test_smoothing_keeps_a_zero_baseline_finite():
    # Without +1 this divides by zero and returns inf, which sorts above
    # everything regardless of how few cases it represents.
    rows = _rows("VIRGINIA", "Measles", CURRENT, WEEKS, 12.0)
    stats = tr.condition_stats(pd.DataFrame(rows), "VIRGINIA", 2026, 22, 29)
    ratio = stats.loc["Measles", "ratio"]

    assert ratio == pytest.approx(13.0)
    assert ratio != float("inf")


def test_smoothing_damps_small_denominators_more_than_large_ones():
    small = _frame(4.0, 1.0)                       # 4x raw
    large = _frame(400.0, 100.0)                   # 4x raw, big numbers
    r_small = tr.condition_stats(small, "VIRGINIA", 2026, 22, 29).loc["Cyclosporiasis", "ratio"]
    r_large = tr.condition_stats(large, "VIRGINIA", 2026, 22, 29).loc["Cyclosporiasis", "ratio"]

    assert r_small < r_large < 4.01


# --- ranking -----------------------------------------------------------------

def test_volume_floor_excludes_a_tiny_but_sharp_rise():
    # 0.5 -> 2 cases/week is a 4x rise that must not reach the board.
    df = _frame(2.0, 0.5)

    assert tr.rank_threats(df) == []


def test_a_real_anomaly_ranks_and_reports_its_evidence():
    df = _frame(16.0, 6.0)
    top = tr.rank_threats(df)[0]

    assert top["condition"] == "Cyclosporiasis"
    assert top["recent_weekly_mean"] == 16.0
    assert top["seasonal_baseline"] == 6.0
    assert top["weeks_compared"] == "W22-W29"
    assert top["as_of_week"] == 29
    assert top["baseline_years"] == tr.BASELINE_YEARS


def test_neighbours_that_are_also_rising_are_named():
    df = _frame(16.0, 6.0, neighbors={"MARYLAND": (10.0, 3.0), "KENTUCKY": (8.0, 2.0)})
    top = tr.rank_threats(df)[0]

    assert top["neighbors_rising"] == 2
    assert top["neighbor_states"] == ["Kentucky", "Maryland"]


def test_a_flat_neighbour_does_not_corroborate():
    df = _frame(16.0, 6.0, neighbors={"MARYLAND": (5.0, 5.0)})

    assert tr.rank_threats(df)[0]["neighbors_rising"] == 0


def test_a_rising_but_tiny_neighbour_does_not_corroborate():
    # Volume floor applies regionally too, or one case in DC counts as evidence.
    df = _frame(16.0, 6.0, neighbors={"DISTRICT OF COLUMBIA": (1.0, 0.1)})

    assert tr.rank_threats(df)[0]["neighbors_rising"] == 0


def test_corroboration_lifts_a_condition_above_a_lone_riser():
    solo = _frame(20.0, 6.0, condition="Solo")
    backed = _frame(16.0, 6.0, condition="Backed",
                    neighbors={"MARYLAND": (9.0, 3.0), "KENTUCKY": (9.0, 3.0),
                               "TENNESSEE": (9.0, 3.0), "WEST VIRGINIA": (9.0, 3.0)})
    ranked = tr.rank_threats(pd.concat([solo, backed], ignore_index=True))

    assert [r["condition"] for r in ranked][:2] == ["Backed", "Solo"]


def test_ranking_is_capped_at_top_n():
    frames = [_frame(20.0 - i, 5.0, condition=f"C{i}") for i in range(9)]
    ranked = tr.rank_threats(pd.concat(frames, ignore_index=True), top_n=5)

    assert len(ranked) == 5


def test_ranking_is_sorted_by_score_descending():
    frames = [_frame(20.0 - 3 * i, 5.0, condition=f"C{i}") for i in range(4)]
    ranked = tr.rank_threats(pd.concat(frames, ignore_index=True))
    scores = [r["score"] for r in ranked]

    assert scores == sorted(scores, reverse=True)


def test_neighbour_rows_never_rank_as_virginia_threats():
    # Only Virginia is ranked; a neighbour spike is evidence, not an entry.
    df = _frame(4.0, 3.5, neighbors={"MARYLAND": (99.0, 1.0)})
    ranked = tr.rank_threats(df)

    assert all(r["condition"] == "Cyclosporiasis" for r in ranked)


# --- sparkline ---------------------------------------------------------------

def test_recent_series_returns_virginia_weeks_in_order():
    df = _frame(16.0, 6.0, neighbors={"MARYLAND": (99.0, 99.0)})
    series = tr.recent_series(df, "Cyclosporiasis", weeks=8)

    assert len(series) == 8
    assert [p["week"] for p in series] == WEEKS
    assert all(p["cases"] == 16.0 for p in series)


def test_recent_series_preserves_suppressed_weeks_as_null():
    rows = _rows("VIRGINIA", "X", 2026, [20, 21, 22], [3.0, None, 5.0])
    series = tr.recent_series(pd.DataFrame(rows), "X")

    assert [p["cases"] for p in series] == [3.0, None, 5.0]


def test_load_region_names_the_command_that_produces_it():
    from pathlib import Path

    with pytest.raises(FileNotFoundError, match="src.ingestion.cdc_nndss"):
        tr.load_region(Path("/nonexistent/region_condition_history.csv"))
