from __future__ import annotations

from typing import Dict

from .amazon_adapter import AmazonAdapter
from .browser_adapter import BrowserAdapter
from .calculator_adapter import CalculatorAdapter
from .explorer_adapter import ExplorerAdapter
from .gmail_browser_adapter import GmailBrowserAdapter
from .google_adapter import GoogleAdapter
from .spotify_adapter import SpotifyAdapter
from .telegram_desktop_adapter import TelegramDesktopAdapter
from .telegram_web_adapter import TelegramWebAdapter
from .text_editor_adapter import TextEditorAdapter
from .twitter_adapter import TwitterAdapter
from .whatsapp_desktop_adapter import WhatsappDesktopAdapter
from .whatsapp_web_adapter import WhatsAppWebAdapter
from .youtube_adapter import YouTubeAdapter


def create_default_adapters(logger, dry_run: bool) -> Dict[str, object]:
    return {
        "browser": BrowserAdapter(logger=logger, dry_run=dry_run),
        "text_editor": TextEditorAdapter(logger=logger, dry_run=dry_run),
        "whatsapp_desktop": WhatsappDesktopAdapter(logger=logger, dry_run=dry_run),
        "telegram_desktop": TelegramDesktopAdapter(logger=logger, dry_run=dry_run),
        "gmail_browser": GmailBrowserAdapter(logger=logger, dry_run=dry_run),
        # Phase 2d: ported from AgentCore/platform_adapters' audit-confirmed
        # real/near-real (class a/b) folders. See docs/adapter_audit.md.
        "amazon": AmazonAdapter(logger=logger, dry_run=dry_run),
        "google": GoogleAdapter(logger=logger, dry_run=dry_run),
        "calculator": CalculatorAdapter(logger=logger, dry_run=dry_run),
        "explorer": ExplorerAdapter(logger=logger, dry_run=dry_run),
        "twitter": TwitterAdapter(logger=logger, dry_run=dry_run),
        "spotify": SpotifyAdapter(logger=logger, dry_run=dry_run),
        "youtube": YouTubeAdapter(logger=logger, dry_run=dry_run),
        # Phase 2g: browser-equivalent adapters, real Playwright
        # automation (see docs/phase2g_browser_automation.md). Reachable
        # via their own explicit aliases ("whatsapp web", "telegram web")
        # -- NOT wired as an automatic fallback for whatsapp_desktop/
        # telegram_desktop yet; resolution_gate.py's Q2 branch stays
        # 2-way until more of these exist to validate the 3-way branch
        # against.
        "whatsapp_web": WhatsAppWebAdapter(logger=logger, dry_run=dry_run),
        "telegram_web": TelegramWebAdapter(logger=logger, dry_run=dry_run),
    }
