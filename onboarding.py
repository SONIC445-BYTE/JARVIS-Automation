"""
First-run onboarding + the visible delivery of Phase 2c's
AvailabilityChecker scan / Phase 2b's installed-app coverage report.

This is not a new scan mechanism -- it reuses CommandRouter's existing
adapter registry and AgentCore.resolution_gate's shared
AvailabilityChecker singleton (the exact same object the resolution
gate reads from on every command), so onboarding's report and the
gate's install-detection can never disagree.

State convention: this repo has no existing dedicated config/state
directory (checked -- jarvis.py's own persistence, e.g. Alam_data.txt/
schedule.txt, is flat files in getcwd(); feature_flags/*.yaml is
static, git-tracked deployment config, not runtime state). state/
follows the same top-level, gitignored-runtime-directory style already
used by logs/ and WakeService/models/, just for small JSON state files
instead of logs or a downloaded model.
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

STATE_DIR = Path("state")
ONBOARDING_MARKER = STATE_DIR / "onboarding_complete.json"

# Pure 7-bit ASCII only -- deliberately, not a style preference. See
# jarvis.py's stdout-reconfigure fix and WakeService/wake_detector.py's
# history: a Unicode symbol in a print() reachable from startup already
# crashed the whole process once on this codebase's default Windows
# console encoding (cp1252). The stdout fix protects this too, but a
# first-run banner should not be the thing testing that defense.
_BANNER_FONT = {
    "J": ["  ###", "   # ", "   # ", "#  # ", " ##  "],
    "A": [" ### ", "#   #", "#####", "#   #", "#   #"],
    "R": ["#### ", "#   #", "#### ", "#  # ", "#   #"],
    "V": ["#   #", "#   #", "#   #", " # # ", "  #  "],
    "I": ["#####", "  #  ", "  #  ", "  #  ", "#####"],
    "S": [" ####", "#    ", " ### ", "    #", "#### "],
}


def _render_banner(word: str = "JARVIS") -> str:
    rows = ["  ".join(_BANNER_FONT[ch][r] for ch in word) for r in range(5)]
    return "\n".join(rows)


def is_first_run() -> bool:
    return not ONBOARDING_MARKER.exists()


def mark_onboarding_complete() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    ONBOARDING_MARKER.write_text(
        json.dumps({"completed_at": datetime.now(timezone.utc).isoformat()}, indent=2),
        encoding="utf-8",
    )


def _coverage_lines(checker) -> List[str]:
    """Reuses CommandRouter's real adapter registry (the exact set
    ResolutionGate checks against) and the shared AvailabilityChecker --
    not a separate enumeration, not a duplicated platform list."""
    from AgentCore.command_router import CommandRouter

    router = CommandRouter()
    lines = []
    installed_count = 0
    entries = sorted(router._adapter_classes.items(), key=lambda kv: kv[0])
    for key, adapter_cls in entries:
        aliases = adapter_cls.PLATFORM_ALIASES or [key]
        display = aliases[0].title()
        found = checker.is_installed(aliases)
        if found:
            installed_count += 1
        status = "found" if found else "not found"
        lines.append(f"  [{'x' if found else ' '}] {display:<20s} {status}")
    lines.append("")
    lines.append(f"  {installed_count} of {len(entries)} controllable platforms found on this machine.")
    return lines


def run_onboarding(checker=None, speak_fn=None) -> None:
    """Runs the full first-run walkthrough: banner, intro, a VISIBLE
    AvailabilityChecker scan (this is the Phase 2b coverage report's
    first real delivery to the physician, not just a doc file), and a
    clear "you're set up" close that mentions --setup / "run setup
    again" so this is discoverable later, not a one-shot secret.

    speak_fn: optional callable(str) -- if provided (jarvis.py passes
    its TTS speak()), key lines are also spoken, not just printed.
    """
    def say(text: str) -> None:
        print(text)
        if speak_fn:
            try:
                speak_fn(text)
            except Exception:
                pass  # onboarding must not fail because TTS hiccuped

    print()
    print("=" * 60)
    print(_render_banner())
    print("=" * 60)
    print()
    say("Hi, I'm JARVIS. This is a one-time setup so I know what I can help you with.")
    print()
    print("Here's what I'm doing right now:")
    print("  - Checking this computer for apps I know how to control")
    print("  - This only happens once -- after this, I start up fast and quiet")
    print()

    print("Scanning your system for installed apps...")
    if checker is None:
        from AgentCore.resolution_gate import _get_default_availability_checker
        checker = _get_default_availability_checker()
        checker.refresh()  # onboarding's scan should be fresh, not whatever ran first in this process
    for line in _coverage_lines(checker):
        print(line)
    print()

    mark_onboarding_complete()

    say("Setup's done. From now on I'll start up quietly -- no walkthrough.")
    print("Anything not found above just isn't installed yet -- ask me to open it")
    print("and I'll offer to install it if I can.")
    print()
    print("You can run this full walkthrough again anytime: `python jarvis.py --setup`,")
    print("or just say \"run setup again\".")
    print("=" * 60)
    print()


# ============ Periodic + on-demand re-scan (closes Phase 2c's ============
# ============ "refresh at startup only" staleness gap)        ============

_DEFAULT_RESCAN_INTERVAL_S = 20 * 60  # 20 min: default of the 15-30 min range asked for


def rescan_interval_seconds() -> float:
    """Configurable via env var, not hardcoded -- a hospital deployment
    may want this tuned differently than a dev machine. Falls back to
    the default on anything unparseable rather than crashing a
    background thread over a bad env value."""
    raw = os.environ.get("JARVIS_AVAILABILITY_RESCAN_INTERVAL_S")
    if not raw:
        return _DEFAULT_RESCAN_INTERVAL_S
    try:
        value = float(raw)
        return value if value > 0 else _DEFAULT_RESCAN_INTERVAL_S
    except ValueError:
        return _DEFAULT_RESCAN_INTERVAL_S


class PeriodicAvailabilityRescanner:
    """Background daemon thread that periodically calls refresh() on the
    SAME shared AvailabilityChecker singleton resolution_gate.py reads
    from -- there is only one instance of that object per process (see
    _get_default_availability_checker), so refreshing it here is
    immediately visible to every ResolutionGate/CommandRouter instance
    without any additional wiring."""

    def __init__(self, checker=None, interval_s: Optional[float] = None):
        import threading

        if checker is None:
            from AgentCore.resolution_gate import _get_default_availability_checker
            checker = _get_default_availability_checker()
        self._checker = checker
        self._interval_s = interval_s if interval_s is not None else rescan_interval_seconds()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        import threading

        if self._thread is not None:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while not self._stop_event.wait(self._interval_s):
            try:
                self._checker.refresh()
            except Exception as e:
                print(f"[AvailabilityRescan] refresh failed (will retry next interval): {e}")

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None


def rescan_now(checker=None) -> str:
    """On-demand re-scan, reusing the exact same refresh()/is_installed()
    logic the periodic thread and the resolution gate use -- not a
    separate scan path. Returns a short, physician-facing summary."""
    if checker is None:
        from AgentCore.resolution_gate import _get_default_availability_checker
        checker = _get_default_availability_checker()

    from AgentCore.command_router import CommandRouter

    router = CommandRouter()
    entries = router._adapter_classes.items()
    before = {
        key: checker.is_installed(cls.PLATFORM_ALIASES or [key]) for key, cls in entries
    }

    checker.refresh()

    newly_found = []
    for key, cls in entries:
        aliases = cls.PLATFORM_ALIASES or [key]
        now_found = checker.is_installed(aliases)
        if now_found and not before.get(key, False):
            newly_found.append((aliases[0].title()))

    total_found = sum(1 for key, cls in entries if checker.is_installed(cls.PLATFORM_ALIASES or [key]))
    total = len(entries)

    if newly_found:
        return f"Rescanned -- found {', '.join(newly_found)} newly installed. {total_found} of {total} platforms available now."
    return f"Rescanned -- no new apps found. {total_found} of {total} platforms available."
