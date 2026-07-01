"""Base classes and shared contract for ingestion sources.

Each source binds to a catalog source_id, reads its access URL from the catalog
(never hardcoded), and returns a DataFrame keyed on 5-digit county_fips filtered
to the target state.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.catalog import Catalog, REPO_ROOT

TARGET_STATE_FIPS = "51"  # Virginia; matches the dashboard's regions
RAW_DIR = REPO_ROOT / "data" / "raw"


class Provenance:
    """How trustworthy a value is; surfaced to the dashboard as a badge."""

    REAL = "real"            # fetched from the real upstream source
    SYNTHETIC = "synthetic"  # generated non-PHI data (by design)
    STUB = "stub"            # placeholder until a coder wires the source


class BaseSource:
    """One ingestion source, bound to a catalog entry."""

    source_id: str = ""
    provenance: str = Provenance.REAL

    def __init__(self, catalog: Catalog) -> None:
        self.catalog = catalog
        self.entry = catalog.source(self.source_id)  # raises if not catalogued

    @property
    def access_url(self) -> str:
        return self.entry["access_url"]

    @property
    def schema_version(self) -> str:
        return self.entry.get("schema_version", "")

    @property
    def raw_path(self) -> Path:
        return RAW_DIR / f"{self.source_id}.csv"  # committed raw cache

    def fetch_raw(self) -> Path:
        """Download upstream data into self.raw_path."""
        raise NotImplementedError

    def extract(self) -> pd.DataFrame:
        """Parse cached raw data into a county_fips-keyed DataFrame."""
        raise NotImplementedError

    def run(self, use_cache: bool = True) -> pd.DataFrame:
        # Fetch (unless cached) then extract.
        if not (use_cache and self.raw_path.exists()):
            RAW_DIR.mkdir(parents=True, exist_ok=True)
            self.fetch_raw()
        df = self.extract()
        _assert_county_keyed(df, self.source_id)
        return df


class RealSource(BaseSource):
    provenance = Provenance.REAL


class StubSource(BaseSource):
    """A catalogued source not yet wired to real data.

    run() never touches the network; it returns placeholder rows for the given
    counties so the dashboard renders with an honest "pending" badge.
    """

    provenance = Provenance.STUB
    stub_columns: list[str] = []

    def run(self, use_cache: bool = True) -> pd.DataFrame:
        # Counties are injected by the orchestrator before run().
        counties = getattr(self, "stub_counties", [])
        df = self.stub_frame(counties)
        _assert_county_keyed(df, self.source_id)
        return df

    def stub_frame(self, county_fips: list[str]) -> pd.DataFrame:
        # USER CONTRIBUTION #3: choose a stub's placeholder value and how the
        # frame signals "stub" (null vs neutral 50 vs synthetic). Return a
        # DataFrame with county_fips plus one column per self.stub_columns.
        raise NotImplementedError(
            f"Stub contract not implemented for '{self.source_id}' "
            "(USER CONTRIBUTION #3 in src/ingestion/base.py)."
        )


def _assert_county_keyed(df: pd.DataFrame, source_id: str) -> None:
    if "county_fips" not in df.columns:
        raise ValueError(f"{source_id}: extract() must return a 'county_fips' column")
