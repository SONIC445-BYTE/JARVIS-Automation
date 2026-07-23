from unittest.mock import MagicMock

from platform_adapters.text_editor_adapter import TextEditorAdapter
from platform_adapters.whatsapp_desktop_adapter import WhatsappDesktopAdapter


class FakeBackend:
    def __init__(self, window_found=True):
        self.calls = []
        # Simulates whether the target window can actually be found/
        # focused -- lets tests exercise the close_window() focus-gate
        # fix (terminal-crash root cause) without needing a real window.
        self.window_found = window_found

    def activate_window(self, title):
        self.calls.append(("activate_window", title))
        return self.window_found

    def hotkey(self, *keys):
        self.calls.append(("hotkey", keys))

    def type_text(self, text):
        self.calls.append(("type_text", text))

    def press(self, key):
        self.calls.append(("press", key))

    def close_window(self, title):
        self.calls.append(("close_window", title))
        if not self.window_found:
            return False
        self.hotkey("alt", "f4")
        return True

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


def test_text_editor_close_app_fires_shortcut_when_window_found():
    backend = FakeBackend(window_found=True)
    logger = MagicMock()
    adapter = TextEditorAdapter(logger=logger, dry_run=False, backend=backend)

    ok = adapter.close_app()

    assert ok is True
    assert ("close_window", "Notepad") in backend.calls
    assert ("hotkey", ("alt", "f4")) in backend.calls


def test_text_editor_close_app_does_not_fire_shortcut_when_window_not_found():
    """
    Regression test for the terminal-crash root cause: close_app() must
    not blindly fire the close shortcut at whatever window currently has
    focus. If the target window can't be found/activated, it must return
    False and skip the shortcut entirely, not fire it anyway.
    """
    backend = FakeBackend(window_found=False)
    logger = MagicMock()
    adapter = TextEditorAdapter(logger=logger, dry_run=False, backend=backend)

    ok = adapter.close_app()

    assert ok is False
    assert ("close_window", "Notepad") in backend.calls
    assert not any(call[0] == "hotkey" for call in backend.calls)
