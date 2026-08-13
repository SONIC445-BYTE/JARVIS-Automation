"""
JARVIS - Voice Assistant with Conversational Intelligence
============================================================
Single entry point for all JARVIS functionality.

Usage:
  python jarvis.py              # Normal interactive mode (browser STT)
  python jarvis.py --service    # Persistent wake mode (offline, low CPU)
  python jarvis.py --convo      # Conversational mode with LLM (offline)
  python jarvis.py --background # Same as --convo, minimal console output
                                 # (--daemon is a deprecated alias for this;
                                 # it does NOT invoke daemon/dispatcher.py --
                                 # that's a separate CLI, `python -m daemon.cli`)
  python jarvis.py --convo --setup  # Re-run the first-run walkthrough
                                     # (banner + installed-app scan) even
                                     # if it already ran once. Combine
                                     # with --convo/--background/--service;
                                     # also reachable mid-session by
                                     # saying "run setup again".

Features:
- FREE Vosk-only wake detection
- Local LLM via Ollama (offline, CPU-safe)
- Offline TTS (Piper/SAPI)
- Multi-turn conversation
- Intent routing (action vs chat)
- State machine: SLEEP → WAKE → LISTEN → THINK → SPEAK → LISTEN
"""

import os
import re
import sys

# Diagnosed root cause of the wake-word "detection failure" report: this
# codebase's console output uses Unicode symbols (arrow, checkmark,
# bullet -- e.g. jarvis.py's own _set_state() below, wake_detector.py's
# detection prints) but never forces a Unicode-capable stdout encoding.
# On a Windows console defaulting to the legacy cp1252 codepage (the
# common case -- confirmed live on this machine: sys.stdout.encoding was
# 'cp1252'), the very first state transition print in
# PersistentWakeService.start() (SLEEP, before wake detection is even
# started) raises an uncaught UnicodeEncodeError and crashes the whole
# process -- after ~15-20s of visible model-loading output, which is
# exactly what "hangs then wake word never works" looks like from the
# outside. Reconfiguring here, before any other import (some of which
# print during import, e.g. LLMEngine), fixes every current and future
# Unicode-symbol print in one place rather than patching each call site
# -- errors='replace' is a second line of defense so an unexpected
# character degrades to '?' instead of crashing.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass
del _stream

import time
import threading
import random
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, Any
from os import getcwd

# Core imports
from internet_check import is_Online
from Alert import Alert
from Data.DLG_Data import online_dlg, offline_dlg
from co_brain import Jarvis
from TextToSpeech.Fast_DF_TTS import speak
from Automation.Battery import check_plug
from Time_Operations.throw_alert import check_schedule, check_Alam

# Learning System (guarded — only active when feature flag ON)
try:
    from AgentCore.learning_system import LearningSystem
    from AgentCore.learning_system.feature_gate import FeatureGate
    _learning_gate = FeatureGate()
    _LEARNING_AVAILABLE = True
except ImportError:
    _LEARNING_AVAILABLE = False
    _learning_gate = None

    _learning_gate = None

# Two-Tier Coding Engine (Sprint: Code Engine)
try:
    from AgentCore.feature_gate import is_enabled
    if is_enabled("code_engine"):
        from AgentCore.code_engine.engine import CodeEngine
        CODE_ENGINE = CodeEngine()
        print("[Service] Code Engine ENABLED")
    else:
        CODE_ENGINE = None
except ImportError:
    CODE_ENGINE = None

import json


# --- ADDITION (safe coding mode hook) ---
import os
import sys
# Check for environment variable or CLI flag
if os.environ.get("JARVIS_CODE_MODE") == "1" or "--enable-code" in sys.argv:
    try:
        from AgentCore.code_engine.engine import CodeEngine
        # lazy singleton or overwrite existing if new mode requested
        if 'CODE_ENGINE' not in globals() or CODE_ENGINE is None:
            CODE_ENGINE = CodeEngine()
            print(f"[Service] Safe Code Mode ENABLED")
    except ImportError as e:
        print(f"[Service] Safe Code Mode FAILED to load: {e}")
        CODE_ENGINE = None
else:
    # If not explicitly enabled via new mode, keep existing CODE_ENGINE or set to None
    # The existing logic above (lines 50-60) might have set it.
    # But if we want to ensure we don't accidentally enable it without the flag:
    # The prompt implies this mode is exclusive/explicit?
    # "By default the CodeEngine is behind a feature flag; test by enabling code mode via CLI flag..."
    # If I set it to None here, I disable the old logic.
    # I will respect existing logic if it was enabled, otherwise None.
    if 'CODE_ENGINE' not in globals():
        CODE_ENGINE = None
# --- END ADDITION ---


def _code_result_is_success(result: Dict) -> bool:
    """
    Interpret a CodeEngine.handle_command() result dict.

    CodeEngine.handle_command() never returns a "success" key -- its
    contract is dry_run/patch_summary/patch_diff/file_path/sandbox_path
    only. Success semantics are decided here, on the caller side, rather
    than faked into engine.py's return contract: a dry run is a success
    if it actually produced a patch summary, and a write is a success if
    it actually produced a file path.
    """
    if result.get("dry_run", True):
        return bool(result.get("patch_summary"))
    return bool(result.get("file_path"))


