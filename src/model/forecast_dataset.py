"""Build the condition x week panel the forecaster trains on (US-049).

Two halves:
- `condition_panel()` turns the NNDSS long series into a per-condition weekly
  panel with lag, rolling and seasonal features.
- `allocate_to_counties()` spreads a state-level number across counties by
  population share, tagging every row with how it was derived.

NNDSS is state-level, so nothing here observes a county. The allocation is
arithmetic on a disclosed rule, not a model.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.ingestion.cdc_nndss import OUT_PATH as HISTORY_PATH, TARGET_JURISDICTION
from src.model import forecast_config as FC


def load_history(path=None) -> pd.DataFrame:
    """Read the series written by `python -m src.ingestion.cdc_nndss`.

    That file now covers Virginia *and* its neighbours (for threat corroboration),
    so this filters to Virginia. Without it every condition would appear seven
    times per week and silently corrupt every lag feature.
    """
    p = path or HISTORY_PATH
    if not p.exists():
        raise FileNotFoundError(
            f"{p} not found. Run `uv run python -m src.ingestion.cdc_nndss` first."
        )
    return virginia_only(pd.read_csv(p))


def virginia_only(df: pd.DataFrame) -> pd.DataFrame:
    """Restrict a regional frame to Virginia."""
    if "jurisdiction" not in df.columns:
        return df
    return df[df["jurisdiction"].astype(str).str.upper() == TARGET_JURISDICTION].reset_index(drop=True)


def week_index(df: pd.DataFrame) -> pd.Series:
    """Monotonic week counter so lags cross year boundaries correctly.

    MMWR years run 52 or 53 weeks, so (year * 52 + week) would misalign. Ranking
    the observed (year, week) pairs keeps the ordering exact.
    """
    pairs = df[["mmwr_year", "mmwr_week"]].drop_duplicates().sort_values(["mmwr_year", "mmwr_week"])
    pairs["week_idx"] = range(len(pairs))
    return df.merge(pairs, on=["mmwr_year", "mmwr_week"], how="left")["week_idx"]


def condition_panel(
    history: pd.DataFrame | None = None,
    conditions: list[str] | None = None,
) -> pd.DataFrame:
    """One row per condition-week with its features and target."""
    # Filter again even when a frame is passed in: callers pass regional frames.
    df = virginia_only(history) if history is not None else load_history()
    wanted = conditions if conditions is not None else FC.FORECAST_CONDITIONS

    # reset_index is load-bearing: week_index() returns a merge-derived Series
    # indexed 0..n-1, which would align by label against a filtered frame.
    df = df[df["condition"].isin(wanted)].reset_index(drop=True)
    df["week_idx"] = week_index(df)
    df = df.sort_values(["condition", "week_idx"]).reset_index(drop=True)

    frames = [_features_for_one(g) for _, g in df.groupby("condition", sort=False)]
    if not frames:
        return pd.DataFrame(columns=["condition", "week_idx", FC.TARGET_COLUMN])
    return pd.concat(frames, ignore_index=True)


def _features_for_one(group: pd.DataFrame) -> pd.DataFrame:
    """Lag/rolling/seasonal features for a single condition's series.

    Every feature is computed from strictly past weeks: `shift(n)` before any
    rolling window, never after. See `assert_no_leakage`.
    """
    g = group.sort_values("week_idx").copy()
    target = g[FC.TARGET_COLUMN]

    for lag in FC.LAG_WEEKS:
        g[f"lag_{lag}"] = target.shift(lag)

    past = target.shift(1)
    for window in FC.ROLLING_WINDOWS:
        g[f"roll_mean_{window}"] = past.rolling(window, min_periods=1).mean()
        g[f"roll_std_{window}"] = past.rolling(window, min_periods=2).std()

    g[f"lag_{FC.SEASONAL_LAG_WEEKS}"] = target.shift(FC.SEASONAL_LAG_WEEKS)

    # Week-of-year as a smooth cycle so week 52 sits next to week 1.
    angle = 2 * np.pi * g["mmwr_week"].astype(float) / 52.0
    g["woy_sin"] = np.sin(angle)
    g["woy_cos"] = np.cos(angle)

    return g


def feature_columns() -> list[str]:
    cols = [f"lag_{lag}" for lag in FC.LAG_WEEKS]
    cols += [f"roll_mean_{w}" for w in FC.ROLLING_WINDOWS]
    cols += [f"roll_std_{w}" for w in FC.ROLLING_WINDOWS]
    cols += [f"lag_{FC.SEASONAL_LAG_WEEKS}", "woy_sin", "woy_cos"]
    return cols


def assert_no_leakage(panel: pd.DataFrame) -> None:
    """Fail if any lag feature equals the same week's target.

    A shift(0) slip is invisible in metrics -- it just makes the model look
    excellent -- so it is asserted rather than reviewed.
    """
    for lag in FC.LAG_WEEKS + [FC.SEASONAL_LAG_WEEKS]:
        col = f"lag_{lag}"
        if col not in panel.columns:
            continue
        for _, g in panel.groupby("condition", sort=False):
            g = g.sort_values("week_idx")
            expected = g[FC.TARGET_COLUMN].shift(lag)
            if not g[col].equals(expected):
                raise AssertionError(f"leakage: {col} is not target.shift({lag})")


def usable_conditions(panel: pd.DataFrame) -> tuple[list[str], list[str]]:
    """Split conditions into (forecastable, insufficient_history)."""
    counts = panel.groupby("condition")[FC.TARGET_COLUMN].count()
    usable = sorted(counts[counts >= FC.MIN_HISTORY_WEEKS].index)
    thin = sorted(counts[counts < FC.MIN_HISTORY_WEEKS].index)
    return usable, thin


def allocate_to_counties(state_value: float, populations: dict[str, float]) -> pd.DataFrame:
    """Split a state-level value across counties by population share.

    Returns one row per county carrying `allocation_method`, so no consumer can
    render an allocated figure as an observed one by accident.
    """
    total = sum(populations.values())
    if total <= 0:
        raise ValueError("allocate_to_counties: total population must be positive")

    rows = [
        {
            "county_fips": fips,
            "population_share": pop / total,
            "allocated_value": (state_value * pop / total) if state_value is not None else None,
            "allocation_method": FC.ALLOCATION_METHOD,
            "is_observed": False,
        }
        for fips, pop in sorted(populations.items())
    ]
    return pd.DataFrame(rows)
