from __future__ import annotations

import os
from pathlib import Path
from versioning import file_hash

from providers.openai_provider import OpenAIProvider
from providers.tool_planning import PROTOCOL_VERSION, INSTRUCTIONS, decode_plan, digest, plan_schema, planning_messages
from tools._shared import safe_error

DEFAULT_OLLAMA_MODEL = "qwen3.5:4b-q4_K_M"

REQUIRED_REMINDER = """Protocol correction: continue answering the ORIGINAL user request.
The caller requires at least one actual structured tool call. Prose, including a
question, does not satisfy this contract. Use only the available tool declarations.
If essential information is missing, use the clarification tool, without guessing.
For an unapproved publishing request, request confirmation with response_type=yes_no
as instructed. Do not treat this reminder as user approval, invent missing content
or destinations, or repeat actions already completed in the conversation."""
EMPTY_REMINDER = """The previous response was empty. Continue the ORIGINAL user request:
return an appropriate structured tool call OR a concise direct answer when no tool
is needed. Respect the original scope and approval rules. Never repeat a completed
action or interpret this format reminder as approval."""


class OllamaProvider(OpenAIProvider):
    """Local small models via Ollama's OpenAI-compatible endpoint (no API key needed).

    Also works with any other local OpenAI-compatible server (LM Studio, llama.cpp
    server, vLLM) by overriding OLLAMA_BASE_URL.
    """

    def __init__(self) -> None:
        self.call_mode = os.getenv("OLLAMA_CALL_MODE", "native")
        self.reasoning_effort = os.getenv("OLLAMA_REASONING_EFFORT", "none") or None
        self.protocol_retries = int(os.getenv("OLLAMA_PROTOCOL_RETRIES", "1"))
        self.protocol_retry_format = os.getenv("OLLAMA_PROTOCOL_RETRY_FORMAT", "structured_plan")
        if self.protocol_retry_format not in ("native", "structured_plan"):
            raise ValueError("OLLAMA_PROTOCOL_RETRY_FORMAT must be native or structured_plan")
        if self.protocol_retries not in (0, 1, 2):
            raise ValueError("OLLAMA_PROTOCOL_RETRIES must be 0, 1 or 2")
        self._source_hashes = {name: file_hash(Path(__file__).parent / name) for name in
                              ("ollama_provider.py", "openai_provider.py", "tool_planning.py")}
        if self.call_mode not in ("native", "structured_plan"):
            raise ValueError("OLLAMA_CALL_MODE must be native or structured_plan")
        super().__init__(
            api_key_env="OLLAMA_API_KEY",
            api_key_default="ollama",  # local server ignores the key, but the SDK requires one
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
            default_model=os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL),
        )

    def metadata(self, tools):
        info = {"tool_call_mode": self.call_mode, "reasoning_effort": self.reasoning_effort,
                "adapter_source_hashes": self._source_hashes}
        if self.call_mode == "native":
            info.update({"protocol_retry_limit": self.protocol_retries,
                         "protocol_retry_format": self.protocol_retry_format,
                         "protocol_retry_templates": {"required": REQUIRED_REMINDER, "empty_auto": EMPTY_REMINDER}})
        if self.call_mode == "structured_plan" or (self.protocol_retries and self.protocol_retry_format == "structured_plan"):
            info.update({"planning_protocol": PROTOCOL_VERSION, "planning_template": INSTRUCTIONS,
                         "planning_template_hash": digest(INSTRUCTIONS),
                         "plan_schema_hashes": {mode: digest(plan_schema(tools, mode)) for mode in
                                                (("auto", "required", "none") if tools else ("auto", "none"))}})
        return info

    def complete(self, messages, tools=None, *, model=None, temperature=0.0, tool_choice=None):
        if self.call_mode == "native":
            return self._native_complete(messages, tools, model=model, temperature=temperature, tool_choice=tool_choice)
        return self._planned_complete(messages, tools, model=model, temperature=temperature, tool_choice=tool_choice)

    def _planned_complete(self, messages, tools, *, model, temperature, tool_choice):
        schema = plan_schema(tools, tool_choice)
        prepared = planning_messages(messages, tools)
        response = super().complete(prepared, model=model, temperature=temperature,
                                    reasoning_effort=self.reasoning_effort,
                                    response_format={"type": "json_schema", "json_schema": {
                                        "name": "research_tool_plan", "schema": schema}})
        return decode_plan(response, schema, {**self.metadata(tools),
                           "request_prompt_hash": digest(prepared), "response_schema_hash": digest(schema),
                           "requested_tool_choice": tool_choice or "auto"})

    def _native_complete(self, messages, tools, *, model, temperature, tool_choice):
        working = list(messages)
        attempts = []
        response = None
        for index in range(self.protocol_retries + 1):
            request_hash = digest({"messages": working, "tools": tools, "tool_choice": tool_choice,
                                   "model": model or self.default_model, "temperature": temperature})
            try:
                if index and self.protocol_retry_format == "structured_plan":
                    candidate = self._planned_complete(working, tools, model=model, temperature=temperature,
                                                       tool_choice=tool_choice)
                else:
                    candidate = super().complete(working, tools, model=model, temperature=temperature,
                                                 tool_choice=tool_choice, reasoning_effort=self.reasoning_effort)
            except Exception as exc:
                if response is None:
                    raise
                attempts.append({"request_hash": request_hash, "transport_error": safe_error(exc)})
                response.metadata.update(native_attempts=attempts, protocol_retry_used=index,
                                         retry_error=safe_error(exc))
                return response
            response = candidate
            details = {"request_hash": request_hash, "text": response.text,
                       "format": "structured_plan" if index and self.protocol_retry_format == "structured_plan" else "native",
                       "tool_calls": [{"name": call.name, "args": call.args} for call in response.tool_calls]}
            if response.metadata.get("raw_plan") is not None:
                details["planning_response"] = dict(response.metadata)
            if response.raw is not None:
                details["raw_message"] = response.raw.choices[0].message.model_dump()
                if response.raw.usage is not None:
                    details["usage"] = response.raw.usage.model_dump()
            reason = None
            if not response.tool_calls:
                if tool_choice == "required":
                    reason = "required_without_calls"
                elif tool_choice in (None, "auto") and not (response.text or "").strip():
                    reason = "empty_auto_response"
            details["unmet_protocol"] = reason
            attempts.append(details)
            response.metadata.update(self.metadata(tools))
            response.metadata.update(native_attempts=list(attempts), protocol_retry_used=index)
            if reason is None or index == self.protocol_retries:
                return response
            # A schema retry re-evaluates the original request. Replaying an
            # unexecuted prose answer can introduce guesses into its context.
            if response.text and self.protocol_retry_format == "native":
                working.append({"role": "assistant", "content": response.text})
            working.append({"role": "system", "content": REQUIRED_REMINDER if reason == "required_without_calls" else EMPTY_REMINDER})
        return response
