from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from providers.base import Provider, ToolCall
from tools import TOOL_FUNCTIONS
from tool_runtime import execute_tool_call


@dataclass
class AgentRun:
    text: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_results: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class ResearchAgent:
    def __init__(
        self,
        provider: Provider,
        *,
        system_prompt: str,
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        dry_run_actions: bool = False,
    ) -> None:
        self.provider = provider
        self.system_prompt = system_prompt
        self.tools = tools or []
        self.model = model
        self.dry_run_actions = dry_run_actions

    def run(self, user_messages: list[dict[str, str]], *, tool_choice: Any | None = None) -> AgentRun:
        messages = [{"role": "system", "content": self.system_prompt}, *user_messages]
        response = self.provider.complete(
            messages,
            self.tools,
            model=self.model,
            temperature=0.0,
            tool_choice=tool_choice,
        )
        results: list[dict[str, Any]] = []
        for call in response.tool_calls:
            func = TOOL_FUNCTIONS.get(call.name)
            if not func:
                results.append({"tool": call.name, "error": "unknown_tool"})
                continue
            results.append(execute_tool_call(call, self.tools or None, dry_run_actions=self.dry_run_actions))
        return AgentRun(text=response.text, tool_calls=response.tool_calls, tool_results=results, metadata=response.metadata)
