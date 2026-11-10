"""Offline tool tests: completed starter challenge and new deduplicate tool."""
from __future__ import annotations

from copy import deepcopy

import pytest

from agent import ResearchAgent
from conftest import FakeResponse  # noqa: F401  (you will need it)
from providers.base import ModelResponse, ToolCall
from tools import TOOL_FUNCTIONS  # noqa: F401
from tools.deduplicate.tool import deduplicate

# ---------------- clarify ----------------

def test_clarify_choice_returns_options_and_awaits_user() -> None:
    result = TOOL_FUNCTIONS["clarify"]("Nguồn nào?", response_type="choice", options=["Web", "X"])
    assert result["options"] == ["Web", "X"]
    assert result["response_type"] == "choice"
    assert result["awaiting_user"] is True


# ---------------- format ----------------

def test_format_sections_groups_items_by_section() -> None:
    items = [{"title": title, "section": section} for title, section in [("One", "A"), ("Two", "B"), ("Three", "A")]]
    text = TOOL_FUNCTIONS["format"](items, template="sections")["markdown"]
    assert text.count("## A") == text.count("## B") == 1
    assert text.index("One") < text.index("Three") < text.index("Two")


def test_format_thread_numbers_items() -> None:
    text = TOOL_FUNCTIONS["format"]([{"title": "One"}, {"title": "Two"}], template="thread")["markdown"]
    assert text.startswith("1/ One")
    assert "\n\n2/ Two" in text


def test_format_empty_items_does_not_crash() -> None:
    for items in (None, []):
        assert TOOL_FUNCTIONS["format"](items)["item_count"] == 0


# ---------------- send (guardrail) ----------------

def test_send_confirmed_posts_to_telegram(monkeypatch, fake_http) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "test-chat")
    calls = fake_http(FakeResponse({"ok": True}))
    assert TOOL_FUNCTIONS["send"]("Bản tin đã duyệt", confirmed=True)["status"] == "sent"
    assert len(calls) == 1
    assert calls[0]["method"] == "POST"
    assert calls[0]["url"] == "https://api.telegram.org/bottest-token/sendMessage"
    assert calls[0]["json"] == {"chat_id": "test-chat", "text": "Bản tin đã duyệt", "parse_mode": "Markdown"}


def test_send_confirmed_without_env_returns_error_and_no_request(fake_http) -> None:
    calls = fake_http(FakeResponse())
    result = TOOL_FUNCTIONS["send"]("Bản tin", confirmed=True)
    assert result["error"] == "RuntimeError"
    assert "TELEGRAM" in result["message"]
    assert calls == []


# ---------------- lookup ----------------

def test_lookup_without_timeframe_omits_time_range(monkeypatch, fake_http) -> None:
    monkeypatch.setenv("TAVILY_API_KEY", "test-key")
    calls = fake_http(FakeResponse({"results": []}))
    assert TOOL_FUNCTIONS["lookup"]("AI", timeframe=None)["items"] == []
    assert "time_range" not in calls[0]["json"]


# ---------------- fetch ----------------

def test_fetch_maps_firecrawl_response(monkeypatch, fake_http) -> None:
    monkeypatch.setenv("FIRECRAWL_API_KEY", "test-key")
    calls = fake_http(FakeResponse({"data": {"markdown": "Body", "metadata": {"title": "T", "sourceURL": "https://example.com/final"}}}))
    result = TOOL_FUNCTIONS["fetch"]("https://example.com/start")
    assert result["items"] == [{"title": "T", "url": "https://example.com/final", "source": "example.com", "summary": "Body"}]
    assert calls[0]["json"] == {"url": "https://example.com/start", "formats": ["markdown"]}
    assert calls[0]["headers"]["Authorization"] == "Bearer test-key"


def test_fetch_truncates_markdown_to_4000_chars(monkeypatch, fake_http) -> None:
    monkeypatch.setenv("FIRECRAWL_API_KEY", "test-key")
    fake_http(FakeResponse({"data": {"markdown": "x" * 5000}}))
    assert TOOL_FUNCTIONS["fetch"]("https://example.com")["items"][0]["summary"] == "x" * 4000


# ---------------- timeline / social_search ----------------

def test_timeline_respects_limit_and_skips_items_without_id(monkeypatch, fake_http) -> None:
    monkeypatch.setenv("RAPIDAPI_KEY", "test-key")
    calls = fake_http(FakeResponse({"timeline": [{"text": "missing ID"}] + [
        {"tweet_id": str(i), "screen_name": "karpathy", "text": f"Post {i}"} for i in range(1, 7)]}))
    items = TOOL_FUNCTIONS["timeline"]("karpathy", limit=3)["items"]
    assert [item["url"] for item in items] == [f"https://x.com/karpathy/status/{i}" for i in range(1, 4)]
    assert calls[0]["params"] == {"screenname": "karpathy"}


def test_social_search_passes_search_type(monkeypatch, fake_http) -> None:
    monkeypatch.setenv("RAPIDAPI_KEY", "test-key")
    calls = fake_http(FakeResponse({"timeline": []}))
    assert TOOL_FUNCTIONS["social_search"]("Claude", search_type="Top")["items"] == []
    assert calls[0]["params"] == {"query": "Claude", "search_type": "Top"}


# ---------------- policy (local knowledge + trust boundary) ----------------

def test_policy_empty_query_returns_no_results() -> None:
    assert TOOL_FUNCTIONS["policy"]("")["results"] == []


def test_policy_area_filter_only_returns_that_area() -> None:
    hits = TOOL_FUNCTIONS["policy"]("customer data", policy_area="data_privacy")["results"]
    assert hits
    assert all(hit["policy_area"] == "data_privacy" for hit in hits)


