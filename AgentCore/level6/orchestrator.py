import yaml
import os
import shutil
import uuid
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, List, Optional

from .planner import Planner
from .metrics import Level6Metrics
from .rollback_manager import RollbackManager
from .sandbox_runner import SandboxRunner
from .verifier import Verifier
from .debug_loop import DebugLoop
from .ast_fixer import ASTFixer


@dataclass
class PendingLevel6Apply:
    """
    Multi-turn confirmation state between a verified Level6 plan and the
    owner's explicit approval to write it to the real repo -- same
    "never act without an unambiguous yes" standard as PendingInstall
    (AgentCore/resolution_gate.py, Phase 2c). Held by the conversation
    loop (jarvis.py), not by Level6Coordinator itself, matching that
    same ownership split: the coordinator returns data, the
    conversation loop owns pending multi-turn state and speaks the
    approval question.

    sandbox_dir is deliberately what gets applied, not plan[i]["content"]
    directly: an "ast_edit" plan step's final content is only ever
    written into the sandbox file by ASTFixer (via SandboxRunner) -- it
    is never written back into the plan list itself. Applying from
    plan content would silently apply stale/empty content for any
    ast_edit step; copying the exact sandbox bytes that were actually
    verified avoids any drift between what was tested and what gets
    applied.
    """
    request_id: str
    plan: List[Dict[str, Any]]
    sandbox_dir: str
    target_dir: str
    explain: Optional[str] = None
    risk_score: float = 0.0


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

        # Phase A/B/C stop here (plan -> sandbox-execute-with-auto-debug
        # -> verify). Nothing has touched the real repo -- applying is
        # Phase D, a separate, explicitly owner-approved step (see
        # apply() / PendingLevel6Apply below). "target_dir" is where an
        # apply would write to if approved; it is context["cwd"] (the
        # real working directory this request came from), never assumed.
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
            "target_dir": context.get("cwd", os.getcwd()),
        }

    def apply(self, pending: PendingLevel6Apply) -> Dict[str, Any]:
        """
        Writes a verified plan's files to the real target directory --
        only ever called after explicit owner approval (see
        PendingLevel6Apply's docstring; jarvis.py is the only caller,
        and only from _handle_level6_apply_confirmation() after
        _is_affirmative(text)).

        Safety sequence: snapshot target_dir via RollbackManager first;
        refuse to apply at all if the snapshot itself fails (never write
        without a safety net); copy each plan file's exact verified
        bytes from the sandbox; on any failure partway through, revert
        everything from the snapshot rather than leaving a half-applied
        change.
        """
        target_dir = Path(pending.target_dir)
        sandbox_dir = Path(pending.sandbox_dir)
        snapshot_id = f"apply_{pending.request_id}"

        if not self.rollback.create_snapshot(snapshot_id, str(target_dir)):
            return {
                "status": "apply_failed",
                "reason": "Could not create a safety snapshot before applying -- refusing to write without one.",
            }

        written = []
        try:
            for step in pending.plan:
                if step.get("type") not in ("create_file", "update_file", "ast_edit"):
                    continue
                target = step.get("target")
                if not target:
                    continue
                src = sandbox_dir / target
                if not src.exists():
                    raise FileNotFoundError(
                        f"Verified sandbox is missing {target} -- refusing to apply an incomplete plan"
                    )
                dest = target_dir / target
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src, dest)
                written.append(str(dest))

            self.metrics.log_metric("level6_applied", {"request_id": pending.request_id, "files": written})
            return {"status": "applied", "files": written, "snapshot_id": snapshot_id}

        except Exception as e:
            print(f"[Level6] Apply failed ({e}), reverting from snapshot {snapshot_id}")
            reverted = self.rollback.revert(snapshot_id, str(target_dir))
            self.metrics.log_failure(pending.request_id, "apply_failed", 0)
            return {
                "status": "apply_failed",
                "reason": str(e),
                "reverted": reverted,
                "snapshot_id": snapshot_id,
            }
