"""Unit tests for US-012 geographic SDoH-to-patient join logic."""

from src.transform.geographic_join import (
    GEO_KEY_COUNTY_FIPS,
    RURALITY_METHOD_POPULATION_PROXY,
    join_sdoh_to_patients,
    normalize_county_fips,
)


def test_normalize_county_fips_pads_numeric_values():
    assert normalize_county_fips(51001) == "51001"
    assert normalize_county_fips("1") == "00001"
    assert normalize_county_fips(None) is None


def test_join_sdoh_to_patients_reports_coverage_and_retains_unmatched_records():
    patients = [
        {"synthetic_patient_id": "p1", "county_fips": "51001"},
        {"synthetic_patient_id": "p2", "county_fips": "51999"},
    ]
    sdoh_by_geo = {
        "51001": {
            "dom": {
                "economic": 75.0,
                "education": 20.0,
                "food": 60.0,
                "environment": 50.0,
                "access": 90.0,
            },
            "rural": 0.82,
            "ruralityMethod": RURALITY_METHOD_POPULATION_PROXY,
            "needIndex": 68.3,
        }
    }

    joined, coverage = join_sdoh_to_patients(patients, sdoh_by_geo, geo_key=GEO_KEY_COUNTY_FIPS)

    assert coverage.total_records == 2
    assert coverage.matched_records == 1
    assert coverage.unmatched_records == 1
    assert coverage.percent_matched == 50.0
    assert coverage.unmatched_keys == ("51999",)

    matched = joined[0]
    assert matched["sdohJoinStatus"] == "matched"
    assert matched["sdohJoinKey"] == "county_fips"
    assert matched["sdohGeoKey"] == "51001"
    assert matched["nb"]["economic"] == 75.0
    assert matched["rural"] == 0.82
    assert matched["needIndex"] == 68.3
    assert matched["surveyFeatures"]["status"] == "pending_survey_results"

    unmatched = joined[1]
    assert unmatched["sdohJoinStatus"] == "unmatched"
    assert unmatched["sdohGeoKey"] == "51999"
    assert unmatched["nb"] == {
        "economic": None,
        "education": None,
        "food": None,
        "environment": None,
        "access": None,
    }
    assert unmatched["rural"] is None
    assert unmatched["needIndex"] is None


def test_join_sdoh_to_patients_does_not_mutate_input_records():
    patients = [{"synthetic_patient_id": "p1", "county_fips": "51001", "nb": {"economic": 1}}]
    sdoh_by_geo = {"51001": {"dom": {"economic": 99}, "rural": 0.1}}

    joined, _ = join_sdoh_to_patients(patients, sdoh_by_geo)

    assert patients[0]["nb"] == {"economic": 1}
    assert joined[0]["nb"]["economic"] == 99