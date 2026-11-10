"""Capture three real Ollama turns through Streamlit; never enable demo fallback.

Run explicitly: python scripts/check_live_ui.py --version v13-scope-check
The UTF-8 source preserves Vietnamese input without a shell text pipeline.
This check calls a local model and local tools; it is not an offline unit test.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
ITEMS = [
    {"title": "Orchid", "url": "https://example.org/orchid", "rank": 8},
    {"title": "Maple", "url": "https://example.org/orchid/", "rank": 5},
    {"title": "Orchid", "url": "https://example.net/second", "tags": ["botany"]},
]
QUESTIONS = [
    "Loại trùng URL, giữ bản đầu tiên và nguyên vẹn mọi trường trong danh sách này: "
    + json.dumps(ITEMS, ensure_ascii=False),
    "Dùng lại danh sách gốc tôi đã gửi ở lượt đầu, lần này bỏ trùng theo tiêu đề, giữ bản đầu tiên và mọi trường.",
    "Tra policy nội bộ thuộc nhóm tool_usage: cần làm gì trước khi một công cụ gửi nội dung ra bên ngoài? Lấy 2 đoạn liên quan.",
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", default="v13-scope-check")
    parser.add_argument("--system-prompt", type=Path, help="Optional candidate; no artifact file is overwritten")
    args = parser.parse_args()
    os.environ["DEFAULT_PROVIDER"] = "ollama"
    os.environ["ARTIFACT_VERSION"] = args.version
    sys.path.insert(0, str(ROOT))
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=300).run()
    assert not app.exception
    assert app.selectbox[0].value == "ollama" and app.checkbox[0].value is False
    if args.system_prompt:
        prompt_input = next(item for item in app.text_input if item.label == "System prompt")
        prompt_input.set_value(str(args.system_prompt.resolve())).run(timeout=300)
        assert not app.exception
    for index, question in enumerate(QUESTIONS, 1):
        app.chat_input[0].set_value(question).run(timeout=300)
        assert not app.exception, app.exception
        turn = app.session_state["transcript"]["turns"][-1]
        assert turn["user"] == question
        print(json.dumps({"turn": index, "status": turn["status"], "mode": turn["execution_mode"],
                          "tools": [event["tool"] for event in turn["tool_events"]]}), flush=True)

    transcript = app.session_state["transcript"]
    turns = transcript["turns"]
    events = [turn["tool_events"] for turn in turns]
    checks = {"three_live_answers": len(turns) == 3 and all(
        turn["status"] == "answered" and turn["execution_mode"] == "live" and not turn.get("fallback_to_demo")
        for turn in turns)}
    for index, key in enumerate(("url", "title")):
        expected = [ITEMS[0], ITEMS[2] if key == "url" else ITEMS[1]]
        checks[f"deduplicate_{key}"] = len(events[index]) == 1 and (
            events[index][0]["tool"] == "deduplicate"
            and events[index][0]["args"].get("items") == ITEMS
            and events[index][0]["args"].get("key_by", "url") == key
            and events[index][0]["result"].get("items") == expected
            and events[index][0]["result"].get("removed_count") == 1)
    policy = events[2][0] if len(events[2]) == 1 else {}
    hits = policy.get("result", {}).get("results", [])
    checks["explicit_policy_filter"] = policy.get("tool") == "policy" and (
        policy["args"].get("policy_area") == "tool_usage" and policy["args"].get("top_k") == 2
        and bool(hits) and all(hit["policy_area"] == "tool_usage" for hit in hits))
    checks["relevant_confirmation_facts"] = any("confirmation" in hit.get("facts", "").lower() for hit in hits)
    summary = {"evidence_kind": "live_ui_apptest", "observed_at": datetime.now(timezone.utc).isoformat(),
               "provider": "ollama", "model": transcript["model"], "fallback_enabled": False,
               "transcript_file": "transcripts/" + transcript["transcript_id"] + ".transcript.json",
               "artifact_version": transcript["artifact_version"], "checks": checks}
    output = ROOT / "analysis" / f"{args.version}_ui_live_check.json"
    output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=True), flush=True)
    if not all(checks.values()):
        raise SystemExit("Live UI semantic checks failed; retained transcript and results.")


if __name__ == "__main__":
    main()
