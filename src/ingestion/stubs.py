"""Catalogued sources not yet wired to real data.

Each is a StubSource placeholder. To wire one, implement its real fetch/extract
(its own module is fine) and swap the base to RealSource, then update registry.py.
"""

from __future__ import annotations

from src.ingestion.base import StubSource


# Feed dashboard panels: emit placeholder rows, badged "pending ingestion".
class HrsaUds(StubSource):
    source_id = "hrsa_uds"  # quality measures + real patient counts
    stub_columns = ["health_center_patient_count", "htn_control", "dm_poor",
                    "depr_screen", "cervical_screen", "child_immun"]


class HudHousing(StubSource):
    source_id = "hud_housing"  # housing-cost portion of the food/housing domain
    stub_columns = ["housing_cost_burden_share", "fair_market_rent_2br"]


# Catalog-only: not on the current dashboard, kept for future use.
class CmsMedicarePuf(StubSource): source_id = "cms_medicare_puf"
class CmsMipsQpp(StubSource): source_id = "cms_mips_qpp"
class CmsQualityStars(StubSource): source_id = "cms_quality_stars"
class CdcNwss(StubSource): source_id = "cdc_nwss"
# cdc_nndss was promoted to a real source in US-048 (src/ingestion/cdc_nndss.py).
# It is deliberately absent from REGISTRY: it is state-keyed, so the county-wide
# merge in build_dataset.py has nothing to join it on.
class GrantsGov(StubSource): source_id = "grants_gov"
class StateFeeds(StubSource): source_id = "state_health_department_feeds"
class AsprHospitalCapacity(StubSource): source_id = "aspr_hospital_capacity"

# Scaffolded for a future county-health-burden expansion (Advanced Analytics &
# County Intelligence epic): high-value, not yet integrated. See
# documents/county-health-indicators.md for the integration writeup.
class CdcAtsdrSvi(StubSource): source_id = "cdc_atsdr_svi"
class NeighborhoodAtlasAdi(StubSource): source_id = "neighborhood_atlas_adi"
