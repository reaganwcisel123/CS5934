"""Synthetic non-PHI patient roster -> patientsList + preventable flag.

Deterministic per county (seeded from county_fips) so builds are reproducible
and no real patient data is touched. The build injects the county list via
self.counties and fills each patient's nb from real county domains.
"""

from __future__ import annotations

import math

import pandas as pd

from src.ingestion.base import BaseSource, Provenance

FIRST = ["Maria", "James", "Dwayne", "Aisha", "Robert", "Linda", "Carlos", "Nina",
         "Tomas", "Grace", "Andre", "Priya", "Wanda", "Eli", "Rosa", "Marcus"]
LAST = ["Whitfield", "Nguyen", "Carter", "Okafor", "Diaz", "Bryant", "Flowers",
        "Ramos", "Coleman", "Park", "Sullivan", "Abara"]
STRUGGLES = [
    ("Food insecurity", "food"), ("Housing instability", "food"),
    ("No reliable transport", "access"), ("Lost insurance coverage", "economic"),
    ("Medication cost", "economic"), ("Uncontrolled diabetes", "access"),
    ("Depression / isolation", "environment"), ("Job loss", "economic"),
]
VISIT_DATES = ["Jun 19, 2026", "Jun 11, 2026", "May 29, 2026", "May 14, 2026",
               "Apr 30, 2026", "Apr 8, 2026", "Mar 22, 2026", "Mar 3, 2026"]
DOMAIN_KEYS = ["economic", "education", "food", "environment", "access"]


class _Rng:
    """Mulberry32 PRNG (matches the dashboard's generator)."""

    def __init__(self, seed: int) -> None:
        self.a = seed & 0xFFFFFFFF

    def next(self) -> float:
        self.a = (self.a + 0x6D2B79F5) & 0xFFFFFFFF
        t = self.a
        t = ((t ^ (t >> 15)) * (t | 1)) & 0xFFFFFFFF
        t ^= (t + (((t ^ (t >> 7)) * (t | 61)) & 0xFFFFFFFF)) & 0xFFFFFFFF
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296.0

    def gauss(self, mu: float, sd: float) -> float:
        u1 = max(self.next(), 1e-9)
        u2 = self.next()
        return mu + sd * math.sqrt(-2 * math.log(u1)) * math.cos(2 * math.pi * u2)


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


class SyntheticClinical(BaseSource):
    source_id = "synthetic_clinical_dataset"
    provenance = Provenance.SYNTHETIC

    def run(self, use_cache: bool = True) -> pd.DataFrame:
        counties = getattr(self, "counties", [])
        return pd.DataFrame([self._roster_for(fips) for fips in counties])

    def _roster_for(self, county_fips: str) -> dict:
        rng = _Rng(int(county_fips))
        n = 3 + int(rng.next() * 2)  # 3-4 patients
        roster, preventable = [], 0
        for _ in range(n):
            struggle, dom = STRUGGLES[int(rng.next() * len(STRUGGLES))]
            sys = round(_clamp(rng.gauss(128, 14), 98, 182))
            dia = round(_clamp(sys * 0.55 + rng.gauss(0, 6), 58, 112))
            a1c = round(_clamp(rng.gauss(6.6, 1.4), 5.0, 12.8), 1)
            flag = 1 if rng.next() < 0.18 else 0
            preventable += flag
            roster.append({
                "name": f"{FIRST[int(rng.next()*len(FIRST))]} {LAST[int(rng.next()*len(LAST))][0]}.",
                "age": round(28 + rng.next() * 51),
                "lastVisit": VISIT_DATES[int(rng.next() * len(VISIT_DATES))],
                "struggle": struggle,
                "struggleDom": dom,
                "bp": f"{sys}/{dia}",
                "sys": sys, "dia": dia, "a1c": a1c,
                "preventable_hospitalization_flag": flag,
                # nb (neighborhood burdens) filled from real county domains in build.
                "nb": {k: None for k in DOMAIN_KEYS},
            })
        return {
            "county_fips": county_fips,
            "patientsList": roster,
            "synthetic_preventable_hospitalization_flag": round(preventable / n, 3),
        }
