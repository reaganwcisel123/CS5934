# US-012 Geographic Join Implementation Notes

## Summary
Implemented the geographic join that attaches community-level social determinants of health (SDoH) context to patient records.

## What changed
- Added `src/transform/geographic_join.py` with pure join utilities:
  - normalizes the geographic key;
  - joins community SDoH onto patient records;
  - applies the same rurality value to each matched patient that is used on the county record;
  - reports join coverage; and
  - keeps unmatched patient records with explicit null SDoH/rurality context.
- Updated `src/ingestion/synthetic_clinical.py` so each synthetic patient now carries `county_fips` directly on the patient record.
- Updated `src/build_dataset.py` so patient `patientsList` rows are passed through the geographic join instead of having only `nb` manually assigned.
- Added top-level `sdoh_join_coverage` metadata to the built dataset output.
- Added `tests/test_geographic_join.py` to unit-test matched and unmatched join behavior against a small fixture.

## Defined geographic key
The implemented join key is `county_fips`, a 5-digit county FIPS code. This matches the existing community-level SDoH pipeline, where county-level indicator frames are keyed by `county_fips`.

Current key flow:

```text
community SDoH by county_fips  +  patient county_fips  ->  joined patient SDoH context