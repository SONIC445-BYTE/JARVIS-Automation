from typing import Dict, Any, List, Optional
import json
from ..intent_parser import IntentParser, Intent
from ..llm_engine import LLMEngine

class IntentRouterError(Exception):
    pass

class IntentRouter:
    """
    Canonical Intent Router.
    Priority:
    1. Rule-based IntentParser (High confidence)
    2. LLM-based Classification (Fallback/Ambiguity)
    """
    def __init__(self, config_path: str = "feature_flags/pipeline_enforce.yaml", llm=None):
        self.parser = IntentParser()
        self.llm = llm or LLMEngine()
        self.confidence_threshold = 0.7
        self._load_config(config_path)

    def _load_config(self, config_path: str):
        try:
            # Simple parsing of yaml for confidence
            import os
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    for line in f:
                        if "intent_confidence_threshold" in line:
                            val = line.split(":")[1].strip()
                            self.confidence_threshold = float(val)
        except Exception:
            pass

    def classify(self, text: str, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Classify input text into structured intent.
        """
        try:
            # 1. Rule-based Parsing
            rule_intent = self.parser.parse(text)
            
            # heuristic for high confidence
            is_high_confidence = rule_intent.confidence >= self.confidence_threshold
            
            if is_high_confidence:
                 return {
                    "intent": self._map_legacy_action_to_intent(rule_intent),
                    "confidence": rule_intent.confidence,
                    "method": "rule_based",
                    "original_intent": rule_intent.to_dict(),
                    "params": rule_intent.parameters
                }

            # 2. LLM Fallback
            if self.llm.is_available():
                llm_result = self._llm_classify(text)
                if llm_result:
                    return llm_result
            
            # 3. Final Fallback (return low confidence rule result)
            return {
                "intent": "UNKNOWN",
                "confidence": rule_intent.confidence,
                "method": "fallback_rule",
                "original_intent": rule_intent.to_dict()
            }

        except Exception as e:
            raise IntentRouterError(f"Routing failed: {e}")

    def _map_legacy_action_to_intent(self, rule_intent: Intent) -> str:
        """Map legacy actions to canonical intents."""
        action = rule_intent.action
        
        code_keywords = ["code", "script", "function", "program", "class", "module", "python", "java", "html", "css", "js", "architect"]
        if action in ["type", "write", "create"] and any(k in rule_intent.raw_command.lower() for k in code_keywords):
             return "CODE_REQUEST"
             
        automation_actions = [
            "open", "close", "scroll", "click", "search", "play", "send", "turn", 
            "upload", "download", "navigate", "screenshot", "move", "copy", "delete"
        ]
        
        # Add more specific mappings for download and upload
        download_keywords = ["download", "save"]
        upload_keywords = ["upload", "post", "share"]

        if action in automation_actions or action in download_keywords or action in upload_keywords:
            return "AUTOMATION"
            
        return "CONVERSATION"

    def _llm_classify(self, text: str) -> Optional[Dict[str, Any]]:
        """Call LLM to classify intent."""
        prompt = f"""
        Classify this user command into one of: CONVERSATION, CODE_REQUEST, AUTOMATION, SYSTEM_CONTROL.
        Command: "{text}"
        Return JSON only: {{"intent": "...", "confidence": 0.0-1.0}}
        """
        try:
            response = self.llm.generate(prompt, max_tokens=50)
            # Naive parsing
            if "{" in response.text:
                import json
                start = response.text.find("{")
                end = response.text.rfind("}") + 1
                json_str = response.text[start:end]
                data = json.loads(json_str)
                data["method"] = "llm"
                return data
        except Exception:
            pass
        return None
