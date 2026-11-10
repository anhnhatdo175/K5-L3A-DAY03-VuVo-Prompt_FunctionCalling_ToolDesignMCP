"""Summarize saved local experiments without invoking a model or changing run logs.

Final accuracy is exported only for internally consistent completed runs. Request
counts are exact only when every saved case includes a native_attempts ledger;
direct-answer checker attempts are included alongside the native ledger.
these count attempted requests, including recorded transport failures. Unknown
costs remain empty. Existing version-log bytes are preserved when appending.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import math
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
VERSION_FIELDS = ["version", "author", "changed_artifact", "artifact_version", "prompt_hash", "tools_hash",
                  "reason", "hypothesis", "metric_before", "metric_after", "run_file"]
METRICS = ["case_accuracy", "tool_routing_accuracy", "argument_accuracy", "multiturn_accuracy"]
CSV_FIELDS = [
    "run_file", "run_id", "version", "status", "reported_status", "eligible_for_version_log", "validation_issue",
    "generated_at", "completed_at", "provider", "model", "tool_call_mode", "planning_protocol", "reasoning_effort",
    "protocol_retry_limit", "protocol_retry_format", "direct_answer_check_enabled", "scorer_version", "dataset_id", "dataset_role", "suite",
    "eval_cases", "dataset_hash", "artifact_version", "prompt_hash", "tools_hash", "planning_template_hash",
    "plan_schema_hashes", "adapter_source_hashes", "code_hashes", "runtime", "actions_mode",
    "completed_cases", "total_cases", "measured_cases", "provider_error_cases", "passed_cases", *METRICS,
    "tool_calls", "tool_error_calls", "action_dry_runs", "successful_tool_calls", "model_requests",
    "recorded_model_requests", "request_ledger_cases", "transport_error_attempts", "prompt_tokens",
    "completion_tokens", "response_check_requests", "response_check_errors", "scope_refusals", "abort_reason", "changed_artifact", "reason", "hypothesis",
]
EXPERIMENTS = {
    "v4-fixes": ("prompt + tool schema + runtime/scorer fixes", "Validate the repaired runtime and complete argument contracts",
                 "Clear source routing and argument rules may improve reliability under strict schema scoring"),
    "v5-prompt": ("system prompt", "Test concise routing instructions and argument serialization guidance",
                  "A clearer prompt may reduce missing and malformed calls"),
    "v5-v3check": ("historical v3 prompt control", "Recheck the historical prompt in the current local runtime",
                   "A runtime control helps separate prompt effects from environment differences"),
    "v6-compact4b": ("compact prompt + local model", "Test a compact prompt with the local 4B model",
                     "A stronger small model and shorter instructions may improve routing and argument retention"),
    "v7-plan4b": ("schema-constrained planning adapter", "Compare model-selected JSON planning with native tool calls",
                  "Constrained output may reduce serialization failures without determining tool intent"),
    "v8-planstate": ("planning protocol", "Add an explicit resolved-request summary to the model plan",
                     "Stating the current request may improve multi-turn constraint retention"),
    "v9-modern": ("local model + native protocol", "Evaluate the newer instruct model with native tool calls",
                  "The newer small model may improve instruction following and tool selection"),
    "v10-native-retry": ("bounded native protocol retry", "Retry only empty responses or an unmet required-call contract",
                        "A protocol reminder may recover missing calls while preserving model-selected routing"),
    "v11-schema-retry": ("bounded structured protocol retry", "Use all-tool schema planning after an unmet native call contract",
                        "Schema-constrained recovery may improve protocol adherence without routing shortcuts"),
    "v12-fresh-retry": ("retry conversation context", "Retry from original messages without unexecuted model prose",
                       "Fresh retry context may prevent earlier generated prose from inventing request details"),
    "v12-local": ("local model + retry context + JSON type guidance",
                  "Evaluate Qwen3.5 4B with fresh original retry context and explicit JSON type wording",
                  "Keeping original user context and clarifying JSON types may reduce invented details and argument type errors"),
}


def selected_version(version):
    if version == "v4-fixes":
        return True
    match = re.match(r"^v(\d+)(?:$|\D)", str(version))
    return bool(match and 5 <= int(match[1]) <= 13)


def compact(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) if value else ""


def relative_file(path, root):
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def metadata_value(run, key):
    metadata = run.get("provider_metadata") or {}
    if isinstance(metadata, dict) and key in metadata:
        return metadata[key]
    results = run.get("results") if isinstance(run.get("results"), list) else []
    values = [item.get("provider_response_metadata", {}).get(key) for item in results
              if isinstance(item, dict) and isinstance(item.get("provider_response_metadata"), dict)
              and key in item["provider_response_metadata"]]
    unique = {compact(value): value for value in values}
    return next(iter(unique.values())) if len(unique) == 1 else (compact(list(unique.values())) if unique else "")


def observed_summary(results):
    measured = [item for item in results if item["result"].get("failure_type") != "provider_error"]
    passed = sum(item["result"]["passed"] for item in measured)
    summary = {"total_cases": len(results), "measured_cases": len(measured),
               "provider_error_cases": len(results) - len(measured), "passed_cases": passed,
               "case_accuracy": round(passed / len(measured), 4) if measured else 0.0}
    phase_b = [item for item in measured if item.get("phase") == "B"]
    if phase_b:
        multi = [item for item in phase_b if item.get("is_multiturn")]
        summary.update(tool_routing_accuracy=round(sum(bool(item["result"].get("routing_correct")) for item in phase_b) / len(phase_b), 4),
                       argument_accuracy=round(sum(bool(item["result"].get("args_correct")) for item in phase_b) / len(phase_b), 4),
                       multiturn_accuracy=round(sum(item["result"]["passed"] for item in multi) / len(multi), 4) if multi else None)
    return summary


def request_costs(results):
    ledgers, check_attempts, refusals = [], [], 0
    for item in results:
        metadata = item.get("provider_response_metadata") or {}
        metadata = metadata if isinstance(metadata, dict) else {}
        native = metadata.get("native_attempts")
        checks = metadata.get("response_check_attempts") or []
        checks_valid = isinstance(checks, list) and all(isinstance(attempt, dict) for attempt in checks)
        if checks_valid:
            check_attempts.extend(checks)
        refusals += metadata.get("direct_answer_replaced") is True
        ledgers.append(native + checks if isinstance(native, list) and checks_valid else None)
    available = [ledger for ledger in ledgers if isinstance(ledger, list) and ledger
                 and all(isinstance(attempt, dict) for attempt in ledger)]
    attempts = [attempt for ledger in available for attempt in ledger]
    complete = bool(results) and len(available) == len(results)
    costs = {"model_requests": len(attempts) if complete else "", "recorded_model_requests": len(attempts),
             "request_ledger_cases": len(available),
             "transport_error_attempts": sum(bool(attempt.get("transport_error")) for attempt in attempts),
             "response_check_requests": len(check_attempts),
             "response_check_errors": sum(bool(attempt.get("error")) for attempt in check_attempts),
             "scope_refusals": refusals}
    for field in ("prompt_tokens", "completion_tokens"):
        values = [attempt.get("usage", {}).get(field) if isinstance(attempt.get("usage"), dict) else None for attempt in attempts]
        known = complete and all(type(value) is int and value >= 0 for value in values)
        costs[field] = sum(values) if known else ""
    return costs


def row_for(path, root=ROOT):
    row = {field: "" for field in CSV_FIELDS}
    row.update(run_file=relative_file(path, root), version=path.name.split("_B_", 1)[0], status="invalid",
               eligible_for_version_log=False)
    try:
        run = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(run, dict):
            raise ValueError("Run JSON must be an object")
    except (OSError, ValueError) as exc:
        row["validation_issue"] = f"{type(exc).__name__}: {exc}"
        return row
    for field in CSV_FIELDS:
        if field in run and field not in {*METRICS, "run_file", "validation_issue", "eligible_for_version_log", "reported_status"} and not isinstance(run[field], (dict, list)):
            row[field] = run[field] if run[field] is not None else ""
    row["reported_status"] = run.get("status", "unknown")
    row["status"] = row["reported_status"]
    row["eligible_for_version_log"] = False
    for field in ("tool_call_mode", "planning_protocol", "reasoning_effort", "protocol_retry_limit", "protocol_retry_format", "direct_answer_check_enabled",
                  "planning_template_hash", "plan_schema_hashes", "adapter_source_hashes"):
        value = metadata_value(run, field)
        row[field] = compact(value) if isinstance(value, (dict, list)) else value
    row["runtime"], row["code_hashes"] = compact(run.get("runtime")), compact(run.get("code_hashes"))
    details = run.get("experiment_metadata") or run.get("experiment") or {}
    details = details if isinstance(details, dict) else {}
    known = EXPERIMENTS.get(row["version"], ("saved local experiment", "Record the completed local experiment",
                                               "Measure actual routing and argument performance; outcome not assumed"))
    for field, default in zip(("changed_artifact", "reason", "hypothesis"), known):
        row[field] = details.get(field) or run.get(field) or default
    issues = []
    results = run.get("results")
    if not isinstance(results, list) or any(not isinstance(item, dict) or not isinstance(item.get("result"), dict)
                                          or type(item["result"].get("passed")) is not bool for item in results):
        row.update(status="invalid", validation_issue="Missing or malformed results/passed flags")
        return row
    row.update(request_costs(results))
    observed = observed_summary(results)
    for field in ("completed_cases", "total_cases", "measured_cases", "provider_error_cases", "passed_cases"):
        row[field] = len(results) if field == "completed_cases" else observed[field]
    if "completed_cases" in run and (type(run["completed_cases"]) is not int or run["completed_cases"] != len(results)):
        issues.append("completed_cases does not match saved results")
    summary = run.get("summary")
    if not isinstance(summary, dict):
        issues.append("Missing summary object")
        summary = {}
    if run.get("status") == "completed" and not results:
        issues.append("Completed run has no results")
    for field, actual in observed.items():
        saved = summary.get(field)
        if field not in summary or (isinstance(actual, float) and
                                   (type(saved) not in (int, float) or not math.isfinite(saved) or abs(saved - actual) > 0.00001)) or (
                                       not isinstance(actual, float) and (type(saved) is not type(actual) or saved != actual)):
            issues.append(f"summary.{field} does not match saved case outcomes")
    event_groups = [item.get("tool_results", []) for item in results]
    events = [event for group in event_groups for event in group] if all(isinstance(group, list) for group in event_groups) else None
    if events is None or any(not isinstance(event, dict) or not isinstance(event.get("result", event), dict) for event in events):
        issues.append("Malformed tool result events")
        events = []
    errors = sum(bool(event.get("result", event).get("error")) for event in events)
    dry_runs = sum(event.get("result", event).get("status") == "dry_run" for event in events)
    row.update(tool_calls=len(events), tool_error_calls=errors, action_dry_runs=dry_runs,
               successful_tool_calls=len(events) - errors - dry_runs)
    if issues and run.get("status") == "completed":
        row["status"] = "invalid"
    row["validation_issue"] = "; ".join(issues)
    if run.get("status") == "completed" and not issues:
        row["eligible_for_version_log"] = selected_version(row["version"])
        for field in METRICS:
            row[field] = observed.get(field) if observed.get(field) is not None else ""
    else:
        for field in METRICS:
            row[field] = ""
    return row


def collect_rows(runs_dir, root=ROOT):
    rows = [row_for(path, root) for path in sorted(runs_dir.glob("*.json"))]
    return sorted((row for row in rows if selected_version(row["version"])),
                  key=lambda row: (row["generated_at"] or "", row["run_file"]))


def write_analysis(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def metric_text(row):
    fields = [*METRICS, "measured_cases", "provider_error_cases", "tool_error_calls", "action_dry_runs"]
    return "; ".join(f"{field}={row[field]}" for field in fields if row.get(field) != "")


def normalized_run_file(value, root):
    value = str(value).replace("\\", "/")
    path = Path(value)
    return relative_file(path, root) if path.is_absolute() else value.removeprefix("./")


def append_version_log(path, rows, root=ROOT):
    original = path.read_bytes() if path.exists() else b""
    reader = csv.DictReader(io.StringIO(original.decode("utf-8-sig"))) if original else None
    fieldnames = reader.fieldnames if reader else VERSION_FIELDS
    if fieldnames is None or not set(VERSION_FIELDS).issubset(fieldnames):
        raise ValueError("Version log header is missing required fields")
    existing = {normalized_run_file(row["run_file"], root) for row in reader} if reader else set()
    additions, prior = [], {}
    for row in rows:
        if row.get("eligible_for_version_log") is not True:
            continue
        key = (row["dataset_id"], row["suite"], row["scorer_version"])
        reference = prior.get(key)
        run_file = normalized_run_file(row["run_file"], root)
        if run_file not in existing:
            context = f"model={row['model']}; protocol={row['tool_call_mode'] or 'unrecorded'}; dataset={row['dataset_id']}"
            additions.append({"version": row["version"], "author": "Team", "changed_artifact": row["changed_artifact"],
                              "artifact_version": row["artifact_version"], "prompt_hash": row["prompt_hash"], "tools_hash": row["tools_hash"],
                              "reason": row["reason"] + "; " + context + "; see analysis CSV for runtime/protocol differences",
                              "hypothesis": row["hypothesis"], "metric_after": metric_text(row), "run_file": run_file,
                              "metric_before": (f"Reference run={reference['run_file']}; {metric_text(reference)}" if reference else "")})
            existing.add(run_file)
        prior[key] = row
    if additions:
        newline = "\r\n" if b"\r\n" in original else "\n"
        buffer = io.StringIO(newline="")
        writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator=newline)
        if not original:
            writer.writeheader()
        writer.writerows(additions)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("ab") as output:
            if original and not original.endswith((b"\n", b"\r")):
                output.write(newline.encode("utf-8"))
            output.write(buffer.getvalue().encode("utf-8"))
    return len(additions)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-dir", type=Path, default=ROOT / "runs")
    parser.add_argument("--output", type=Path, default=ROOT / "analysis/local_tuning_results.csv")
    parser.add_argument("--version-log", type=Path, default=ROOT / "artifacts/version_log.csv")
    parser.add_argument("--append-version-log", action="store_true", help="Append validated completed experiments; preserve existing rows")
    args = parser.parse_args()
    rows = collect_rows(args.runs_dir)
    write_analysis(args.output, rows)
    print(f"Saved {len(rows)} experiments to {args.output}")
    if args.append_version_log:
        print(f"Appended {append_version_log(args.version_log, rows)} rows to {args.version_log}")


if __name__ == "__main__":
    main()