def handle_rhinal_capture(text: str, capture_text: str) -> str:
    """
    The `elif intent.handler == "rhinal_capture":` dispatch branch, as a
    real callable rather than code buried inside _conversation_loop's
    method body.

    Extracted for two reasons. First, tests/test_rhinal_dispatch.py used
    to *mirror* this branch's logic in the test file itself (a documented
    but fragile precedent) -- a mirror can pass while the real branch is
    broken, which is exactly the wrong property for the audit path of an
    external clinical-adjacent write. Second, the audit wiring below is
    the kind of thing that must be tested against the real code, not a
    copy of it. Nothing about the routing changed: the loop still reaches
    this the same way, still outside CommandRouter/ResolutionGate/
    AdapterBase, for the reasons in the call site's comment.

    DEC-002 (D15, rhinal_capture half): rhinal_capture is a real network
    write into the physician's external RHINAL vault, and until now it
    emitted no who/what/when/why/source/consent record at all -- it never
    reaches UIExecutor.execute_intent(), the chokepoint that covers every
    Intent-routed action. Covered here via AgentCore.mcp_audit, which
    reuses audit_trail.py's mechanism (and its exact two-tier failure
    model) without pretending an MCP tool is a GUI platform. See
    AgentCore/mcp_audit.py for the ordering argument (two records:
    "attempted" before the wire, outcome after) and the pairing
    limitation.

    Field values, chosen deliberately -- none of these are defaults:

    - what_adapter="rhinal_mcp". Not a platform_adapters/ registry key,
      and deliberately not shaped like one: no `rhinal` adapter exists
      or should exist (checked). A compliance reader must not read this
      record as "a GUI adapter drove a window"; it was an MCP tool call
      to an external service.
    - what_action="rhinal_capture". The actual MCP tool name as
      registered in RHINAL's mcp-server/src/index.ts, so the record names
      something externally verifiable rather than a JARVIS-side
      paraphrase.
    - what_target="rhinal_vault". The destination of the write -- the
      physician's external vault. Deliberately NOT the captured text:
      that content already appears once in `why` (below), and copying
      clinical-adjacent content into a second field of the same record
      buys nothing and doubles the exposure.
    - why=text, the physician's actual spoken words for this turn. Same
      choice UIExecutor makes (it passes Intent.source_text), and the
      same honest reasoning: this system has no model of intent beyond
      what was said, so the closest true answer to "why" is the
      utterance. Note the consequence, inherited from the existing
      convention rather than introduced here: for "remember that X", the
      utterance contains X, so the captured content does land in the
      audit log. That is a property of the DEC-002 record shape (which
      already logs dictated message bodies for send_message), not
      something this branch can decide unilaterally -- flagged, not
      silently accepted.
    - source="voice". Not the emit_clinical_action() default taken by
      omission -- passed explicitly because it is checkable here and
      happens to be true: this function is reached only from
      _conversation_loop, whose only input is self._stt.listen_once(),
      i.e. the microphone. If a typed/remote channel is ever routed here
      (Stage 1c's WhatsApp/Telegram inbound), this argument is the one
      line that must change, and it is visible rather than implicit.
    - who: not passed -- emit_clinical_action() fills it with
      getpass.getuser(). What it can honestly mean today: the OS account
      that ran JARVIS on this machine. What it cannot mean: a verified
      physician identity. There is no per-physician login, no ABDM/ABHA
      identity, and nothing here proves the person who spoke is the
      account owner. Additionally specific to this path: the *vault side*
      attributes the write to whoever owns the rhk_ key in
      RHINAL_API_KEY, which need not be the same principal as the OS
      user -- so `who` is "the local account that initiated it", not
      "the account the external system will show".
    - consent: fixed at "direct_user_action" by emit_clinical_action(),
      and literally true here -- the physician said the words that
      triggered it. No ambient capture path exists.
    """
    if not capture_text:
        # Nothing is sent and nothing external happens, so there is no
        # write to audit -- this is a clarification prompt, not an
        # action. Auditing it would put non-events in a log whose value
        # depends on every line being a real action.
        return "I didn't catch what you wanted me to remember -- try 'remember that ...' with the thought included."

    from AgentCore.mcp_audit import audited_mcp_write
    from AgentCore.rhinal_mcp_client import RhinalCallError, RhinalConfigError, RhinalMCPClient

    audited = audited_mcp_write(
        what_adapter="rhinal_mcp",
        what_action="rhinal_capture",
        what_target="rhinal_vault",
        why=text,
        source="voice",
        call=lambda: RhinalMCPClient().capture(capture_text),
    )

    if audited.blocked:
        # Tier-1 audit failure: the vault write did not happen. Say so.
        return audited.blocked_reason

    if audited.ok:
        rhinal_result = audited.value
        # rhinal_capture always completes the full classify -> distill ->
        # save pipeline and saves unconditionally once it gets this far
        # (verified against RHINAL's own mcp-server/src/tools.ts:
        # vaultWorthy/worthinessReason are informational, not a save/skip
        # gate in this MCP tool -- the "worthiness gate" the code comment
        # there refers to is the web app's own UI behavior, not
        # replicated here). Report the save as fact, the worthiness read
        # as a note.
        response = "Saved that to your Rhinal vault."
        if rhinal_result.get("vaultWorthy") is False:
            reason = rhinal_result.get("worthinessReason")
            response += f" (Rhinal's classifier flagged it as borderline{': ' + reason if reason else ''}, but saved it anyway.)"
    elif isinstance(audited.error, RhinalConfigError):
        response = str(audited.error)
    elif isinstance(audited.error, RhinalCallError):
        response = f"Couldn't reach Rhinal to save that: {audited.error}"
    else:
        # Neither known Rhinal error type. Never report success for
        # something that raised -- surface it honestly instead of
        # letting an unexpected exception type fall through as a save.
        response = f"Something went wrong saving that to Rhinal: {audited.error}"

    if audited.audit_warning:
        # Tier-2: the write happened (or genuinely failed) either way;
        # the audit problem is spoken, never swallowed into a log.
        response = f"{response} {audited.audit_warning}"

    return response


# RHINAL 13-tool wiring phase: handler names IntentRouter routes to for the
# 12 tools other than rhinal_capture (rhinal_attach_file is a named hard
# stop and has neither a client method nor a handler). Read-only tools call
# RhinalMCPClient directly -- no audit wrapping, matching mcp_audit.py's own
# scope ("non-GUI MCP *writes*"); a vault read has no external side effect
# to record. Write-capable tools go through audited_mcp_write(), reusing
# D16's mechanism exactly as its own module docstring recommended for "the
# eleven other verified-live RHINAL tools" -- now built rather than just
# invited.
_RHINAL_WRITE_CAPABLE_HANDLERS = frozenset({
    "rhinal_decision_log", "rhinal_idea_to_spec", "rhinal_tag_prediction",
    "rhinal_resolve_prediction", "rhinal_start_case",
})
_RHINAL_READ_ONLY_HANDLERS = frozenset({
    "rhinal_recall", "rhinal_ask_vault", "rhinal_classify_worthiness",
    "rhinal_confront", "rhinal_get_calibration_score", "rhinal_get_case_graph",
    "rhinal_check_contradiction",
})
RHINAL_OTHER_HANDLERS = _RHINAL_WRITE_CAPABLE_HANDLERS | _RHINAL_READ_ONLY_HANDLERS


def _summarize_rhinal_sources(sources) -> str:
    """Shared by recall/ask_vault: RHINAL's own tool description says the
    calling agent is expected to synthesize an answer from the cited
    sources (there is no server-side synthesis route to call instead --
    confirmed reading tools.ts). No LLM synthesis step exists in this
    dispatch layer and adding one is a real feature, not implied by wiring
    the tool -- so this reports the citation count and the strongest match's
    own summary, honestly, rather than fabricating a synthesized answer."""
    if not sources:
        return "I didn't find anything in your vault about that."
    top = sources[0]
    summary = top.get("summary") or top.get("source_quotes") or "(no summary)"
    plural = "" if len(sources) == 1 else f" ({len(sources)} sources found)"
    return f"Closest match from your vault{plural}: {summary}"


