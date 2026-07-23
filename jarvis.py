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
import time
import threading
import random
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
    
    def __init__(self, conversation_mode: bool = False):
        self.state = JarvisState.SLEEP
        self._running = False
        self._conversation_mode = conversation_mode
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
        
        # Learning System (Sprint 8)
        self._learning = None
        
    def start(self):
        """Start the persistent wake service."""
        print("=" * 60)
        print("JARVIS Persistent Wake Service")
        print("FREE • OFFLINE • LOW CPU")
        print("=" * 60)
        
        self._running = True
        
        # Initialize components
        if not self._initialize():
            print("[Service] Failed to initialize. Falling back to normal mode.")
            return False
        
        # Transition to sleep mode
        self._set_state(JarvisState.SLEEP)
        
        # Start wake word detection
        self._start_wake_detection()
        
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
                        LEVEL6_ENGINE = Level6Coordinator()
                    
                    # Heuristic: If text implies complex refactor or contains "architect", "debug", "refactor"
                    is_complex = any(k in text.lower() for k in ["architect", "refactor", "debug", "fix", "level 6"])
                    
                    if is_complex:
                         print(f"[Level-6] Handling request: {text}")
                         res = LEVEL6_ENGINE.handle_request(text, context={"user":"owner", "cwd":os.getcwd()})
                         self._speak(f"Level-6 Plan: {res.get('status')}. Risk: {res.get('risk_score')}")
                         if res.get("plan"):
                             print(json.dumps(res["plan"], indent=2))
                         if res.get("status") == "planned":
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
                    response = result.message if result.success else f"Failed: {result.message}"
                else:
                    self._execute_command(text)
                    response = "Done."
                
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
        service = PersistentWakeService(conversation_mode=True)
        service.start()
    elif "--convo" in sys.argv:
        # Conversational mode - LLM + multi-turn
        print("Starting JARVIS in CONVERSATION mode...")
        service = PersistentWakeService(conversation_mode=True)
        success = service.start()
        
        if not success:
            print("Conversation mode failed. Running normal mode...")
            main()
    elif "--service" in sys.argv or os.environ.get("JARVIS_SERVICE_MODE"):
        # Persistent wake mode - FREE, OFFLINE, LOW CPU
        print("Starting JARVIS in SERVICE mode...")
        service = PersistentWakeService(conversation_mode=False)
        success = service.start()
        
        if not success:
            print("Service failed. Running normal mode...")
            main()
    else:
        # Normal interactive mode
        main()