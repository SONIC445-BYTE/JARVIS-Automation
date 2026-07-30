"""
D12: GUIBackend.activate_window()/close_window() exclude_process_names.

Confirmed live (2026-07-30): pyautogui.getWindowsWithTitle() does
substring matching, so WhatsappDesktopAdapter's WINDOW_TITLE="WhatsApp"
matched a real Chrome window titled "WhatsApp Web" -- Get-Process
confirmed the window belonged to chrome.exe, not the native app;
Get-AppxPackage confirmed no real WhatsApp Desktop package was even
installed. open_app() reported success by activating that browser
window without ever reaching the real launch-fallback path.
"""
import unittest
from unittest import mock

from platform_adapters.gui_backend import GUIBackend


class _FakeWin32Window:
    def __init__(self, hwnd, title="fake"):
        self._hWnd = hwnd
        self.title = title
        self.activated = False

    def activate(self):
        self.activated = True


class TestExcludeProcessNames(unittest.TestCase):
    def _backend_with_windows(self, windows):
        backend = GUIBackend.__new__(GUIBackend)
        backend.pyautogui = mock.Mock()
        backend.pyautogui.getWindowsWithTitle.return_value = windows
        backend.keyboard = None
        return backend

    def test_no_exclusion_list_preserves_existing_substring_match_behavior(self):
        # Default (None) must not change any of the browser-based
        # adapters (amazon/google/gmail/youtube/twitter/...) that
        # deliberately rely on substring matching against browser tabs.
        w = _FakeWin32Window(hwnd=1)
        backend = self._backend_with_windows([w])
        self.assertTrue(backend.activate_window("Amazon"))
        self.assertTrue(w.activated)

    def test_excludes_a_window_owned_by_a_listed_process(self):
        real_app_window = _FakeWin32Window(hwnd=1, title="native app")
        browser_window = _FakeWin32Window(hwnd=2, title="WhatsApp Web")
        backend = self._backend_with_windows([browser_window, real_app_window])

        def fake_process_in(window, names):
            return window is browser_window  # simulate: hwnd 2 is chrome.exe

        with mock.patch.object(GUIBackend, "_window_process_in", staticmethod(fake_process_in)):
            result = backend.activate_window("WhatsApp", exclude_process_names={"chrome.exe"})

        self.assertTrue(result)
        self.assertTrue(real_app_window.activated)
        self.assertFalse(browser_window.activated)

    def test_returns_false_when_every_matching_window_is_excluded(self):
        # This is the exact bug: only a browser tab matches, no real app
        # window exists -- must fail honestly (so open_app() falls
        # through to the real launch path), not silently succeed against
        # the browser window.
        browser_window = _FakeWin32Window(hwnd=2, title="WhatsApp Web")
        backend = self._backend_with_windows([browser_window])

        with mock.patch.object(GUIBackend, "_window_process_in", staticmethod(lambda w, n: True)):
            result = backend.activate_window("WhatsApp", exclude_process_names={"chrome.exe"})

        self.assertFalse(result)
        self.assertFalse(browser_window.activated)

    def test_fails_open_when_process_identity_cannot_be_determined(self):
        # pywin32/psutil unavailable (or any lookup failure) must not
        # make desktop adapters *more* broken than before this fix --
        # falls back to the pre-D12 behavior of trusting the title match.
        w = _FakeWin32Window(hwnd=1)
        backend = self._backend_with_windows([w])

        with mock.patch("win32process.GetWindowThreadProcessId", side_effect=ImportError("no pywin32")):
            result = backend.activate_window("WhatsApp", exclude_process_names={"chrome.exe"})

        self.assertTrue(result)
        self.assertTrue(w.activated)

    def test_close_window_forwards_the_exclusion_to_activate_window(self):
        backend = self._backend_with_windows([])
        with mock.patch.object(backend, "activate_window", return_value=False) as m_activate:
            result = backend.close_window("WhatsApp", exclude_process_names={"chrome.exe"})

        m_activate.assert_called_once_with("WhatsApp", exclude_process_names={"chrome.exe"})
        self.assertFalse(result)


class TestWindowProcessInRealLogic(unittest.TestCase):
    """Exercises the real _window_process_in() implementation, mocking only win32process/psutil."""

    def test_matches_when_owning_process_is_in_the_set(self):
        window = _FakeWin32Window(hwnd=12345)
        fake_process = mock.Mock()
        fake_process.name.return_value = "chrome.exe"

        with mock.patch("win32process.GetWindowThreadProcessId", return_value=(0, 999)), \
             mock.patch("psutil.Process", return_value=fake_process):
            result = GUIBackend._window_process_in(window, {"chrome.exe"})

        self.assertTrue(result)

    def test_does_not_match_when_owning_process_is_not_in_the_set(self):
        window = _FakeWin32Window(hwnd=12345)
        fake_process = mock.Mock()
        fake_process.name.return_value = "telegram.exe"

        with mock.patch("win32process.GetWindowThreadProcessId", return_value=(0, 999)), \
             mock.patch("psutil.Process", return_value=fake_process):
            result = GUIBackend._window_process_in(window, {"chrome.exe"})

        self.assertFalse(result)

    def test_case_insensitive_process_name_match(self):
        window = _FakeWin32Window(hwnd=1)
        fake_process = mock.Mock()
        fake_process.name.return_value = "Chrome.EXE"

        with mock.patch("win32process.GetWindowThreadProcessId", return_value=(0, 1)), \
             mock.patch("psutil.Process", return_value=fake_process):
            result = GUIBackend._window_process_in(window, {"chrome.exe"})

        self.assertTrue(result)


if __name__ == "__main__":
    unittest.main()