def handle_rhinal_other(handler: str, text: str, entities: Dict[str, Any]) -> str:
    """
    Dispatch for the 12 RHINAL tools other than rhinal_capture. Same
    "real callable, not inline elif-chain code" extraction rationale as
    handle_rhinal_capture -- and the same reason it matters more here:
    five of these are external writes into the physician's Rhinal vault
    or a tracked prediction/case, and a test that mirrors this branch's
    logic instead of calling it can pass while the real branch is broken.

    Every RhinalMCPClient method called below was written against a real
    read of RHINAL's mcp-server/src/{index,tools}.ts (see
    AgentCore/rhinal_mcp_client.py's own comment block), and every read-
    only tool plus check_contradiction was called live at least once
    against the real deployed backend before this dispatch code was
    written -- see the execution log's RHINAL 13-tool wiring entry.
    """
    from AgentCore.rhinal_mcp_client import RhinalCallError, RhinalConfigError, RhinalMCPClient

    # Lazy, not constructed until a call is actually about to be made --
    # matching handle_rhinal_capture's behavior of never touching the
    # client for an empty-input clarification prompt (RhinalMCPClient()
    # itself does no I/O, but the empty-input branches below are meant to
    # be genuine no-ops, and tests pin that with assert_not_called()).
    _client_holder: list = []

    def client() -> RhinalMCPClient:
        if not _client_holder:
            _client_holder.append(RhinalMCPClient())
        return _client_holder[0]

    def call_read_only(fn, missing_msg: str) -> str:
        try:
            return fn()
        except RhinalConfigError as e:
            return str(e)
        except RhinalCallError as e:
            return f"Couldn't reach Rhinal: {e}"

    if handler == "rhinal_recall":
        query = entities.get("rhinal_text", "")
        if not query:
            return "What would you like me to recall from your vault?"
        def do():
            result = client().recall(query)
            return _summarize_rhinal_sources(result.get("sources") or [])
        return call_read_only(do, "")

    if handler == "rhinal_ask_vault":
        question = entities.get("rhinal_text", "")
        if not question:
            return "What would you like to ask your vault?"
        def do():
            result = client().ask_vault(question)
            return _summarize_rhinal_sources(result.get("sources") or [])
        return call_read_only(do, "")

    if handler == "rhinal_classify_worthiness":
        content = entities.get("rhinal_text", "")
        if not content:
            return "What would you like me to check?"
        def do():
            result = client().classify_worthiness(content)
            worthy = result.get("vaultWorthy")
            reason = result.get("reason")
            verdict = "worth saving" if worthy else "probably not worth saving"
            return f"That looks {verdict}." + (f" ({reason})" if reason else "")
        return call_read_only(do, "")

    if handler == "rhinal_confront":
        outline = entities.get("rhinal_text", "")
        if not outline:
            return "What's your understanding that you want checked against your vault?"
        def do():
            result = client().confront(outline)
            if result.get("noResults"):
                return "I didn't find anything relevant in your vault to confront that against."
            n_correct = len(result.get("correct") or [])
            n_missed = len(result.get("missed") or [])
            n_contradicts = len(result.get("contradicts") or [])
            n_unverified = len(result.get("unverified") or [])
            parts = []
            if n_correct:
                parts.append(f"{n_correct} confirmed")
            if n_missed:
                parts.append(f"{n_missed} you missed")
            if n_contradicts:
                parts.append(f"{n_contradicts} contradicting your vault")
            if n_unverified:
                parts.append(f"{n_unverified} unverified")
            return "Checked against your vault: " + ", ".join(parts) + "." if parts else "No differences found."
        return call_read_only(do, "")

    if handler == "rhinal_get_calibration_score":
        def do():
            score = client().get_calibration_score()
            if not score:
                return "You don't have any calibration data yet -- tag a prediction first."
            return (
                f"Your calibration score is {score.get('calibrationScore')}, from "
                f"{score.get('resolvedPredictions')} of {score.get('totalPredictions')} "
                f"tracked predictions resolved."
            )
        return call_read_only(do, "")

    if handler == "rhinal_get_case_graph":
        case_id = entities.get("rhinal_text") or None
        def do():
            result = client().get_case_graph(case_id=case_id)
            if case_id:
                if not result:
                    return "I couldn't find that case."
                title = result.get("title", "(untitled)")
                return f"Case '{title}': {result.get('nodeCount', 0)} nodes, {result.get('edgeCount', 0)} edges."
            cases = result or []
            if not cases:
                return "You don't have any case graphs yet."
            names = ", ".join(c.get("title", "(untitled)") for c in cases[:5])
            more = f" and {len(cases) - 5} more" if len(cases) > 5 else ""
            return f"You have {len(cases)} case graph(s): {names}{more}."
        return call_read_only(do, "")

    if handler == "rhinal_check_contradiction":
        notion_id = entities.get("notion_id", "")
        def do():
            result = client().check_contradiction(notion_id)
            contradictions = result.get("contradictions") or []
            if not contradictions:
                return "No contradictions found for that record."
            return f"Found {len(contradictions)} contradiction(s) for that record."
        return call_read_only(do, "")

    # --- Write-capable tools: audited_mcp_write(), same field-value
    # reasoning as handle_rhinal_capture's docstring (why=text, source=
    # "voice", who left to emit_clinical_action()'s getpass.getuser()
    # default) -- not re-derived per tool, since none of that reasoning is
    # tool-specific.
    from AgentCore.mcp_audit import audited_mcp_write

    if handler == "rhinal_decision_log":
        content = entities.get("rhinal_text", "")
        if not content:
            return "I didn't catch the decision -- try 'log this decision: ...' with the decision included."
        audited = audited_mcp_write(
            what_adapter="rhinal_mcp", what_action="rhinal_decision_log",
            what_target="rhinal_vault", why=text, source="voice",
            call=lambda: client().decision_log(content),
        )
        return _rhinal_write_response(audited, "Logged that decision to your Rhinal vault.")

    if handler == "rhinal_idea_to_spec":
        content = entities.get("rhinal_text", "")
        if not content:
            return "I didn't catch the idea -- try 'turn this into a spec: ...' with the idea included."
        audited = audited_mcp_write(
            what_adapter="rhinal_mcp", what_action="rhinal_idea_to_spec",
            what_target="rhinal_vault", why=text, source="voice",
            call=lambda: client().idea_to_spec(content),
        )
        return _rhinal_write_response(audited, "Turned that into a spec in your Rhinal vault.")

    if handler == "rhinal_start_case":
        title = entities.get("rhinal_text", "")
        if not title:
            return "What should I call the new case?"
        audited = audited_mcp_write(
            what_adapter="rhinal_mcp", what_action="rhinal_start_case",
            what_target="rhinal_vault", why=text, source="voice",
            call=lambda: client().start_case(title),
        )
        return _rhinal_write_response(audited, f"Started a new case: {title}.")

    if handler == "rhinal_tag_prediction":
        notion_id = entities.get("notion_id", "")
        confidence = entities.get("confidence")
        audited = audited_mcp_write(
            what_adapter="rhinal_mcp", what_action="rhinal_tag_prediction",
            what_target="rhinal_vault", why=text, source="voice",
            call=lambda: client().tag_prediction(notion_id, confidence),
        )
        return _rhinal_write_response(audited, f"Tagged that record as a prediction at {confidence}% confidence.")

    if handler == "rhinal_resolve_prediction":
        notion_id = entities.get("notion_id", "")
        outcome = entities.get("outcome", "")
        audited = audited_mcp_write(
            what_adapter="rhinal_mcp", what_action="rhinal_resolve_prediction",
            what_target="rhinal_vault", why=text, source="voice",
            call=lambda: client().resolve_prediction(notion_id, outcome),
        )
        return _rhinal_write_response(audited, f"Resolved that prediction as {outcome}.")

    # Unreachable if IntentRouter and RHINAL_OTHER_HANDLERS stay in sync --
    # fails loudly rather than silently returning a fabricated success for
    # a handler this function does not actually know how to dispatch.
    raise ValueError(f"handle_rhinal_other: no dispatch for handler {handler!r}")


def _rhinal_write_response(audited, success_message: str) -> str:
    """Shared response-building for the 5 write-capable RHINAL tools --
    same three-way branch (blocked / ok / config-vs-call error) as
    handle_rhinal_capture, factored out since it doesn't vary per tool."""
    from AgentCore.rhinal_mcp_client import RhinalCallError, RhinalConfigError

    if audited.blocked:
        response = audited.blocked_reason
    elif audited.ok:
        response = success_message
    elif isinstance(audited.error, RhinalConfigError):
        response = str(audited.error)
    elif isinstance(audited.error, RhinalCallError):
        response = f"Couldn't reach Rhinal: {audited.error}"
    else:
        response = f"Something went wrong: {audited.error}"

    if audited.audit_warning:
        response = f"{response} {audited.audit_warning}"
    return response


_AFFIRMATIVE_WORDS = ("yes", "yeah", "yep", "sure", "confirm", "go ahead", "do it", "install it", "please", "continue")
_NEGATIVE_WORDS = ("no", "nope", "don't", "do not", "cancel", "nevermind", "never mind", "stop")

# Onboarding re-trigger and on-demand availability re-scan phrases.
# Matched as plain substrings against the lowercased turn, same style as
# goodbye_phrases -- checked before normal intent classification since
# these are service-level commands, not platform actions.
RUN_SETUP_PHRASES = ("run setup again", "run setup", "redo setup", "start setup")
RESCAN_PHRASES = ("check what's installed", "check whats installed", "scan for new apps", "rescan apps", "rescan for apps")


def _is_affirmative(text: str) -> bool:
    lower = text.lower().strip()
    return any(lower == w or lower.startswith(w + " ") or lower.startswith(w + ",") for w in _AFFIRMATIVE_WORDS)


def _is_negative(text: str) -> bool:
    lower = text.lower().strip()
    return any(lower == w or lower.startswith(w + " ") or lower.startswith(w + ",") for w in _NEGATIVE_WORDS)


