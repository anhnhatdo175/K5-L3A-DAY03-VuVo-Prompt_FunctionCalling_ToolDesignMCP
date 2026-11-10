import csv
import io
import json

import pytest

from scripts.summarize_experiments import (
    VERSION_FIELDS, append_version_log, collect_rows, row_for, selected_version, write_analysis,
)


def saved_run(path, *, version="v5-prompt", status="completed", passed=True, ledger=True):
    metadata = {"tool_call_mode": "native", "protocol_retry_limit": 1, "protocol_retry_format": "structured_plan"}
    response_metadata = {"native_attempts": [
        {"usage": {"prompt_tokens": 10, "completion_tokens": 2}},
        {"usage": {"prompt_tokens": 12, "completion_tokens": 3}},
    ]} if ledger else {}
    run = {"version": version, "run_id": path.stem, "status": status, "generated_at": "2026-11-10T12:00:00",
           "model": "fixture-model", "provider": "ollama", "dataset_id": "fixture", "suite": "base",
           "scorer_version": "schema-v2", "provider_metadata": metadata,
           "artifact_version": "fixture-artifact", "prompt_hash": "a" * 64, "tools_hash": "b" * 64,
           "completed_cases": 1, "results": [{"id": "one", "phase": "B", "is_multiturn": False,
             "result": {"passed": passed, "routing_correct": passed, "args_correct": passed,
                        "failure_type": None if passed else "wrong_tool"},
             "provider_response_metadata": response_metadata,
             "tool_results": [{"tool": "send", "result": {"status": "dry_run"}},
                              {"tool": "lookup", "result": {"error": "RuntimeError"}}]}],
           "summary": {"total_cases": 1, "measured_cases": 1, "provider_error_cases": 0,
                       "passed_cases": int(passed), "case_accuracy": float(passed),
                       "tool_routing_accuracy": float(passed), "argument_accuracy": float(passed),
                       "multiturn_accuracy": None}}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(run), encoding="utf-8")
    return run


def test_summary_uses_saved_case_outcomes_and_request_ledgers(tmp_path):
    path = tmp_path / "runs/v5-prompt_B_fixture.json"
    saved_run(path)
    row = row_for(path, tmp_path)
    assert row["eligible_for_version_log"] is True
    assert row["case_accuracy"] == 1.0
    assert row["model_requests"] == row["recorded_model_requests"] == 2
    assert row["prompt_tokens"] == 22 and row["completion_tokens"] == 5
    assert row["tool_error_calls"] == row["action_dry_runs"] == 1
    assert row["successful_tool_calls"] == 0
    assert row["protocol_retry_format"] == "structured_plan"


def test_unknown_historical_request_cost_is_not_inferred(tmp_path):
    path = tmp_path / "runs/v6-compact4b_B_fixture.json"
    saved_run(path, version="v6-compact4b", ledger=False)
    row = row_for(path, tmp_path)
    assert row["model_requests"] == row["prompt_tokens"] == row["completion_tokens"] == ""
    assert row["request_ledger_cases"] == row["recorded_model_requests"] == 0
    assert row["eligible_for_version_log"] is True


def test_direct_answer_checker_is_included_in_inference_budget(tmp_path):
    path = tmp_path / "runs/v13-scope-check_B_fixture.json"
    run = saved_run(path, version="v13-scope-check")
    run["provider_metadata"]["direct_answer_check_enabled"] = True
    metadata = run["results"][0]["provider_response_metadata"]
    metadata["response_check_attempts"] = [{"scope": "outside", "usage": {
        "prompt_tokens": 7, "completion_tokens": 1}}]
    metadata["direct_answer_replaced"] = True
    path.write_text(json.dumps(run), encoding="utf-8")
    row = row_for(path, tmp_path)
    assert row["model_requests"] == 3
    assert row["prompt_tokens"] == 29 and row["completion_tokens"] == 6
    assert row["response_check_requests"] == row["scope_refusals"] == 1
    assert row["response_check_errors"] == 0
    assert row["direct_answer_check_enabled"] is True


