from copy import deepcopy
import json
from pathlib import Path

import pytest
from jsonschema import Draft7Validator

from agent import ResearchAgent
from providers.base import ModelResponse, ToolCall
from providers.ollama_provider import OllamaProvider
from tools import TOOL_FUNCTIONS, load_tool_declarations, to_openai_tools


TOOLS = to_openai_tools(load_tool_declarations(Path(__file__).resolve().parents[1] / "artifacts/tools.yaml"))


def provider_with_responses(monkeypatch, responses, *, retry_format="native"):
    monkeypatch.setenv("OLLAMA_CALL_MODE", "native")
    monkeypatch.setenv("OLLAMA_PROTOCOL_RETRIES", "1")
    monkeypatch.setenv("OLLAMA_PROTOCOL_RETRY_FORMAT", retry_format)
    calls = []
    def complete(self, messages, tools=None, **kwargs):
        calls.append({"messages": deepcopy(messages), "tools": tools, **kwargs})
        value = responses[len(calls) - 1]
        if isinstance(value, Exception):
            raise value
        return value
    monkeypatch.setattr("providers.openai_provider.OpenAIProvider.complete", complete)
    return OllamaProvider(), calls


def test_required_retry_keeps_request_and_uses_only_second_model_calls(monkeypatch):
    first = ModelResponse(text="Which account?")
    second = ModelResponse(tool_calls=[ToolCall("clarify", {"question": "Which account?", "response_type": "text"})])
    provider, calls = provider_with_responses(monkeypatch, [first, second])
    original = [{"role": "user", "content": "Show recent posts"}]
    tools = [{"name": "clarify"}, {"name": "timeline"}]
    result = provider.complete(original, tools, tool_choice="required")
    assert len(calls) == 2 and calls[1]["tools"] is tools
    assert calls[1]["messages"][0] == original[0]
    assert len(original) == 1
    assert result.tool_calls is second.tool_calls
    assert result.metadata["native_attempts"][0]["tool_calls"] == []
    assert result.metadata["protocol_retry_used"] == 1


def test_direct_auto_answer_and_valid_calls_are_not_retried(monkeypatch):
    for response in [ModelResponse(text="Hello"), ModelResponse(tool_calls=[ToolCall("fetch", {"url": "https://example.org"})])]:
        provider, calls = provider_with_responses(monkeypatch, [response])
        result = provider.complete([], [])
        assert len(calls) == 1
        assert result is response


def test_empty_auto_retry_still_allows_a_direct_answer(monkeypatch):
    provider, calls = provider_with_responses(monkeypatch, [ModelResponse(), ModelResponse(text="Research assistant")])
    result = provider.complete([{"role": "user", "content": "Who are you?"}], [])
    assert len(calls) == 2
    assert "OR a concise direct answer" in calls[1]["messages"][-1]["content"]
    assert result.tool_calls == []


def test_retry_transport_error_preserves_measured_model_failure(monkeypatch):
    provider, calls = provider_with_responses(monkeypatch, [ModelResponse(text="Which URL?"), RuntimeError("test retry failure")])
    result = provider.complete([], [], tool_choice="required")
    assert result.text == "Which URL?" and result.tool_calls == []
    assert len(calls) == 2
    assert result.metadata["protocol_retry_used"] == 1
    assert "test retry failure" in result.metadata["retry_error"]


def test_zero_retry_control_is_available(monkeypatch):
    provider, calls = provider_with_responses(monkeypatch, [ModelResponse(text="Which URL?")])
    provider.protocol_retries = 0
    result = provider.complete([], [], tool_choice="required")
    assert len(calls) == 1 and result.tool_calls == []


def encoded_plan(calls, *, text="", request="Resolved original request"):
    return json.dumps({"request": request, "text": text, "tool_calls": calls}, ensure_ascii=False)


def test_structured_required_retry_keeps_all_declarations_and_original_request(monkeypatch):
    raw_plan = encoded_plan([{"name": "clarify", "args": {
        "question": "Which source should I read?", "response_type": "text"}}])
    provider, calls = provider_with_responses(
        monkeypatch, [ModelResponse(text="Which source?"), ModelResponse(text=raw_plan)],
        retry_format="structured_plan")
    original = [{"role": "system", "content": "Follow the user and tool contracts."},
                {"role": "user", "content": "Please read the source I meant."}]
    original_copy, tools_copy = deepcopy(original), deepcopy(TOOLS)

    result = provider.complete(original, TOOLS, tool_choice="required")

    assert len(calls) == 2
    assert calls[0]["tools"] is TOOLS
    assert "response_format" not in calls[0]
    assert calls[1]["tools"] is None
    schema = calls[1]["response_format"]["json_schema"]["schema"]
    alternatives = schema["properties"]["tool_calls"]["items"]["oneOf"]
    names = {branch["properties"]["name"]["const"] for branch in alternatives}
    assert len(names) == 11
    assert names == {tool["function"]["name"] for tool in TOOLS}
    assert schema["properties"]["tool_calls"]["minItems"] == 1
    assert original[1] in calls[1]["messages"]
    assert not any(message["role"] == "assistant" and message["content"] == "Which source?"
                   for message in calls[1]["messages"])
    assert original == original_copy and TOOLS == tools_copy
    assert result.tool_calls == [ToolCall("clarify", {
        "question": "Which source should I read?", "response_type": "text"})]
    assert result.metadata["raw_plan"] == raw_plan
    assert len(result.metadata["native_attempts"]) == 2
    assert result.metadata["native_attempts"][0]["unmet_protocol"] == "required_without_calls"
    assert [attempt["format"] for attempt in result.metadata["native_attempts"]] == ["native", "structured_plan"]
    assert result.metadata["native_attempts"][1]["planning_response"]["raw_plan"] == raw_plan
    assert result.metadata["protocol_retry_used"] == 1


