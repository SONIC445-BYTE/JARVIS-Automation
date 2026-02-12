import yaml
import os
import uuid
import time
from typing import Dict, Any, Optional

from .planner import Planner
from .metrics import Level6Metrics
from .rollback_manager import RollbackManager

class Level6Coordinator:
    def __init__(self, config_path="feature_flags/level6_engine.yaml", llm=None, code_engine=None):
        self.config_path = config_path
        self.config = self._load_config()
        self.llm = llm
        self.code_engine = code_engine
        
        self.metrics = Level6Metrics(self.config.get("log_path", "data/level6/metrics.jsonl"))
        self.rollback = RollbackManager(self.config.get("sandbox_base_path", "projects/sandbox_level6"))
        self.planner = Planner(llm)
        
        # Lazy load other components as we implement them
        # self.sandbox_runner = ...
        # self.debug_loop = ...
        # self.verifier = ...

    def _load_config(self) -> Dict[str, Any]:
        if not os.path.exists(self.config_path):
            return {"enabled": False}
        try:
            with open(self.config_path, "r") as f:
                return yaml.safe_load(f) or {}
        except Exception:
            return {}

    def handle_request(self, user_text: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main entry point for Level-6 requests.
        """
        req_id = str(uuid.uuid4())
        self.metrics.log_request_start(req_id)
        
        if not self.config.get("enabled", False):
            return {"status": "disabled", "message": "Level-6 Engine is disabled."}

        # 1. Plan
        print(f"[Level6] Planning refactor for: {user_text}")
        plan_result = self.planner.plan_refactor(user_text, context)
        
        if "error" in plan_result:
             self.metrics.log_failure(req_id, "planning_failed", 0)
             return {"status": "failed", "error": plan_result["error"]}

        # TODO: 2. Sandbox Setup & Execution (SandboxRunner)
        # TODO: 3. Tests & Debug Loop (DebugLoop)
        # TODO: 4. Verification (Verifier)
        
        # For now, just return the plan as proof of concept
        return {
            "status": "planned",
            "request_id": req_id,
            "plan": plan_result.get("plan"),
            "tests": plan_result.get("tests"),
            "risk_score": plan_result.get("estimated_risk", 0.0),
            "explain": plan_result.get("explain")
        }
