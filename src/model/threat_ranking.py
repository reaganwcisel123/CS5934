"""Rank which notifiable diseases most threaten Virginia clinics right now (US-056).

Answers a different question from src/model/forecast.py. The forecast says how
many cases to expect for a fixed set of conditions; this ranks *all* reported
conditions by how far above their own seasonal norm they are running, and checks
whether neighbouring states corroborate the rise.

The baseline is seasonal on purpose. Against a trailing window Cyclosporiasis
looks like a 16x explosion every July, which is just summer. Against the same
MMWR weeks in prior years it is 2.4x, which is an actual anomaly.

Run:
    uv run python -m src.model.threat_ranking
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from src.ingestion.cdc_nndss import (
    NEIGHBOR_JURISDICTIONS,
    TARGET_JURISDICTION,
    OUT_PATH as HISTORY_PATH,
)

RECENT_WEEKS = 8
BASELINE_YEARS = 4

# +1 on both sides of the ratio. Load-bearing: Measles has no prior-year reports
# in 3 of 4 years, so an unsmoothed ratio divides by ~0 and returns infinity.
SMOOTHING = 1.0

# A condition must be doing this much per week in Virginia to rank at all, so a
# 1-to-4 case jump cannot top the list.
MIN_RECENT_CASES = 3.0

# What counts as "rising" in a neighbour: a real ratio and enough volume to mean it.
NEIGHBOR_RATIO = 1.2
NEIGHBOR_MIN_CASES = 2.0

NEIGHBOR_WEIGHT = 0.10
TOP_N = 5


def load_region(path=None) -> pd.DataFrame:
    p = path or HISTORY_PATH
    if not p.exists():
        raise FileNotFoundError(
            f"{p} not found. Run `uv run python -m src.ingestion.cdc_nndss` first."
        )
    return pd.read_csv(p)


def latest_week(df: pd.DataFrame) -> tuple[int, int]:
    """The most recent (mmwr_year, mmwr_week) carrying any reported value."""
    reported = df.dropna(subset=["cases"])
    if reported.empty:
        raise ValueError("threat_ranking: no reported cases in the history")
    year = int(reported["mmwr_year"].max())
    week = int(reported.loc[reported["mmwr_year"] == year, "mmwr_week"].max())
    return year, week


def _window(year: int, week: int) -> tuple[int, int]:
    """The recent comparison window, as an inclusive MMWR week range."""
    return max(1, week - RECENT_WEEKS + 1), week


def condition_stats(
    df: pd.DataFrame,
    jurisdiction: str,
    year: int,
    lo: int,
    hi: int,
) -> pd.DataFrame:
    """Recent mean vs the same weeks in prior years, per condition."""
    j = df[df["jurisdiction"].astype(str).str.upper() == jurisdiction.upper()]
    in_window = j[j["mmwr_week"].between(lo, hi)]

    recent = (in_window[in_window["mmwr_year"] == year]
              .groupby("condition")["cases"].mean())
    baseline = (in_window[(in_window["mmwr_year"] < year)
                          & (in_window["mmwr_year"] >= year - BASELINE_YEARS)]
                .groupby("condition")["cases"].mean())

    out = pd.DataFrame({"recent": recent}).join(baseline.rename("seasonal_base"), how="left")
    out = out.dropna(subset=["recent"])
    # A condition absent in prior years has a baseline of zero, not unknown.
    out["seasonal_base"] = out["seasonal_base"].fillna(0.0)
    out["ratio"] = (out["recent"] + SMOOTHING) / (out["seasonal_base"] + SMOOTHING)
    return out


def rank_threats(df: pd.DataFrame | None = None, top_n: int = TOP_N) -> list[dict]:
    """Rank Virginia conditions by seasonal anomaly, corroborated regionally."""
    region = df if df is not None else load_region()
    year, week = latest_week(region)
    lo, hi = _window(year, week)

    va = condition_stats(region, TARGET_JURISDICTION, year, lo, hi)
    va = va[va["recent"] >= MIN_RECENT_CASES]
    if va.empty:
        return []

    # Which neighbours are also above their own seasonal norm.
    corroborating: dict[str, list[str]] = {c: [] for c in va.index}
    for neighbor in NEIGHBOR_JURISDICTIONS:
        stats = condition_stats(region, neighbor, year, lo, hi)
        rising = stats[(stats["ratio"] > NEIGHBOR_RATIO)
                       & (stats["recent"] >= NEIGHBOR_MIN_CASES)]
        for condition in rising.index:
            if condition in corroborating:
                corroborating[condition].append(_title(neighbor))

    rows = []
    for condition, r in va.iterrows():
        neighbors = sorted(corroborating.get(condition, []))
        rows.append({
            "condition": condition,
            "recent_weekly_mean": round(float(r["recent"]), 1),
            "seasonal_baseline": round(float(r["seasonal_base"]), 1),
            "ratio": round(float(r["ratio"]), 2),
            "neighbors_rising": len(neighbors),
            "neighbor_states": neighbors,
            "score": round(float(r["ratio"]) * (1 + NEIGHBOR_WEIGHT * len(neighbors)), 3),
            "weeks_compared": f"W{lo}-W{hi}",
            "as_of_year": year,
            "as_of_week": week,
            "baseline_years": BASELINE_YEARS,
        })

    rows.sort(key=lambda r: r["score"], reverse=True)
    return rows[:top_n]


def recent_series(df: pd.DataFrame, condition: str, weeks: int = 16) -> list[dict]:
    """Trailing weekly values for one Virginia condition, for a sparkline."""
    va = df[(df["jurisdiction"].astype(str).str.upper() == TARGET_JURISDICTION)
            & (df["condition"] == condition)]
    va = va.sort_values(["mmwr_year", "mmwr_week"]).tail(weeks)
    return [{"year": int(r.mmwr_year), "week": int(r.mmwr_week),
             "cases": None if pd.isna(r.cases) else float(r.cases)}
            for r in va.itertuples()]


def _title(name: str) -> str:
    return " ".join(w.capitalize() if w.lower() != "of" else "of" for w in name.split())


def main() -> int:
    region = load_region()
    threats = rank_threats(region, top_n=8)
    year, week = latest_week(region)

    print(f"Virginia threat ranking, {RECENT_WEEKS} weeks through W{week}/{year}")
    print(f"vs the same weeks in the prior {BASELINE_YEARS} years\n")
    print(f"{'condition':<46}{'now/wk':>8}{'normal':>8}{'ratio':>7}{'nbrs':>6}{'score':>7}")
    for t in threats:
        print(f"{t['condition'][:45]:<46}{t['recent_weekly_mean']:>8.1f}"
              f"{t['seasonal_baseline']:>8.1f}{t['ratio']:>7.2f}"
              f"{t['neighbors_rising']:>6}{t['score']:>7.2f}")
        if t["neighbor_states"]:
            print(f"{'':>4}also rising in: {', '.join(t['neighbor_states'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
