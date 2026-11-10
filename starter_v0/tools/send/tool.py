from __future__ import annotations

import os
from typing import Any

import requests

from tools._shared import TIMEOUT, err


def send_telegram(text: str = "", confirmed: bool = False) -> dict[str, Any]:
    if not isinstance(confirmed, bool):
        return err("send_telegram", TypeError("confirmed must be a boolean"))
    if not confirmed:
        return {
            "tool": "send_telegram",
            "status": "needs_confirmation",
            "message": "Only send after the user explicitly confirms.",
        }
    try:
        if not isinstance(text, str) or not text.strip():
            raise ValueError("text must be a non-empty string")
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        chat_id = os.getenv("TELEGRAM_CHAT_ID")
        if not token or not chat_id:
            raise RuntimeError("Missing TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID env var")
        response = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("ok") is not True:
            raise RuntimeError(f"Telegram rejected the message: {payload.get('description', 'unknown error')}")
        return {"tool": "send_telegram", "status": "sent"}
    except Exception as exc:
        return err("send_telegram", exc)

