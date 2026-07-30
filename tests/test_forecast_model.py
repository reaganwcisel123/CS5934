"""US-050: baselines, rolling-origin backtest, and conformal prediction intervals.

Fixture-driven; the sklearn-dependent tests are skipped when the optional model
extra is absent, matching tests/test_model.py.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.model import forecast_config as FC
from src.model import forecast as fc
from src.model import forecast_dataset as fd

sklearn = pytest.importorskip("sklearn", reason="needs `uv sync --extra model`")


def _seasonal_series(condition: str, weeks: int, seed: int = 0, noise: float = 3.0) -> pd.DataFrame:
    """A seasonal series with trend and noise, so a model can beat naive."""
    rng = np.random.default_rng(seed)
    rows, year, week = [], 2020, 1
    for i in range(weeks):
        level = 40 + 18 * np.sin(2 * np.pi * week / 52.0) + 0.03 * i
        rows.append({
            "jurisdiction": "VIRGINIA", "condition": condition,
            "mmwr_year": year, "mmwr_week": week,
            "cases": max(0.0, float(level + rng.normal(0, noise))),
        })
        week += 1
        if week > 52:
            year, week = year + 1, 1
    return pd.DataFrame(rows)


def _panel(weeks: int = 200, **kw) -> pd.DataFrame:
    return fd.condition_panel(_seasonal_series("Pertussis", weeks, **kw), conditions=["Pertussis"])


# --- baselines ---------------------------------------------------------------

def test_naive_forecast_carries_the_last_value():
    assert fc.naive_forecast(pd.Series([1.0, 2.0, 7.0])) == 7.0


def test_naive_forecast_ignores_trailing_nulls():
    assert fc.naive_forecast(pd.Series([1.0, 5.0, np.nan])) == 5.0


def test_naive_forecast_on_an_empty_series_is_nan():
    assert np.isnan(fc.naive_forecast(pd.Series([], dtype=float)))


def test_seasonal_naive_falls_back_when_history_is_short():
    short = pd.Series([3.0, 4.0, 9.0])

    assert fc.seasonal_naive_forecast(short) == 9.0


# --- metrics -----------------------------------------------------------------

def test_mae_is_mean_absolute_error():
    assert fc.mae(np.array([1.0, 3.0]), np.array([2.0, 5.0])) == pytest.approx(1.5)


def test_mape_skips_zero_actuals():
    # Zero actuals would divide by zero and blow the metric up.
    value = fc.mape(np.array([0.0, 10.0]), np.array([5.0, 12.0]))

    assert value == pytest.approx(20.0)


def test_mape_is_nan_when_every_actual_is_zero():
    assert np.isnan(fc.mape(np.zeros(3), np.ones(3)))


# --- supervised framing ------------------------------------------------------

def test_supervised_target_is_the_horizon_ahead_value():
    panel = _panel(120)
    frame = fc.supervised_frame(panel, horizon=4)
    merged = panel.merge(frame[["week_idx", "y"]], on="week_idx", how="inner").sort_values("week_idx")

    row = merged.iloc[0]
    future = panel.loc[panel.week_idx == row.week_idx + 4, "cases"]
    assert row["y"] == pytest.approx(float(future.iloc[0]))


def test_supervised_frame_drops_rows_without_a_future():
    panel = _panel(120)
    frame = fc.supervised_frame(panel, horizon=4)

    assert frame["y"].notna().all()
    assert frame["week_idx"].max() <= panel["week_idx"].max() - 4


# --- backtest ----------------------------------------------------------------

def test_backtest_is_rolling_origin_and_never_tests_before_it_trains():
    results = fc.backtest(_panel(200), folds=3)

    assert results["folds"], "expected at least one fold"
    for fold in results["folds"]:
        assert fold["n_test"] > 0
        assert fold["cut_week_idx"] >= fc.MIN_TRAIN_WEEKS


def test_backtest_reports_mean_and_sd_for_every_summary_metric():
    summary = fc.backtest(_panel(200), folds=3)["summary"]

    for key in ("mape", "interval_coverage", "skill_vs_naive", "skill_vs_seasonal"):
        assert "mean" in summary[key] and "sd" in summary[key]


def test_backtest_beats_naive_on_a_seasonal_series():
    # The series is genuinely seasonal, so a model that cannot beat last-week
    # carry-forward is not learning anything.
    results = fc.backtest(_panel(240, noise=2.0), folds=3)

    assert results["summary"]["skill_vs_naive"]["mean"] < 1.0


def test_backtest_returns_an_empty_shape_when_there_is_no_usable_data():
    empty = fd.condition_panel(_seasonal_series("Pertussis", 5), conditions=["Pertussis"])
    results = fc.backtest(empty, folds=3)

    assert results["folds"] == []
    assert results["summary"] == {}


def test_beats_baseline_requires_winning_both():
    assert fc.beats_baseline({"summary": {
        "skill_vs_naive": {"mean": 0.8}, "skill_vs_seasonal": {"mean": 0.9}}})
    assert not fc.beats_baseline({"summary": {
        "skill_vs_naive": {"mean": 0.8}, "skill_vs_seasonal": {"mean": 1.1}}})
    assert not fc.beats_baseline({"summary": {}})


# --- intervals ---------------------------------------------------------------

def test_conformal_widening_is_never_negative():
    panel = _panel(200)
    frame = fc.supervised_frame(panel)
    forecaster = fc._fit_quantiles(frame[fd.feature_columns()], frame["y"])

    assert forecaster.delta >= 0.0


def test_interval_brackets_the_point_estimate():
    panel = _panel(200)
    frame = fc.supervised_frame(panel)
    forecaster = fc._fit_quantiles(frame[fd.feature_columns()], frame["y"])

    lo, mid, hi = forecaster.predict(frame[fd.feature_columns()].head(20))
    assert (lo <= hi).all()


def test_calibration_is_skipped_when_there_are_too_few_rows():
    panel = _panel(90)
    frame = fc.supervised_frame(panel).head(25)
    forecaster = fc._fit_quantiles(frame[fd.feature_columns()], frame["y"])

    assert forecaster.delta == 0.0


# --- prediction --------------------------------------------------------------

def test_forecast_returns_a_bracketed_non_negative_estimate():
    out = fc.forecast_conditions(_panel(200))
    ok = [r for r in out if r["status"] == "ok"]

    assert ok, "expected a forecastable condition"
    row = ok[0]
    assert row["lower"] <= row["point"] <= row["upper"]
    assert row["lower"] >= 0.0
    assert row["horizon_weeks"] == FC.HORIZON_WEEKS


def test_thin_series_returns_insufficient_history_not_a_number():
    # The property that matters clinically: a quiet-looking forecast must never
    # stand in for "we don't know".
    history = pd.concat([
        _seasonal_series("Pertussis", 200, seed=1),
        _seasonal_series("Mumps", 12, seed=2),
    ], ignore_index=True)
    panel = fd.condition_panel(history, conditions=["Pertussis", "Mumps"])

    out = {r["condition"]: r for r in fc.forecast_conditions(panel)}
    assert out["Mumps"]["status"] == fc.INSUFFICIENT_HISTORY
    assert out["Mumps"]["point"] is None


def test_forecast_reports_the_week_it_was_made_from():
    out = [r for r in fc.forecast_conditions(_panel(200)) if r["status"] == "ok"]

    assert out[0]["as_of_year"] >= 2020
    assert 1 <= out[0]["as_of_week"] <= 53
    assert out[0]["weeks_stale"] == 0


def test_a_series_that_stopped_reporting_is_flagged_stale():
    # Conditions stop reporting at different weeks. Without weeks_stale, a
    # forecast anchored to an old week looks just as current as a fresh one.
    fresh = _seasonal_series("Pertussis", 200, seed=1)
    lagging = _seasonal_series("Shigellosis", 200, seed=2).iloc[:-15]
    panel = fd.condition_panel(pd.concat([fresh, lagging], ignore_index=True),
                               conditions=["Pertussis", "Shigellosis"])

    out = {r["condition"]: r for r in fc.forecast_conditions(panel) if r["status"] == "ok"}
    assert out["Pertussis"]["weeks_stale"] == 0
    assert out["Shigellosis"]["weeks_stale"] == 15
