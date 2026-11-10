"""Shared fixtures for tool unit tests.

Rules for this test suite:
- Tests must run OFFLINE and FREE: no real API key, no real HTTP call.
- Any real network call fails the test (see `block_network`), so mock it with `fake_http`.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

API_ENV_VARS = [
    "TAVILY_API_KEY", "FIRECRAWL_API_KEY", "RAPIDAPI_KEY", "RAPIDAPI_TWITTER_HOST",
    "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID",
]


class FakeResponse:
    """Minimal stand-in for requests.Response."""

    def __init__(self, payload: Any = None, status_code: int = 200, text: str = "", content: bytes = b"") -> None:
        self._payload = payload if payload is not None else {}
        self.status_code = status_code
        self.text = text
        self.content = content

    def json(self) -> Any:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Start every test with no API keys, so tests never depend on the developer's .env."""
    for name in API_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    # Existing provider controls exercise one protocol at a time. Tests for the
    # optional direct-answer check opt in explicitly and mock its model request.
    monkeypatch.setenv("OLLAMA_DIRECT_ANSWER_CHECK", "0")


class RealNetworkCall(BaseException):
    """BaseException on purpose: tools catch `Exception`, so this one cannot be swallowed."""


@pytest.fixture(autouse=True)
def block_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def _blocked(*args: Any, **kwargs: Any) -> None:
        raise RealNetworkCall(f"Real network call in a unit test: {args[:2]} - mock it with the fake_http fixture")

    monkeypatch.setattr(requests.Session, "request", _blocked)


@pytest.fixture
def fake_http(monkeypatch: pytest.MonkeyPatch):
    """Patch requests.get/post with a recorder that returns a FakeResponse.

    Usage:
        calls = fake_http(FakeResponse({"results": [...]}))
        result = web_search("x")
        assert calls[0]["url"] == "https://api.tavily.com/search"
    """

    def _install(response: FakeResponse | Exception) -> list[dict[str, Any]]:
        calls: list[dict[str, Any]] = []

        def _fake(method: str):
            def _call(url: str, **kwargs: Any) -> FakeResponse:
                calls.append({"method": method, "url": url, **kwargs})
                if isinstance(response, Exception):
                    raise response
                return response
            return _call

        monkeypatch.setattr(requests, "get", _fake("GET"))
        monkeypatch.setattr(requests, "post", _fake("POST"))
        return calls

    return _install
