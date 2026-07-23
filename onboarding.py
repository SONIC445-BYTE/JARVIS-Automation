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
from typing import Dict, List, Optional

STATE_DIR = Path("state")
ONBOARDING_MARKER = STATE_DIR / "onboarding_complete.json"
SCAN_CACHE_MARKER = STATE_DIR / "availability_scan_cache.json"
PENDING_STATE_MARKER = STATE_DIR / "pending_state.json"

# Kept in sync with pyproject.toml's [project].version by hand -- this
# is a display string for the startup box, not a second source of truth
# consumed by packaging.
JARVIS_VERSION = "0.1.0"

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


def _installed_map(checker) -> Dict[str, bool]:
    """adapter_key -> is_installed, for CommandRouter's real adapter
    registry against the given AvailabilityChecker. Single shared
    computation used by the full coverage report, the scan cache the
    compact status box reads, and rescan_now() -- not reimplemented
    per caller."""
    from AgentCore.command_router import CommandRouter

    router = CommandRouter()
    return {
        key: checker.is_installed(cls.PLATFORM_ALIASES or [key])
        for key, cls in router._adapter_classes.items()
    }


def _coverage_lines(checker) -> List[str]:
    """Reuses CommandRouter's real adapter registry (the exact set
    ResolutionGate checks against) and the shared AvailabilityChecker --
    not a separate enumeration, not a duplicated platform list."""
    from AgentCore.command_router import CommandRouter

    router = CommandRouter()
    installed = _installed_map(checker)
    lines = []
    installed_count = sum(1 for v in installed.values() if v)
    for key, adapter_cls in sorted(router._adapter_classes.items(), key=lambda kv: kv[0]):
        aliases = adapter_cls.PLATFORM_ALIASES or [key]
        display = aliases[0].title()
        found = installed[key]
        status = "found" if found else "not found"
        lines.append(f"  [{'x' if found else ' '}] {display:<20s} {status}")
    lines.append("")
    lines.append(f"  {installed_count} of {len(installed)} controllable platforms found on this machine.")
    return lines


def _write_scan_cache(checker) -> None:
    """Called after every real AvailabilityChecker.refresh() (onboarding's
    own first-run scan, PeriodicAvailabilityRescanner's tick, and
    rescan_now()) so the compact status box (every launch) can show
    live-sourced counts instantly without forcing its own blocking scan
    just to render a status line -- it reads this cache instead. Not a
    second scanning mechanism: the data always comes from a refresh()
    that already happened for its own reason."""
    installed = _installed_map(checker)
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    SCAN_CACHE_MARKER.write_text(
        json.dumps({"installed": installed, "checked_at": _now_iso()}, indent=2),
        encoding="utf-8",
    )


