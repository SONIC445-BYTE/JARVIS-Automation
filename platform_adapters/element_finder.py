"""
Phase 2d: real element-finding for the rare action that genuinely has no
fixed keyboard shortcut (e.g. "click play on the first search result" --
the target's position depends on page state, unlike Gmail's Ctrl+Enter
or WhatsApp's Enter-to-send).

Uses AgentCore.ui_perception.UIScanner directly -- confirmed real,
working code (Phase 2c-prime investigation) -- bypassing
AgentCore/ui_agent's escalation ladder and soft-pass ValidationEngine
entirely. Both would make a broken click look successful, which is worse
than an honest failure.

Imported lazily inside functions, not at module load time:
AgentCore/__init__.py eagerly imports the full UI automation stack (a
pre-existing, Phase-3-flagged coupling issue). platform_adapters/ was
previously independent of AgentCore (daemon/dispatcher.py's standalone
CLI doesn't otherwise need it) -- a lazy import keeps that true except
for the specific calls that actually need real element-finding.
"""
from __future__ import annotations

from typing import Optional, Tuple


def find_element_center(target_text: str) -> Optional[Tuple[int, int]]:
    """Scan the current screen and return the (x, y) center of the first
    element matching target_text, or None if it can't be found -- an
    honest failure, never a guessed fallback coordinate."""
    from AgentCore.ui_perception import UIScanner

    scanner = UIScanner()
    snapshot = scanner.scan()
    element = scanner.find_element(target_text, snapshot)
    if element is None:
        return None
    return element.center


def find_first_clickable_center() -> Optional[Tuple[int, int]]:
    """Scan the current screen and return the (x, y) center of the
    topmost-then-leftmost clickable element -- used for "play/open the
    first result" style actions where there's no fixed text label to
    search for (e.g. a video thumbnail). Element ordering follows
    UIScanner's position sort, a real (if heuristic) signal, not a
    hardcoded guess -- returns None, an honest failure, if nothing
    clickable was found."""
    from AgentCore.ui_perception import UIScanner

    scanner = UIScanner()
    snapshot = scanner.scan()
    element = scanner.find_by_position("first", snapshot)
    if element is None:
        return None
    return element.center
