from typing import Dict, Any, List

class PolicyGate:
    """
    Enforces safety and policy rules before and after execution.
    """
    def __init__(self, config_path: str = "feature_flags/pipeline_enforce.yaml"):
        self.require_confirm = True
        self.blacklisted_patterns = ["rm -rf", "format c:", "delete system32"]
        self._load_config(config_path)

    def _load_config(self, config_path: str):
        try:
            import os
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    for line in f:
                        if "require_policy_gate" in line:
                            # Parse boolean
                            val = line.split(":")[1].strip().lower()
                            self.require_confirm = (val == "true")
        except Exception:
            pass

    def pre_check(self, intent_data: Dict[str, Any], metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check if request is allowed to proceed.
        """
        intent_type = intent_data.get("intent", "UNKNOWN")
        
        # Destructive check
        if intent_type == "SYSTEM_CONTROL" or intent_type == "DESTRUCTIVE":
            return {
                "allowed": False,
                "require_confirm": True,
                "confirm_prompt": "This action is destructive. Are you sure?",
                "block_reasons": ["Destructive intent detected"]
            }

        # Code Request safety
        if intent_type == "CODE_REQUEST":
            # Always allowed but might need confirmation in future
            return {"allowed": True, "require_confirm": False, "block_reasons": []}

        # Default allow
        return {"allowed": True, "require_confirm": False, "block_reasons": []}

    def post_check(self, engine_result: Any) -> Dict[str, Any]:
        """
        Validate engine output before delivery.
        """
        # Example: Don't leak raw code in voice channel
        # For now, just pass
        return {"validated": True, "flags": []}
