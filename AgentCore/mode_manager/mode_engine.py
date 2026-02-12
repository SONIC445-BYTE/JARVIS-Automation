import yaml
import os
import threading
from pathlib import Path

from AgentCore.mode_manager.intent_rules import match_rules
from AgentCore.mode_manager.confidence import classify_with_llm
from AgentCore.mode_manager.mic_arbitrator import MicArbitrator
from AgentCore.mode_manager.audit import write_log
from AgentCore.mode_manager.state_machine import ModeState
from AgentCore.mode_manager.cooldown import Cooldown

class ModeEngine:
    def __init__(self, config_path="feature_flags/auto_mode.yaml", llm=None, code_engine=None):
        self.config_path = config_path
        self.config = self._load_config()
        self.llm = llm
        self.code_engine = code_engine
        self.mic = MicArbitrator()
        self.cooldown = Cooldown(self.config.get("cooldown_seconds", 2))
        self.current_mode = "NORMAL"
        self.state = ModeState.COMPLETED
        self.routing_lock = threading.Lock() # freeze routing during transitions

    def _load_config(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r") as f:
                    return yaml.safe_load(f) or {}
            except Exception:
                pass
        return {}

    def decide_and_transition(self, text, context=None):
        # 1. Config Check
        if not self.config.get("enabled", False):
            return {"action": "no_switch", "reason": "AMS disabled"}

        # 2. Intent Detection
        intent, rule_conf, source = match_rules(text)
        if intent:
            confidence = rule_conf
            method = source
        else:
            if not self.llm:
                return {"action": "no_switch", "reason": "Ambiguous and no LLM"}
            intent, confidence, method = classify_with_llm(self.llm, text)
            
        # 3. Cooldown Check
        if not self.cooldown.allow():
             return {"action": "no_switch", "reason": "Cooldown"}

        # Audit Log Entry
        entry = {
            "user_text": text[:50], 
            "detected_intent": intent, 
            "confidence": confidence, 
            "method": method, 
            "previous_mode": self.current_mode
        }

        # 4. Confidence Threshold
        threshold = self.config.get("auto_switch_confidence_threshold", 0.75)
        if confidence < threshold:
            entry.update({"action": "ask_clarify"})
            write_log(self.config.get("log_path", "data/logs/mode_switch.log"), entry)
            return {"action": "ask_clarify", "message": f"I think you want to {intent}. Shall I switch?"}

        # 5. Determine Target Mode
        target_mode = self.current_mode # Default stay
        if intent == "CODING":
            target_mode = "CODE"
        elif intent == "WAKE":
            target_mode = "SERVICE"
        elif intent == "SLEEP":
            target_mode = "NORMAL"
        elif intent in ("OPEN_IDE", "EXECUTE_LOCAL"):
            target_mode = "CONVERSATION"
        elif intent == "SYSTEM_DELETE":
            # Destructive -> Require Confirm
            if self.config.get("require_owner_confirm_for_destructive", True):
                entry.update({"action": "require_confirm"})
                write_log(self.config.get("log_path", "data/logs/mode_switch.log"), entry)
                return {"action": "require_confirm", "message": "This is a destructive action. Please confirm."}
            else:
                 # If confirmed allowed, maybe conversation? Or execute?
                 # ideally system delete should be handled by a specific tool, 
                 # but picking a mode for it:
                 target_mode = "CONVERSATION" 

        # 6. Stop if no change
        if target_mode == self.current_mode:
             # But if it is CODE mode, run the code engine
             if target_mode == "CODE" and intent == "CODING":
                 pass # Fall through to execution logic
             else:
                return {"action": "no_switch", "reason": "Already in mode"}

        # 7. Transition Logic
        with self.routing_lock:
            prev = self.current_mode
            entry.update({"action": "switch_attempt", "target_mode": target_mode})
            write_log(self.config.get("log_path", "data/logs/mode_switch.log"), entry)

            # Pre-checks (Mic)
            if target_mode in ("SERVICE", "CODE"): # Maybe CODE needs mic?
                owner = self.config.get("owner_voice_id", "owner")
                if not self.mic.acquire(owner, timeout=5.0):
                    entry.update({"action": "switch_failed", "reason": "mic_unavailable"})
                    write_log(self.config.get("log_path", "data/logs/mode_switch.log"), entry)
                    return {"action": "no_switch", "reason": "Mic unavailable"}

            # Update State
            self.state = ModeState.RUNNING
            self.current_mode = target_mode
            entry.update({"action": "switched", "new_mode": self.current_mode})
            write_log(self.config.get("log_path", "data/logs/mode_switch.log"), entry)

        # 8. Execution (if CODE)
        if target_mode == "CODE" and self.code_engine:
            # Route to Code Engine (Default Dry Run)
            # Only if intent was coding (to avoid running on "switch to code mode")
            if intent == "CODING":
                try:
                    result = self.code_engine.handle_command(text, context=context, dry_run=True)
                    entry.update({"code_result_summary": result.get("patch_summary", "")})
                    write_log(self.config.get("log_path", "data/logs/mode_switch.log"), entry)
                    
                    # Updates for Correctness
                    self.state = ModeState.COMPLETED
                    self.release_resources() # Automatic release after dry-run
                    
                    return {"action": "switched", "target_mode": "CODE", "result": result}
                except Exception as e:
                    self.state = ModeState.FAILED
                    self.release_resources()
                    entry.update({"action": "execution_failed", "error": str(e)})
                    write_log(self.config.get("log_path", "data/logs/mode_switch.log"), entry)
                    return {"action": "no_switch", "reason": f"Code execution failed: {e}"}
        
        return {"action": "switched", "target_mode": target_mode}

    def release_resources(self):
        try:
            self.mic.release(self.config.get("owner_voice_id", "owner"))
        except Exception:
            self.mic.force_release()
