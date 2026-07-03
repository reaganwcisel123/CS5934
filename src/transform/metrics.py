"""Composite metrics over normalized domain scores (pure functions)."""

from __future__ import annotations


def need_index(dom: dict[str, float], weights: dict[str, float],
               available: set[str] | None = None) -> float:
    """Weighted 0-100 composite; weights renormalize over `available` domains so stubs don't bias it."""
    keys = [k for k in weights if available is None or k in available]
    if not keys:  # nothing available: use all
        keys = list(weights)
    total = sum(weights[k] for k in keys) or 1.0
    return round(sum(dom[k] * weights[k] for k in keys) / total, 1)
