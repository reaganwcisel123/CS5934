from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_funding_matches_is_an_isolated_additive_view() -> None:
    app = (ROOT / "dashboard" / "app.html").read_text(encoding="utf-8")
    main = (ROOT / "dashboard" / "app" / "main.js").read_text(encoding="utf-8")
    shell = (ROOT / "dashboard" / "app" / "components" / "shell.js").read_text(encoding="utf-8")
    view = (ROOT / "dashboard" / "app" / "views" / "funding-matches.js").read_text(encoding="utf-8")
    css = (ROOT / "dashboard" / "app" / "funding-matches.css").read_text(encoding="utf-8")
    assert 'src="app/views/funding-matches.js"' in app
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
    assert "data-county-fips={selectedFips}" in view
    assert "initialFips !== selectedFips" in view
    assert "setSelectedId(null)" in view
    assert "countyRows={rawRows}" in view
    assert "Gemini relevance" in view
    assert "TF-IDF" not in view and "cosine distance" not in view
