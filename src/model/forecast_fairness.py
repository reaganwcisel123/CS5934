"""Fairness of the state-to-county allocation across rurality (US-054).

The forecast is state-level, so there is no county-level forecast error to
measure. The equity question sits in the allocation: population share assumes
disease burden tracks headcount, and rural counties carry more of the access
burden that turns a case into an untreated case.

This module quantifies that gap rather than assuming it away. It compares each
county's allocated share against its share of the population weighted by access
burden, and reports the shortfall by RUCC 2023 stratum.

Run:
    uv run python -m src.model.forecast_fairness
"""

from __future__ import annotations

import json
import sys

import pandas as pd

from src.catalog import REPO_ROOT
from src.model import forecast_config as FC

RUCC_REF = REPO_ROOT / "data" / "reference" / "va_county_rucc.csv"
ATLAS_PATH = REPO_ROOT / "dashboard" / "data" / "clinic_atlas.json"

# RUCC 2023: 1-3 metro, 4-6 nonmetro adjacent, 7-9 most rural.
RUCC_STRATA = {"metro": (1, 3), "nonmetro": (4, 6), "rural": (7, 9)}


def load_rucc(path=None) -> dict[str, int]:
    df = pd.read_csv(path or RUCC_REF, dtype={"county_fips": str})
    return dict(zip(df["county_fips"].str.zfill(5), df["rucc_2023"].astype(int)))


def load_county_context(path=None) -> pd.DataFrame:
    """County population and access-burden domain from the built atlas."""
    p = path or ATLAS_PATH
    if not p.exists():
        raise FileNotFoundError(
            f"{p} not found. Run `uv run python src/build_dataset.py` first."
        )
    records = json.loads(p.read_text(encoding="utf-8"))["records"]
    return pd.DataFrame([
        {"county_fips": r["id"],
         "population": float(r.get("patients") or 0),
         "access_burden": float((r.get("dom") or {}).get("access") or 50.0)}
        for r in records
    ])


def stratum_for(rucc: int) -> str:
    for name, (lo, hi) in RUCC_STRATA.items():
        if lo <= rucc <= hi:
            return name
    return "unknown"


def allocation_equity(
    context: pd.DataFrame | None = None,
    rucc: dict[str, int] | None = None,
) -> pd.DataFrame:
    """Per-county allocated share vs an access-weighted need share.

    `need_share` is a comparison yardstick, not a proposed allocation: it weights
    each county's population by its access burden. Where allocated < need, the
    forecast under-serves that county relative to how hard care is to reach.
    """
    ctx = context if context is not None else load_county_context()
    codes = rucc if rucc is not None else load_rucc()

    df = ctx.copy()
    total_pop = df["population"].sum()
    if total_pop <= 0:
        raise ValueError("allocation_equity: total population must be positive")

    df["allocated_share"] = df["population"] / total_pop

    weighted = df["population"] * (df["access_burden"] / 100.0)
    total_weighted = weighted.sum()
    if total_weighted <= 0:
        raise ValueError("allocation_equity: access-weighted population must be positive")
    df["need_share"] = weighted / total_weighted

    df["shortfall"] = df["need_share"] - df["allocated_share"]
    # >1 means the county is allocated less than its access-weighted need.
    df["need_ratio"] = df["need_share"] / df["allocated_share"].replace(0, pd.NA)

    df["rucc"] = df["county_fips"].map(codes)
    df["stratum"] = df["rucc"].map(lambda r: stratum_for(int(r)) if pd.notna(r) else "unknown")
    return df


def stratum_summary(equity: pd.DataFrame) -> pd.DataFrame:
    """Aggregate the shortfall by rurality stratum."""
    return (equity.groupby("stratum")
            .agg(counties=("county_fips", "count"),
                 population=("population", "sum"),
                 allocated_share=("allocated_share", "sum"),
                 need_share=("need_share", "sum"),
                 mean_access_burden=("access_burden", "mean"),
                 mean_need_ratio=("need_ratio", "mean"))
            .assign(shortfall=lambda d: d["need_share"] - d["allocated_share"])
            .reset_index()
            .sort_values("stratum"))


def disparity_verdict(summary: pd.DataFrame, threshold: float = 0.01) -> dict:
    """Whether any non-metro stratum is systematically under-allocated.

    Checks every non-metro stratum, not just the most rural one. On Virginia
    data the worst-served group is nonmetro-adjacent rather than rural, so a
    rural-only check reports "no disparity" while missing the real gap.

    threshold is an absolute share gap: 0.01 means the stratum collectively
    receives one percentage point less than its access-weighted need.
    """
    candidates = summary[summary["stratum"].isin(["rural", "nonmetro"])]
    if candidates.empty:
        return {"disparity": False, "reason": "no non-metro stratum present"}

    worst = candidates.loc[candidates["shortfall"].idxmax()]
    shortfall = float(worst["shortfall"])
    disparity = shortfall > threshold

    return {
        "disparity": disparity,
        "worst_stratum": str(worst["stratum"]),
        "worst_shortfall": round(shortfall, 4),
        "by_stratum": {str(r.stratum): round(float(r.shortfall), 4)
                       for r in candidates.itertuples()},
        "threshold": threshold,
        "allocation_method": FC.ALLOCATION_METHOD,
        "interpretation": (
            f"Population-share allocation gives {worst['stratum']} counties "
            f"{shortfall:.1%} less than their access-weighted need implies. "
            f"Treat {worst['stratum']} county figures as a floor, not an estimate."
            if disparity else
            "Population-share allocation tracks access-weighted need within the "
            "stated threshold across all non-metro strata."
        ),
    }


def main() -> int:
    equity = allocation_equity()
    summary = stratum_summary(equity)
    verdict = disparity_verdict(summary)

    print(f"Allocation equity by RUCC 2023 stratum (method: {FC.ALLOCATION_METHOD})\n")
    print(summary.to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    print(f"\nshortfall by stratum: {verdict.get('by_stratum')} "
          f"(threshold {verdict['threshold']})")
    print(f"worst: {verdict.get('worst_stratum')} | disparity: {verdict['disparity']}")
    print(f"\n{verdict['interpretation']}")

    worst = equity.nlargest(5, "shortfall")[["county_fips", "stratum", "access_burden", "need_ratio"]]
    print("\nMost under-allocated counties:")
    print(worst.to_string(index=False, float_format=lambda v: f"{v:.3f}"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
