from __future__ import annotations

import os
import subprocess
import sys
import time
from typing import Iterable, Optional


def _optional_import(name: str):
    try:
        return __import__(name)
    except Exception:
        return None


class GUIBackend:
    def __init__(self):
        self.pyautogui = _optional_import("pyautogui")
        self.keyboard = _optional_import("keyboard") if os.name == "nt" else None

    def activate_window(self, title: str, exclude_process_names: Optional[Iterable[str]] = None) -> bool:
        """
        D12: pyautogui.getWindowsWithTitle() does substring matching, and
        several adapters (amazon, google, gmail, youtube, twitter, ...)
        deliberately rely on that to find their tab among browser
        windows -- exclude_process_names defaults to None so none of
        that changes. It exists for the opposite case: a *desktop* app
        adapter (whatsapp_desktop, telegram_desktop) whose WINDOW_TITLE
        happens to collide with a browser tab title for the same web
        service (confirmed live: "WhatsApp" matched a Chrome window
        titled "WhatsApp Web", not the native app -- Get-Process
        confirmed chrome.exe, Get-AppxPackage confirmed no real WhatsApp
        Desktop package was even installed). Callers that need this pass
        the set of process names to skip; if process identity can't be
        determined (pywin32/psutil unavailable), this fails open --
        doesn't exclude -- rather than making desktop adapters *more*
        broken when the introspection isn't available.
        """
        if self.pyautogui and hasattr(self.pyautogui, "getWindowsWithTitle"):
            windows = self.pyautogui.getWindowsWithTitle(title)
            if exclude_process_names:
                exclude = {p.lower() for p in exclude_process_names}
                windows = [w for w in windows if not self._window_process_in(w, exclude)]
            if windows:
                windows[0].activate()
                time.sleep(0.2)
                return True
        if sys.platform.startswith("linux"):
            return subprocess.call(["xdotool", "search", "--name", title, "windowactivate"]) == 0
        return False

    @staticmethod
    def _window_process_in(window, process_names: set) -> bool:
        try:
            import win32process
            import psutil

            hwnd = getattr(window, "_hWnd", None)
            if hwnd is None:
                return False
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            return psutil.Process(pid).name().lower() in process_names
        except Exception:
            return False

    def hotkey(self, *keys: str) -> None:
        if self.pyautogui:
            self.pyautogui.hotkey(*keys)
            return
        if self.keyboard and len(keys) >= 2:
            self.keyboard.send("+".join(keys))

    def type_text(self, text: str) -> None:
        if self.pyautogui:
            self.pyautogui.typewrite(text)
            return
        if self.keyboard:
            self.keyboard.write(text)

    def press(self, key: str) -> None:
        if self.pyautogui:
            self.pyautogui.press(key)
            return
        if self.keyboard:
            self.keyboard.send(key)

    def click(self, x: int, y: int) -> None:
        if self.pyautogui:
            self.pyautogui.click(x, y)

    def open_command(self, command: str) -> bool:
        try:
            subprocess.Popen(command, shell=True)
            return True
        except Exception:
            return False

    def close_window(self, title: str, exclude_process_names: Optional[Iterable[str]] = None) -> bool:
        """
        Requires the target window to actually be focused before sending
        a close shortcut. Root cause of the terminal-crash incident:
        close_window() used to fire Alt+F4 unconditionally, with no check
        of what window currently had focus -- if the target app hadn't
        actually gained OS foreground focus yet (e.g. Windows denying a
        newly-launched background process foreground-stealing rights),
        the shortcut landed on whatever *did* have focus instead, which
        was the terminal running this process. Reusing activate_window()
        here rather than inventing a second focus mechanism.

        exclude_process_names forwards to activate_window() (D12) -- a
        desktop adapter calling this to close its own app must not
        activate-then-Alt+F4 the user's unrelated browser window just
        because a tab title happened to collide with WINDOW_TITLE.
        """
        if not self.activate_window(title, exclude_process_names=exclude_process_names):
            return False
        if os.name == "nt":
            self.hotkey("alt", "f4")
        elif sys.platform == "darwin":
            self.hotkey("command", "q")
        else:
            self.hotkey("alt", "f4")
        return True

    def read_visible_text(self) -> str:
        # Window text scraping would be first choice. Keep this lightweight and optional.
        pywinauto = _optional_import("pywinauto")
        if pywinauto and os.name == "nt":
            try:
                app = pywinauto.Application().connect(active_only=True)
                window = app.top_window()
                return window.window_text()
            except Exception:
                pass

        # Accessibility APIs could be integrated here (Quartz/AT-SPI) if available.
        # OCR is last resort.
        pytesseract = _optional_import("pytesseract")
        imagegrab = None
        try:
            from PIL import ImageGrab  # type: ignore

            imagegrab = ImageGrab
        except Exception:
            imagegrab = None
        if pytesseract and imagegrab:
            try:
                image = imagegrab.grab()
                return pytesseract.image_to_string(image)
            except Exception:
                return ""
        return ""
