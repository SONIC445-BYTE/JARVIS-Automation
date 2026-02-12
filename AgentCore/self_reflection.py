"""
Self Reflection - Failure Analysis and Learning
=================================================
Analyzes failures, suggests alternatives, learns from mistakes.

Sprint 7: Gap Fixes
"""

import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum


class FailureType(Enum):
    """Types of execution failures."""
    ELEMENT_NOT_FOUND = "element_not_found"
    TIMEOUT = "timeout"
    PERMISSION_DENIED = "permission_denied"
    APP_NOT_RESPONDING = "app_not_responding"
    UNEXPECTED_STATE = "unexpected_state"
    NETWORK_ERROR = "network_error"
    UNKNOWN = "unknown"


@dataclass
class FailureAnalysis:
    """Result of failure analysis."""
    failure_type: FailureType
    root_cause: str
    confidence: float
    alternatives: List[str]
    should_retry: bool
    retry_with_changes: Dict = field(default_factory=dict)
    learned_pattern: Optional[str] = None


class SelfReflection:
    """
    Analyzes failures and suggests corrections.
    
    "Why did this fail?" + "How can I fix it?"
    """
    
    # Common failure patterns
    FAILURE_PATTERNS = {
        "element not found": FailureType.ELEMENT_NOT_FOUND,
        "not found": FailureType.ELEMENT_NOT_FOUND,
        "timeout": FailureType.TIMEOUT,
        "timed out": FailureType.TIMEOUT,
        "access denied": FailureType.PERMISSION_DENIED,
        "permission": FailureType.PERMISSION_DENIED,
        "not responding": FailureType.APP_NOT_RESPONDING,
        "hung": FailureType.APP_NOT_RESPONDING,
        "unexpected": FailureType.UNEXPECTED_STATE,
        "network": FailureType.NETWORK_ERROR,
        "connection": FailureType.NETWORK_ERROR,
    }
    
    # Recovery strategies by failure type
    RECOVERY_STRATEGIES = {
        FailureType.ELEMENT_NOT_FOUND: [
            "Wait longer for element to appear",
            "Try alternative selector (by position instead of label)",
            "Check if window is focused",
            "Scroll to make element visible",
            "Use keyboard navigation instead"
        ],
        FailureType.TIMEOUT: [
            "Increase timeout duration",
            "Check if application is responsive",
            "Try again with fresh window",
            "Break into smaller steps"
        ],
        FailureType.PERMISSION_DENIED: [
            "Request elevated permissions",
            "Try alternative approach that doesn't require admin",
            "Notify user to grant access"
        ],
        FailureType.APP_NOT_RESPONDING: [
            "Wait for application to recover",
            "Close and reopen application",
            "Use keyboard interrupt to unblock",
            "Skip this action if non-critical"
        ],
        FailureType.UNEXPECTED_STATE: [
            "Re-scan UI to understand current state",
            "Reset to known state and retry",
            "Ask user for clarification",
            "Take screenshot for debugging"
        ],
        FailureType.NETWORK_ERROR: [
            "Check internet connection",
            "Retry after short delay",
            "Use cached/offline version if available"
        ],
        FailureType.UNKNOWN: [
            "Retry with logging enabled",
            "Fall back to simpler approach",
            "Ask user for guidance"
        ]
    }
    
    def __init__(self):
        self._failure_history: List[Dict] = []
        self._learned_fixes: Dict[str, str] = {}
    
    def analyze(self, action: Dict, error_message: str, 
               ui_state: Dict = None) -> FailureAnalysis:
        """
        Analyze a failure and suggest recovery.
        
        Args:
            action: The action that failed
            error_message: Error description
            ui_state: Current UI state (optional)
            
        Returns:
            FailureAnalysis with diagnosis and suggestions
        """
        # Classify failure type
        failure_type = self._classify_failure(error_message)
        
        # Determine root cause
        root_cause = self._find_root_cause(
            action, error_message, failure_type, ui_state
        )
        
        # Get recovery strategies
        alternatives = self.RECOVERY_STRATEGIES.get(
            failure_type, 
            self.RECOVERY_STRATEGIES[FailureType.UNKNOWN]
        )
        
        # Check if we've learned a fix for this
        learned_pattern = None
        action_key = f"{action.get('type', 'unknown')}:{action.get('target', '')}"
        if action_key in self._learned_fixes:
            learned_pattern = self._learned_fixes[action_key]
            alternatives = [learned_pattern] + alternatives
        
        # Determine if retry is worthwhile
        should_retry = failure_type not in [
            FailureType.PERMISSION_DENIED,
            FailureType.NETWORK_ERROR
        ]
        
        # Suggest modifications for retry
        retry_changes = self._suggest_retry_changes(
            action, failure_type, ui_state
        )
        
        analysis = FailureAnalysis(
            failure_type=failure_type,
            root_cause=root_cause,
            confidence=0.7,
            alternatives=alternatives[:3],
            should_retry=should_retry,
            retry_with_changes=retry_changes,
            learned_pattern=learned_pattern
        )
        
        # Record for learning
        self._failure_history.append({
            "action": action,
            "error": error_message,
            "analysis": analysis,
            "timestamp": time.time()
        })
        
        return analysis
    
    def _classify_failure(self, error_message: str) -> FailureType:
        """Classify the type of failure."""
        error_lower = error_message.lower()
        
        for pattern, failure_type in self.FAILURE_PATTERNS.items():
            if pattern in error_lower:
                return failure_type
        
        return FailureType.UNKNOWN
    
    def _find_root_cause(self, action: Dict, error: str, 
                        failure_type: FailureType, ui_state: Dict) -> str:
        """Determine the root cause of failure."""
        action_type = action.get("type", "unknown")
        target = action.get("target", "")
        
        if failure_type == FailureType.ELEMENT_NOT_FOUND:
            if ui_state:
                visible_count = len(ui_state.get("elements", []))
                return f"Element '{target}' not found in {visible_count} visible elements. May need different selector or scroll."
            return f"Element '{target}' not in current view. Window may not be focused or element not rendered."
        
        elif failure_type == FailureType.TIMEOUT:
            return f"Action '{action_type}' did not complete within time limit. Application may be slow or blocked."
        
        elif failure_type == FailureType.APP_NOT_RESPONDING:
            return f"Application stopped responding during '{action_type}'. May need restart or unblock."
        
        return f"Action '{action_type}' on '{target}' failed: {error}"
    
    def _suggest_retry_changes(self, action: Dict, failure_type: FailureType,
                              ui_state: Dict) -> Dict:
        """Suggest modifications for retry attempt."""
        changes = {}
        
        if failure_type == FailureType.ELEMENT_NOT_FOUND:
            # Try position-based selection
            changes["use_position"] = True
            changes["selector_type"] = "position"
        
        elif failure_type == FailureType.TIMEOUT:
            # Increase timeout
            current_timeout = action.get("timeout", 10)
            changes["timeout"] = min(current_timeout * 2, 60)
        
        return changes
    
    def learn_from_success(self, action: Dict, fix_applied: str):
        """Record a successful fix for future use."""
        action_key = f"{action.get('type', 'unknown')}:{action.get('target', '')}"
        self._learned_fixes[action_key] = fix_applied
        print(f"[SelfReflection] Learned: {action_key} → {fix_applied}")
    
    def explain_failure(self, analysis: FailureAnalysis) -> str:
        """Generate human-readable explanation."""
        lines = [
            f"The action failed due to: {analysis.failure_type.value}",
            f"Root cause: {analysis.root_cause}",
            "",
            "Suggested fixes:"
        ]
        
        for i, alt in enumerate(analysis.alternatives, 1):
            lines.append(f"  {i}. {alt}")
        
        if analysis.should_retry:
            lines.append("")
            lines.append("I'll retry with adjustments.")
        
        return "\n".join(lines)
    
    def get_failure_summary(self) -> Dict:
        """Get summary of recent failures."""
        if not self._failure_history:
            return {"total": 0, "by_type": {}}
        
        by_type = {}
        for record in self._failure_history:
            ft = record["analysis"].failure_type.value
            by_type[ft] = by_type.get(ft, 0) + 1
        
        return {
            "total": len(self._failure_history),
            "by_type": by_type,
            "learned_fixes": len(self._learned_fixes)
        }


def test_self_reflection():
    """Test self reflection."""
    print("Self Reflection Test")
    print("=" * 50)
    
    reflection = SelfReflection()
    
    # Test failure analysis
    action = {"type": "click", "target": "Submit Button"}
    error = "Element not found: Submit Button"
    
    analysis = reflection.analyze(action, error)
    
    print(f"Failure: {analysis.failure_type.value}")
    print(f"Root cause: {analysis.root_cause}")
    print(f"Alternatives: {analysis.alternatives}")
    print(f"Should retry: {analysis.should_retry}")
    print()
    print(reflection.explain_failure(analysis))


if __name__ == "__main__":
    test_self_reflection()
