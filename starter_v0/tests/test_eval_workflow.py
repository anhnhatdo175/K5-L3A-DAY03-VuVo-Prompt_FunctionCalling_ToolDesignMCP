import json

import pytest

import run_eval
from providers.base import ModelResponse, ToolCall
from scripts.replay_eval import replay
from tools import load_tool_declarations


def prepare_run(tmp_path, monkeypatch, call):
    case = {"id": "offline", "phase": "B", "failure_type": "wrong_arg_value",
            "query": "Offline fixture", "expect": {"tool_calls": [{"name": call.name, "args": call.args}]}}
    cases_file = tmp_path / "cases.json"
    cases_file.write_text(json.dumps({"cases": [case]}), encoding="utf-8")
    class Provider:
        default_model = "test-provider"
        def complete(self, *args, **kwargs):
            return ModelResponse(tool_calls=[call])
    monkeypatch.setattr(run_eval, "make_provider", lambda name: Provider())
    monkeypatch.setattr(run_eval, "configure_stdio", lambda: None)
    monkeypatch.setattr("sys.argv", ["run_eval.py", "--provider", "ollama", "--version", "offline-test",
                                     "--eval-cases", str(cases_file), "--runs-dir", str(tmp_path / "runs")])


def test_scoring_exception_is_harness_error_and_retains_call(tmp_path, monkeypatch):
    prepare_run(tmp_path, monkeypatch, ToolCall("deduplicate", {"items": []}))
    def broken_scorer(*args):
        raise TypeError("test scorer bug")
    monkeypatch.setattr(run_eval, "evaluate_phase_b", broken_scorer)
    run_eval.main()
    saved = json.loads(next((tmp_path / "runs").glob("*.json")).read_text(encoding="utf-8"))
    assert saved["results"][0]["result"]["failure_type"] == "harness_error"
    assert saved["results"][0]["result"]["actual_tool_calls"][0]["name"] == "deduplicate"
    assert saved["summary"]["provider_error_cases"] == 0
    assert saved["summary"]["measured_cases"] == 1


def test_eval_defaults_to_dry_run_for_confirmed_send(tmp_path, monkeypatch, fake_http):
    from conftest import FakeResponse
    calls = fake_http(FakeResponse({"ok": True}))
    prepare_run(tmp_path, monkeypatch, ToolCall("send", {"text": "Fixture only", "confirmed": True}))
    run_eval.main()
    saved = json.loads(next((tmp_path / "runs").glob("*.json")).read_text(encoding="utf-8"))
    assert saved["actions_mode"] == "dry_run"
    assert saved["summary"]["tool_execution"]["dry_run_calls"] == 1
    assert saved["summary"]["tool_execution"]["successful_calls"] == 0
    assert calls == []


def test_offline_replay_regrades_without_changing_source():
    source = {"run_id": "fixture", "summary": {"passed_cases": 1}, "results": [{
        "id": "one", "phase": "B", "result": {"passed": True, "actual_text": None,
        "actual_tool_calls": [{"name": "deduplicate", "args": {}}]}, "tool_results": []}]}
    original = json.dumps(source)
    cases = [{"id": "one", "failure_type": "wrong_arg_value", "expect": {
        "tool_calls": [{"name": "deduplicate", "args": {}}]}}]
    result = replay(source, cases, load_tool_declarations(run_eval.ARTIFACTS_DIR / "tools.yaml"))
    assert result["evidence_kind"] == "offline_replay"
    assert not result["results"][0]["result"]["passed"]
    assert json.dumps(source) == original


@pytest.mark.parametrize("source_ids", [[], ["one", "one"], ["one", "unexpected"]])
def test_offline_replay_rejects_incomplete_or_duplicate_coverage(source_ids):
    source = {"results": [{"id": case_id} for case_id in source_ids]}
    with pytest.raises(ValueError, match="coverage|duplicate"):
        replay(source, [{"id": "one"}], [])