def _read_scan_cache() -> Optional[dict]:
    if not SCAN_CACHE_MARKER.exists():
        return None
    try:
        return json.loads(SCAN_CACHE_MARKER.read_text(encoding="utf-8"))
    except Exception:
        return None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _age_description(iso_timestamp: str) -> str:
    try:
        then = datetime.fromisoformat(iso_timestamp)
    except Exception:
        return "unknown"
    seconds = (datetime.now(timezone.utc) - then).total_seconds()
    if seconds < 60:
        return "just now"
    minutes = int(seconds // 60)
    if minutes < 60:
        return f"{minutes} min ago"
    hours = int(minutes // 60)
    if hours < 24:
        return f"{hours}h ago"
    return f"{int(hours // 24)}d ago"


# ============ Pending PendingInstall/PendingResume, surfaced across restarts ============

def persist_pending_state(kind: str, description: str) -> None:
    """kind: "install" | "resume". PersistentWakeService's
    _pending_install/_pending_resume are in-memory only -- if the
    process restarts (or crashes) while one is set, it's silently lost
    with no indication anything was waiting, until the exact right
    trigger phrase is spoken again in a process that never restarted.
    Called from jarvis.py at the same points those fields get set, so
    the NEXT launch's compact status box can at least tell the
    physician something was left unresolved, instead of it vanishing
    unnoticed. Does not attempt to restore the pending state itself
    (e.g. auto re-arm _pending_resume from a dead session) -- only
    surfaces that it existed; re-issuing the original command is still
    required."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    PENDING_STATE_MARKER.write_text(
        json.dumps({"kind": kind, "description": description, "recorded_at": _now_iso()}, indent=2),
        encoding="utf-8",
    )


def clear_pending_state() -> None:
    try:
        PENDING_STATE_MARKER.unlink()
    except FileNotFoundError:
        pass


def read_pending_state_summary() -> Optional[str]:
    if not PENDING_STATE_MARKER.exists():
        return None
    try:
        data = json.loads(PENDING_STATE_MARKER.read_text(encoding="utf-8"))
    except Exception:
        return None
    kind = data.get("kind")
    if kind == "install":
        return "1 install awaiting your confirmation"
    if kind == "resume":
        return "1 browser task waiting on you"
    return None


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
    _write_scan_cache(checker)  # so the compact status box has data immediately after this

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
                _write_scan_cache(self._checker)
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
    _write_scan_cache(checker)

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


# ============ Compact status box (every launch) ============
#
# Replaces the old "full walkthrough once, quiet after" split for the
# startup display itself: the FULL walkthrough (banner, visible scan,
# explanation) still only runs once, on first run -- run_onboarding()
# above is unchanged. But every launch, first-run included, now ends
# with this compact box as the standing header, modeled on Claude
# Code's own startup box. Deliberately excluded, per instruction: no
# account/identity line (no equivalent -- local/single-user), no
# working-directory line (not meaningful for a voice assistant), no
# "what's new"/tips filler (would need a real changelog feeding it, not
# invented placeholder text), no full per-platform table (stays behind
# "check what's installed"), no visible toggle for the install-
# confirmation safety requirement (non-negotiable, not something to
# present as adjustable).

_FAST_TIER_MODELS = {"tinyllama", "phi3:mini"}


def _model_tier(model_name: str) -> str:
    """tinyllama/phi3:mini are the two smallest, CPU-friendly entries at
    the front of LLMEngine.PREFERRED_MODELS ("smallest first" per its
    own docstring) -- everything after them is larger/slower and more
    accurate. There's no literal Fast/Accurate toggle anywhere in
    LLMEngine today; this is a friendly label derived from where the
    currently-active model already sits in that existing ordering, not
    a new switch."""
    base = model_name.split(":")[0]
    return "Fast" if model_name in _FAST_TIER_MODELS or base in _FAST_TIER_MODELS else "Accurate"


def render_status_box(wake_active: bool, llm_model: Optional[str], llm_ready: bool, checker=None) -> str:
    """The compact, every-launch status box. Reads the persisted scan
    cache (written by run_onboarding()/PeriodicAvailabilityRescanner/
    rescan_now()) for the platform-count line rather than forcing a
    fresh AvailabilityChecker scan just to render -- keeps every launch
    fast, and makes "last scan" genuinely meaningful (it can honestly
    be "4 min ago", not always "just now"). Falls back to a live check
    via `checker` only if no cache exists yet at all (true first-ever
    launch, before onboarding's own scan has written one)."""
    lines = [f"JARVIS v{JARVIS_VERSION}", ""]
    lines.append(f"Wake word:  {'listening' if wake_active else 'not active'}")

    if llm_model:
        status = "ready" if llm_ready else "not available"
        lines.append(f"Model:      {llm_model} ({_model_tier(llm_model)}) -- {status}")
    else:
        lines.append("Model:      not available")

    from platform_adapters.platform_catalog import DAEMON_ADAPTER_FOR, PLATFORM_CATALOG

    not_wired = len(PLATFORM_CATALOG) - len(DAEMON_ADAPTER_FOR)

    cache = _read_scan_cache()
    if cache is not None:
        installed = cache["installed"]
        ready = sum(1 for v in installed.values() if v)
        pending = len(installed) - ready
        checked_desc = _age_description(cache["checked_at"])
    elif checker is not None:
        installed = _installed_map(checker)
        ready = sum(1 for v in installed.values() if v)
        pending = len(installed) - ready
        checked_desc = "just now"
    else:
        ready = pending = None
        checked_desc = "not yet checked"

    if ready is not None:
        lines.append(f"Platforms:  {ready} ready . {pending} pending install . {not_wired} not yet wired")
    else:
        lines.append("Platforms:  not yet checked")

    lines.append(f"Pending:    {read_pending_state_summary() or 'none'}")
    lines.append(f"Last scan:  {checked_desc}")

    width = max(len(line) for line in lines) + 2
    border = "+" + "-" * (width + 2) + "+"
    body = "\n".join(f"| {line.ljust(width)} |" for line in lines)
    return f"{border}\n{body}\n{border}"
