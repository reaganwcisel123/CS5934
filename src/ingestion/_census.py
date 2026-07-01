"""Shared Census Data API helper."""

from __future__ import annotations

import requests


def census_json(endpoint: str, params: dict) -> list[list]:
    # The Census API returns an HTML "Missing Key" page (HTTP 200) when no key
    # is supplied; turn that into a clear error, not a JSONDecodeError.
    resp = requests.get(endpoint, params=params, timeout=60)
    resp.raise_for_status()
    text = resp.text.lstrip()
    if text.startswith("<"):
        if "key" in text.lower():
            raise RuntimeError(
                "Census API requires a valid key. Set CENSUS_API_KEY "
                "(free: https://api.census.gov/data/key_signup.html)."
            )
        raise RuntimeError(f"Census API returned unexpected HTML from {endpoint}")
    return resp.json()
