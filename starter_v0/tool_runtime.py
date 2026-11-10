"""Validate model arguments before dispatching a tool (shared by chat and eval)."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator

from providers.base import ToolCall
from tools import TOOL_FUNCTIONS, load_tool_declarations
from tools._shared import err

LOCAL_TOOLS = {"clarify", "format", "policy", "deduplicate"}
DEFAULT_TOOLS = Path(__file__).parent / "artifacts" / "tools.yaml"


def argument_errors(name: str, args: Any, declarations=None) -> list[str]:
    declarations = load_tool_declarations(DEFAULT_TOOLS) if declarations is None else declarations
    functions = [item.get("function", item) for item in declarations]
    declaration = next((item for item in functions if item["name"] == name), None)
    if declaration is None:
        return [f"Unknown or disabled tool: {name}"]
    schema = deepcopy(declaration["parameters"])
    schema["additionalProperties"] = False
    if name == "deduplicate":
        # Items retain arbitrary metadata; the implementation validates only the selected key.
        selected = args.get("key_by", "url") if isinstance(args, dict) else "url"
        properties = {selected: {"type": ["string", "null"]}} if isinstance(selected, str) and selected in ("url", "title") else {}
        schema["properties"]["items"]["items"] = {"type": "object", "properties": properties}
    errors = sorted(Draft7Validator(schema).iter_errors(args), key=lambda error: str(error.path))
    messages = [f"{'.'.join(map(str, error.path)) or 'args'}: {error.message}" for error in errors]
    if name == "send" and isinstance(args, dict) and isinstance(args.get("text"), str) and not args["text"].strip():
        messages.append("text: must not be empty")
    return messages


def execute_tool_call(call: ToolCall, declarations=None, *, offline=False, dry_run_actions=False) -> dict[str, Any]:
    event = {"tool": call.name, "args": call.args}
    errors = argument_errors(call.name, call.args, declarations)
    if errors:
        result = {"error": "InvalidToolArguments", "message": "; ".join(errors)}
    elif offline and call.name not in LOCAL_TOOLS:
        result = {"error": "OfflineToolUnavailable", "message": f"{call.name} cần kết nối bên ngoài; hãy chọn provider thật."}
    elif dry_run_actions and call.name == "send" and call.args.get("confirmed") is True:
        result = {"tool": "send", "status": "dry_run", "confirmed": True, "text_length": len(call.args["text"])}
    else:
        func = TOOL_FUNCTIONS.get(call.name)
        try:
            result = func(**call.args) if func else {"error": "unknown_tool", "message": call.name}
        except Exception as exc:
            result = err(call.name, exc)
    return {**event, "result": result}
