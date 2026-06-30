# US-006 Data Source Catalog

## Purpose

This file documents the data sources used by the rural health analytics pipeline. The machine-readable source of truth is:

```text
config/data_sources.yml
```

This Markdown file is the human-readable companion. It explains what each source is, how the project expects to access it, and what limitations need to be considered before ingestion.

# Data Catalog

## Catalog Metadata Fields

Every catalog entry has identifiers (`source_id`, `source_name`), context (`provider`, `source_category`), and access-related information (`access_method`, `access_url`, `documentation_url`, `auth_required`, `api_key_env_var` - never use real keys). The geographic and temporal aspects are described by `geographic_granularity`, `temporal_granularity`, `refresh_cadence`, and `schema_version`. Integration fields (`join_keys`, `fields_used`) explain how the source relates to the resulting dataset, whereas `limitations` and `privacy_classification` identify any limitations and privacy classification of the data. Finally, the implementation status is described by `ingestion_status`, `ingestion_script`, and `last_verified_date`.

---

## source Inventory

3 sources from the CDC. **CDC PLACES: Local Data for Better Health** (`cdc_places`) can be accessed using the CDC Data Portal, Socrata API, and CSV; it has the granularity of county, place, tract, and ZCTA; its cadence is once per year (`access_verified`). **CDC National Wastewater Surveillance System** (`cdc_nwss`) has the same access methods; its granularities are plant, county, and state; it is refreshed weekly, every Friday (`access_verified`). **CDC National Notifiable Diseases Surveillance System Tables** (`cdc_nndss`) can be accessed using NNDSS, CDC WONDER, and Data.CDC.gov; it has the granularity of national, state, and territory; it is published weekly, provisionally and yearly (`schema_reviewed`).

The **HRSA Health Professional Shortage Area Designations** (`hrsa_hpsa`) come from the HRSA Data Warehouse, dashboard, and GIS REST services; they have a publisher-specific schedule; include shortage area, county, and state geographies; and are refreshed on a publisher-specific schedule (`access_verified`). The **HRSA Health Center Program Uniform Data System** (`hrsa_uds`) comes from the UDS dashboard downloads, CSV, and XLSX; includes health center, state, and national geographies; and is refreshed annually (`access_verified`).

Three CMS data sets provide Medicare and quality payment, as well as provider rating information. The **CMS Medicare Public Use Files and Program Datasets** (`cms_medicare_puf`) come from the data.cms.gov API and CSV; include provider, NPI, facility, county, and state geographies; and refresh annually or quarterly, depending on the particular dataset (`schema_reviewed`). The **CMS Quality Payment Program / MIPS Public Resources** (`cms_mips_qpp`) come from the QPP download and public APIs; include clinician, group, practice, and state geographies; and refresh annually (`not_started`). The **CMS Provider Data Catalog Quality Star Ratings** (`cms_quality_stars`) come from the Provider Data Catalog API and CSV; include facilities and states; and refresh according to the CMS scheduled cadence, which can be found in the Data Updates dataset (`access_verified`).

Two sources from the Census Bureau contain demographic and population statistics. **American Community Survey SDoH Variables** (`census_acs_sdoh`), which are retrieved from the Census Data API, include state, county, tract, and block group geography and are released yearly (`access_verified`). **Census Population Estimates Program County Population Estimates** (`county_population_estimates`) can be obtained using the Census Data API and CSV and involve county, state, and national geographies and are also released yearly (`schema_reviewed`).

Each of the remaining sources has its own distinct sphere of application. **EPA EJSCREEN Environmental Justice Indicators** (`epa_ejscreen`) are accessible via historical downloads, archives, or mirrors when the official link is not available, apply to block groups, tracts, and counties, and have been updated annually, though the current status needs to be verified (`needs_verification`). **HHS/ASPR Hospital Capacity and Utilization Data** (`aspr_hospital_capacity`) can be found on HealthData.gov, CSV, and Socrata API, are applicable to facility and state geographies, but their update ceased on 2024-05-03 (`deprecated_or_historical`). **USDA Food Access Research Atlas** (`usda_food_access`) can be found via Excel and mapping services, apply to census tracts, and are released according to an irregular release schedule (`access_verified`). **HUD Housing Affordability and Fair Market Rent Data** (`hud_housing`) are accessible via HUD USER API and open data downloads, apply to county, metro, ZIP, and state geographies, and are updated annually for FMR and income limits, while other datasets differ (`access_verified`). The **Grants.gov Public Funding Opportunity Search** (`grants_gov`) is available using REST API, includes opportunities, agencies, listings, and eligibility and is continually updated as more agencies post (`access_verified`). The **State Health Department Public Feeds** (`state_health_department_feeds`) include state and territory level health department data sources via state-level specific APIs, dashboards, RSS, Socrata, or ArcGIS Hub, depending on state, with geographic and temporal variation by state — all of which should be described prior to ingest (`not_started`). Lastly, the **Project Synthetic Non-PHI Clinical Dataset** (`synthetic_clinical_dataset`) is a generated repository dataset involving synthetic patient, clinic, and county level data, to be generated anew for each version (`not_started`).

## notes for my other team members

- `epa_ejscreen` was marked `needs_verification` because official access needed to be confirmed before production ingestion. I looked into this and updated the access url(still kinda iffy on where they were using this on the health engine though)
- `aspr_hospital_capacity` is marked `deprecated_or_historical` because the COVID-era HealthData.gov feed is historical and should not be treated as current hospital-capacity surveillance.
- `state_health_department_feeds` is intentionally generic until target states are selected. Once a state is selected, add one child catalog entry per feed or state.
- `synthetic_clinical_dataset` must remain synthetic and non-PHI. Do not commit real patient data.
