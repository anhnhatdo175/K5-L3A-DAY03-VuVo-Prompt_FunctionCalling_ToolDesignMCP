from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from chat import run_model_tool_loop
from conftest import FakeResponse
from providers.base import ModelResponse, ToolCall
from run_eval import compare_subset, evaluate_phase_b, summarize
from tool_runtime import argument_errors, execute_tool_call
from tools import TOOL_FUNCTIONS, load_tool_declarations, to_openai_tools
from ui_support import DemoProvider, conversation_history

ROOT = Path(__file__).resolve().parents[1]
TOOLS = to_openai_tools(load_tool_declarations(ROOT / "artifacts/tools.yaml"))


@pytest.mark.parametrize("confirmed", ["false", "true", 1, [], None])
def test_send_requires_real_boolean_without_http(confirmed, fake_http):
    calls = fake_http(FakeResponse({"ok": True}))
    assert TOOL_FUNCTIONS["send"]("Text", confirmed=confirmed)["error"] == "TypeError"
    assert not calls


def test_send_detects_telegram_rejection(monkeypatch, fake_http):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "test-chat")
    fake_http(FakeResponse({"ok": False, "description": "rejected"}))
    assert TOOL_FUNCTIONS["send"]("Text", confirmed=True)["error"] == "RuntimeError"


def test_send_http_error_does_not_leak_bot_token(monkeypatch, fake_http):
    import requests
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-secret-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "test-chat")
    fake_http(requests.HTTPError("403 for https://api.telegram.org/bottest-secret-token/sendMessage"))
    result = TOOL_FUNCTIONS["send"]("Text", confirmed=True)
    assert "test-secret-token" not in result["message"]
    assert "[REDACTED]" in result["message"]


def test_eval_compares_nested_items_in_original_order():
    items = [{"url": "A", "data": {"tags": ["one", "two"]}}, {"url": "B"}]
    assert compare_subset({"items": items}, {"items": items})[0]
    assert not compare_subset({"items": items}, {"items": list(reversed(items))})[0]
    assert not compare_subset({"items": items}, {"items": [{"url": "a"}, {"url": "B"}]})[0]


def test_eval_preserves_approved_text_and_json_types():
    assert not compare_subset({"text": "APPROVED: OpenAI"}, {"text": "approved: openai"})[0]
    assert not compare_subset({"text": "Approved "}, {"text": "Approved"})[0]
    assert not compare_subset({"items": [{"flag": True}]}, {"items": [{"flag": 1}]})[0]


@pytest.mark.parametrize("key_by,items", [("url", [{"url": 1}]), ("title", [{"title": False}])])
def test_dedupe_validation_rejects_invalid_selected_key(key_by, items):
    assert argument_errors("deduplicate", {"items": items, "key_by": key_by})


def test_dedupe_validation_preserves_arbitrary_nonselected_metadata():
    items = [{"url": None, "title": {"data": 1}, "extra": [True, 1]}]
    event = execute_tool_call(ToolCall("deduplicate", {"items": items}))
    assert event["result"]["items"] == items


@pytest.mark.parametrize("text", ["", "  \n"])
def test_dry_run_rejects_empty_send_text(text, fake_http):
    calls = fake_http(FakeResponse())
    event = execute_tool_call(ToolCall("send", {"text": text, "confirmed": True}), dry_run_actions=True)
    assert event["result"]["error"] == "InvalidToolArguments"
    assert not calls


@pytest.mark.parametrize("name,args", [("deduplicate", {}), ("send", {"text": "x", "confirmed": 1}),
                                       ("social_search", {"screenname": "Claude", "search_type": "Top"})])
def test_eval_rejects_invalid_schema_even_with_subset_expectation(name, args):
    case = {"failure_type": "wrong_arg_value", "expect": {"tool_calls": [{"name": name, "args": {}}]}}
    assert not evaluate_phase_b(case, [{"name": name, "args": args}], None)["passed"]


def test_harness_error_is_measured_as_failure():
    results = [{"phase": "B", "result": {"passed": False, "failure_type": "harness_error"}}]
    assert summarize(results)["measured_cases"] == 1
    assert summarize(results)["case_accuracy"] == 0


def test_eval_action_dry_run_never_sends(fake_http):
    calls = fake_http(FakeResponse({"ok": True}))
    event = execute_tool_call(ToolCall("send", {"text": "Approved text", "confirmed": True}), dry_run_actions=True)
    assert event["result"]["status"] == "dry_run"
    assert calls == []


