"""
Orchestrator for Level-4 Engine.
Handles top-level routing and execution flow.
"""
from typing import Dict, Any, Optional
import os
import json
from ..tier1.patch_builder import PatchBuilder
from ..tier2.planner import Planner
from ..audit.audit_log import AuditLog
from ..metrics.metrics_collector import MetricsCollector
from AgentCore.feature_gate import is_enabled

class Level4Orchestrator:
    def __init__(self):
        self.patch_builder = PatchBuilder()
        self.planner = Planner()
        self.audit = AuditLog()
        self.metrics = MetricsCollector()

    def handle_code_request(self, user_id: str, command_text: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Public API request handler.
        1. Check feature flag.
        2. Plan (Tier-1 or Tier-2).
        3. Dry-run.
        4. Audit.
        5. Return report.
        """
        if not is_enabled("level4_engine"):
            return {"success": False, "message": "Level-4 Engine disabled"}

        self.metrics.log_request(user_id)
        context = context or {}
        
        # 2. Plan
        # Simple routing logic (can use IntentRouter if integrated)
        plan = self.planner.create_plan(command_text, context)
        
        # 3. Patch Build & Dry Run
        patch_result = self.patch_builder.build_and_verify(plan)
        
        # 4. Audit
        self.audit.log_entry(
            user_id=user_id,
            command=command_text,
            plan=plan,
            result=patch_result
        )

        return {
            "success": patch_result['success'],
            "plan": plan,
            "patch": patch_result.get('patch'),
            "report": {
                "confidence": plan.get('confidence'),
                "risks": plan.get('risks'),
                "dry_run_result": patch_result.get('dry_run_result')
            }
        }
