from __future__ import annotations

from typing import Dict

from .browser_adapter import BrowserAdapter
from .gmail_browser_adapter import GmailBrowserAdapter
from .telegram_desktop_adapter import TelegramDesktopAdapter
from .text_editor_adapter import TextEditorAdapter
from .whatsapp_desktop_adapter import WhatsappDesktopAdapter


def create_default_adapters(logger, dry_run: bool) -> Dict[str, object]:
    return {
        "browser": BrowserAdapter(logger=logger, dry_run=dry_run),
        "text_editor": TextEditorAdapter(logger=logger, dry_run=dry_run),
        "whatsapp_desktop": WhatsappDesktopAdapter(logger=logger, dry_run=dry_run),
        "telegram_desktop": TelegramDesktopAdapter(logger=logger, dry_run=dry_run),
        "gmail_browser": GmailBrowserAdapter(logger=logger, dry_run=dry_run),
    }
