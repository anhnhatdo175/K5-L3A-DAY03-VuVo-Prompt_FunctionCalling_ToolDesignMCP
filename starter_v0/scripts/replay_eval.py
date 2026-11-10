"""Regrade saved calls offline; never execute a provider or a tool."""
from __future__ import annotations

import argparse
import csv
import json
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from run_eval import evaluate_phase_b, load_cases, summarize
from tools import load_tool_declarations
from versioning import file_hash


def replay(source, cases, declarations):
    by_id = {case["id"]: case for case in cases}
    source_ids = [item["id"] for item in source["results"]]
    if len(source_ids) != len(set(source_ids)):
        raise ValueError("Source run contains duplicate case IDs")
    if set(source_ids) != set(by_id):
        raise ValueError(f"Replay requires complete coverage; missing={sorted(set(by_id) - set(source_ids))}, unexpected={sorted(set(source_ids) - set(by_id))}")
    results = []
    for original in source["results"]:
        case = by_id[original["id"]]
        item = deepcopy(original)
        item["expect"] = case["expect"]
        if original["result"].get("failure_type") != "provider_error":
            item["result"] = evaluate_phase_b(case, original["result"]["actual_tool_calls"],
                                              original["result"].get("actual_text"), declarations)
        results.append(item)
    return {"evidence_kind": "offline_replay", "scorer_version": "schema-v2",
            "source_run_id": source["run_id"], "source_summary": source["summary"],
            "execution_note": "Calls are regraded; tool results are historical and were not rerun.",
            "summary": summarize(results), "results": results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--eval-cases", type=Path, default=ROOT / "data/eval_group.json")
    parser.add_argument("--tools", type=Path, default=ROOT / "artifacts/tools.yaml")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source = json.loads(args.source.read_text(encoding="utf-8"))
    result = replay(source, load_cases(args.eval_cases, "B"), load_tool_declarations(args.tools))
    result["source_file"] = str(args.source)
    result["eval_cases"] = str(args.eval_cases)
    result["tools"] = str(args.tools)
    result["source_hash"] = file_hash(args.source)
    result["eval_cases_hash"] = file_hash(args.eval_cases)
    result["tools_hash"] = file_hash(args.tools)
    result["generated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    with args.output.with_suffix(".csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["case_id", "historical_passed", "replay_passed", "failures"])
        writer.writeheader()
        for old, new in zip(source["results"], result["results"]):
            writer.writerow({"case_id": new["id"], "historical_passed": old["result"]["passed"],
                             "replay_passed": new["result"]["passed"], "failures": "; ".join(new["result"]["failures"])})
    print(json.dumps(result["summary"]))


if __name__ == "__main__":
    main()
