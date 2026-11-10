import json
import sys
from types import SimpleNamespace
from pathlib import Path

import pytest
from jsonschema import Draft7Validator, ValidationError

from agent import ResearchAgent
from conftest import FakeResponse
from providers.base import ModelResponse
from providers.ollama_provider import OllamaProvider
from providers.openai_provider import OpenAIProvider
from providers.tool_planning import decode_plan, plan_schema
from tools import load_tool_declarations, to_openai_tools

TOOLS = to_openai_tools(load_tool_declarations(Path(__file__).resolve().parents[1] / "artifacts/tools.yaml"))


def test_plan_schema_binds_names_to_their_own_arguments_and_keeps_optional_fields():
    schema = plan_schema(TOOLS)
    validator = Draft7Validator(schema)
    validator.validate({"request": "Test request", "text": "", "tool_calls": [{"name": "fetch", "args": {"url": "https://example.org"}}]})
    validator.validate({"request": "Test request", "text": "", "tool_calls": [{"name": "policy", "args": {"query": "citation"}}]})
    with pytest.raises(ValidationError):
        validator.validate({"request": "Test request", "text": "", "tool_calls": [{"name": "fetch", "args": {"query": "citation"}}]})


def test_plan_tool_choice_auto_required_and_none_follow_caller_contract():
    direct = {"request": "Greeting", "tool_calls": [], "text": "Hello"}
    Draft7Validator(plan_schema(TOOLS)).validate(direct)
    Draft7Validator(plan_schema(TOOLS, "none")).validate(direct)
    with pytest.raises(ValidationError):
        Draft7Validator(plan_schema(TOOLS, "required")).validate(direct)
    with pytest.raises(ValidationError):
        Draft7Validator(plan_schema(TOOLS, "none")).validate({"request": "Test request", "text": "", "tool_calls": [{
            "name": "clarify", "args": {"question": "Which account?"}}]})


def test_plan_preserves_arbitrary_item_metadata_without_argument_repairs():
    items = [{"url": None, "title": "A", "metadata": {"tags": [True, 1, "x"]}}]
    plan = {"request": "Test request", "text": "", "tool_calls": [{"name": "deduplicate", "args": {"items": items}}]}
    response = decode_plan(ModelResponse(text=json.dumps(plan)), plan_schema(TOOLS), {})
    assert response.tool_calls[0].args == {"items": items}
    assert "key_by" not in response.tool_calls[0].args


@pytest.mark.parametrize("bad_output", ['{"tool_calls": [', json.dumps({"request": "Test request", "text": "", "tool_calls": [
    {"name": "send", "args": {"text": "Draft", "confirmed": "true"}}]})])
def test_bad_plan_is_visible_and_never_dispatches_actions(bad_output, fake_http):
    requests = fake_http(FakeResponse())
    class Provider:
        def complete(self, *args, **kwargs):
            return decode_plan(ModelResponse(text=bad_output), plan_schema(TOOLS), {})
    result = ResearchAgent(Provider(), system_prompt="Test", tools=TOOLS).run([])
    assert result.tool_calls[0].name == "__invalid_plan__"
    assert result.metadata["model_output_error"]
    assert result.tool_results[0]["error"] == "unknown_tool"
    assert not requests


def test_structured_provider_grounds_all_tools_and_records_protocol(monkeypatch):
    monkeypatch.setenv("OLLAMA_CALL_MODE", "structured_plan")
    captured = {}
    def complete(self, messages, tools=None, **kwargs):
        captured.update(messages=messages, tools=tools, kwargs=kwargs)
        return ModelResponse(text=json.dumps({"request": "Test request", "text": "", "tool_calls": [{"name": "clarify", "args": {
            "question": "Which URL?", "response_type": "text"}}]}))
    monkeypatch.setattr("providers.openai_provider.OpenAIProvider.complete", complete)
    original = [{"role": "system", "content": "Research only"}, {"role": "user", "content": "Read an article"}]
    response = OllamaProvider().complete(original, TOOLS, tool_choice="required")
    assert captured["tools"] is None
    schema = captured["kwargs"]["response_format"]["json_schema"]["schema"]
    names = {branch["properties"]["name"]["const"] for branch in schema["properties"]["tool_calls"]["items"]["oneOf"]}
    assert names == {tool["function"]["name"] for tool in TOOLS}
    assert original[0]["content"] == "Research only"
    assert response.tool_calls[0].name == "clarify"
    assert response.metadata["tool_call_mode"] == "structured_plan"
    assert response.metadata["requested_tool_choice"] == "required"
    assert len(response.metadata["request_prompt_hash"]) == 64


def test_native_provider_is_preserved_and_empty_tool_lists_work(monkeypatch):
    monkeypatch.setenv("OLLAMA_CALL_MODE", "native")
    seen = {}
    def complete(self, messages, tools=None, **kwargs):
        seen.update(tools=tools, kwargs=kwargs)
        return ModelResponse(text="Hello")
    monkeypatch.setattr("providers.openai_provider.OpenAIProvider.complete", complete)
    assert OllamaProvider().complete([], TOOLS).text == "Hello"
    assert seen["tools"] is TOOLS
    assert "response_format" not in seen["kwargs"]
    monkeypatch.setenv("OLLAMA_CALL_MODE", "structured_plan")
    assert OllamaProvider().metadata([])["tool_call_mode"] == "structured_plan"


@pytest.mark.parametrize("raw", [
    '{"request":"Test","text":"","tool_calls":[{"name":"send","args":{"text":"Draft","confirmed":false,"confirmed":true}}]}',
    '{"request":"Test","text":"","tool_calls":[{"name":"deduplicate","args":{"items":[{"value":NaN}]}}]}',
])
def test_plan_rejects_duplicate_keys_and_nonfinite_json(raw):
    response = decode_plan(ModelResponse(text=raw), plan_schema(TOOLS), {})
    assert response.tool_calls[0].name == "__invalid_plan__"
    assert "ValueError" in response.metadata["model_output_error"]


@pytest.mark.parametrize("arguments", [
    '{"text":"Draft","confirmed":false,"confirmed":true}',
    '{"text":"Draft","confirmed":NaN}',
])
def test_native_decoder_preserves_invalid_arguments_as_failure(monkeypatch, arguments):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    call = SimpleNamespace(function=SimpleNamespace(name="send", arguments=arguments))
    message = SimpleNamespace(content=None, tool_calls=[call])
    response = SimpleNamespace(choices=[SimpleNamespace(message=message)])
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **kwargs: response)))
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=lambda **kwargs: client))
    result = OpenAIProvider().complete([], TOOLS)
    assert result.tool_calls[0].name == "send"
    assert result.tool_calls[0].args == {"_invalid_json_arguments": arguments}
