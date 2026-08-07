"""Translate condition forecasts into anticipated clinic supply needs (US-051).

The mapping itself is hand-authored in data/reference/condition_supply_map.yml
and read here verbatim. Nothing in this module infers what a clinic should
stock; it multiplies a disclosed per-case factor by a forecast range.

Quantities are ranges taken from the forecast's prediction interval, so a
clinic sees planning bounds rather than a false-precision single number.
"""

from __future__ import annotations

import math

import yaml

from src.catalog import REPO_ROOT

SUPPLY_MAP_PATH = REPO_ROOT / "data" / "reference" / "condition_supply_map.yml"

UNMAPPED = "unmapped"
INSUFFICIENT_HISTORY = "insufficient_history"

DISCLAIMER = (
    "Planning aid only. Quantities are modelled estimates from state-level "
    "surveillance, not a procurement instruction or a clinical protocol."
)


def load_supply_map(path=None) -> dict:
    p = path or SUPPLY_MAP_PATH
    if not p.exists():
        raise FileNotFoundError(f"Missing supply map: {p}")
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


def review_status(supply_map: dict | None = None) -> dict:
    """Whether the blurbs have been signed off by a clinician.

    Surfaced on every payload so the UI cannot render un-reviewed clinical
    guidance as settled.
    """
    data = supply_map if supply_map is not None else load_supply_map()
    return {
        "clinical_review": data.get("clinical_review", "pending"),
        "note": (data.get("clinical_review_note") or "").strip(),
    }


def blurb_for(condition: str, supply_map: dict | None = None) -> str | None:
    data = supply_map if supply_map is not None else load_supply_map()
    entry = (data.get("conditions") or {}).get(condition)
    return ((entry or {}).get("blurb") or "").strip() or None


def supply_needs(
    forecasts: list[dict],
    supply_map: dict | None = None,
    overrides: dict | None = None,
) -> list[dict]:
    """Expand condition forecasts into per-item quantity ranges.

    `overrides` maps "Condition::Item" to a replacement per_case factor, so a
    clinic can correct a figure without editing the shared mapping file.
    """
    mapping = (supply_map if supply_map is not None else load_supply_map()).get("conditions", {})
    overrides = overrides or {}
    out = []

    for row in forecasts:
        condition = row.get("condition")
        entry = mapping.get(condition)

        if entry is None:
            # Surfaced, not dropped: an unmapped condition is a gap in the
            # mapping file, and hiding it would read as "nothing to stock".
            out.append({"condition": condition, "status": UNMAPPED, "items": [],
                        "rationale": None, "blurb": None, "disclaimer": DISCLAIMER})
            continue

        if row.get("status") != "ok":
            out.append({"condition": condition, "status": row.get("status", INSUFFICIENT_HISTORY),
                        "items": [], "rationale": entry.get("rationale"),
                        "blurb": (entry.get("blurb") or "").strip() or None,
                        "disclaimer": DISCLAIMER})
            continue

        lower, upper = row.get("lower"), row.get("upper")
        point = row.get("point")
        items = []
        for item in entry.get("supplies", []):
            key = f"{condition}::{item['item']}"
            per_case = float(overrides.get(key, item.get("per_case", 0.0)))
            items.append({
                "item": item["item"],
                "per_case": per_case,
                "overridden": key in overrides,
                "quantity_low": _units(lower, per_case),
                "quantity_expected": _units(point, per_case),
                "quantity_high": _units(upper, per_case),
                "note": item.get("note"),
            })

        out.append({
            "condition": condition,
            "status": "ok",
            "rationale": entry.get("rationale"),
            "blurb": (entry.get("blurb") or "").strip() or None,
            "forecast_low": lower,
            "forecast_expected": point,
            "forecast_high": upper,
            "horizon_weeks": row.get("horizon_weeks"),
            "weeks_stale": row.get("weeks_stale"),
            "items": items,
            "disclaimer": DISCLAIMER,
        })

    return out


def _units(cases: float | None, per_case: float) -> int | None:
    """Round up: under-stocking a clinic is worse than over-stocking it."""
    if cases is None:
        return None
    return int(math.ceil(max(0.0, float(cases)) * per_case))


def unmapped_conditions(forecasts: list[dict], supply_map: dict | None = None) -> list[str]:
    """Conditions being forecast with no entry in the mapping file."""
    mapping = (supply_map if supply_map is not None else load_supply_map()).get("conditions", {})
    return sorted({r["condition"] for r in forecasts if r.get("condition") not in mapping})