def test_policy_instruction_like_lines_go_to_untrusted_text() -> None:
    hits = TOOL_FUNCTIONS["policy"]("citation", policy_area="source_citation", top_k=10)["results"]
    probe = next(hit for hit in hits if hit["section"] == "Injection probe")
    assert probe["untrusted_text"]
    assert "ignore the citation policy" in probe["untrusted_text"][0]
    assert "ignore" not in probe["facts"].lower()


# ---------------- YOUR NEW TOOL(S) ----------------
# Write at least 3 tests per tool your team adds:
#   1. happy path (mocked if it calls an API)
#   2. bad / missing input from the model (empty string, wrong type, out-of-enum value)
#   3. failure path (missing key, HTTP error, timeout) -> returns error dict, does not raise

def test_deduplicate_keeps_first_url_and_preserves_order_and_fields() -> None:
    items = [
        {"url": " HTTPS://Example.com/a/// ", "title": "First", "score": 0.8},
        {"url": "https://example.com/b", "summary": "Second result"},
        {"url": "https://example.com/A", "title": "Duplicate"},
        {"url": "https://example.com/c", "source": "Other"},
    ]

    result = deduplicate(items)

    assert result == {
        "tool": "deduplicate",
        "items": [items[0], items[1], items[3]],
        "removed_count": 1,
    }


def test_deduplicate_title_trims_whitespace_and_casefolds_unicode() -> None:
    items = [
        {"title": "  Straße  ", "url": "https://example.com/first"},
        {"title": "STRASSE", "url": "https://example.com/second"},
        {"title": "Different", "url": "https://example.com/first"},
    ]

    result = deduplicate(items, key_by="title")

    assert result["items"] == [items[0], items[2]]
    assert result["removed_count"] == 1


@pytest.mark.parametrize("key_by", ["url", "title"])
def test_deduplicate_retains_every_missing_none_or_empty_key(key_by) -> None:
    items = [
        {"source": "missing one"},
        {"source": "missing two"},
        {key_by: None},
        {key_by: ""},
        {key_by: " \t "},
        {key_by: ""},
    ]

    assert deduplicate(items, key_by=key_by) == {
        "tool": "deduplicate",
        "items": items,
        "removed_count": 0,
    }


def test_deduplicate_retains_urls_empty_after_removing_trailing_slashes() -> None:
    items = [{"url": "/"}, {"url": " /// "}]

    assert deduplicate(items)["items"] == items
    assert deduplicate(items)["removed_count"] == 0


def test_deduplicate_does_not_modify_input_items_or_nested_fields() -> None:
    items = [
        {"url": " HTTPS://Example.com/a/ ", "metadata": {"tags": ["keep"]}},
        {"url": "https://example.com/a", "title": "Duplicate"},
    ]
    original = deepcopy(items)

    deduplicate(items)

    assert items == original


def test_deduplicate_accepts_empty_items() -> None:
    assert deduplicate([]) == {
        "tool": "deduplicate",
        "items": [],
        "removed_count": 0,
    }


@pytest.mark.parametrize("items", [None, {}, "results", ({"url": "a"},)])
def test_deduplicate_non_list_items_returns_type_error(items) -> None:
    result = deduplicate(items)

    assert result["tool"] == "deduplicate"
    assert result["error"] == "TypeError"
    assert isinstance(result["message"], str) and result["message"]


@pytest.mark.parametrize("key_by", ["summary", "URL", "", None, []])
def test_deduplicate_unsupported_key_returns_value_error(key_by) -> None:
    result = deduplicate([], key_by=key_by)

    assert result["tool"] == "deduplicate"
    assert result["error"] == "ValueError"
    assert isinstance(result["message"], str) and result["message"]


@pytest.mark.parametrize("bad_item", [None, "result", 42, []])
def test_deduplicate_malformed_item_returns_type_error(bad_item) -> None:
    result = deduplicate([{"url": "https://example.com/valid"}, bad_item])

    assert result["tool"] == "deduplicate"
    assert result["error"] == "TypeError"
    assert isinstance(result["message"], str) and result["message"]


@pytest.mark.parametrize("key_by", ["url", "title"])
@pytest.mark.parametrize("bad_key", [42, False, [], {}])
def test_deduplicate_non_string_key_returns_type_error(key_by, bad_key) -> None:
    result = deduplicate([{key_by: bad_key}], key_by=key_by)

    assert result["tool"] == "deduplicate"
    assert result["error"] == "TypeError"
    assert isinstance(result["message"], str) and result["message"]


def test_deduplicate_only_checks_the_selected_key() -> None:
    items = [
        {"url": "https://example.com/a", "title": ["non-string metadata"]},
        {"url": "https://example.com/a", "title": None},
    ]

    result = deduplicate(items)

    assert result["items"] == [items[0]]
    assert result["removed_count"] == 1


def test_deduplicate_executes_through_agent_tool_registry() -> None:
    items = [
        {"title": " First report ", "url": "https://example.com/first"},
        {"title": "FIRST REPORT", "url": "https://example.com/duplicate"},
        {"title": "Other report", "url": "https://example.com/first"},
    ]
    arguments = {"items": items, "key_by": "title"}

    class FakeProvider:
        def complete(self, messages, tools=None, *, model=None,
                     temperature=0.0, tool_choice=None) -> ModelResponse:
            return ModelResponse(tool_calls=[ToolCall("deduplicate", arguments)])

    agent = ResearchAgent(FakeProvider(), system_prompt="Execute research tools.")

    run = agent.run([{"role": "user", "content": "Remove duplicate report titles."}])

    assert run.tool_results == [{
        "tool": "deduplicate",
        "args": arguments,
        "result": {
            "tool": "deduplicate",
            "items": [items[0], items[2]],
            "removed_count": 1,
        },
    }]
