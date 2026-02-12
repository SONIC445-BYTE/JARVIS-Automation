from .vision.screen_capture import ScreenCapture
from .vision.ocr import OCRWrapper
from .inspector.accessibility_adapter import AccessibilityAdapter
from .inspector.browser_adapter import BrowserAdapter
from .action_router import ActionPlanner, ActionExecutor
from .executor.ui_executor import UIExecutor, ExecutionResult
from .utils.permission_manager import PermissionManager
from .utils.ui_audit import UIAudit
from .utils.ui_policy import UIPolicy

# Import adapters so they register themselves
from .adapters.whatsapp_adapter import WhatsAppAdapter
from .adapters.file_explorer_adapter import FileExplorerAdapter
from .adapters.generic_adapters import GenericDesktopAdapter, GenericBrowserAdapter, UnknownAppFallbackAdapter

from .utils.health_guard import check_system_health
from .dynamic_loader import DynamicAdapterLoader

import os
import yaml
import uuid
from typing import Dict, Any, List, Optional

class UIAgentMain:
    """Main coordinator for the UI Vision + Action layer."""
    
    def __init__(self):
        self.vision = ScreenCapture()
        self.ocr = OCRWrapper()
        self.acc_adapter = AccessibilityAdapter()
        self.browser_adapter = BrowserAdapter()
        self.executor = UIExecutor(self.acc_adapter, self.browser_adapter)
        self.planner = ActionPlanner()
        self.action_executor = ActionExecutor(self.executor)
        self.permission = PermissionManager()
        self.audit = UIAudit()
        self.policy = UIPolicy()
        
        # 4. Dynamic Adapter Loader
        self.loader = DynamicAdapterLoader()
        self.loader.load_all()
        
        self._load_flags()
        
        # 4. System Health Guard
        if self.vision_enabled:
             check_system_health(self)
             
        self.context = {} # Session context (active app, history)

    def _load_flags(self):
        self.vision_enabled = False
        self.exec_enabled = False
        
        if os.path.exists("feature_flags/ui_vision.yaml"):
            with open("feature_flags/ui_vision.yaml", "r") as f:
                self.vision_enabled = yaml.safe_load(f).get("enabled", False)
        
        if os.path.exists("feature_flags/ui_execute.yaml"):
            with open("feature_flags/ui_execute.yaml", "r") as f:
                self.exec_enabled = yaml.safe_load(f).get("enabled", False)

    def execute_instruction(self, instruction: str, dry_run: bool = True) -> ExecutionResult:
        """
        Highest-level entry point. 
        instruction: "Attach photo to WhatsApp status"
        """
        if not self.vision_enabled:
            return ExecutionResult(success=False, steps=[], error="UI Vision disabled by feature flag.")
            
        request_id = str(uuid.uuid4())
        print(f"[UIAgent] Processing instruction: {instruction} ({request_id})")
        
        # 1. Inference/Planning -> Get Intent
        # In real JARVIS, IntentRouter does this.
        intent = self._infer_action(instruction)
        
        # 2. Safety Check
        if not self.policy.validate_action(intent.get("action", "generic"), intent.get("target", "")):
             return ExecutionResult(success=False, steps=[], error="Action blocked by safety policy.")
             
        # 3. Planning via ActionPlanner (Central Authority)
        # Context Awareness: Pass session context (e.g. last app) to planner
        try:
            selected_adapter, plan = self.planner.plan(intent, self.context)
        except Exception as e:
            return ExecutionResult(success=False, steps=[], error=f"Planning failed: {e}")
            
        # 4. Permission Check
        if not dry_run and self.exec_enabled:
            # Check app-level allowlist
            platform = intent.get("platform") or intent.get("app") or getattr(selected_adapter, 'platform', 'unknown')
            if platform and platform != "unknown" and not self.permission.is_app_allowed(platform):
                return ExecutionResult(success=False, steps=[], error=f"App {platform} not in allowlist.")
        
        # 5. Routing & Execution (Try Native -> UI fallback handled by ActionExecutor)
        result = self.action_executor.execute(plan, intent, {"dry_run": dry_run}, adapter=selected_adapter)
        
        # Update context if successful
        if result.success:
            platform = getattr(selected_adapter, 'platform', 'unknown')
            if platform != 'unknown' and platform != 'generic':
                 self.context["active_app"] = platform
                 print(f"[UIAgent] Context updated: active_app={platform}")
        
        # 6. Audit
        self.audit.log_action(request_id, intent, result)
        
        return result

    def _infer_action(self, instruction: str) -> Dict[str, Any]:
        """Placeholder for LLM-based planning."""
        cmd = instruction.lower()
        intent = {"app": "generic", "action": "unknown", "raw": instruction}
        
        if "whatsapp" in cmd:
            intent["app"] = "whatsapp"
            intent["platform"] = "whatsapp"
        elif "explorer" in cmd or "file" in cmd:
            intent["app"] = "explorer"
            intent["platform"] = "explorer"
            
        if "click" in cmd:
            intent["action"] = "click"
            # Extract target
            if "click " in cmd:
                intent["target"] = instruction.split("click ")[-1]
        elif "send" in cmd:
            intent["action"] = "send_message"
            intent["message"] = "Automated hello"
            intent["recipient"] = "myself"
        elif "navigate" in cmd or "open" in cmd:
            intent["action"] = "navigate_to"
            intent["path"] = "C:\\"
            
        return intent
