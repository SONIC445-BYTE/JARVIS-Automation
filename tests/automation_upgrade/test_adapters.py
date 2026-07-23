from unittest.mock import MagicMock, patch

from platform_adapters.telegram_desktop_adapter import TelegramDesktopAdapter
from platform_adapters.text_editor_adapter import TextEditorAdapter
from platform_adapters.whatsapp_desktop_adapter import WhatsappDesktopAdapter


class FakeBackend:
    def __init__(self, window_found=True, open_command_result=True):
        self.calls = []
        # Simulates whether the target window can actually be found/
        # focused -- lets tests exercise the close_window() focus-gate
        # fix (terminal-crash root cause) without needing a real window.
        self.window_found = window_found
        self.open_command_result = open_command_result

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

    def open_command(self, command):
        self.calls.append(("open_command", command))
        return self.open_command_result

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


def test_telegram_open_app_activates_existing_window_without_launching():
    backend = FakeBackend(window_found=True)
    adapter = TelegramDesktopAdapter(logger=MagicMock(), dry_run=False, backend=backend)

    ok = adapter.open_app()

    assert ok is True
    assert not any(call[0] == "open_command" for call in backend.calls)


def test_telegram_open_app_launches_when_no_window_found():
    """
    Regression test for a real bug found live: open_app() used to only
    call activate_window(), with no fallback to actually launch the app
    -- a freshly-installed Telegram with no existing window silently
    failed to open at all (confirmed live, then fixed and re-verified
    live: the app genuinely launches now).
    """
    backend = FakeBackend(window_found=False, open_command_result=True)
    adapter = TelegramDesktopAdapter(logger=MagicMock(), dry_run=False, backend=backend)

    ok = adapter.open_app()

    assert ok is True
    launch_calls = [c for c in backend.calls if c[0] == "open_command"]
    assert len(launch_calls) == 1
    assert "Telegram.exe" in launch_calls[0][1]


def test_whatsapp_open_app_launches_via_discovered_package_family_name():
    """
    Same missing-fallback bug class as Telegram's, but WhatsApp Desktop
    is a Microsoft Store app -- launched via shell:AppsFolder, not a
    plain .exe path. The PackageFamilyName is looked up from what's
    actually installed rather than hardcoded (Store app IDs aren't
    something that could be verified live on this machine -- no real
    WhatsApp Desktop install was found here during the audit).
    """
    backend = FakeBackend(window_found=False, open_command_result=True)
    adapter = WhatsappDesktopAdapter(logger=MagicMock(), dry_run=False, backend=backend)

    with patch.object(adapter, "_find_whatsapp_package_family_name", return_value="Fake.WhatsApp_abc123"):
        ok = adapter.open_app()

    assert ok is True
    launch_calls = [c for c in backend.calls if c[0] == "open_command"]
    assert len(launch_calls) == 1
    assert "Fake.WhatsApp_abc123" in launch_calls[0][1]
    assert "shell:AppsFolder" in launch_calls[0][1]


def test_whatsapp_open_app_fails_honestly_when_not_actually_installed():
    """
    Confirmed live: no real WhatsApp Desktop package exists on this
    machine, so the lookup returns None. open_app() must return False
    honestly, not crash or claim success.
    """
    backend = FakeBackend(window_found=False)
    adapter = WhatsappDesktopAdapter(logger=MagicMock(), dry_run=False, backend=backend)

    with patch.object(adapter, "_find_whatsapp_package_family_name", return_value=None):
        ok = adapter.open_app()

    assert ok is False
    assert not any(call[0] == "open_command" for call in backend.calls)
