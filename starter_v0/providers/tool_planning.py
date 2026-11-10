"""Schema-constrained tool planning; all routing decisions remain model output."""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy

from jsonschema import Draft7Validator, ValidationError

from .base import ModelResponse, ToolCall

PROTOCOL_VERSION = "tool-plan-v2"
INSTRUCTIONS = """Return a JSON tool plan, with request, tool_calls and text.
First summarize the resolved user request in one short sentence in request:
current source, topic/author/URL, requested count/timeframe/category, and missing
essential information. This is a request summary, not an explanation of reasoning.
Then choose calls that preserve those values. Explicit optional constraints still
belong in args; a topic word does not replace a timeframe or policy_area field.
Each call has name and args. Choose names and argument values yourself from the
user's request, conversation and available declarations below. Copy data faithfully.
When asking the user a question, use clarify rather than putting the question only
in text. If neither a specific account nor a search topic was supplied for posts,
ask which account/topic; words like 'recent' or 'latest' are not a topic.
Process corrections in chronological order: the newest value replaces the old
value, so a corrected author is not an ambiguous choice between two authors.
Use defaults without clarification for optional settings that were not specified.
For direct answers needing no tool, use an empty tool_calls list and answer in text.
Use declared defaults only when the user has not specified a value. Never invent
missing facts, items, accounts, URLs or approval. No tool executes until this whole
plan has been validated. Available tool declarations:
"""


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def functions(tools):
    return [deepcopy(item.get("function", item)) for item in tools or []]


def plan_schema(tools, tool_choice=None):
    if tool_choice not in (None, "auto", "none", "required"):
        raise ValueError("structured_plan supports auto, none and required tool_choice")
    branches = []
    for tool in functions(tools):
        args = deepcopy(tool["parameters"])
        args["additionalProperties"] = False
        branches.append({"type": "object", "properties": {
            "name": {"const": tool["name"]}, "args": args},
            "required": ["name", "args"], "additionalProperties": False})
    calls = {"type": "array", "items": {"oneOf": branches}} if branches else {"type": "array"}
    if not branches or tool_choice == "none":
        calls["maxItems"] = 0
    if tool_choice == "required":
        if not branches:
            raise ValueError("required tool_choice needs at least one declaration")
        calls["minItems"] = 1
    return {"type": "object", "properties": {"request": {"type": "string", "minLength": 1},
            "tool_calls": calls, "text": {"type": "string"}},
            "required": ["request", "tool_calls", "text"], "additionalProperties": False}


def planning_messages(messages, tools):
    result = deepcopy(messages)
    protocol = INSTRUCTIONS + json.dumps(functions(tools), ensure_ascii=False, separators=(",", ":"))
    if result and result[0]["role"] == "system":
        result[0]["content"] += "\n\n" + protocol
    else:
        result.insert(0, {"role": "system", "content": protocol})
    return result


def decode_plan(response, schema, metadata):
    raw = response.text or ""
    details = {**metadata, "raw_plan": raw}
    try:
        plan = json.loads(raw, parse_constant=reject_constant, object_pairs_hook=unique_keys)
        Draft7Validator(schema).validate(plan)
        if not plan["tool_calls"] and not plan["text"].strip():
            raise ValueError("An empty plan must contain a direct answer")
    except (ValueError, ValidationError) as exc:
        # A visible, non-executable diagnostic. Never repair or partially dispatch
        # malformed output, or hide it as a transport error excluded from scoring.
        details["model_output_error"] = type(exc).__name__ + ": " + str(exc)
        return ModelResponse(text=None, tool_calls=[ToolCall("__invalid_plan__", {
            "error": "InvalidModelPlan", "message": details["model_output_error"]})],
            raw=response.raw, metadata=details)
    return ModelResponse(text=plan["text"] or None,
                         tool_calls=[ToolCall(call["name"], call["args"]) for call in plan["tool_calls"]],
                         raw=response.raw, metadata=details)


def reject_constant(value):
    raise ValueError(f"Non-finite JSON constant: {value}")


def unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result