def test_offline_execution_blocks_external_tools(fake_http):
    calls = fake_http(FakeResponse())
    event = execute_tool_call(ToolCall("papers", {"query": "AI"}), offline=True)
    assert event["result"]["error"] == "OfflineToolUnavailable"
    assert not calls


def test_policy_vietnamese_query_finds_english_sources():
    hits = TOOL_FUNCTIONS["policy"]("trích dẫn nguồn", policy_area="source_citation")["results"]
    assert hits and all(hit["policy_area"] == "source_citation" for hit in hits)


def test_policy_rejects_zero_top_k():
    assert TOOL_FUNCTIONS["policy"]("citation", top_k=0)["error"] == "ValueError"


def test_demo_deduplicates_given_urls_and_retains_fields():
    items = [{"url": "https://example.com/a/", "extra": 1}, {"url": "https://example.com/a"}, {"url": "https://example.com/b"}]
    result = run_model_tool_loop(provider=DemoProvider(), messages=[{"role": "user", "content": "Bỏ trùng URL: " + json.dumps(items)}],
                                 tools=TOOLS, model=None, max_tool_rounds=3)
    assert result["tool_events"][0]["tool"] == "deduplicate"
    assert result["tool_events"][0]["result"]["items"] == [items[0], items[2]]
    assert "Đã loại 1" in result["assistant_text"]


def test_demo_asks_for_missing_items_and_does_not_search_for_capability():
    demo = DemoProvider()
    assert demo.complete([{"role": "user", "content": "Bạn là ai?"}]).tool_calls == []
    assert demo.complete([{"role": "user", "content": "Bỏ trùng giúp mình"}]).tool_calls[0].name == "clarify"
    assert demo.complete([{"role": "user", "content": "Tìm paper arxiv"}]).tool_calls == []


def test_demo_reads_key_instruction_after_json_and_ignores_metadata_words():
    response = DemoProvider().complete([{"role": "user", "content":
        'Deduplicate: [{"title":"A","url":"x"},{"title":"a","url":"y"}]. By title please'}])
    assert response.tool_calls[0].args["key_by"] == "title"
    assert not DemoProvider().complete([{"role": "user", "content": "Tìm trung tâm nghiên cứu AI"}]).tool_calls


def test_demo_handles_complete_large_tool_results():
    items = [{"url": "x", "summary": "a" * 25000}]
    result = run_model_tool_loop(provider=DemoProvider(), messages=[{"role": "user", "content":
        "Deduplicate: " + json.dumps(items)}], tools=TOOLS, model=None, max_tool_rounds=3)
    assert result["status"] == "answered"
    assert result["tool_events"][0]["result"]["items"] == items
    assert "Đã loại 0" in result["assistant_text"]


@pytest.mark.parametrize("status", ["answered", "provider_error"])
def test_ui_history_drops_empty_failed_turn_but_keeps_executed_tool_results(status):
    history = conversation_history([
        {"role": "user", "content": "failed request"},
        {"role": "assistant", "content": "failure", "status": "provider_error"},
        {"role": "user", "content": "working request"},
        {"role": "assistant", "content": "done", "status": status,
         "tool_events": [{"result": {"items": []}}]},
    ])
    assert [message["role"] for message in history] == ["user", "assistant"]
    assert history[0]["content"] == "working request"
    assert "Prior tool results" in history[1]["content"]


def test_chat_tool_logging_works_on_cp1252(monkeypatch):
    class Provider:
        def complete(self, *args, **kwargs):
            return ModelResponse(tool_calls=[ToolCall("clarify", {"question": "Bạn cần gì?"})])
    with io.TextIOWrapper(io.BytesIO(), encoding="cp1252") as stream:
        monkeypatch.setattr("sys.stdout", stream)
        result = run_model_tool_loop(provider=Provider(), messages=[], tools=TOOLS, model=None, max_tool_rounds=2)
    assert result["status"] == "waiting_for_user"


def test_provider_error_keeps_already_executed_rounds():
    class Provider:
        count = 0
        def complete(self, *args, **kwargs):
            self.count += 1
            if self.count == 1:
                return ModelResponse(tool_calls=[ToolCall("deduplicate", {"items": []})])
            raise RuntimeError("offline failure")
    result = run_model_tool_loop(provider=Provider(), messages=[], tools=TOOLS, model=None, max_tool_rounds=3)
    assert result["status"] == "provider_error"
    assert len(result["rounds"]) == len(result["tool_events"]) == 1
