"""Map every catalog source_id to its ingestion class (stubs live in stubs.py)."""

from __future__ import annotations

from src.ingestion import stubs
from src.ingestion.cdc_places import CdcPlaces
from src.ingestion.census_acs import CensusAcs
from src.ingestion.census_pep import CensusPep
from src.ingestion.cdc_eji import CdcEji
from src.ingestion.hrsa_hpsa import HrsaHpsa
from src.ingestion.hrsa_uds import HrsaUds
from src.ingestion.hud_housing import HudHousing
from src.ingestion.synthetic_clinical import SyntheticClinical
from src.ingestion.usda_food_access import UsdaFoodAccess
from src.ingestion.virginia_chronic_disease_hospitalization import VirginiaChronicDiseaseHospitalization

# Wired (real + synthetic).
_WIRED = [CdcPlaces, CensusAcs, CensusPep, CdcEji, HrsaHpsa, HrsaUds,
          HudHousing, UsdaFoodAccess, SyntheticClinical,
          VirginiaChronicDiseaseHospitalization]
# Stubs for a future coder to promote to RealSource.
_STUBS = [stubs.CmsMedicarePuf, stubs.CmsMipsQpp, stubs.CmsQualityStars,
          stubs.CdcNwss, stubs.GrantsGov, stubs.StateFeeds,
          stubs.AsprHospitalCapacity]

# NOTE: cdc_nndss (US-048) is intentionally not registered. REGISTRY drives the
# county-wide merge in build_dataset.py, and NNDSS is state-keyed weekly data
# with no county column. It runs on its own via `python -m src.ingestion.cdc_nndss`
# and feeds the forecasting pipeline in src/model/ instead.

REGISTRY = {cls.source_id: cls for cls in _WIRED + _STUBS}
