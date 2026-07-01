"""Normalize raw indicators onto the dashboard's 0-100 burden scale."""

from __future__ import annotations

import pandas as pd


def normalize_burden(series: pd.Series, direction: str = "up") -> pd.Series:
    """Map a raw indicator to a 0-100 burden score (higher = more need).

    direction: "up" if higher raw means more burden, "down" to invert (e.g. income).
    """
    # USER CONTRIBUTION #1: pick the strategy (min-max / percentile / z-score),
    # handle direction="down" (invert) and NaNs, return a 0-100 pd.Series.
    raise NotImplementedError(
        "Implement normalize_burden in src/transform/normalize.py (USER CONTRIBUTION #1)."
    )


def blend_domain(components: dict[str, pd.Series]) -> pd.Series:
    """Average already-normalized 0-100 components into one domain score."""
    if not components:
        raise ValueError("blend_domain requires at least one component series")
    return pd.DataFrame(components).mean(axis=1)
