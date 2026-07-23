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
from .debug_loop import DebugLoop
from .ast_fixer import ASTFixer

class Level6Coordinator:
    def __init__(self, config_path="feature_flags/level6_engine.yaml", llm=None, code_engine=None):
        self.config_path = config_path
        self.config = self._load_config()
        self.llm = llm
        self.code_engine = code_engine

        self.metrics = Level6Metrics(self.config.get("log_path", "data/level6/metrics.jsonl"))
        self.rollback = RollbackManager(self.config.get("sandbox_base_path", "projects/sandbox_level6"))
        self.planner = Planner(llm)
        self.ast_fixer = ASTFixer()
        self.sandbox_runner = SandboxRunner(
            self.config.get("sandbox_base_path", "projects/sandbox_level6"),
            ast_fixer=self.ast_fixer,
        )
        self.verifier = Verifier()
        self.debug_loop = DebugLoop(llm, self.sandbox_runner, self.ast_fixer)
        self.debug_loop.max_iterations = self.config.get("max_iterations", self.debug_loop.max_iterations)

        # Phase C: ASTFixer now does real LibCST-based structural
        # transforms (replace_function), wired into SandboxRunner for
        # "ast_edit" plan steps. DebugLoop's own fixes (Phase B) still
        # use full-file replacement, not ast_edit -- that was a
        # deliberate, separate design choice (see debug_loop.py), not a
        # placeholder limitation, so it's unchanged here.

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

        # 2 & 3. Sandbox Setup & Execution, with the auto-debug loop
        # (DebugLoop): runs the plan in an isolated sandbox dir via
        # pytest, and on failure asks the LLM for a real fix, applies
        # it, and retries -- up to its iteration budget. Never touches
        # the real repo.
        print(f"[Level6] Executing plan in sandbox (with auto-debug) for request {req_id}")
        debug_result = self.debug_loop.iterate(plan, tests, req_id)
        final_plan = debug_result.get("final_plan", plan)
        sandbox_result = debug_result.get("evidence", {})

        # 4. Verification (Verifier) -- static safety check on the final
        # (possibly auto-fixed) plan (secrets, destructive actions).
        verify_result = self.verifier.verify_plan(final_plan)

        if debug_result.get("status") != "success":
            self.metrics.log_failure(req_id, "sandbox_failed", debug_result.get("iterations", 0))
            return {
                "status": "sandbox_failed",
                "request_id": req_id,
                "plan": final_plan,
                "tests": tests,
                "risk_score": risk_score,
                "explain": explain,
                "sandbox_result": sandbox_result,
                "verify_result": verify_result,
                "debug_iterations": debug_result.get("iterations"),
                "debug_reason": debug_result.get("reason"),
                "debug_history": debug_result.get("history"),
            }

        if not verify_result.get("safe", True):
            self.metrics.log_failure(req_id, "verification_failed", debug_result.get("iterations", 0))
            return {
                "status": "verification_failed",
                "request_id": req_id,
                "plan": final_plan,
                "tests": tests,
                "risk_score": risk_score,
                "explain": explain,
                "sandbox_result": sandbox_result,
                "verify_result": verify_result,
                "debug_iterations": debug_result.get("iterations"),
            }

        # Phase A/B stop here (plan -> sandbox-execute-with-auto-debug ->
        # verify). No apply-to-real-repo step yet -- that's Phase D,
        # gated on explicit owner approval and using RollbackManager as
        # the safety net.
        self.metrics.log_success(req_id, debug_result.get("iterations", 1), risk_score)
        return {
            "status": "verified",
            "request_id": req_id,
            "plan": final_plan,
            "tests": tests,
            "risk_score": risk_score,
            "explain": explain,
            "sandbox_result": sandbox_result,
            "verify_result": verify_result,
            "debug_iterations": debug_result.get("iterations"),
        }
