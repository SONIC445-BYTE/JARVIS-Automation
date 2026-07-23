from unittest.mock import MagicMock

from platform_adapters.gui_backend import GUIBackend


def test_close_window_fires_hotkey_when_target_activated():
    backend = GUIBackend()
    backend.activate_window = MagicMock(return_value=True)
    backend.hotkey = MagicMock()

    result = backend.close_window("Notepad")

    assert result is True
    backend.activate_window.assert_called_once_with("Notepad")
    backend.hotkey.assert_called_once()


def test_close_window_skips_hotkey_when_target_not_found():
    """
    Regression test for the terminal-crash root cause: close_window()
    used to fire a global Alt+F4 unconditionally, with no check of what
    window currently had OS focus. If the target window can't be found
    or activated, it must return False and must not send any shortcut --
    firing a global close hotkey blind can close an unrelated window
    (e.g. the terminal running this process) instead of the intended
    target.
    """
    backend = GUIBackend()
    backend.activate_window = MagicMock(return_value=False)
    backend.hotkey = MagicMock()

    result = backend.close_window("Notepad")

    assert result is False
    backend.hotkey.assert_not_called()
