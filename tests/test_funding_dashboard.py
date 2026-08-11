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


def test_canonical_shell_removes_obsolete_title_without_changing_navigation() -> None:
    shell = (ROOT / "dashboard" / "app" / "components" / "shell.js").read_text(encoding="utf-8")
    main = (ROOT / "dashboard" / "app" / "main.js").read_text(encoding="utf-8")
    api = (ROOT / "dashboard" / "app" / "api.js").read_text(encoding="utf-8")
    funding_view = (ROOT / "dashboard" / "app" / "views" / "funding-matches.js").read_text(encoding="utf-8")

    assert "Triad Signal" not in shell
    assert "Clinic Needs Atlas" not in shell
    assert "wordmark" not in shell and "wm-text" not in shell
    for label in ("Overview", "County", "Worklist", "Needs Forest", "Trends", "Explore", "Methods", "Funding Matches"):
        assert f'label: "{label}"' in shell
    assert 'navigate("/overview", { replace: true })' in main
    assert '"funding"' in main and "FundingMatchesView" in main
    assert "Funding Matches is an optional static artifact" in api
    assert "Funding Matches is not available yet" in funding_view


def test_existing_views_do_not_receive_funding_content() -> None:
    existing = ["overview.js", "forest.js", "county.js", "worklist.js", "trends.js", "explore.js", "methods.js"]
    prohibited = ("Funding Matches", "Grants.gov", "grant recommender", "opportunity match", "eligibility status")
    for name in existing:
        content = (ROOT / "dashboard" / "app" / "views" / name).read_text(encoding="utf-8")
        assert not any(term in content for term in prohibited), name
