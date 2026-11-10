from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

import chat
import ui_support
from providers.base import ModelResponse

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def ui(monkeypatch, tmp_path):
    monkeypatch.setenv("DEFAULT_PROVIDER", "demo (offline)")
    monkeypatch.setenv("ARTIFACT_VERSION", "ui-test")
    monkeypatch.setattr("env_loader.load_lab_env", lambda root: None)
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: io.BytesIO(b'{"models":[]}'))
    original_write = chat.write_transcript
    monkeypatch.setattr(chat, "write_transcript", lambda path, payload: original_write(tmp_path / path.name, payload))
    st.cache_data.clear()
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=15).run()
    assert not app.exception
    return app, tmp_path


def test_ui_dedupe_preserves_title_selection_and_logs_hashes(ui):
    app, folder = ui
    items = [{"title": "A", "url": "https://a.com"}, {"title": "a", "url": "https://b.com"}]
    app.chat_input[0].set_value("Bỏ trùng theo tiêu đề: " + json.dumps(items)).run()
    assert not app.exception
    saved = json.loads(next(folder.glob("*.json")).read_text(encoding="utf-8"))
    assert saved["version"] == "ui-test"
    assert len(saved["prompt_hash"]) == len(saved["tools_hash"]) == 64
    assert saved["turns"][0]["execution_mode"] == "scripted"
    event = saved["turns"][0]["tool_events"][0]
    assert event["args"]["key_by"] == "title"
    assert event["result"]["items"] == [items[0]]


def test_ui_can_dedupe_items_from_previous_turn(ui):
    app, _ = ui
    app.chat_input[0].set_value('Bỏ trùng: [{"title":"A"},{"title":"a"}]').run()
    app.chat_input[0].set_value("Bỏ trùng theo tiêu đề nhé").run()
    event = app.session_state["transcript"]["turns"][-1]["tool_events"][0]
    assert event["result"]["removed_count"] == 1


class BrokenProvider:
    default_model = "audit-model"
    def complete(self, *args, **kwargs):
        raise RuntimeError("offline test provider failure")


def test_ui_records_failed_provider_turn_without_fallback(ui, monkeypatch):
    app, folder = ui
    monkeypatch.setattr(ui_support, "make_provider", lambda name: BrokenProvider())
    app.selectbox[0].select("ollama").run()
    assert app.checkbox[0].value is False
    app.chat_input[0].set_value("What can you do?").run()
    assert not app.exception
    saved = json.loads(next(folder.glob("*.json")).read_text(encoding="utf-8"))
    assert saved["turns"][0]["status"] == "provider_error"
    assert "offline test provider failure" in saved["turns"][0]["error"]
    assert app.error


def test_ui_records_explicit_fallback_mode(ui, monkeypatch):
    app, _ = ui
    monkeypatch.setattr(ui_support, "make_provider", lambda name: BrokenProvider())
    app.selectbox[0].select("ollama").run()
    app.checkbox[0].check().run()
    app.chat_input[0].set_value("What can you do?").run()
    turn = app.session_state["transcript"]["turns"][0]
    assert turn["execution_mode"] == "scripted_fallback"
    assert turn["fallback_to_demo"]
    assert app.warning


def test_ui_provider_change_starts_new_session(ui, monkeypatch):
    app, _ = ui
    app.chat_input[0].set_value("What can you do?").run()
    previous_id = app.session_state["transcript"]["transcript_id"]
    class GoodProvider:
        default_model = "audit-model"
        def complete(self, *args, **kwargs):
            return ModelResponse(text="Stub provider response")
    monkeypatch.setattr(ui_support, "make_provider", lambda name: GoodProvider())
    app.selectbox[0].select("openai").run()
    assert not app.session_state["messages"]
    app.chat_input[0].set_value("What can you do?").run()
    saved = app.session_state["transcript"]
    assert saved["provider"] == "openai" and saved["model"] == "audit-model"
    assert saved["transcript_id"] != previous_id
    assert len(saved["turns"]) == 1
