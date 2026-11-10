from __future__ import annotations

import json
import os
from typing import Any

from providers.base import ModelResponse, ToolCall
from providers.tool_planning import reject_constant, unique_keys


class OpenAIProvider:
    """OpenAI Chat Completions provider with normalized tool_calls output."""

    def __init__(
        self,
        *,
        api_key_env: str = "OPENAI_API_KEY",
        base_url: str | None = None,
        default_model: str = "gpt-4o-mini",
        api_key_default: str | None = None,
    ) -> None:
        self.api_key_env = api_key_env
        self.api_key_default = api_key_default
        self.base_url = base_url
        self.default_model = default_model

    def complete(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
        *,
        model: str | None = None,
        temperature: float = 0.0,
        tool_choice: Any | None = None,
        response_format: dict[str, Any] | None = None,
        reasoning_effort: str | None = None,
    ) -> ModelResponse:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("Install live provider dependency first: pip install openai") from exc

        api_key = os.getenv(self.api_key_env) or self.api_key_default
        if not api_key:
            raise RuntimeError(f"Missing API key env var: {self.api_key_env}")

        client = OpenAI(api_key=api_key, base_url=self.base_url)
        kwargs: dict[str, Any] = {
            "model": model or self.default_model,
            "messages": messages,
            "temperature": temperature,
        }
        if tools:
            kwargs["tools"] = tools
        if tool_choice is not None:
            kwargs["tool_choice"] = tool_choice
        if response_format is not None:
            kwargs["response_format"] = response_format
        if reasoning_effort is not None:
            kwargs["reasoning_effort"] = reasoning_effort

        resp = client.chat.completions.create(**kwargs)
        msg = resp.choices[0].message
        calls: list[ToolCall] = []
        for call in msg.tool_calls or []:
            raw_args = call.function.arguments or "{}"
            try:
                args = json.loads(raw_args, parse_constant=reject_constant, object_pairs_hook=unique_keys)
            except ValueError:
                # Small models often emit malformed JSON. Keep the call so eval grades it
                # as a wrong-argument failure instead of hiding it as provider_error.
                args = {"_invalid_json_arguments": raw_args}
            if not isinstance(args, dict):
                args = {"_invalid_json_arguments": raw_args}
            calls.append(ToolCall(name=call.function.name, args=args))
        return ModelResponse(text=msg.content, tool_calls=calls, raw=resp)
