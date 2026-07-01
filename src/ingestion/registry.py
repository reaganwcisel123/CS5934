"""Map every catalog source_id to its ingestion class (stubs live in stubs.py)."""

from __future__ import annotations

from src.ingestion import stubs
from src.ingestion.cdc_places import CdcPlaces
from src.ingestion.census_acs import CensusAcs
from src.ingestion.census_pep import CensusPep
from src.ingestion.hrsa_hpsa import HrsaHpsa
from src.ingestion.synthetic_clinical import SyntheticClinical
from src.ingestion.usda_food_access import UsdaFoodAccess

# Wired (real + synthetic).
_WIRED = [CdcPlaces, CensusAcs, CensusPep, HrsaHpsa, UsdaFoodAccess, SyntheticClinical]
# Stubs for a future coder to promote to RealSource.
_STUBS = [stubs.EpaEjscreen, stubs.HrsaUds, stubs.HudHousing, stubs.CmsMedicarePuf,
          stubs.CmsMipsQpp, stubs.CmsQualityStars, stubs.CdcNwss, stubs.CdcNndss,
          stubs.GrantsGov, stubs.StateFeeds, stubs.AsprHospitalCapacity]

REGISTRY = {cls.source_id: cls for cls in _WIRED + _STUBS}
