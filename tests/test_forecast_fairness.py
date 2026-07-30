"""US-054: allocation equity across RUCC 2023 rurality strata."""

from __future__ import annotations

import pandas as pd
import pytest

from src.model import forecast_fairness as ff


def _context(rows: list[tuple[str, float, float]]) -> pd.DataFrame:
    return pd.DataFrame(
        [{"county_fips": f, "population": p, "access_burden": a} for f, p, a in rows]
    )


def test_stratum_boundaries_follow_rucc_2023():
    assert ff.stratum_for(1) == "metro"
    assert ff.stratum_for(3) == "metro"
    assert ff.stratum_for(4) == "nonmetro"
    assert ff.stratum_for(6) == "nonmetro"
    assert ff.stratum_for(7) == "rural"
    assert ff.stratum_for(9) == "rural"


def test_allocated_shares_sum_to_one():
    equity = ff.allocation_equity(
        _context([("51001", 100.0, 50.0), ("51003", 300.0, 50.0)]),
        {"51001": 8, "51003": 2},
    )

    assert equity["allocated_share"].sum() == pytest.approx(1.0)
    assert equity["need_share"].sum() == pytest.approx(1.0)


def test_equal_access_burden_means_no_shortfall():
    # When burden is uniform, need share collapses to population share.
    equity = ff.allocation_equity(
        _context([("51001", 100.0, 60.0), ("51003", 300.0, 60.0)]),
        {"51001": 8, "51003": 2},
    )

    assert equity["shortfall"].abs().max() == pytest.approx(0.0, abs=1e-9)


def test_a_high_burden_county_is_under_allocated():
    equity = ff.allocation_equity(
        _context([("51001", 100.0, 90.0), ("51003", 100.0, 30.0)]),
        {"51001": 9, "51003": 1},
    )
    high = equity.set_index("county_fips").loc["51001"]

    assert high["shortfall"] > 0
    assert high["need_ratio"] > 1


def test_stratum_summary_groups_and_totals():
    equity = ff.allocation_equity(
        _context([("51001", 100.0, 90.0), ("51003", 100.0, 30.0), ("51005", 100.0, 60.0)]),
        {"51001": 9, "51003": 1, "51005": 5},
    )
    summary = ff.stratum_summary(equity)

    assert set(summary["stratum"]) == {"metro", "nonmetro", "rural"}
    assert summary["counties"].sum() == 3


def test_verdict_checks_nonmetro_not_only_rural():
    # The blind spot this guards: on Virginia data the worst-served stratum is
    # nonmetro-adjacent, so a rural-only check reports "no disparity".
    summary = pd.DataFrame([
        {"stratum": "metro", "shortfall": -0.05},
        {"stratum": "nonmetro", "shortfall": 0.04},
        {"stratum": "rural", "shortfall": -0.001},
    ])
    verdict = ff.disparity_verdict(summary, threshold=0.01)

    assert verdict["disparity"] is True
    assert verdict["worst_stratum"] == "nonmetro"


def test_verdict_is_clean_when_every_stratum_is_within_threshold():
    summary = pd.DataFrame([
        {"stratum": "metro", "shortfall": 0.001},
        {"stratum": "nonmetro", "shortfall": 0.002},
        {"stratum": "rural", "shortfall": -0.003},
    ])
    verdict = ff.disparity_verdict(summary, threshold=0.01)

    assert verdict["disparity"] is False
    assert "within the stated threshold" in verdict["interpretation"]


def test_verdict_reports_every_non_metro_stratum():
    summary = pd.DataFrame([
        {"stratum": "metro", "shortfall": -0.05},
        {"stratum": "nonmetro", "shortfall": 0.04},
        {"stratum": "rural", "shortfall": 0.01},
    ])
    verdict = ff.disparity_verdict(summary, threshold=0.01)

    assert set(verdict["by_stratum"]) == {"nonmetro", "rural"}


def test_verdict_names_the_allocation_method_it_judged():
    from src.model import forecast_config as FC

    summary = pd.DataFrame([{"stratum": "rural", "shortfall": 0.0}])

    assert ff.disparity_verdict(summary)["allocation_method"] == FC.ALLOCATION_METHOD


def test_equity_rejects_zero_population():
    with pytest.raises(ValueError, match="positive"):
        ff.allocation_equity(_context([("51001", 0.0, 50.0)]), {"51001": 9})


def test_counties_without_a_rucc_code_are_not_silently_dropped():
    equity = ff.allocation_equity(
        _context([("51001", 100.0, 50.0), ("51999", 100.0, 50.0)]),
        {"51001": 9},
    )

    assert len(equity) == 2
    assert "unknown" in set(equity["stratum"])


def test_load_county_context_names_the_command_that_produces_it():
    from pathlib import Path

    with pytest.raises(FileNotFoundError, match="build_dataset"):
        ff.load_county_context(Path("/nonexistent/clinic_atlas.json"))
