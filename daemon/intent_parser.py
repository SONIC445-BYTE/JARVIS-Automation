from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict


@dataclass
class Intent:
    adapter: str
    action: str
    target: str = ""
    message: str = ""
    destructive: bool = False
    meta: Dict[str, str] = field(default_factory=dict)


_RISK_TERMS = {"delete", "format", "erase", "wipe", "run script", "shutdown"}


def parse_command(text: str) -> Intent:
    raw = text.strip()
    lower = raw.lower()

    destructive = any(term in lower for term in _RISK_TERMS)
    if destructive:
        return Intent(
            adapter="system",
            action="dangerous_command",
            target="system",
            message=raw,
            destructive=True,
        )

    if "whatsapp" in lower:
        if "read" in lower or "unread" in lower:
            return Intent(adapter="whatsapp_desktop", action="read_unread", target="whatsapp")
        return _parse_send(raw, lower, default_adapter="whatsapp_desktop")

    if "telegram" in lower:
        if "read" in lower or "unread" in lower:
            return Intent(adapter="telegram_desktop", action="read_unread", target="telegram")
        return _parse_send(raw, lower, default_adapter="telegram_desktop")

    if "gmail" in lower:
        if "read" in lower or "unread" in lower:
            return Intent(adapter="gmail_browser", action="read_unread", target="gmail")
        return _parse_send(raw, lower, default_adapter="gmail_browser")

    if "chrome" in lower or "browser" in lower:
        return Intent(adapter="browser", action="open_app", target="browser")

    if "notepad" in lower or "text editor" in lower or "editor" in lower:
        if "open" in lower:
            return Intent(adapter="text_editor", action="open_app", target="text_editor")
        return _parse_send(raw, lower, default_adapter="text_editor")

    return Intent(adapter="text_editor", action="send_message", target="notes", message=raw)


def _parse_send(raw: str, lower: str, default_adapter: str) -> Intent:
    if "send" not in lower:
        return Intent(adapter=default_adapter, action="open_app", target=default_adapter)

    target = "unknown"
    message = raw
    marker = " to "
    if marker in lower:
        split_at = lower.rfind(marker)
        target = raw[split_at + len(marker) :].strip()
        message = raw[:split_at].strip()
        message = message[4:].strip() if message.lower().startswith("send ") else message

    return Intent(
        adapter=default_adapter,
        action="send_message",
        target=target,
        message=message,
    )
