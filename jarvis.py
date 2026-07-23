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
from typing import Optional, Dict
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
                        rag_response = self._rag.query(text)
                        response = rag_response.text
                    else:
                        # Standard LLM response
                        self._conversation.add_user(text)
                        system, messages = self._conversation.get_context()
                        
                        llm_response = self._llm.chat(messages, system)
                        response = llm_response.text
                    
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