@dataclass
class PendingResume:
    """Phase 2g: multi-turn state between a CAPTCHA/login-wall block and
    the physician completing it manually. Unlike PendingInstall, the
    NEXT turn is not assumed to be an answer to this -- only an explicit
    "continue"-style affirmative consumes it; anything else falls
    through to normal handling so other commands/questions still work
    while a browser sits blocked, and the pending state just stays alive
    until the physician is actually ready (bounded by the conversation
    loop's existing silence-timeout, so this can never truly hang
    forever)."""
    original_text: str
    reason: str


# Paths

# Paths
Alam_path = f"{getcwd()}\\Alam_data.txt"
file_path = f'{getcwd()}\\schedule.txt'

# Random dialogs
ran_online_dlg = random.choice(online_dlg)
ran_offline_dlg = random.choice(offline_dlg)


# ============================================================
# STATE MACHINE FOR PERSISTENT WAKE MODE
# ============================================================

class JarvisState(Enum):
    """JARVIS operational states."""
    SLEEP = "sleep"           # Listening for wake word only
    WAKE = "wake"             # Wake detected, acknowledging
    LISTEN = "listen"         # Listening for user input
    THINK = "think"           # Processing with LLM
    SPEAK = "speak"           # Speaking response
    ACTIVE = "active"         # Legacy: Listening for command
    EXECUTION = "execution"   # Executing command
    SHUTDOWN = "shutdown"     # Shutting down


