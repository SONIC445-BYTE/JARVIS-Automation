"""
Phase 2c: resolution gate.

Sits ahead of command execution with a two-question check, so every
command produces a distinct, honest outcome instead of a silent no-op:

  Q1: Is there a real, WORKING adapter for the platform this command
      names? "Working" means wired through platform_adapters/registry.py
      (platform_catalog.DAEMON_ADAPTER_FOR) -- not merely "audit-
      classified (a)/(b)" in AgentCore/platform_adapters/, since as of
      Phase 2c none of those have been ported onto the working contract
      yet (that's Phase 2d). If no -> "I don't know how to control
      [platform] yet." Never offers to install -- a fabricated/
      nonexistent adapter means installing the app wouldn't help.

  Q2 (only if Q1 = yes): Is the app actually installed, per
      AvailabilityChecker? If no -> offer to install (winget), listing
      the adapter's real declared actions. Never auto-installs; waits
      for explicit confirmation.

If no platform name is recognized at all, or a recognized *and wired*
platform's verb just didn't match this phrasing, the gate steps aside
(PLATFORM_UNKNOWN) and normal classification proceeds unchanged.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple

from daemon.intent_parser import Intent
from platform_adapters.availability import AvailabilityChecker
from platform_adapters.platform_catalog import (
    DAEMON_ADAPTER_FOR,
    PLATFORM_CATALOG,
    find_catalog_entry,
)
from platform_adapters.registry import create_default_adapters
from AgentCore.command_router import CommandRouter


# (winget package id, source) for platforms with a real, verified package.
# None = no separate installable package exists for this platform (e.g.
# Notepad ships with Windows; Gmail is a website, not an installable app)
# -- these correctly produce the "no winget match" honest branch.
WINGET_IDS: Dict[str, Optional[Tuple[str, str]]] = {
    "browser": ("Google.Chrome", "winget"),
    "telegram_desktop": ("Telegram.TelegramDesktop", "winget"),
    "whatsapp_desktop": ("9NKSQGP7F2NH", "msstore"),
    "text_editor": None,
    "gmail_browser": None,
    # Phase 2d: ported adapters. amazon/google/twitter/youtube are
    # browser-based (like gmail) -- no separate installable desktop app.
    # calculator/explorer ship with Windows -- no separate package.
    "amazon": None,
    "google": None,
    "calculator": None,
    "explorer": None,
    "twitter": None,
    "spotify": ("Spotify.Spotify", "winget"),
    "youtube": None,
}


class GateOutcome(Enum):
    RESOLVED = "resolved"
    NO_ADAPTER = "no_adapter"
    NOT_INSTALLED = "not_installed"
    PLATFORM_UNKNOWN = "platform_unknown"


@dataclass
class PendingInstall:
    """Multi-turn confirmation state: held by the conversation loop
    between "want me to install it?" and the user's next reply, so the
    original command can be retried once installation succeeds."""
    original_text: str
    platform_display_name: str
    adapter_key: str
    winget_id: Optional[Tuple[str, str]]


@dataclass
class GateResult:
    outcome: GateOutcome
    intent: Optional[Intent] = None
    platform_display_name: Optional[str] = None
    adapter_key: Optional[str] = None
    winget_id: Optional[Tuple[str, str]] = None
    real_actions: Optional[List[str]] = None

    @property
    def message(self) -> str:
        """The distinct, honest message for this outcome. Every branch
        has one -- never a generic "Done." or silent no-op."""
        if self.outcome == GateOutcome.NO_ADAPTER:
            return f"I don't know how to control {self.platform_display_name} yet."
        if self.outcome == GateOutcome.NOT_INSTALLED:
            actions = ", ".join(self.real_actions or [])
            return (
                f"{self.platform_display_name} isn't installed. Want me to install it? "
                f"Once installed, I can: {actions}."
            )
        if self.outcome == GateOutcome.RESOLVED:
            return ""  # caller proceeds to execute; no gate message needed
        return ""  # PLATFORM_UNKNOWN: caller falls through to normal classification


_default_availability_checker: Optional[AvailabilityChecker] = None


def _get_default_availability_checker() -> AvailabilityChecker:
    """Real installed-app enumeration is a ~1-2s subprocess call. Both
    jarvis.py and ODAVLoop construct their own IntentRouter (each of
    which constructs a ResolutionGate by default), so without this
    module-level cache the real machine would get scanned twice per
    process start, and every test file constructing a bare IntentRouter()
    would trigger its own scan. Matches Phase 2c's "refresh at startup"
    scope -- first use per process, not per instance; call refresh() on
    the checker directly for a later re-scan."""
    global _default_availability_checker
    if _default_availability_checker is None:
        _default_availability_checker = AvailabilityChecker()
    return _default_availability_checker


class ResolutionGate:
    def __init__(
        self,
        command_router: Optional[CommandRouter] = None,
        availability_checker: Optional[AvailabilityChecker] = None,
    ):
        self._router = command_router or CommandRouter()
        self._availability = availability_checker or _get_default_availability_checker()
        self._adapter_classes = self._router._adapter_classes

    def check(self, text: str) -> GateResult:
        intent = self._router.resolve(text)

        if intent is not None:
            return self._check_installed(intent)

        # No working adapter matched this text. Distinguish "recognized
        # platform name, no real adapter" from "platform is wired but
        # this phrasing's verb didn't match" (the latter must NOT claim
        # "no adapter" -- that would be false) from "not a platform
        # command at all".
        catalog_key = find_catalog_entry(text.lower())
        if catalog_key is None or catalog_key in DAEMON_ADAPTER_FOR:
            return GateResult(outcome=GateOutcome.PLATFORM_UNKNOWN)

        info = PLATFORM_CATALOG[catalog_key]
        return GateResult(
            outcome=GateOutcome.NO_ADAPTER,
            platform_display_name=info["display_name"],
        )

    def _check_installed(self, intent: Intent) -> GateResult:
        adapter_cls = self._adapter_classes.get(intent.adapter)
        aliases = adapter_cls.PLATFORM_ALIASES if adapter_cls else [intent.adapter]
        display_name = aliases[0].title() if aliases else intent.adapter

        if self._availability.is_installed(aliases):
            return GateResult(outcome=GateOutcome.RESOLVED, intent=intent)

        real_actions = [spec.name for spec in adapter_cls.ACTIONS] if adapter_cls else []
        return GateResult(
            outcome=GateOutcome.NOT_INSTALLED,
            intent=intent,
            platform_display_name=display_name,
            adapter_key=intent.adapter,
            winget_id=WINGET_IDS.get(intent.adapter),
            real_actions=real_actions,
        )
