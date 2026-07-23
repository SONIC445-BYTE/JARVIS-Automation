from __future__ import annotations

import os
import subprocess
import sys
import time
from typing import Optional


def _optional_import(name: str):
    try:
        return __import__(name)
    except Exception:
        return None


class GUIBackend:
    def __init__(self):
        self.pyautogui = _optional_import("pyautogui")
        self.keyboard = _optional_import("keyboard") if os.name == "nt" else None

    def activate_window(self, title: str) -> bool:
        if self.pyautogui and hasattr(self.pyautogui, "getWindowsWithTitle"):
            windows = self.pyautogui.getWindowsWithTitle(title)
            if windows:
                windows[0].activate()
                time.sleep(0.2)
                return True
        if sys.platform.startswith("linux"):
            return subprocess.call(["xdotool", "search", "--name", title, "windowactivate"]) == 0
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

    def close_window(self, title: str) -> bool:
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
        """
        if not self.activate_window(title):
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
