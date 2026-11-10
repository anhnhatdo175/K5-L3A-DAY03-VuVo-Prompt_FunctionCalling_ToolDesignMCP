from __future__ import annotations

import json
import os
from pathlib import Path
from urllib import request as urlrequest

import streamlit as st

from chat import now_iso, run_model_tool_loop, trim_history, write_transcript
from env_loader import load_lab_env
from tools import load_tool_declarations, to_openai_tools
from ui_support import build_provider, conversation_history, new_transcript
from versioning import build_artifact_version
from tools._shared import safe_error
from providers.ollama_provider import DEFAULT_OLLAMA_MODEL

ROOT = Path(__file__).parent
ARTIFACTS = ROOT / "artifacts"
TRANSCRIPTS = ROOT / "transcripts"
load_lab_env(ROOT)
PROVIDERS = ["demo (offline)", "ollama", "openrouter", "openai", "anthropic", "gemini"]
st.set_page_config(page_title="Research Agent", page_icon="🔎", layout="wide")


@st.cache_data(ttl=30, show_spinner=False)
def list_ollama_models(base_url: str) -> list[str]:
    root = base_url.rstrip("/")
    if root.endswith("/v1"):
        root = root[:-3]
    try:
        with urlrequest.urlopen(f"{root}/api/tags", timeout=1.0) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return [item["name"] for item in payload.get("models", [])
                if isinstance(item, dict) and isinstance(item.get("name"), str)]
    except Exception:
        return []


if "messages" not in st.session_state:
    st.session_state.messages = []
if "transcript" not in st.session_state:
    st.session_state.transcript = None

with st.sidebar:
    st.header("Cấu hình")
    preferred = os.getenv("DEFAULT_PROVIDER", "").strip()
    installed = [] if preferred.startswith("demo") else list_ollama_models(
        os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"))
    default = preferred if preferred in PROVIDERS else ("ollama" if installed else PROVIDERS[0])
    provider_name = st.selectbox("Provider", PROVIDERS, index=PROVIDERS.index(default))
    model_override = st.text_input("Model (để trống = mặc định provider)", value="")
    if installed:
        st.caption("Model Ollama đã cài: " + ", ".join(installed))
    fallback = st.checkbox("Dùng demo scripted nếu provider lỗi", value=False,
                          help="Bật tùy chọn này tạo bằng chứng demo; không tính là model live thành công.")
    version_label = st.text_input("Version label", value=os.getenv("ARTIFACT_VERSION", "v13-scope-check"))
    with st.expander("Cấu hình nâng cao"):
        prompt_path = Path(st.text_input("System prompt", value=str(ARTIFACTS / "system_prompt.md")))
        tools_path = Path(st.text_input("Tool declarations", value=str(ARTIFACTS / "tools.yaml")))
        history_window = st.slider("History window (cặp lượt)", 1, 10, 5)
        max_rounds = st.slider("Max tool rounds", 1, 6, 4)
    reset = st.button("Cuộc trò chuyện mới", use_container_width=True)

st.title("🔎 Research Agent")
st.caption("Tìm nguồn, đọc bài, tra policy, bỏ trùng và tổng hợp kết quả nghiên cứu.")
if provider_name.startswith("demo"):
    st.info("Demo offline: bỏ trùng và tra policy nội bộ; không dùng model hoặc gọi API bên ngoài.")

try:
    prompt_text = prompt_path.read_text(encoding="utf-8")
    declarations = load_tool_declarations(tools_path)
    openai_tools = to_openai_tools(declarations)
    artifact = build_artifact_version(version_label, prompt_path, tools_path)
except Exception as exc:
    st.error(f"Không nạp được cấu hình: {exc}")
    st.stop()

configured_model = model_override.strip() or None
if provider_name == "ollama" and not configured_model:
    default_model = os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)
    configured_model = default_model if default_model in installed or not installed else next(
        (name for name in installed if name.split(":")[0] == default_model.split(":")[0]), installed[0])

config = (provider_name, configured_model, artifact.artifact_version, str(prompt_path), str(tools_path),
          fallback, history_window, max_rounds)
if reset or st.session_state.get("conversation_config") != config:
    st.session_state.messages = []
    st.session_state.transcript = None
st.session_state.conversation_config = config
st.caption(f"{len(declarations)} tools · {artifact.artifact_version}")
with st.sidebar.expander("Tool đang bật"):
    for item in declarations:
        st.write(item["name"])


def render_message(message):
    with st.chat_message(message["role"]):
        if message.get("status") == "provider_error":
            st.error(message["content"])
        else:
            st.markdown(message.get("content") or "")
        if message.get("fallback_to_demo"):
            st.warning("Provider lỗi; phần trả lời này có dùng demo scripted: " + message["fallback_to_demo"])
        events = message.get("tool_events") or []
        if events:
            with st.expander(f"{len(events)} tool call(s)"):
                for event in events:
                    st.write(event["tool"])
                    st.json({"args": event["args"], "result": event["result"]})


for message in st.session_state.messages:
    render_message(message)

user_text = st.chat_input("Hỏi về nghiên cứu hoặc gửi danh sách JSON để bỏ trùng…")
if user_text:
    started_at = now_iso()
    history = conversation_history(st.session_state.messages)
    user_message = {"role": "user", "content": user_text}
    st.session_state.messages.append(user_message)
    render_message(user_message)
    selected_model = configured_model
    try:
        provider, default_model = build_provider(provider_name, allow_fallback=fallback)
        selected_model = selected_model or default_model
        with st.spinner("Đang xử lý…"):
            result = run_model_tool_loop(
                provider=provider,
                messages=[{"role": "system", "content": prompt_text},
                          *trim_history(history, history_window), {"role": "user", "content": user_text}],
                tools=openai_tools, model=selected_model, max_tool_rounds=max_rounds)
    except Exception as exc:
        error = safe_error(exc)
        result = {"status": "provider_error", "error": error,
                  "assistant_text": "Không gọi được provider: " + error, "rounds": [], "tool_events": []}

    reasons = [rnd["fallback_to_demo"] for rnd in result["rounds"] if rnd.get("fallback_to_demo")]
    modes = sorted({rnd.get("execution_mode", "live") for rnd in result["rounds"]})
    mode = modes[0] if len(modes) == 1 else ("mixed" if modes else "provider_error")
    assistant_message = {"role": "assistant", "content": result["assistant_text"],
                         "status": result["status"], "tool_events": result["tool_events"],
                         "fallback_to_demo": "; ".join(dict.fromkeys(reasons)) or None}
    st.session_state.messages.append(assistant_message)
    if st.session_state.transcript is None:
        st.session_state.transcript = new_transcript(
            artifact, provider_name, selected_model, prompt_path, tools_path, history_window, max_rounds)
    transcript = st.session_state.transcript
    transcript["turns"].append({
        "turn_index": len(transcript["turns"]) + 1, "started_at": started_at, "ended_at": now_iso(),
        "user": user_text, **result, "execution_mode": mode,
        **({"fallback_to_demo": assistant_message["fallback_to_demo"]} if reasons else {})})
    try:
        write_transcript(TRANSCRIPTS / f"{transcript['transcript_id']}.transcript.json", transcript)
    except OSError as exc:
        st.error(f"Không lưu được transcript: {exc}")
        st.stop()
    st.rerun()

if st.session_state.transcript:
    st.download_button("Tải transcript JSON",
                       json.dumps(st.session_state.transcript, ensure_ascii=False, indent=2),
                       file_name=st.session_state.transcript["transcript_id"] + ".transcript.json",
                       mime="application/json")
