"""Offline demo routing and session metadata, independent of Streamlit."""
from __future__ import annotations

import json
import re
from datetime import datetime

from chat import now_iso, safe_slug
from providers import make_provider
from providers.base import ModelResponse, ToolCall
from tools._shared import fold_text, safe_error
from versioning import artifact_version_dict


def item_list_span(text):
    for match in re.finditer(r"\[", text):
        try:
            value, length = json.JSONDecoder().raw_decode(text[match.start():])
        except ValueError:
            continue
        if isinstance(value, list):
            return value, match.start(), match.start() + length
    return None


def find_items(text):
    found = item_list_span(text)
    return found[0] if found is not None else None


def instruction_text(text):
    found = item_list_span(text)
    if found is not None:
        text = text[:found[1]] + " " + text[found[2]:]
    return fold_text(text).replace("đ", "d")


def requests_dedupe(text):
    return bool(re.search(r"\b(?:dedup(?:e|licate|lication)?|remove duplicates)\b|"
                          r"\b(?:bo|loai|loai bo|xoa|loc) (?:cac )?(?:muc )?trung\b", text))


class DemoProvider:
    default_model = "demo-scripted"

    def __init__(self, live_provider=None):
        self.live_provider = live_provider
        self.fallback_reason = None
        self.last_execution_mode = "scripted"
        if live_provider:
            self.default_model = live_provider.default_model

    def complete(self, messages, tools=None, *, model=None, temperature=0.0, tool_choice=None):
        self.fallback_reason = None
        if self.live_provider:
            try:
                response = self.live_provider.complete(messages, tools, model=model,
                                                       temperature=temperature, tool_choice=tool_choice)
                self.last_execution_mode = "live"
                return response
            except Exception as exc:
                self.fallback_reason = safe_error(exc)
        self.last_execution_mode = "scripted_fallback" if self.live_provider else "scripted"
        return self._scripted(messages)

    def _scripted(self, messages):
        latest = messages[-1]["content"]
        if latest.startswith("TOOL_RESULTS_JSON:"):
            events, _ = json.JSONDecoder().raw_decode(latest.split(":", 1)[1].lstrip())
            outputs = []
            for event in events:
                result = event["result"]
                if result.get("error"):
                    outputs.append(f"Không thực hiện được: {result['message']}")
                elif event["tool"] == "deduplicate":
                    outputs.append(f"Đã loại {result['removed_count']} mục trùng; còn {len(result['items'])} mục.\n\n"
                                   + json.dumps(result["items"], ensure_ascii=False, indent=2))
                elif event["tool"] == "format":
                    outputs.append(result["markdown"])
                elif event["tool"] == "policy":
                    outputs.extend(f"**{hit['title']} — {hit['section']}**\n\n{hit['facts']}\n\n"
                                   f"Nguồn: {hit['source']} ({hit['effective_date']})"
                                   for hit in result["results"])
                    if not result["results"]:
                        outputs.append("Không tìm thấy chính sách phù hợp trong bộ tài liệu nội bộ.")
            return ModelResponse(text="\n\n".join(outputs) or "Không có kết quả.")

        folded = instruction_text(latest)
        user_messages = [m["content"] for m in messages if m["role"] == "user"
                         and not m["content"].startswith("TOOL_RESULTS_JSON:")]
        dedupe_intent = requests_dedupe(folded)
        dedupe_context = any(requests_dedupe(instruction_text(text)) for text in user_messages)
        dedupe_followup = dedupe_context and (find_items(latest) is not None or
                         any(word in folded for word in ("theo tieu de", "by title", "theo url", "by url")))
        if dedupe_intent or dedupe_followup:
            items = next((found for text in reversed(user_messages) if (found := find_items(text)) is not None), None)
            if items is None:
                return ModelResponse(tool_calls=[ToolCall("clarify", {
                    "question": "Bạn gửi danh sách kết quả dạng JSON cần bỏ trùng nhé.", "response_type": "text"})])
            key_by = "url"
            for text in reversed(user_messages):
                instruction = instruction_text(text)
                if "tieu de" in instruction or re.search(r"\btitles?\b", instruction):
                    key_by = "title"
                    break
                if re.search(r"\burl\b", instruction):
                    break
            return ModelResponse(tool_calls=[ToolCall("deduplicate", {"items": items, "key_by": key_by})])
        if any(phrase in folded for phrase in ("ban la ai", "lam duoc", "what can you do", "who are you")):
            return ModelResponse(text="Mình hỗ trợ nghiên cứu bằng các tool. Demo offline có thể bỏ trùng và tra policy nội bộ. Chọn provider thật để tìm web, tweet hoặc paper.")
        if "policy" in folded or "chinh sach" in folded:
            return ModelResponse(tool_calls=[ToolCall("policy", {"query": latest})])
        if "telegram" in folded or "dang" in folded:
            return ModelResponse(text="Demo offline không gửi Telegram. Chọn provider thật, duyệt nội dung và đích gửi trước khi xác nhận.")
        if re.search(r"https?://", latest) or any(word in folded for word in ("tweet", "twitter", "paper", "arxiv", "tin tuc", "tin ai", "news")):
            return ModelResponse(text="Yêu cầu này cần nguồn bên ngoài. Chọn provider thật và cấu hình API tương ứng; demo offline không gọi mạng.")
        return ModelResponse(text="Demo offline sẵn sàng. Bạn có thể gửi danh sách JSON để bỏ trùng hoặc hỏi chính sách nội bộ.")


def build_provider(name, *, allow_fallback=False):
    if name.startswith("demo"):
        return DemoProvider(), "demo-scripted"
    provider = make_provider(name)
    return (DemoProvider(provider) if allow_fallback else provider), provider.default_model


def new_transcript(version, provider, model, prompt_path, tools_path, history_window, max_rounds):
    return {
        "transcript_id": "_".join([safe_slug(version.version), safe_slug(provider),
                                     datetime.now().strftime("%Y%m%dT%H%M%S%f")]),
        **artifact_version_dict(version), "source": "streamlit", "provider": provider,
        "model": model, "system_prompt": str(prompt_path), "tools": str(tools_path),
        "history_window": history_window, "max_tool_rounds": max_rounds,
        "created_at": now_iso(), "turns": [],
    }


def conversation_history(messages):
    history = []
    pending_user = None
    for message in messages:
        if message["role"] == "user":
            pending_user = {"role": "user", "content": message.get("content") or ""}
            continue
        if message.get("status") == "provider_error" and not message.get("tool_events"):
            pending_user = None
            continue
        content = message.get("content") or ""
        if message.get("tool_events"):
            content += "\n\nPrior tool results:\n" + json.dumps(message["tool_events"], ensure_ascii=False)
        if message["role"] == "assistant" and pending_user is not None:
            history.extend([pending_user, {"role": "assistant", "content": content}])
            pending_user = None
    return history
