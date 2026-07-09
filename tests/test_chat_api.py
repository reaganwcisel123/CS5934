"""Chatbot endpoint: gated on ANTHROPIC_API_KEY; answers grounded county data.

The Anthropic client is mocked, so these tests make no network call and cost
nothing. They exercise the /api/chat contract, not the model.
"""

from __future__ import annotations

import anthropic
import pytest
from fastapi.testclient import TestClient

from src.api.main import app


class _Block:
    type = "text"

    def __init__(self, text: str) -> None:
        self.text = text


class _Resp:
    def __init__(self, text: str) -> None:
        self.content = [_Block(text)]


class _FakeAnthropic:
    """Stands in for anthropic.Anthropic(); returns a fixed answer."""

    ANSWER = "Essex County shows elevated care-access need (HRSA HPSA)."

    def __init__(self, *a, **k) -> None:
        self.messages = self

    def create(self, **kwargs):
        return _Resp(self.ANSWER)


@pytest.fixture
def client(monkeypatch):
    # No DB: the chat context reads the static clinic_atlas.json fallback.
    monkeypatch.delenv("DATABASE_URL", raising=False)
    return TestClient(app)


def test_chat_requires_key(client, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    r = client.post("/api/chat", json={"question": "why is need high?", "county_fips": "51001"})
    assert r.status_code == 503
    assert "ANTHROPIC_API_KEY" in r.json()["detail"]


def test_chat_answers_with_key(client, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(anthropic, "Anthropic", _FakeAnthropic)
    r = client.post("/api/chat", json={"question": "why is need high?", "county_fips": "51001"})
    assert r.status_code == 200
    body = r.json()
    assert body["answer"] == _FakeAnthropic.ANSWER
    assert body["county_fips"] == "51001"
