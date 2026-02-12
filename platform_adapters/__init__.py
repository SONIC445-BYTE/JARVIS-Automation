from .adapter_base import AdapterBase
from .browser_adapter import BrowserAdapter
from .gmail_browser_adapter import GmailBrowserAdapter
from .telegram_desktop_adapter import TelegramDesktopAdapter
from .text_editor_adapter import TextEditorAdapter
from .whatsapp_desktop_adapter import WhatsappDesktopAdapter

__all__ = [
    "AdapterBase",
    "BrowserAdapter",
    "GmailBrowserAdapter",
    "TelegramDesktopAdapter",
    "TextEditorAdapter",
    "WhatsappDesktopAdapter",
]