def test_running_aborted_and_invalid_runs_have_no_final_accuracy_or_version_rows(tmp_path):
    for status in ("running", "aborted"):
        saved_run(tmp_path / f"runs/v6-{status}_B_fixture.json", version=f"v6-{status}", status=status)
    broken = tmp_path / "runs/v7-broken_B_fixture.json"
    broken.write_text('{"version":', encoding="utf-8")
    inconsistent = tmp_path / "runs/v8-badcount_B_fixture.json"
    run = saved_run(inconsistent, version="v8-badcount")
    run["completed_cases"] = 2
    inconsistent.write_text(json.dumps(run), encoding="utf-8")
    missing = tmp_path / "runs/v9-malformed_B_fixture.json"
    run = saved_run(missing, version="v9-malformed")
    del run["results"][0]["result"]["passed"]
    missing.write_text(json.dumps(run), encoding="utf-8")

    rows = collect_rows(tmp_path / "runs", tmp_path)

    assert len(rows) == 5
    assert {row["status"] for row in rows} == {"running", "aborted", "invalid"}
    assert all(row["case_accuracy"] == "" and row["eligible_for_version_log"] is False for row in rows)
    assert append_version_log(tmp_path / "versions.csv", rows, tmp_path) == 0
    assert not (tmp_path / "versions.csv").exists()
    write_analysis(tmp_path / "analysis.csv", rows)
    with (tmp_path / "analysis.csv").open(encoding="utf-8", newline="") as output:
        assert len(list(csv.DictReader(output))) == 5


def test_append_preserves_historical_bytes_and_records_nonwinners_without_duplicates(tmp_path):
    first = tmp_path / "runs/v5-prompt_B_first.json"
    second = tmp_path / "runs/v6-compact4b_B_second.json"
    saved_run(first, passed=False)
    saved_run(second, version="v6-compact4b", passed=True)
    rows = collect_rows(tmp_path / "runs", tmp_path)
    historical = io.StringIO(newline="")
    writer = csv.DictWriter(historical, fieldnames=VERSION_FIELDS, lineterminator="\r\n")
    writer.writeheader()
    writer.writerow({"version": "v3", "reason": "Preserve this historical row exactly", "run_file": "runs/v3.json"})
    original = historical.getvalue().encode("utf-8")
    log = tmp_path / "version_log.csv"
    log.write_bytes(original)

    assert append_version_log(log, rows, tmp_path) == 2
    assert log.read_bytes().startswith(original)
    after_first = log.read_bytes()
    assert append_version_log(log, rows, tmp_path) == 0
    assert log.read_bytes() == after_first
    with log.open(encoding="utf-8", newline="") as output:
        saved = list(csv.DictReader(output))
    assert len(saved) == 3
    assert saved[1]["version"] == "v5-prompt" and "case_accuracy=0.0" in saved[1]["metric_after"]
    assert saved[2]["version"] == "v6-compact4b"
    assert "Reference run=runs/v5-prompt_B_first.json" in saved[2]["metric_before"]


def test_only_requested_experiment_generations_are_selected():
    assert all(selected_version(version) for version in ("v4-fixes", "v5-prompt", "v11-next", "v13"))
    assert not any(selected_version(version) for version in ("v3", "v4-other", "v14-next", "v50", "fixture"))


@pytest.mark.parametrize("broken_part", ["results", "tool_results", "count_type"])
def test_malformed_nested_rows_are_visible_without_stopping_other_summaries(tmp_path, broken_part):
    path = tmp_path / "runs/v12-local_B_fixture.json"
    run = saved_run(path, version="v12-local")
    if broken_part == "results":
        run["results"] = None
    elif broken_part == "tool_results":
        run["results"][0]["tool_results"] = None
    else:
        run["summary"]["total_cases"] = True
    path.write_text(json.dumps(run), encoding="utf-8")
    row = row_for(path, tmp_path)
    assert row["status"] == "invalid"
    assert row["validation_issue"]
    assert row["case_accuracy"] == "" and row["eligible_for_version_log"] is False
