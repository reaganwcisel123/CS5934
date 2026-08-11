from __future__ import annotations

import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).parents[1]


def test_funding_matches_is_an_isolated_additive_view() -> None:
    app = (ROOT / "dashboard" / "app.html").read_text(encoding="utf-8")
    main = (ROOT / "dashboard" / "app" / "main.js").read_text(encoding="utf-8")
    shell = (ROOT / "dashboard" / "app" / "components" / "shell.js").read_text(encoding="utf-8")
    view = (ROOT / "dashboard" / "app" / "views" / "funding-matches.js").read_text(encoding="utf-8")
    css = (ROOT / "dashboard" / "app" / "funding-matches.css").read_text(encoding="utf-8")
    assert 'src="app/views/funding-matches.js"' in app
    assert 'src="app/funding-state.js"' in app
    assert 'href="app/funding-matches.css"' in app
    assert '"funding"' in main
    assert 'label: "Funding Matches"' in shell
    assert "FundingMatchesView" in view
    assert "Grants.gov" in view
    assert "target=\"_blank\" rel=\"noopener noreferrer\"" in view
    assert ".funding-matches" in css


def test_existing_views_do_not_receive_funding_content() -> None:
    existing = ["overview.js", "forest.js", "county.js", "worklist.js", "trends.js", "explore.js", "methods.js"]
    prohibited = ("Funding Matches", "Grants.gov", "grant recommender", "opportunity match", "eligibility status")
    for name in existing:
        content = (ROOT / "dashboard" / "app" / "views" / name).read_text(encoding="utf-8")
        assert not any(term in content for term in prohibited), name


def test_funding_view_resets_county_scoped_state_and_uses_county_rows_for_metrics() -> None:
    view = (ROOT / "dashboard" / "app" / "views" / "funding-matches.js").read_text(encoding="utf-8")
    state = (ROOT / "dashboard" / "app" / "funding-state.js").read_text(encoding="utf-8")
    assert "data-county-fips={selectedFips}" in view
    assert "data-lookback-days={lookbackDays}" in view
    assert "initialFips !== selectedFips" in view
    assert "setSelectedId(null)" in view
    assert "State.countyRows" in view
    assert "Opportunity posted within" in view
    assert "Show more" in view
    assert "Gemini relevance" in view
    assert "TF-IDF" not in view and "cosine distance" not in view
    assert "LOOKBACK_OPTIONS" in state and "isOpenInWindow" in state


def test_funding_state_matrix_keeps_county_and_lookback_results_in_sync() -> None:
    artifact = {
        "opportunities": {
            "seven": {"status": "posted", "postingDate": "2026-08-03", "closingDate": "2026-09-01", "agency": "HHS"},
            "fourteen": {"status": "posted", "postingDate": "2026-07-27", "closingDate": "2026-09-10", "agency": "USDA"},
            "thirty": {"status": "posted", "postingDate": "2026-07-12", "closingDate": "2026-09-20", "agency": "DOL"},
            "ninety": {"status": "posted", "postingDate": "2026-05-15", "closingDate": "2026-10-01", "agency": "HHS"},
            "oneeighty": {"status": "posted", "postingDate": "2026-03-01", "closingDate": "2026-10-05", "agency": "HHS"},
            "year": {"status": "posted", "postingDate": "2025-09-01", "closingDate": "2026-11-01", "agency": "USDA"},
            "expired": {"status": "posted", "postingDate": "2026-08-02", "closingDate": "2026-08-09", "agency": "HHS"},
        },
        "matchesByCounty": {
            "A": [{"opportunityId": "seven", "matchTier": "Strong relevance", "matchScore": .9, "daysRemaining": 22}, {"opportunityId": "fourteen", "matchTier": "Moderate relevance", "matchScore": .6, "daysRemaining": 31}, {"opportunityId": "thirty", "matchTier": "Limited relevance", "matchScore": .4, "daysRemaining": 41}],
            "B": [{"opportunityId": "seven", "matchTier": "Limited relevance", "matchScore": .3, "daysRemaining": 22}, {"opportunityId": "ninety", "matchTier": "Strong relevance", "matchScore": .8, "daysRemaining": 52}],
            "C": [{"opportunityId": "oneeighty", "matchTier": "Moderate relevance", "matchScore": .5, "daysRemaining": 56}, {"opportunityId": "year", "matchTier": "Strong relevance", "matchScore": .7, "daysRemaining": 83}],
        },
    }
    state_path = ROOT / "dashboard" / "app" / "funding-state.js"
    script = "const S=require(process.argv[1]); const A=JSON.parse(process.argv[2]); const t='2026-08-10'; const out={available:[7,14,30,90,180,365].map(d=>S.availableOpportunities(A,d,t).length),a30:S.countyRows(A,'A',30,t).length,b30:S.countyRows(A,'B',30,t).length,c30:S.countyRows(A,'C',30,t).length,c180:S.countyRows(A,'C',180,t).length,metrics:S.metrics(S.availableOpportunities(A,30,t),S.countyRows(A,'A',30,t))}; console.log(JSON.stringify(out));"
    completed = subprocess.run(["node", "-e", script, str(state_path), json.dumps(artifact)], check=True, capture_output=True, text=True)
    result = json.loads(completed.stdout)
    assert result["available"] == sorted(result["available"])
    assert result["available"] == [1, 2, 3, 4, 5, 6]
    assert (result["a30"], result["b30"], result["c30"], result["c180"]) == (3, 1, 0, 1)
    assert result["metrics"]["strongCount"] == 1
    assert result["metrics"]["nearestDeadline"] == "2026-09-01"
