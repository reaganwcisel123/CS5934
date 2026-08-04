# Rural Clinic Grant Funding Recommender — data-science report

## Problem definition

The recommender answers a retrieval question: which active public grant opportunities have language most relevant to a county-informed rural clinic planning profile? It is not a classifier and has no historical award-success target. In particular, it is not a replacement for the Atlas `needIndex`, county high-need model, patient model, forecast, or a grant-award probability.

## Data provenance and extraction

The sole opportunity source is the public [Grants.gov API](https://www.grants.gov/api/api-guide). The live run recorded in `dashboard/data/grant_funding_matches.json` was retrieved at `2026-08-04T17:29:35Z`, with 30 detail records requested from the documented `search2` and `fetchOpportunity` endpoints. No user, clinic, patient, survey, or protected-health data enters the corpus.

| Official field | Internal field | Cleaning | Use |
| --- | --- | --- | --- |
| ID/title/number | identifier/title metadata | required string checks and deduplication | artifact key and display |
| agency/category/instrument/ALN | structured grant metadata | stable list normalization | filters and context |
| synopsis/forecast text | grant document | HTML removal and whitespace cleanup | TF-IDF and explanations |
| response/posted/archive dates | ISO dates | multi-format safe parser | filtering and deadline usability |
| award/cost-share/count | planning fields | numeric parser, `null` stays unavailable | award range/readiness |
| applicants/eligibility prose | compatibility evidence | preserve unknown text | restrained screen |

The selected live sample had 30 raw and normalized rows, no duplicates, and no rejected rows. It contained 11 posted and 19 forecasted records; six rows were closed or had a passed deadline, leaving an open-deadline rate of 0.80. Missingness was 0.0% description, 16.7% eligibility prose, 3.3% closing date, and 43.3% award range. The retained 18-record corpus had Health in every selected record's category list, while the raw data also exposed Agriculture, Community Development, Food and Nutrition, Income Security and Social Services, Business and Commerce, and Energy categories.

## Filtering and corpus profile

The small corpus is intentionally scoped by configurable rural-health planning terms, HHS (including HRSA and CDC), and USDA Rural Development subagencies. A record must be posted or forecasted, not past a stated deadline, healthcare-relevant in structured/text fields, and not clearly incompatible with Virginia or organizational applicants. The live filtering rate was 18/30 = 60.0% after the agency, relevance, deadline, and geography screens.

This is an operational search corpus, not a national census of grants. It favors explainability and manageable manual review over breadth. Because forecasts can lack a closing date, they are visible with a deadline-unavailable state rather than falsely treated as expired.

## County-profile generation

The 133 Virginia Atlas records are converted deterministically into a county-informed clinic planning profile. Controlled tags are activated only by centralized thresholds; the table below describes the rules and their planning interpretation.

| Profile tag | Source field | Trigger | Meaning |
| --- | --- | --- | --- |
| rural healthcare delivery | `rural` | >= 0.5 | rurality context |
| primary care workforce shortage | `hpsaScore` | >= 14 | HPSA planning context |
| behavioral health access | `outcomes.mhlth` | >= 20 | mental-distress context |
| diabetes prevention and management | `outcomes.diabetes` | >= 11 | chronic-condition context |
| hypertension management | `outcomes.bphigh` | >= 34 | chronic-condition context |
| food access | `dom.food` | >= 60 | social-needs planning context |
| care coordination | `dom.access` | >= 60 | access planning context |
| health equity / quality improvement | `needIndex` | >= 65 | elevated aggregate-need context |

The profile text labels itself as public county context, not a confirmed operational plan. Each tag keeps its source field, observed value, threshold rule, and human-readable explanation, which is sufficient for audit without inferring organizational facts.

## Text features and nearest-neighbor retrieval

Grant documents concatenate title, agency, synopsis/description, funding categories, instruments, applicant types, and eligibility description. A `TfidfVectorizer` lowercases text, removes English stop words, uses one- and two-word terms, applies sublinear term frequency, permits `min_df=1` in the small corpus, and caps features at 2,000. The 2026-08-04 corpus reached that 2,000-feature cap.

The same vectorizer converts each county profile. `NearestNeighbors(metric="cosine", algorithm="brute")` returns the nearest grant documents. Cosine similarity measures textual directional alignment, not an applicant's chance of success; the fitted vectorizer, neighbor index, ID ordering, corpus size, configuration, and retrieval timestamp are saved in ignored model artifacts.

## Composite score and screening

| Score component | Weight | Meaning |
| --- | ---: | --- |
| Semantic similarity | 0.75 | cosine similarity between profile and grant document |
| Category alignment | 0.10 | Health category and observed tag-term overlap |
| Eligibility compatibility | 0.10 | conservative structured screening |
| Deadline usability | 0.05 | usable date horizon or forecast/unknown fallback |

All components are clamped to 0–1 and the final score is clamped to 0–1. `Likely incompatible` hard-excludes only clear cases: closed/past deadline, named geography excluding Virginia, or individual-only applicant types. `Likely compatible` indicates organization-type categories are present; otherwise the result is `Needs verification`. The model never determines legal eligibility.

## Evaluation strategy and results

There is no award label, so supervised accuracy, ROC-AUC, and PR-AUC are intentionally not calculated. The offline fixture contains rural behavioral-health, primary-care workforce, unrelated arts, closed health, and geographically incompatible opportunities. It verifies expected behavioral/workforce ranking, closed/excluded omission, deterministic output, JSON serialization, and bound scores.

| Validation measure | Live result | Interpretation |
| --- | ---: | --- |
| Valid opportunity rate | 1.00 | every normalized record had ID/title |
| Open-deadline rate | 0.80 | six raw rows excluded as closed/past deadline |
| Healthcare relevance filtering rate | 0.600 | 18 of 30 remained in corpus |
| Opportunity coverage | 0.944 | 17 of 18 candidates appeared in at least one top-ten list |
| County recommendation coverage | 1.00 | all 133 localities received recommendations |
| Average recommendations per county | 10.0 | generated top-ten list |
| Duplicate recommendation rate | 0.00 | no duplicate ID within a county list |
| Agency diversity | 9 | agency-code diversity among recommendations |
| Category diversity | 3 | category diversity among recommendations |
| Nonempty explanation rate | 1.00 | every displayed match has reasons |
| Official-link validity rate | 1.00 | all candidates use `https://www.grants.gov/` links |

These are retrieval and data-quality checks, not claims of funding effectiveness. A manual plausibility snapshot for Accomack County surfaced, among others, a youth mental-health research opportunity (NIH), `Centers of Excellence in Healthcare Quality and Safety` (CDC), `Teaching Health Center Graduate Medical Education` (HRSA), and `Comprehensive Suicide Prevention Program for States` (CDC). These results should be reviewed by a grants professional for applicant type, geography, scope, and actual current availability; the sample is not a ground-truth ranking.

## Appropriate use, limitations, and reproducibility

Use Funding Matches to organize grant discovery and prepare a human review queue. Do not use it to assert eligibility, promise award success, rank clinical risk, or infer an individual clinic's plan. The source can change; descriptions may be incomplete; the small topical corpus can omit relevant opportunities; grant language does not capture every implementation constraint; and no PHI is used.

To reproduce the live artifact, run `uv sync --extra model` followed by `uv run python -m src.grants.pipeline --refresh --max-results 30`. To reproduce tests without external calls, run `uv run python -m src.grants.pipeline --fixture tests/fixtures/grants_gov_opportunities.json` and `uv run pytest tests/test_grants_ingestion.py tests/test_grant_recommender.py tests/test_funding_dashboard.py -q`. Raw-response, normalized-record, and fitted-model caches are ignored; the static dashboard artifact is committed so the tab has a usable initial state.