class PersistentWakeService:
    """
    Persistent Wake System with Conversational Intelligence.
    
    Modes:
    - Normal: SLEEP → WAKE → ACTIVE → EXECUTION → SLEEP
    - Convo:  SLEEP → WAKE → LISTEN → THINK → SPEAK → LISTEN (loop)
    
    All FREE, offline, CPU-safe.
    """
    
    # Timeouts
    COMMAND_TIMEOUT = 15.0  # Seconds to wait for command after wake
    SILENCE_TIMEOUT = 30.0  # Seconds of silence before sleep
    
    def __init__(self, conversation_mode: bool = False, force_setup: bool = False):
        self.state = JarvisState.SLEEP
        self._running = False
        self._conversation_mode = conversation_mode
        self._force_setup = force_setup  # --setup CLI flag: re-run onboarding even if already done
        self._state_lock = threading.Lock()
        self._wake_detector = None
        self._stt = None

        # Sprint 6: Conversation components
        self._llm = None
        self._tts = None
        self._router = None
        self._cpu_guard = None
        self._conversation = None
        self._last_activity = time.time()
        self._pending_install = None  # Phase 2c: AgentCore.resolution_gate.PendingInstall
        self._pending_resume = None  # Phase 2g: PendingResume (CAPTCHA/login-wall)
        self._pending_level6_apply = None  # Phase D: AgentCore.level6.orchestrator.PendingLevel6Apply
        self._availability_rescanner = None  # periodic AvailabilityChecker refresh, see onboarding.py

        # Learning System (Sprint 8)
        self._learning = None

    def start(self):
        """Start the persistent wake service."""
        self._running = True

        # Initialize components
        if not self._initialize():
            print("[Service] Failed to initialize. Falling back to normal mode.")
            return False

        # First-run onboarding: once, ever, unless explicitly
        # re-triggered (--setup, or "run setup again" mid-session --
        # see the conversation loop below). The full walkthrough (banner,
        # visible scan, explanation) still only runs once -- what changed
        # is the compact status box below, which now runs every launch,
        # first-run included, replacing the old bare "=..." banner.
        from onboarding import is_first_run, run_onboarding
        if self._force_setup or is_first_run():
            run_onboarding(speak_fn=self._speak)
            self._force_setup = False

        # Transition to sleep mode
        self._set_state(JarvisState.SLEEP)

        # Start wake word detection
        self._start_wake_detection()

        # Periodic AvailabilityChecker re-scan -- closes Phase 2c's
        # "refresh at startup only" staleness gap. Configurable interval
        # (JARVIS_AVAILABILITY_RESCAN_INTERVAL_S env var), not hardcoded.
        from onboarding import PeriodicAvailabilityRescanner
        self._availability_rescanner = PeriodicAvailabilityRescanner()
        self._availability_rescanner.start()

        # Terminal identity -- orb + status box, every launch (§3.8).
        # Static frame only (~13ms): with import time already ~16s against
        # a <3s target, animating on every launch isn't defensible. The
        # full play() animation stays reserved for first-run onboarding
        # only, per the standing design decision -- not wired here, a
        # separate, smaller follow-up if it's ever picked up.
        from jarvis_orb import render_frame
        print(render_frame(0.6, 0.3))

        # Compact status box -- every launch (first run included, as the
        # standing header the full walkthrough above hands off to).
        from onboarding import render_status_box
        llm_model = self._llm.model if self._llm else None
        llm_ready = bool(self._llm and self._llm.is_available())
        wake_active = bool(self._wake_detector and self._wake_detector.is_listening)
        print(render_status_box(wake_active=wake_active, llm_model=llm_model, llm_ready=llm_ready))

        # Speak greeting
        self._speak("JARVIS online. Say Jarvis to wake me.")

        print("[Service] Listening for 'Jarvis'...")
        print("[Service] Press Ctrl+C to stop")

        # Main service loop
        try:
            while self._running:
                time.sleep(0.5)
        except KeyboardInterrupt:
            print("\n[Service] Interrupted by user")

        self.stop()
        return True
    
    def _initialize(self) -> bool:
        """Initialize wake detector and conversation components."""
        try:
            from WakeService.wake_detector import WakeDetector
            from WakeService.local_stt import LocalSTT
            
            self._wake_detector = WakeDetector(callback=self._on_wake_detected)
            self._stt = LocalSTT()
            
            print("[Service] Core components initialized")
            
            # Sprint 6: Initialize conversation components
            if self._conversation_mode:
                self._initialize_conversation()
            
            return True
            
        except ImportError as e:
            print(f"[Service] Import error: {e}")
            return False
        except Exception as e:
            print(f"[Service] Init error: {e}")
            return False
    
    def _set_state(self, new_state: JarvisState):
        """Transition to new state."""
        with self._state_lock:
            old_state = self.state
            self.state = new_state
            print(f"[State] {old_state.value} → {new_state.value}")
    
    def _start_wake_detection(self):
        """Start listening for wake word."""
        if self._wake_detector:
            self._wake_detector.start()
    
    def _stop_wake_detection(self):
        """Stop wake word detection."""
        if self._wake_detector:
            self._wake_detector.stop()
    
    def _on_wake_detected(self):
        """Called when 'Jarvis' is detected."""
        if self.state != JarvisState.SLEEP:
            return  # Ignore if not in sleep mode
        
        print("[Service] Wake word detected!")
        
        # Transition to WAKE state
        self._set_state(JarvisState.WAKE)
        
        # Stop wake detection to free mic
        self._stop_wake_detection()
        
        # Acknowledge
        self._speak("Yes?")
        
        # Route based on mode
        if self._conversation_mode:
            self._set_state(JarvisState.LISTEN)
            self._conversation_loop()
        else:
            # Legacy: ACTIVE → single command → SLEEP
            self._set_state(JarvisState.ACTIVE)
            self._listen_for_command()
    
    def _listen_for_command(self):
        """Listen for a single command with timeout."""
        print(f"[Service] Listening for command ({self.COMMAND_TIMEOUT}s timeout)...")
        
        start_time = time.time()
        command = None
        
        while time.time() - start_time < self.COMMAND_TIMEOUT:
            if not self._running:
                break
            
            # Listen for speech
            text = self._stt.listen_once(timeout=5.0)
            
            if text:
                text = text.strip().lower()
                print(f"[Service] Heard: '{text}'")
                
                # Check for cancel phrases
                if any(phrase in text for phrase in ["never mind", "cancel", "stop", "go to sleep"]):
                    self._speak("Going to sleep")
                    break
                
                # Check for shutdown
                if any(phrase in text for phrase in ["shut down", "shutdown"]):
                    self._speak("Are you sure you want to shut down? Say yes to confirm.")
                    confirm = self._stt.listen_once(timeout=5.0)
                    if confirm and "yes" in confirm.lower():
                        self._speak("Shutting down. Goodbye.")
                        self._running = False
                        break
                    else:
                        self._speak("Shutdown cancelled")
                        continue
                
                # Valid command
                command = text
                break
        
        # Execute command if we have one
        if command:
            self._execute_command(command)
        else:
            print("[Service] No command received")
        
        # Return to sleep
        self._return_to_sleep()
    
    def _execute_command(self, command: str):
        """Execute command through existing JARVIS system."""
        self._set_state(JarvisState.EXECUTION)
        print(f"[Service] Executing: '{command}'")
        
        try:
            # Write to input.txt for co_brain to process
            input_file = os.path.join(getcwd(), "input.txt")
            
            # Add jarvis prefix if not present
            if not command.startswith("jarvis"):
                command = f"jarvis {command}"
            
            with open(input_file, "w") as f:
                f.write(command)
            
            print(f"[Service] Command written to input.txt")
            
            # Give co_brain time to process
            time.sleep(1.0)
            
        except Exception as e:
            print(f"[Service] Execution error: {e}")
            self._speak(f"Error: {str(e)[:30]}")

    def _handle_install_confirmation(self, text: str) -> str:
        """Phase 2c: handle the user's reply to "want me to install it?".
        Always clears self._pending_install and returns a distinct,
        honest message -- confirm+install+retry, decline, or no winget
        match. Never auto-installs; an ambiguous reply is treated the
        same as a decline (never install without a clear yes)."""
        pending = self._pending_install
        self._pending_install = None
        from onboarding import clear_pending_state
        clear_pending_state()

        if not _is_affirmative(text):
            return f"Okay, I won't install {pending.platform_display_name}."

        if pending.winget_id is None:
            return (
                f"I can't find {pending.platform_display_name} in the Windows "
                f"package manager -- you'll need to install it manually."
            )

        package_id, source = pending.winget_id
        print(f"[Install] Installing {pending.platform_display_name} ({package_id} via {source})...")
        from platform_adapters.winget_installer import install as winget_install
        result = winget_install(package_id, source)

        if not result.ok:
            return f"Couldn't install {pending.platform_display_name}: {result.message}"

        # Refresh availability so the retry below sees it as installed.
        from AgentCore.resolution_gate import _get_default_availability_checker
        _get_default_availability_checker().refresh()

        # Retry the original command now that the app is installed.
        if hasattr(self, '_odav') and self._odav:
            retry_result = self._odav.execute(pending.original_text)
            retry_msg = retry_result.message if retry_result.success else f"Failed: {retry_result.message}"
            return f"Installed {pending.platform_display_name}. {retry_msg}"

        return f"Installed {pending.platform_display_name}."

    def _handle_level6_apply_confirmation(self, text: str) -> str:
        """Phase D: handle the user's reply to "want me to apply it?"
        for a verified Level6 plan. Always clears
        self._pending_level6_apply and returns a distinct, honest
        message -- applied+file list, declined, or apply_failed+reverted.
        Never applies without a clear yes -- same standard as
        _handle_install_confirmation (Phase 2c): an ambiguous reply is
        treated the same as a decline."""
        pending = self._pending_level6_apply
        self._pending_level6_apply = None

        if not _is_affirmative(text):
            return "Okay, I won't apply that change."

        global LEVEL6_ENGINE
        result = LEVEL6_ENGINE.apply(pending)

        if result.get("status") == "applied":
            files = ", ".join(result.get("files", []))
            return f"Applied: {files}."

        reverted_note = " and reverted" if result.get("reverted") else ""
        return f"Apply failed{reverted_note}: {result.get('reason')}"

    def _handle_resume(self, text: str) -> str:
        """Phase 2g: handle an affirmative "continue" after a CAPTCHA/
        login-wall block. Re-executes the ORIGINAL command -- the
        browser session persisted (platform_adapters/browser_automation.py's
        shared session), so this re-checks the block and, if the
        physician actually cleared it, proceeds with the real action.
        Always clears self._pending_resume first: if the retry hits a
        NEW block (e.g. a second CAPTCHA, or the same one because it
        wasn't actually solved), a fresh PendingResume is set by the
        normal "action" handler path this delegates to -- never leaves
        stale pending state around."""
        pending = self._pending_resume
        self._pending_resume = None
        from onboarding import clear_pending_state, persist_pending_state
        clear_pending_state()

        if pending is None:
            # Defensive: the real conversation loop only calls this when
            # self._pending_resume is not None (see the dispatch check
            # above), so this shouldn't be reachable there -- but a
            # direct/future-refactor call with no pending state should
            # get an honest answer, not an AttributeError crash.
            return "Nothing is waiting to be resumed."

        if not (hasattr(self, '_odav') and self._odav):
            return f"Still blocked: {pending.reason}"

        result = self._odav.execute(pending.original_text)
        if getattr(result, "blocked", False):
            self._pending_resume = PendingResume(original_text=pending.original_text, reason=result.message)
            persist_pending_state("resume", result.message)
            return result.message
        if result.success:
            return f"Continuing... {result.message}"
        return f"Continued, but it still failed: {result.message}"

    def _return_to_sleep(self):
        """Return to sleep mode."""
        self._set_state(JarvisState.SLEEP)
        
        # Restart wake detection
        if self._wake_detector:
            self._wake_detector.reset()
            self._wake_detector.start()
        
        print("[Service] Listening for 'Jarvis'...")
    
    def _speak(self, text: str):
        """Speak using TTS."""
        try:
            # Use Sprint 6 TTS if available
            if self._tts:
                self._tts.speak(text)
            else:
                speak(text)
        except Exception as e:
            print(f"[Service] TTS error: {e}")
            # Fallback
            try:
                import pyttsx3
                engine = pyttsx3.init()
                engine.say(text)
                engine.runAndWait()
            except:
                print(f"[JARVIS] {text}")

    _SENTENCE_BOUNDARY_RE = re.compile(r'[.!?]\s+')

    # Adversarial finding while testing this (2026-07-30): the naive
    # version of this split "Dr. Smith will see the patient at 3pm."
    # into "Dr." + "Smith will see the patient at 3pm." -- a genuinely
    # bad failure mode for a physician-facing voice product, since "Dr."
    # is about as common a token as this system will ever speak. Not a
    # general sentence-boundary solver (that's NLTK/spaCy territory) --
    # a bounded, honest guard against the abbreviations most likely to
    # appear in this system's actual conversational output.
    # Deliberately conservative -- "no" or "fig" were considered and
    # dropped: both are common standalone words/sentence-starters (e.g.
    # "No, that's not right.") in ordinary conversation, and including
    # them would trade a rare abbreviation-splitting glitch for a more
    # common false suppression of a real sentence boundary. Kept to
    # titles/honorifics and academic-style abbreviations, which are
    # unambiguous almost everywhere they appear.
    _ABBREVIATIONS = {
        "dr", "mr", "mrs", "ms", "prof", "sr", "jr", "st",
        "vs", "etc", "e.g", "i.e", "approx",
    }

    def _stream_and_speak_chat(self, messages, system) -> str:
        """
        S0-E9: streams LLMEngine.chat_stream() and speaks each completed
        sentence as it arrives, instead of the old chat()-then-speak
        path that waited for the entire response before saying a word
        (live-measured: ~23.7s of silence for a 3-sentence answer,
        vs. a first chunk at ~2.3s). Returns the full accumulated text
        so the caller can still store it in conversation history.

        Sentence-level, not token-level: speaking mid-word or mid-clause
        as raw tokens arrive would sound worse than the flat TTS voice
        already does, not better -- the win is starting sooner, not
        chopping speech into fragments.
        """
        buffer = ""
        full_text = ""

        for chunk in self._llm.chat_stream(messages, system):
            buffer += chunk
            full_text += chunk
            buffer = self._speak_complete_sentences(buffer)

        # Speak whatever's left -- the final sentence often has no
        # trailing punctuation captured before the stream ends.
        if buffer.strip():
            self._speak(buffer.strip())

        return full_text.strip()

    def _speak_complete_sentences(self, buffer: str) -> str:
        """
        Speaks every complete sentence in buffer, skipping boundaries
        that are really just an abbreviation ("Dr.", "e.g.") rather than
        a real sentence end. Returns whatever's left unspoken (the
        trailing incomplete sentence, or the abbreviation-adjacent text
        that needs more input before it can be judged).
        """
        last_spoken_end = 0
        for match in self._SENTENCE_BOUNDARY_RE.finditer(buffer):
            candidate = buffer[last_spoken_end:match.start() + 1].strip()
            last_word = candidate.rstrip(".!?").split()[-1].lower() if candidate else ""
            if last_word in self._ABBREVIATIONS:
                continue  # not a real boundary -- keep accumulating
            if candidate:
                self._speak(candidate)
            last_spoken_end = match.end()

        return buffer[last_spoken_end:]

    # ============================================================
    # SPRINT 6: CONVERSATIONAL INTELLIGENCE
    # ============================================================
    
    def _initialize_conversation(self):
        """Initialize Sprint 6+7 conversation components."""
        try:
            from AgentCore.llm_engine import LLMEngine
            from AgentCore.tts_engine import TTSEngine
            from AgentCore.intent_router import IntentRouter
            from AgentCore.cpu_guard import CPUGuard
            from AgentCore.conversation_manager import ConversationManager
            from AgentCore.prompt_templates import PromptTemplates
            
            self._llm = LLMEngine()
            # S0-E9: warm the model in the background rather than blocking
            # startup on it -- a cold-load measured ~7.6s live, and startup
            # is already ~16s against a <3s target (D3). By the time wake
            # word + STT actually produce a first utterance, the model
            # should already be resident in memory.
            if self._llm.is_available():
                threading.Thread(target=self._llm.warm_up, daemon=True).start()
            self._tts = TTSEngine()
            self._router = IntentRouter()
            self._cpu_guard = CPUGuard()
            self._conversation = ConversationManager()
            
            # Set JARVIS system prompt
            self._conversation.set_system(PromptTemplates.JARVIS_SYSTEM)
            
            # Start CPU monitoring
            self._cpu_guard.start()
            
            # Sprint 7: RAG and ODAV
            try:
                from AgentCore.rag_engine import RAGEngine
                from AgentCore.odav_loop import ODAVLoop
                
                self._rag = RAGEngine()
                self._odav = ODAVLoop()
                print("[Service] RAG + ODAV initialized")
            except ImportError as e:
                print(f"[Service] RAG/ODAV not available: {e}")
                self._rag = None
                self._odav = None
            
            print("[Service] Conversation components initialized")
            print(f"[Service] LLM Available: {self._llm.is_available()}")
            
            # Sprint 8: Learning System (guarded)
            if _LEARNING_AVAILABLE and _learning_gate and _learning_gate.enabled('learning_system'):
                try:
                    self._learning = LearningSystem()
                    print("[Service] Learning System initialized (shadow mode)")
                except Exception as le:
                    print(f"[Service] Learning System init skipped: {le}")
                    self._learning = None
            
        except Exception as e:
            print(f"[Service] Conversation init error: {e}")
            self._conversation_mode = False
    
    def _conversation_loop(self):
        """
        Multi-turn conversation loop.
        
        LISTEN → THINK → SPEAK → LISTEN (repeat)
        Exit on: silence timeout, goodbye, or max turns
        """
        global MODE_ENGINE, LEVEL6_ENGINE
        turn_count = 0
        max_turns = 20
        goodbye_phrases = ["goodbye", "bye", "go to sleep", "stop listening", "that's all"]
        
        print("[Convo] Entering conversation loop...")
        self._last_activity = time.time()
        
        while self._running and turn_count < max_turns:
            # Check silence timeout
            if time.time() - self._last_activity > self.SILENCE_TIMEOUT:
                print("[Convo] Silence timeout")
                self._speak("Going to sleep.")
                break
            
            # LISTEN
            self._set_state(JarvisState.LISTEN)
            text = self._stt.listen_once(timeout=8.0)
            
            if not text:
                continue
            
            text = text.strip()
            print(f"[Convo] User: '{text}'")

            self._last_activity = time.time()
            turn_count += 1
            
            # Check goodbye
            if any(phrase in text.lower() for phrase in goodbye_phrases):
                self._speak("Goodbye.")
                break

            # On-demand full setup re-run (discoverable per onboarding's
            # own closing message: "run this walkthrough again anytime").
            if any(phrase in text.lower() for phrase in RUN_SETUP_PHRASES):
                self._set_state(JarvisState.EXECUTION)
                from onboarding import run_onboarding
                run_onboarding(speak_fn=self._speak)
                self._set_state(JarvisState.LISTEN)
                self._last_activity = time.time()
                continue

            # On-demand availability re-scan -- forces an immediate
            # refresh outside the periodic cycle, reusing the exact same
            # AvailabilityChecker.refresh() the periodic thread and
            # onboarding's own scan use (see onboarding.rescan_now).
            if any(phrase in text.lower() for phrase in RESCAN_PHRASES):
                self._set_state(JarvisState.EXECUTION)
                from onboarding import rescan_now
                response = rescan_now()
                self._set_state(JarvisState.SPEAK)
                print(f"[Convo] JARVIS: '{response}'")
                self._speak(response)
                self._last_activity = time.time()
                continue

            # Phase 2c: pending install confirmation takes priority over
            # normal classification -- this turn is answering "want me to
            # install it?", not a new command.
            if self._pending_install is not None:
                self._set_state(JarvisState.EXECUTION)
                response = self._handle_install_confirmation(text)
                self._set_state(JarvisState.SPEAK)
                print(f"[Convo] JARVIS: '{response[:100]}...'")
                self._speak(response)
                self._last_activity = time.time()
                continue

            # Phase D: pending Level6 apply confirmation -- same priority
            # and "never act without a clear yes" standard as pending
            # install. This turn is answering "want me to apply it?",
            # not a new command.
            if self._pending_level6_apply is not None:
                self._set_state(JarvisState.EXECUTION)
                response = self._handle_level6_apply_confirmation(text)
                self._set_state(JarvisState.SPEAK)
                print(f"[Convo] JARVIS: '{response[:100]}...'")
                self._speak(response)
                self._last_activity = time.time()
                continue

            # Phase 2g: pending resume (CAPTCHA/login-wall) -- unlike
            # pending install, only an explicit affirmative consumes this;
            # anything else falls through to normal handling below so
            # other commands/questions still work while a browser sits
            # blocked (see PendingResume's docstring for why).
            if self._pending_resume is not None and _is_affirmative(text):
                self._set_state(JarvisState.EXECUTION)
                response = self._handle_resume(text)
                self._set_state(JarvisState.SPEAK)
                print(f"[Convo] JARVIS: '{response[:100]}...'")
                self._speak(response)
                self._last_activity = time.time()
                continue

            # Route intent
            intent = self._router.classify(text)
            print(f"[Convo] Intent: {intent.intent_type.value} → {intent.handler}")
            
            # Learning System: enhanced classification (shadow mode)
            if self._learning and self._learning.gate.enabled('intent_graph'):
                try:
                    ls_intent = self._learning.intent.classify_intent(text)
                    print(f"[Learning] Intent type: {ls_intent.intent_type} (conf={ls_intent.confidence:.2f})")
                except Exception:
                    pass  # non-critical, shadow only
            
            # THINK
            self._set_state(JarvisState.THINK)
            
            response = None
            response = None
            spoken_already = False

            # --- ADDITION: Level-6 Engine Hook ---
            try:
                from AgentCore.feature_gate import is_enabled as feature_enabled
                if feature_enabled("level6_engine"):
                    from AgentCore.level6.orchestrator import Level6Coordinator
                    if 'LEVEL6_ENGINE' not in globals():
                        global LEVEL6_ENGINE
                        # Previously constructed with no llm= argument at
                        # all, so Planner always fell back to
                        # _mock_plan() (an empty plan) regardless of
                        # anything else about Level6 -- it was
                        # unreachable in practice even when enabled.
                        from AgentCore.code_engine.tier2.llm_adapter import LLMAdapter
                        LEVEL6_ENGINE = Level6Coordinator(llm=LLMAdapter())
                    
                    # Heuristic: If text implies complex refactor or contains "architect", "debug", "refactor"
                    is_complex = any(k in text.lower() for k in ["architect", "refactor", "debug", "fix", "level 6"])
                    
                    if is_complex:
                         print(f"[Level-6] Handling request: {text}")
                         res = LEVEL6_ENGINE.handle_request(text, context={"user":"owner", "cwd":os.getcwd()})
                         if res.get("plan"):
                             print(json.dumps(res["plan"], indent=2))

                         if res.get("status") == "verified":
                             # Phase D: never apply automatically -- hold
                             # a pending confirmation and ask, same
                             # standard as the install-confirmation gate
                             # (Phase 2c). The next turn answers this,
                             # not a new command (see the
                             # _pending_level6_apply routing check above).
                             from AgentCore.level6.orchestrator import PendingLevel6Apply
                             self._pending_level6_apply = PendingLevel6Apply(
                                 request_id=res["request_id"],
                                 plan=res["plan"],
                                 sandbox_dir=res["sandbox_result"].get("sandbox_dir", ""),
                                 target_dir=res.get("target_dir", os.getcwd()),
                                 explain=res.get("explain"),
                                 risk_score=res.get("risk_score", 0.0),
                             )
                             files = ", ".join(
                                 step.get("target", "") for step in res["plan"] if step.get("target")
                             )
                             self._speak(
                                 f"I have a verified fix ready: {res.get('explain') or 'no summary given'}. "
                                 f"Files: {files or 'none'}. Want me to apply it?"
                             )
                         else:
                             self._speak(f"Level-6 Plan: {res.get('status')}. Risk: {res.get('risk_score')}")
                         continue
            except Exception as e:
                print(f"[Level-6] Error: {e}")
            # --- END LEVEL-6 ADDITION ---

            # Code Engine Hook
            if intent.handler == "code_engine" and CODE_ENGINE:
                self._set_state(JarvisState.EXECUTION)
                print(f"[CodeEngine] Handling: {text}")
                result = CODE_ENGINE.handle_command(text, context={"user": "owner", "cwd": os.getcwd()})
                if _code_result_is_success(result):
                    if result.get("dry_run", True):
                        response = f"I have prepared a dry run: {result.get('patch_summary')}"
                    else:
                        response = f"I have written the file at {result.get('file_path')}"
                else:
                    response = f"Code task failed: no output produced for '{text}'"

            elif intent.handler == "rhinal_capture":
                # RHINAL MCP integration: capture a thought into the
                # physician's Rhinal vault. Same "special handler checked
                # directly in this elif chain" shape as code_engine above
                # -- not routed through CommandRouter/ResolutionGate/
                # AdapterBase, since Rhinal isn't a GUI platform with an
                # install-detection question; it's always available if
                # configured, unavailable (with an honest reason) if not.
                #
                # DEC-002/D15: this branch bypasses the Intent path, so it
                # also bypasses UIExecutor.execute_intent(), the audit
                # chokepoint -- an external vault write with no record.
                # Closed in handle_rhinal_capture() via AgentCore.mcp_audit,
                # which reuses the audit *mechanism* without routing this
                # through the GUI-shaped machinery described above.
                self._set_state(JarvisState.EXECUTION)
                response = handle_rhinal_capture(
                    text, intent.extracted_entities.get("capture_text", "")
                )

            elif intent.handler in RHINAL_OTHER_HANDLERS:
                # RHINAL 13-tool wiring phase: same non-Intent-path shape as
                # rhinal_capture above, for the same reason (not a GUI
                # platform, no install-detection question). Read-only tools
                # have no audit chokepoint gap to close (mcp_audit.py's own
                # scope is external writes); the 5 write-capable tools are
                # individually wrapped in audited_mcp_write() inside
                # handle_rhinal_other() itself.
                self._set_state(JarvisState.EXECUTION)
                response = handle_rhinal_other(intent.handler, text, intent.extracted_entities)

            elif intent.handler == "action":
                # Execute action with ODAV loop if available
                self._set_state(JarvisState.EXECUTION)
                if hasattr(self, '_odav') and self._odav:
                    result = self._odav.execute(text)
                    if getattr(result, "blocked", False):
                        # Phase 2g: CAPTCHA/login-wall -- pause, tell the
                        # physician plainly, wait for "continue". Not a
                        # failure, not a silent retry, not an infinite hang.
                        if self._pending_resume is not None:
                            # A second block arrived while an earlier one
                            # was still unresolved. There is only one
                            # pending-resume slot, so the earlier one is
                            # about to be replaced -- say so plainly
                            # instead of silently dropping it (found via
                            # adversarial testing: without this, saying
                            # "continue" later would silently retry the
                            # WRONG command with no indication the first
                            # block was ever abandoned).
                            response = (
                                f"Note: I still had '{self._pending_resume.original_text}' waiting on "
                                f"a manual step -- switching to this new one instead. {result.message}"
                            )
                        else:
                            response = f"{result.message}"
                        self._pending_resume = PendingResume(original_text=text, reason=result.message)
                        from onboarding import persist_pending_state
                        persist_pending_state("resume", result.message)
                    else:
                        response = result.message if result.success else f"Failed: {result.message}"
                else:
                    self._execute_command(text)
                    response = "Done."

            elif intent.handler == "action_no_adapter":
                # Phase 2c gate: platform recognized, no real adapter --
                # do not offer to install (a fabricated/nonexistent
                # adapter means installing wouldn't make it controllable).
                gate_result = intent.extracted_entities.get("gate_result")
                response = gate_result.message if gate_result else "I don't know how to control that yet."

            elif intent.handler == "action_not_installed":
                # Phase 2c gate: real adapter exists, app isn't installed.
                # Offer to install; wait for explicit confirmation next turn.
                gate_result = intent.extracted_entities.get("gate_result")
                if gate_result:
                    from AgentCore.resolution_gate import PendingInstall
                    self._pending_install = PendingInstall(
                        original_text=text,
                        platform_display_name=gate_result.platform_display_name,
                        adapter_key=gate_result.adapter_key,
                        winget_id=gate_result.winget_id,
                    )
                    from onboarding import persist_pending_state
                    persist_pending_state("install", f"install {gate_result.platform_display_name}")
                    response = gate_result.message
                else:
                    response = "That app isn't installed."

            elif intent.handler == "llm" and self._llm and self._llm.is_available():
                # Check CPU before LLM
                if self._cpu_guard and not self._cpu_guard.should_proceed("llm"):
                    response = "System is busy. Please try again."
                else:
                    # Use RAG if available for grounded answers
                    if hasattr(self, '_rag') and self._rag:
                        rag_response = self._rag.query(text, notify=self._speak)
                        response = rag_response.text
                    else:
                        # Standard LLM response -- streamed (S0-E9).
                        # chat() waited for the full response before
                        # speaking anything; live-measured, that's ~23.7s
                        # of silence vs. a first chunk at ~2.3s. Speaks
                        # each completed sentence as it arrives instead
                        # of waiting for the whole thing, then skips the
                        # generic end-of-loop self._speak(response) below
                        # via spoken_already so the answer isn't spoken
                        # twice.
                        self._conversation.add_user(text)
                        system, messages = self._conversation.get_context()

                        self._set_state(JarvisState.SPEAK)
                        response = self._stream_and_speak_chat(messages, system)
                        spoken_already = True

                    self._conversation.add_assistant(response)
                    
            elif intent.handler == "canned":
                # Simple response
                if intent.intent_type.value == "confirm":
                    response = "Okay."
                elif intent.intent_type.value == "abort":
                    response = "Cancelled."
                    break
            
            if not response:
                response = "I'm not sure how to help with that."

            # SPEAK
            self._set_state(JarvisState.SPEAK)
            print(f"[Convo] JARVIS: '{response[:100]}...'")
            if not spoken_already:
                self._speak(response)
            self._last_activity = time.time()
        
        # Return to sleep
        print(f"[Convo] Exiting after {turn_count} turns")
        self._return_to_sleep()
    
    def stop(self):
        """Stop the service."""
        print("[Service] Stopping...")
        self._running = False
        self._set_state(JarvisState.SHUTDOWN)

        if self._wake_detector:
            self._wake_detector.stop()

        if self._cpu_guard:
            self._cpu_guard.stop()

        if self._availability_rescanner:
            self._availability_rescanner.stop()

        print("[Service] Stopped")


