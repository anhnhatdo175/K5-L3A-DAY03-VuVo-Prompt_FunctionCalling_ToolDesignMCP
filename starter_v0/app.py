from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib import request as urlrequest

import streamlit as st

from chat import now_iso, run_model_tool_loop, safe_slug, trim_history, write_transcript
from env_loader import load_lab_env
from providers import make_provider
from providers.base import ModelResponse, ToolCall

from tools import load_tool_declarations, to_openai_tools
from versioning import build_artifact_version

ROOT = Path(__file__).parent
ARTIFACTS = ROOT / "artifacts"
TRANSCRIPTS = ROOT / "transcripts"
load_lab_env(ROOT)

PROVIDERS = ["demo (offline)", "openrouter", "openai", "anthropic", "gemini", "ollama"]

st.set_page_config(page_title="Research Agent", page_icon="🔎", layout="wide")

# Provider
class DemoProvider:
    default_model = "demo-scripted"

    def __init__(self, live_provider=None, *, live_name: str | None = None) -> None:
        self.live_provider = live_provider
        self.live_name = live_name
        self.fallback_reason: str | None = None
        if live_provider is not None:
            self.default_model = getattr(live_provider, "default_model", self.default_model)

    def complete(self, messages, tools=None, *, model=None, temperature=0.0, tool_choice=None) -> ModelResponse:
        if self.live_provider is not None:
            try:
                return self.live_provider.complete(
                    messages,
                    tools,
                    model=model,
                    temperature=temperature,
                    tool_choice=tool_choice,
                )
            except Exception as exc:  # graceful degradation for demos
                self.fallback_reason = f"{type(exc).__name__}: {exc}"
        return self._scripted(messages)

    def _scripted(self, messages) -> ModelResponse:
        latest = messages[-1]["content"]
        folded = latest.casefold()

        if "TOOL_RESULTS_JSON" in latest:
            return ModelResponse(
                text="Mình đã chạy tool xong. Kết quả chi tiết nằm trong phần **Tool calls** ở trên; "
                     "đây là chế độ demo offline nên chưa có câu trả lời do model viết.",
                tool_calls=[],
            )

        url = re.search(r"https?://\S+", latest)
        if url:
            return ModelResponse(tool_calls=[ToolCall("fetch", {"url": url.group(0).rstrip(".,)")})])

        if "telegram" in folded or "đăng" in folded:
            return ModelResponse(tool_calls=[ToolCall("clarify", {
                "question": "Bạn xác nhận muốn đăng nội dung này lên Telegram chứ?",
                "response_type": "yes_no",
            })])

        if "trùng" in folded or "dedupe" in folded:
            return ModelResponse(tool_calls=[ToolCall("deduplicate", {"items": [], "key_by": "url"})])

        if "paper" in folded or "arxiv" in folded:
            return ModelResponse(tool_calls=[ToolCall("papers", {"query": latest[:100], "max_results": 3})])

        if "chính sách" in folded or "policy" in folded:
            return ModelResponse(tool_calls=[ToolCall("policy", {"query": latest[:100]})])

        if "tweet" in folded or "twitter" in folded:
            return ModelResponse(tool_calls=[ToolCall("social_search", {"query": latest[:100], "search_type": "Latest"})])

        if "ai" in folded:
            return ModelResponse(tool_calls=[ToolCall("lookup", {"query": "AI", "topic": "news", "timeframe": "day"})])

        return ModelResponse(text="Mình là research agent: hãy hỏi về tin tức, tweet, paper, policy hoặc gửi lên Telegram.")


def build_provider(name: str, *, allow_fallback: bool = True):
    if name.startswith("demo"):
        return DemoProvider(), "demo-scripted"
    provider = make_provider(name)
    default_model = getattr(provider, "default_model", None)
    if allow_fallback:
        return DemoProvider(provider, live_name=name), default_model
    return provider, default_model


# Ollama discovery: the local server is the default provider whenever it is up.
def _ollama_root() -> str:
    base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1").rstrip("/")
    return base[: -len("/v1")] if base.endswith("/v1") else base


@st.cache_data(ttl=30, show_spinner=False)
def list_ollama_models() -> list[str]:
    """Models installed in the local Ollama server (empty list when it is down)."""
    try:
        with urlrequest.urlopen(f"{_ollama_root()}/api/tags", timeout=1.0) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        return []
    names = [item.get("name") for item in payload.get("models", []) if item.get("name")]
    return names