@pytest.mark.parametrize("tool_name,args", [
    ("policy", {"query": "Source Citations", "policy_area": "source_citation", "top_k": 2}),
    ("deduplicate", {"items": [
        {"url": None, "title": {"original": True}, "metadata": [True, 1, "VALUE"]},
        {"url": " HTTPS://Example.org/A/ ", "title": "Title"},
    ]}),
    ("send", {"text": "APPROVED: Exact text.\nKeep the trailing space ", "confirmed": True}),
])
def test_structured_retry_normalizes_only_the_model_plan_without_repairing_arguments(monkeypatch, tool_name, args):
    raw_plan = encoded_plan([{"name": tool_name, "args": args}])
    provider, calls = provider_with_responses(
        monkeypatch, [ModelResponse(), ModelResponse(text=raw_plan)], retry_format="structured_plan")

    result = provider.complete([{"role": "user", "content": "A generic original request"}], TOOLS)

    assert result.tool_calls == [ToolCall(tool_name, args)]
    assert json.dumps(result.tool_calls[0].args, ensure_ascii=False) == json.dumps(args, ensure_ascii=False)
    if tool_name == "deduplicate":
        assert "key_by" not in result.tool_calls[0].args
    branches = calls[1]["response_format"]["json_schema"]["schema"]["properties"]["tool_calls"]["items"]["oneOf"]
    branch = next(item for item in branches if item["properties"]["name"]["const"] == tool_name)
    declaration = next(tool["function"]["parameters"] for tool in TOOLS if tool["function"]["name"] == tool_name)
    expected_args_schema = {**deepcopy(declaration), "additionalProperties": False}
    assert branch["properties"]["args"] == expected_args_schema


def test_structured_empty_auto_retry_allows_model_to_choose_a_direct_answer(monkeypatch):
    raw_plan = encoded_plan([], text="I can help with research.")
    provider, calls = provider_with_responses(
        monkeypatch, [ModelResponse(), ModelResponse(text=raw_plan)], retry_format="structured_plan")

    result = provider.complete([{"role": "user", "content": "What can you do?"}], TOOLS, tool_choice="auto")

    schema = calls[1]["response_format"]["json_schema"]["schema"]
    Draft7Validator(schema).validate(json.loads(raw_plan))
    assert result.text == "I can help with research." and result.tool_calls == []
    assert result.metadata["native_attempts"][0]["unmet_protocol"] == "empty_auto_response"
    assert result.metadata["raw_plan"] == raw_plan


@pytest.mark.parametrize("raw_plan", [
    '{"request":"Read source","tool_calls":[',
    encoded_plan([{"name": "deduplicate", "args": {"items": []}},
                  {"name": "send", "args": {"text": "Draft", "confirmed": "true"}}]),
])
def test_malformed_structured_retry_is_an_observable_failure_and_executes_nothing(monkeypatch, raw_plan):
    provider, calls = provider_with_responses(
        monkeypatch, [ModelResponse(text="Which source?"), ModelResponse(text=raw_plan)],
        retry_format="structured_plan")
    executed = []
    for name in ("send", "deduplicate"):
        monkeypatch.setitem(TOOL_FUNCTIONS, name, lambda **kwargs: executed.append(kwargs))

    result = ResearchAgent(provider, system_prompt="Research only", tools=TOOLS).run(
        [{"role": "user", "content": "Read the source."}], tool_choice="required")

    assert len(calls) == 2 and executed == []
    assert [call.name for call in result.tool_calls] == ["__invalid_plan__"]
    assert result.metadata["model_output_error"]
    assert result.metadata["raw_plan"] == raw_plan
    assert result.tool_results[0]["error"] == "unknown_tool"
    assert len(result.metadata["native_attempts"]) == 2


def test_structured_retry_transport_error_preserves_the_initial_model_result(monkeypatch):
    first = ModelResponse(text="Which URL should I read?")
    provider, calls = provider_with_responses(
        monkeypatch, [first, RuntimeError("structured retry transport failed")], retry_format="structured_plan")

    result = provider.complete([{"role": "user", "content": "Read the article"}], TOOLS, tool_choice="required")

    assert len(calls) == 2
    assert result is first and result.tool_calls == []
    assert result.text == "Which URL should I read?"
    assert "structured retry transport failed" in result.metadata["retry_error"]
    assert result.metadata["native_attempts"][0]["unmet_protocol"] == "required_without_calls"
    assert "transport_error" in result.metadata["native_attempts"][1]


def test_valid_native_call_never_uses_configured_structured_retry(monkeypatch):
    first = ModelResponse(tool_calls=[ToolCall("fetch", {"url": "https://example.org/KeepCase"})])
    provider, calls = provider_with_responses(monkeypatch, [first], retry_format="structured_plan")

    result = provider.complete([{"role": "user", "content": "Read the given URL"}], TOOLS, tool_choice="required")

    assert result is first and len(calls) == 1
    assert calls[0]["tools"] is TOOLS
    assert "response_format" not in calls[0]
    assert result.metadata["protocol_retry_used"] == 0
