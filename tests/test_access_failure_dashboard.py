"""Static regression checks for an isolated access-failure dashboard tab."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "dashboard" / "clinic-needs-atlas-live.html"
TAB_SCRIPT = ROOT / "dashboard" / "access-failure-tab.js"
TAB_STYLES = ROOT / "dashboard" / "access-failure-tab.css"


def _normalized(value: str) -> str:
    return value.replace("\r\n", "\n")


def _baseline_dashboard() -> str:
    result = subprocess.run(
        ["git", "show", "HEAD:dashboard/clinic-needs-atlas-live.html"],
        check=True,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return _normalized(result.stdout)


def _style_block(html: str) -> str:
    match = re.search(r"(?s)<style>(.*?)</style>", html)
    assert match
    return match.group(1)


def _function_body(html: str, name: str) -> str:
    match = re.search(rf"(?s)function {name}\([^)]*\)\{{.*?\n\}}", html)
    assert match, f"{name} was not found"
    return match.group(0)


def _atlas_panel(html: str) -> str:
    match = re.search(r'(?s)<main id="atlas-panel"[^>]*>(.*?)</main>\s*<main id="access-panel"', html)
    assert match
    return match.group(1)


def test_existing_dashboard_style_and_selection_behavior_match_head():
    current = _normalized(DASHBOARD.read_text(encoding="utf-8"))
    baseline = _baseline_dashboard()

    assert _style_block(current) == _style_block(baseline)
    assert _function_body(current, "selectClinic") == _function_body(baseline, "selectClinic")
    assert _function_body(current, "renderAll") == _function_body(baseline, "renderAll")
    assert "const PROV_LABELS={real:\"live source\",synthetic:\"synthetic (by design)\",stub:\"sample data — pending ingestion\"};" in current
    assert "const PROV_COLOR={real:\"#009E73\",synthetic:\"#56B4E9\",stub:\"#E69F00\"};" in current


def test_existing_panel_does_not_include_access_failure_content_or_data_contract():
    current = DASHBOARD.read_text(encoding="utf-8")
    atlas = _atlas_panel(current)
    for term in ("Access Failure", "accessFailureRisk", "accessFailureModel", "Preventable Hospital"):
        assert term not in atlas

    original_inline = re.findall(r"(?s)<script>(.*?)</script>", current)[-1]
    assert "accessFailureRisk" not in original_inline
    assert "accessFailureModel" not in original_inline
    assert "AccessFailureTab.init(tabPayload)" in original_inline


def test_access_failure_tab_is_isolated_in_dedicated_assets():
    html = DASHBOARD.read_text(encoding="utf-8")
    script = TAB_SCRIPT.read_text(encoding="utf-8")
    styles = TAB_STYLES.read_text(encoding="utf-8")

    assert 'href="access-failure-tab.css"' in html
    assert 'src="access-failure-tab.js"' in html
    assert 'id="access-tab"' in html
    assert 'id="access-panel"' in html
    assert 'data-access-failure-view="atlas"' in html
    assert 'aria-selected="true"' in html
    assert "Rural Care Access Failure Risk" in html
    assert 'target="_blank"' not in html  # Source links are generated only inside the new module.
    assert 'rel="noopener noreferrer"' in script
    for shared_name in ("CLINICS", "byId", "selectClinic", "renderAll"):
        assert shared_name not in script
    assert "header{" not in styles
    assert ".toolbar" not in styles
    assert ".access-failure-tab" in styles


def test_access_failure_field_is_not_added_to_existing_provenance_contract():
    from src.build_dataset import FIELD_SOURCE

    assert "accessFailureRisk" not in FIELD_SOURCE
