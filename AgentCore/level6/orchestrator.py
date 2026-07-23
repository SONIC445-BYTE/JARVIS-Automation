import yaml
import os
import uuid
import time
from typing import Dict, Any, Optional

from .planner import Planner
from .metrics import Level6Metrics
from .rollback_manager import RollbackManager
from .sandbox_runner import SandboxRunner
from .verifier import Verifier

class Level6Coordinator:
    def __init__(self, config_path="feature_flags/level6_engine.yaml", llm=None, code_engine=None):
        self.config_path = config_path
        self.config = self._load_config()
        self.llm = llm
        self.code_engine = code_engine

        self.metrics = Level6Metrics(self.config.get("log_path", "data/level6/metrics.jsonl"))
        self.rollback = RollbackManager(self.config.get("sandbox_base_path", "projects/sandbox_level6"))
        self.planner = Planner(llm)
        self.sandbox_runner = SandboxRunner(self.config.get("sandbox_base_path", "projects/sandbox_level6"))
        self.verifier = Verifier()

        # Phase B/C: real auto-fix-on-failure (DebugLoop) and real
        # AST-based transforms (ASTFixer) are not implemented yet --
        # DebugLoop.iterate() as it stands today is a no-op retry loop
        # (its fix-generation is commented-out dead code), so it isn't
        # wired in here. A failed sandbox run is reported as-is for now.
        # self.debug_loop = ...

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

        plan = plan_result.get("plan") or []
        tests = plan_result.get("tests") or []
        risk_score = plan_result.get("estimated_risk", 0.0)
        explain = plan_result.get("explain")

        # 2. Sandbox Setup & Execution (SandboxRunner) -- isolated dir,
        # real pytest run, never touches the real repo.
        print(f"[Level6] Executing plan in sandbox for request {req_id}")
        sandbox_result = self.sandbox_runner.run_plan(plan, tests, req_id)

        # 3. Tests & Debug Loop (DebugLoop) -- Phase B. Not wired yet: a
        # failed sandbox run is reported as-is, no auto-fix attempted.

        # 4. Verification (Verifier) -- static safety check on the plan
        # (secrets, destructive actions).
        verify_result = self.verifier.verify_plan(plan)

        if not sandbox_result.get("passed", False):
            self.metrics.log_failure(req_id, "sandbox_failed", 0)
            return {
                "status": "sandbox_failed",
                "request_id": req_id,
                "plan": plan,
                "tests": tests,
                "risk_score": risk_score,
                "explain": explain,
                "sandbox_result": sandbox_result,
                "verify_result": verify_result,
            }

        if not verify_result.get("safe", True):
            self.metrics.log_failure(req_id, "verification_failed", 0)
            return {
                "status": "verification_failed",
                "request_id": req_id,
                "plan": plan,
                "tests": tests,
                "risk_score": risk_score,
                "explain": explain,
                "sandbox_result": sandbox_result,
                "verify_result": verify_result,
            }

        # Phase A stops here (plan -> sandbox-execute -> verify). No
        # apply-to-real-repo step yet -- that's Phase D, gated on
        # explicit owner approval and using RollbackManager as the
        # safety net. "verified" replaces the old "planned"-only
        # proof-of-concept status.
        self.metrics.log_success(req_id, 1, risk_score)
        return {
            "status": "verified",
            "request_id": req_id,
            "plan": plan,
            "tests": tests,
            "risk_score": risk_score,
            "explain": explain,
            "sandbox_result": sandbox_result,
            "verify_result": verify_result,
        }
