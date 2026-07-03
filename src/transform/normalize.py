"""Normalize raw indicators onto the dashboard's 0-100 burden scale."""

from __future__ import annotations

import pandas as pd


def normalize_burden(series: pd.Series, direction: str = "up") -> pd.Series:
    """Percentile-rank a raw indicator to a 0-100 burden score; "down" inverts (e.g. income)."""
    ranked = series.rank(pct=True) * 100  # NaN stays NaN
    if direction == "down":
        ranked = 100 - ranked
    return ranked.round(1)


def blend_domain(components: dict[str, pd.Series]) -> pd.Series:
    """Average already-normalized 0-100 components into one domain score."""
    if not components:
        raise ValueError("blend_domain requires at least one component series")
    return pd.DataFrame(components).mean(axis=1)