# ============================================================
# NORMAL INTERACTIVE MODE (Original behavior)
# ============================================================

def main():
    """Normal interactive mode with browser STT."""
    if is_Online():
        t1 = threading.Thread(target=speak, args=(ran_online_dlg,))
        t3 = threading.Thread(target=check_plug)
        t4 = threading.Thread(target=check_schedule, args=(file_path,))
        t5 = threading.Thread(target=Jarvis)
        t6 = threading.Thread(target=check_Alam, args=(Alam_path,))
        t1.start()
        t1.join()
        t3.start()
        t4.start()
        t5.start()
        t6.start()
        t3.join()
        t4.join()
        t5.join()
        t6.join()
    else:
        Alert(ran_offline_dlg)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    # Parse command line
    if "--health" in sys.argv:
        # Health check — show learning system status
        print("JARVIS Health Check")
        print("=" * 40)
        if _LEARNING_AVAILABLE:
            ls = LearningSystem()
            import json
            print(json.dumps(ls.health(), indent=2))
            pending = 0
            if ls.human:
                pending = ls.human.pending_count()
            print(f"Pending approvals: {pending}")
        else:
            print("Learning system: NOT INSTALLED")
        sys.exit(0)
    elif "--validate-platforms" in sys.argv:
        print("--- [Invariant 1] Startup Validation ---")
        try:
            from AgentCore.ui_agent.ui_agent_main import UIAgentMain
            agent = UIAgentMain()
            
            from AgentCore.ui_agent.adapter_registry import registry
            platforms = set()
            for alist in registry.adapters.values():
                for a in alist:
                    if hasattr(a, 'platform'): platforms.add(a.platform.lower())
            
            search_path = "AgentCore/platform_adapters"
            folders = [f.name for f in os.scandir(search_path) if f.is_dir() and f.name != "__pycache__"]
            
            print(f"✅ No uncaught exceptions")
            print(f"✅ Folder count: {len(folders)}")
            print(f"✅ Registration count: {len(platforms)}")
            
            if len(platforms) >= len(folders):
                print("✅ Count of discovered folders <= count of registered platforms")
            else:
                print(f"🚨 FAILED: {len(folders)} folders but only {len(platforms)} platforms")
                
        except Exception as e:
            print(f"🚨 FAILED: Startup Validation Exception: {e}")
            sys.exit(1)
            
    elif "--dry-run" in sys.argv:
        # Step 3: Planner Hard Invariant
        instruction = sys.argv[sys.argv.index("--dry-run") + 1] if len(sys.argv) > sys.argv.index("--dry-run") + 1 else "unknown"
        from AgentCore.ui_agent.ui_agent_main import UIAgentMain
        import json
        agent = UIAgentMain()
        
        # We need a way to get the plan without execution
        intent = agent._infer_action(instruction)
        if "unknown" in instruction:
             intent["platform"] = "unknown_app"
             
        adapter, plan = agent.planner.plan(intent, {})
        
        output = {
            "plan_length": len(plan),
            "fallback_level": "unknown" if "UnknownAppFallback" in adapter.__class__.__name__ else "ui",
            "adapter": adapter.__class__.__name__
        }
        print(json.dumps(output, indent=2))
        sys.exit(0)

    elif "--simulate-ui" in sys.argv:
        # Step 4: Native -> UI Fallback
        instruction = sys.argv[sys.argv.index("--simulate-ui") + 1]
        from AgentCore.ui_agent.ui_agent_main import UIAgentMain
        agent = UIAgentMain()
        # Enable vision for log flow
        agent.vision_enabled = True
        # Pass dry_run=False to actually trigger the escalation ladder
        result = agent.execute_instruction(instruction, dry_run=False)
        print("--- Execution Trace ---")
        for step in result.steps:
             print(f"[{step.get('fallback', 'ui')}] {step.get('action')} on {step.get('target')}: {'OK' if step.get('ok') else 'FAIL'}")
        sys.exit(0)

    elif "--enable-ui-exec" in sys.argv:
        # Step 6: End-to-End Autonomous UI Test
        instruction = sys.argv[sys.argv.index("--enable-ui-exec") + 1]
        print(f"--- [Invariant 6] End-to-End UI Execution (Instruction: {instruction}) ---")
        
        from AgentCore.ui_agent.ui_agent_main import UIAgentMain
        agent = UIAgentMain()
        agent.vision_enabled = True
        agent.exec_enabled = True # Gate 1
        
        # Plain text confirmation
        print("CONFIRMATION REQUIRED: Autonomous execution detected.")
        print(f"Do you want to proceed with: '{instruction}'? [y/n]: ", end="")
        print("y (Simulated)")
        
        result = agent.execute_instruction(instruction, dry_run=False)
        print("--- Execution Trace ---")
        for step in result.steps:
             print(f"[{step.get('fallback', 'ui')}] {step.get('action')} on {step.get('target')}: {'OK' if step.get('ok') else 'FAIL'}")
        
        print(f"Status: {result.success}")
        sys.exit(0)

    elif "--background" in sys.argv or "--daemon" in sys.argv:
        # Background process with minimal output (voice conversation loop,
        # same as --convo, just quieter). Renamed from --daemon: that name
        # implied this invokes daemon/dispatcher.py's CommandDispatcher (the
        # text-command dispatcher reachable via `python -m daemon.cli`) --
        # it never did, and still doesn't. --daemon is kept as a deprecated
        # alias so existing scripts/muscle memory don't break.
        if "--daemon" in sys.argv:
            print("[Deprecated] --daemon has been renamed to --background (it never invoked daemon/dispatcher.py; that name was misleading). Use --background going forward.")
        print("Starting JARVIS in BACKGROUND mode...")
        import logging
        logging.basicConfig(level=logging.WARNING)  # Suppress most output
        service = PersistentWakeService(conversation_mode=True, force_setup=("--setup" in sys.argv))
        service.start()
    elif "--convo" in sys.argv:
        # Conversational mode - LLM + multi-turn
        print("Starting JARVIS in CONVERSATION mode...")
        service = PersistentWakeService(conversation_mode=True, force_setup=("--setup" in sys.argv))
        success = service.start()

        if not success:
            print("Conversation mode failed. Running normal mode...")
            main()
    elif "--service" in sys.argv or os.environ.get("JARVIS_SERVICE_MODE"):
        # Persistent wake mode - FREE, OFFLINE, LOW CPU
        print("Starting JARVIS in SERVICE mode...")
        service = PersistentWakeService(conversation_mode=False, force_setup=("--setup" in sys.argv))
        success = service.start()
        
        if not success:
            print("Service failed. Running normal mode...")
            main()
    else:
        # Normal interactive mode
        main()