def default_provider_name(ollama_models: list[str]) -> str:
    preferred = os.getenv("DEFAULT_PROVIDER", "").strip()
    if preferred.startswith("demo"):
        return "demo (offline)"
    if preferred in PROVIDERS:
        return preferred
    return "ollama" if ollama_models else "demo (offline)"


def resolve_model(provider_name: str, default_model: str | None, override: str | None) -> str | None:
    """Pick a model the provider can actually serve.

    For Ollama, prefers the configured/default model but falls back to the first
    installed tag when that model has not been pulled.
    """
    if override:
        return override
    if provider_name != "ollama":
        return None
    models = list_ollama_models()
    configured = default_model or os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
    if configured in models:
        return configured
    # Same model family (e.g. qwen2.5) before an unrelated model.
    family = configured.split(":", 1)[0]
    same_family = [name for name in models if name.split(":", 1)[0] == family]
    if same_family:
        return same_family[0]
    return models[0] if models else None


# Session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "transcript" not in st.session_state:
    st.session_state.transcript = None


def new_conversation() -> None:
    st.session_state.messages = []
    st.session_state.transcript = None


# Sidebar
with st.sidebar:
    st.header("⚙️ Cấu hình")
    ollama_models = list_ollama_models()
    provider_name = st.selectbox("Provider", PROVIDERS, index=PROVIDERS.index(default_provider_name(ollama_models)))
    if ollama_models:
        st.caption(
            f"🟢 Ollama sẵn sàng · {len(ollama_models)} model: "
            + " · ".join(f"`{name}`" for name in ollama_models[:4])
        )
    else:
        st.caption("")
    demo_fallback = st.checkbox(
        "Fallback sang demo scripted khi provider lỗi",
        value=True,
        help=(
            "Nếu provider live không gọi được (thiếu API key, chưa pull model, "
            "mất mạng…), agent trả lời bằng kịch bản offline thay vì báo lỗi."
        ),
    )
    model_override = st.text_input(
        "Model (để trống = mặc định provider)",
        value="",
        placeholder="openai/gpt-4o-mini · qwen2.5:7b · demo-scripted",
    )
    version_label = st.text_input("Version label", value="v3-ui")
    prompt_path = st.text_input("System prompt", value=str(ARTIFACTS / "system_prompt.md"))
    tools_path = st.text_input("Tool declarations", value=str(ARTIFACTS / "tools.yaml"))
    history_window = st.slider("History window (cặp lượt)", 1, 10, 5)
    max_rounds = st.slider("Max tool rounds", 1, 6, 4)

    if st.button("🆕 Cuộc trò chuyện mới", use_container_width=True):
        new_conversation()
        st.rerun()

    st.divider()
    st.caption("Agent có thể:")
    st.caption(
        "• Tin tức web · tweet theo tài khoản/chủ đề\n"
        "• Đọc URL · paper arXiv\n"
        "• Policy nội bộ · bỏ trùng kết quả\n"
        "• Format digest · gửi Telegram sau xác nhận"
    )
    with st.expander("Tool đang bật"):
        try:
            declarations = load_tool_declarations(Path(tools_path))
            for item in declarations:
                st.markdown(f"- `{item['name']}` — {item.get('description', '').split('.')[0][:90]}…")
        except Exception as exc:  # keep the UI alive with a bad path
            st.error(f"Không đọc được tools.yaml: {exc}")

# Header
st.title("🔎 Research Agent")
st.caption(
    "Tìm tin theo chủ đề/tài khoản, đọc URL, tìm paper, tra policy nội bộ, "
    "bỏ trùng kết quả và gửi Telegram sau khi bạn xác nhận."
)

selected_model = model_override.strip() or None
try:
    prompt_text = Path(prompt_path).read_text(encoding="utf-8")
    declarations = load_tool_declarations(Path(tools_path))
    openai_tools = to_openai_tools(declarations)
    artifact_version = build_artifact_version(version_label, Path(prompt_path), Path(tools_path))
    st.caption(
        f"artifact_version `{artifact_version.artifact_version}` · "
        f"{len(declarations)} tools · provider `{provider_name}`"
    )
except Exception as exc:
    st.error(f"Không nạp được artifact: {exc}")
    st.stop()

