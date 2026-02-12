from unittest.mock import MagicMock

from platform_adapters.text_editor_adapter import TextEditorAdapter
from platform_adapters.whatsapp_desktop_adapter import WhatsappDesktopAdapter


class FakeBackend:
    def __init__(self):
        self.calls = []

    def activate_window(self, title):
        self.calls.append(("activate_window", title))
        return True

    def hotkey(self, *keys):
        self.calls.append(("hotkey", keys))

    def type_text(self, text):
        self.calls.append(("type_text", text))

    def press(self, key):
        self.calls.append(("press", key))

    def close_window(self):
        self.calls.append(("close_window",))

    def read_visible_text(self):
        self.calls.append(("read_visible_text",))
        return "hello"


def test_whatsapp_send_message_uses_backend_when_not_dry_run():
    backend = FakeBackend()
    logger = MagicMock()
    adapter = WhatsappDesktopAdapter(logger=logger, dry_run=False, backend=backend)

    ok = adapter.send_message("alice", "hello world")

    assert ok is True
    assert ("hotkey", ("ctrl", "f")) in backend.calls
    assert ("type_text", "alice") in backend.calls
    assert ("type_text", "hello world") in backend.calls


def test_text_editor_dry_run_skips_backend_calls():
    backend = FakeBackend()
    logger = MagicMock()
    adapter = TextEditorAdapter(logger=logger, dry_run=True, backend=backend)

    ok = adapter.send_message("notes", "hello")

    assert ok is True
    assert backend.calls == []
