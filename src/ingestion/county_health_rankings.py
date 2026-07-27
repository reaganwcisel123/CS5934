"""County Health Rankings national county analytic data for access-failure modeling.

The March 2026 supplemental release is a national, public county analytic file.
This adapter intentionally retains only the measure values used by the Rural Care
Access Failure Model; it is not part of the normal Virginia dashboard build.
"""

from __future__ import annotations

import logging
import math
import os
from pathlib import Path

import pandas as pd
import requests

from src.ingestion.base import RealSource, _assert_county_keyed

logger = logging.getLogger(__name__)

LOCAL_PATH_ENV = "COUNTY_HEALTH_RANKINGS_PATH"
RELEASE_YEAR = 2026

# Field names are verified against the CHR&R March 25, 2026 supplemental
# analytic-dataset codebook. *_rawalternatevalue is population per provider.
TARGET_COLUMN = "v005_rawvalue"
FIELD_MAP = {
    "v003_rawvalue": "uninsured_percent",
    "v004_rawalternatevalue": "primary_care_physician_burden",
    "v062_rawalternatevalue": "mental_health_provider_burden",
    "v131_rawalternatevalue": "other_primary_care_provider_burden",
    "v166_rawvalue": "broadband_access_percent",
}
MISSING_MARKERS = {
    "",
    "na",
    "n/a",
    "nan",
    "null",
    "none",
    "suppressed",
    "not available",
    "not applicable",
    "*",
}


class CountyHealthRankingsSchemaError(ValueError):
    """Raised when the official analytic file lacks a required model field."""


def normalize_county_fips(value: object) -> str | None:
    """Return a five-digit county FIPS, preserving county-equivalent codes."""
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    if not text or text.lower() in MISSING_MARKERS:
        return None
    if text.endswith(".0") and text[:-2].isdigit():
        text = text[:-2]
    if not text.isdigit() or len(text) > 5:
        return None
    return text.zfill(5)


def parse_number(value: object) -> float | None:
    """Parse a finite numeric source value while treating suppression as null."""
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    if not text or text.lower() in MISSING_MARKERS:
        return None
    text = text.replace(",", "").replace("%", "")
    try:
        number = float(text)
    except ValueError:
        return None
    return number if math.isfinite(number) else None


def parse_population_per_provider(value: object) -> float | None:
    """Parse CHR&R's documented population-to-provider ratio as burden.

    A zero in the official ratio field denotes zero providers, not a usable
    finite ratio, so it remains missing rather than becoming an extreme value.
    """
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    if not text or text.lower() in MISSING_MARKERS:
        return None
    if ":" in text:
        numerator, denominator, *rest = text.replace(",", "").split(":")
        if rest:
            return None
        numerator_value = parse_number(numerator)
        denominator_value = parse_number(denominator)
        if numerator_value is None or denominator_value != 1:
            return None
        number = numerator_value
    else:
        number = parse_number(text)
    return number if number is not None and number > 0 else None


def parse_percent(value: object) -> float | None:
    """Normalize CHR&R proportion/percentage values to the 0-100 scale."""
    number = parse_number(value)
    if number is None or number < 0:
        return None
    if number <= 1:
        return number * 100
    return number if number <= 100 else None


class CountyHealthRankings(RealSource):
    """Extract a national, county-keyed access-failure modeling table."""

    source_id = "county_health_rankings"
    training_only = True

    @property
    def _local_override(self) -> Path | None:
        raw_path = os.environ.get(LOCAL_PATH_ENV)
        return Path(raw_path).expanduser() if raw_path else None

    @property
    def input_path(self) -> Path:
        return self._local_override or self.raw_path

    def run(self, use_cache: bool = True) -> pd.DataFrame:
        override = self._local_override
        if override is not None:
            if not override.exists():
                raise FileNotFoundError(
                    f"{LOCAL_PATH_ENV} points to a missing file: {override}"
                )
            df = self.extract()
            _assert_county_keyed(df, self.source_id)
            return df
        return super().run(use_cache=use_cache)

    def fetch_raw(self) -> None:
        response = requests.get(self.access_url, timeout=120)
        response.raise_for_status()
        self.raw_path.write_bytes(response.content)

    def extract(self) -> pd.DataFrame:
        raw = pd.read_csv(self.input_path, dtype=str, low_memory=False)
        if "fipscode" not in raw.columns:
            raise CountyHealthRankingsSchemaError(
                "County Health Rankings data is missing required 'fipscode'."
            )
        if TARGET_COLUMN not in raw.columns:
            raise CountyHealthRankingsSchemaError(
                "County Health Rankings data is missing required "
                f"preventable-hospital-stays field '{TARGET_COLUMN}'."
            )

        available = {
            source: canonical
            for source, canonical in FIELD_MAP.items()
            if source in raw.columns
        }
        missing_optional = sorted(set(FIELD_MAP) - set(available))
        if missing_optional:
            logger.warning(
                "county_health_rankings optional fields unavailable: %s",
                ", ".join(missing_optional),
            )

        frame = pd.DataFrame(
            {
                "county_fips": raw["fipscode"].map(normalize_county_fips),
                "preventable_hospital_stays": raw[TARGET_COLUMN].map(parse_number),
            }
        )
        for source, canonical in available.items():
            parser = (
                parse_population_per_provider
                if canonical.endswith("_burden")
                else parse_percent
            )
            frame[canonical] = raw[source].map(parser)

        source_year = RELEASE_YEAR
        if "supplement" in raw.columns:
            release_years = raw["supplement"].astype(str).str.extract(r"(20\d{2})")[0]
            if release_years.notna().any():
                source_year = int(release_years.dropna().iloc[0])
        frame["source_year"] = source_year

        source_rows = len(frame)
        missing_fips = int(frame["county_fips"].isna().sum())
        # National and state rows use 000 county codes. All other valid FIPS,
        # including Virginia independent cities, remain county equivalents.
        frame = frame[
            frame["county_fips"].notna()
            & ~frame["county_fips"].str.endswith("000", na=False)
        ].copy()

        value_columns = [
            column
            for column in frame.columns
            if column not in {"county_fips", "source_year"}
        ]
        frame["_nonnull_count"] = frame[value_columns].notna().sum(axis=1)
        frame["_row_order"] = range(len(frame))
        duplicate_rows = int(frame.duplicated("county_fips", keep=False).sum())
        frame = (
            frame.sort_values(
                ["county_fips", "_nonnull_count", "_row_order"],
                ascending=[True, False, True],
            )
            .drop_duplicates("county_fips", keep="first")
            .drop(columns=["_nonnull_count", "_row_order"])
            .sort_values("county_fips")
            .reset_index(drop=True)
        )

        null_rates = {
            column: round(float(frame[column].isna().mean()), 3)
            for column in value_columns
        }
        virginia_count = int(frame["county_fips"].str.startswith("51").sum())
        logger.info(
            "county_health_rankings source_rows=%d retained_counties=%d "
            "unique_fips=%d duplicate_rows=%d missing_fips=%d "
            "virginia_coverage=%d national_county_coverage=%d null_rates=%s",
            source_rows,
            len(frame),
            frame["county_fips"].nunique(),
            duplicate_rows,
            missing_fips,
            virginia_count,
            len(frame),
            null_rates,
        )
        return frame