# Render history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message.get("content") or "")
        if message.get("fallback_to_demo"):
            st.warning(
                "Câu trả lời này do demo scripted tạo ra vì provider live lỗi: "
                f"`{message['fallback_to_demo']}`"
            )
        events = message.get("tool_events") or []
        if events:
            with st.expander(f"🔧 {len(events)} tool call(s)"):
                for event in events:
                    st.markdown(f"**{event['name']}**")
                    st.json({"args": event.get("args", {})})
                    result = event.get("result", {})
                    preview = json.dumps(result, ensure_ascii=False, default=str)
                    if len(preview) > 2500:
                        preview = preview[:2500] + "… <truncated>"
                    st.code(preview, language="json")

# Chat input
prompt = st.chat_input("Hỏi gì đó: tin AI hôm nay, tweet của Sam Altman, tóm tắt link, paper, policy…")
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Agent đang chạy…"):
            try:
                provider, default_model = build_provider(provider_name, allow_fallback=demo_fallback)
                chosen_model = resolve_model(provider_name, default_model, selected_model)
                history = [
                    {"role": item["role"], "content": item.get("content") or ""}
                    for item in st.session_state.messages
                    if item["role"] in {"user", "assistant"} and item.get("content")
                ]
                messages = [
                    {"role": "system", "content": prompt_text},
                    *trim_history(history[:-1], history_window),
                    {"role": "user", "content": prompt},
                ]

                result = run_model_tool_loop(
                    provider=provider,
                    messages=messages,
                    tools=openai_tools,
                    model=chosen_model,
                    max_tool_rounds=max_rounds,
                )

                events: list[dict[str, Any]] = []
                for rnd in result["rounds"]:
                    calls = rnd.get("tool_calls") or []
                    tool_results = rnd.get("tool_results") or []
                    for index, call in enumerate(calls):
                        events.append({
                            "name": call["name"],
                            "args": call.get("args", {}),
                            "result": tool_results[index]["result"] if index < len(tool_results) else {},
                        })

                assistant_text = result["assistant_text"] or "(không có nội dung trả về)"
                fallback_reason = (
                    provider.fallback_reason
                    if isinstance(provider, DemoProvider) and provider.fallback_reason
                    else None
                )
                if fallback_reason:
                    st.warning(
                        f"Provider `{provider_name}` không gọi được nên câu trả lời này "
                        f"do demo scripted tạo ra.\n\n`{fallback_reason}`"
                    )
                st.markdown(assistant_text)
                if events:
                    with st.expander(f"🔧 {len(events)} tool call(s)"):
                        for event in events:
                            st.markdown(f"**{event['name']}**")
                            st.json({"args": event["args"]})
                            preview = json.dumps(event["result"], ensure_ascii=False, default=str)
                            st.code(preview[:2500] + ("… <truncated>" if len(preview) > 2500 else ""), language="json")

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": assistant_text,
                    "tool_events": events,
                    "fallback_to_demo": fallback_reason,
                })

                # Persist the same transcript format as chat.py.
                if st.session_state.transcript is None:
                    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S%f")
                    transcript_id = "_".join([
                        safe_slug(version_label),
                        safe_slug(provider_name),
                        timestamp,
                    ])
                    st.session_state.transcript = {
                        "transcript_id": transcript_id,
                        "source": "streamlit",
                        "provider": provider_name,
                        "model": chosen_model or default_model,
                        "system_prompt": prompt_path,
                        "tools": tools_path,
                        "created_at": now_iso(),
                        "turns": [],
                    }
                transcript = st.session_state.transcript
                turn_record = {
                    "turn_index": len(transcript["turns"]) + 1,
                    "started_at": now_iso(),
                    "ended_at": now_iso(),
                    "user": prompt,
                    "status": result["status"],
                    "assistant_text": assistant_text,
                    "rounds": result["rounds"],
                }
                if fallback_reason:
                    turn_record["fallback_to_demo"] = fallback_reason
                transcript["turns"].append(turn_record)
                transcript_path = TRANSCRIPTS / f"{transcript['transcript_id']}.transcript.json"
                write_transcript(transcript_path, transcript)
                st.caption(f"Transcript: `{transcript_path.relative_to(ROOT)}`")

            except Exception as exc:
                error_text = f"Không gọi được provider: `{type(exc).__name__}: {exc}`"
                st.error(error_text)
                st.info(
                    "Kiểm tra `.env` (copy từ `.env.example`) và chạy "
                    "`python scripts/preflight_provider.py --provider openrouter`. "
                    "Hoặc chọn provider **demo (offline)** hay bật "
                    "**Fallback sang demo scripted** để thử UI không cần key."
                )
                st.session_state.messages.append({"role": "assistant", "content": error_text})

    st.rerun()
