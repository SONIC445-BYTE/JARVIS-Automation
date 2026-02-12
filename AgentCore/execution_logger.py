"""
Execution Logger - Structured Event Logging
=============================================
Logs execution events for debugging and audit.

Sprint 2: Autonomous Action
"""

import os
import json
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum


class LogLevel(Enum):
    """Log severity levels."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ExecutionEvent:
    """Single execution event."""
    timestamp: float
    event_type: str
    plan_id: Optional[str]
    step_id: Optional[int]
    action_type: Optional[str]
    status: str
    level: LogLevel
    message: str
    metadata: Dict = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
    
    def to_dict(self) -> Dict:
        d = asdict(self)
        d['level'] = self.level.value
        d['datetime'] = datetime.fromtimestamp(self.timestamp).isoformat()
        return d
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict())


class ExecutionLogger:
    """
    Logs execution events to file and memory.
    
    Features:
    - Structured JSON logging
    - File rotation
    - Memory buffer for recent events
    - Query by plan/step
    """
    
    MAX_MEMORY_EVENTS = 1000
    
    def __init__(self, log_dir: Optional[Path] = None):
        if log_dir is None:
            log_dir = Path(__file__).parent.parent / "logs" / "execution"
        
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        self._events: List[ExecutionEvent] = []
        self._current_log_file: Optional[Path] = None
        self._init_log_file()
    
    def _init_log_file(self):
        """Initialize log file for today."""
        date_str = datetime.now().strftime("%Y%m%d")
        self._current_log_file = self.log_dir / f"execution_{date_str}.jsonl"
    
    def log(self, event_type: str, status: str, message: str,
            plan_id: Optional[str] = None, step_id: Optional[int] = None,
            action_type: Optional[str] = None, level: LogLevel = LogLevel.INFO,
            metadata: Dict = None) -> ExecutionEvent:
        """
        Log an execution event.
        
        Args:
            event_type: Type of event (plan_start, step_execute, etc.)
            status: Status (success, failed, etc.)
            message: Human-readable message
            plan_id: Associated plan ID
            step_id: Associated step ID
            action_type: Type of action
            level: Log severity
            metadata: Additional data
            
        Returns:
            The logged event
        """
        event = ExecutionEvent(
            timestamp=time.time(),
            event_type=event_type,
            plan_id=plan_id,
            step_id=step_id,
            action_type=action_type,
            status=status,
            level=level,
            message=message,
            metadata=metadata or {}
        )
        
        # Add to memory
        self._events.append(event)
        if len(self._events) > self.MAX_MEMORY_EVENTS:
            self._events = self._events[-self.MAX_MEMORY_EVENTS:]
        
        # Write to file
        self._write_event(event)
        
        # Print if ERROR or above
        if level in [LogLevel.ERROR, LogLevel.CRITICAL]:
            print(f"[{level.value.upper()}] {message}")
        
        return event
    
    def _write_event(self, event: ExecutionEvent):
        """Write event to log file."""
        try:
            with open(self._current_log_file, "a", encoding="utf-8") as f:
                f.write(event.to_json() + "\n")
        except Exception as e:
            print(f"[Logger] Write error: {e}")
    
    # Convenience methods
    
    def plan_start(self, plan_id: str, intent: str, step_count: int):
        """Log plan execution start."""
        self.log(
            event_type="plan_start",
            status="started",
            message=f"Started plan '{plan_id}' with {step_count} steps",
            plan_id=plan_id,
            metadata={"intent": intent, "step_count": step_count}
        )
    
    def plan_complete(self, plan_id: str, success: bool, duration_ms: float):
        """Log plan completion."""
        self.log(
            event_type="plan_complete",
            status="success" if success else "failed",
            message=f"Plan '{plan_id}' {'completed' if success else 'failed'}",
            plan_id=plan_id,
            level=LogLevel.INFO if success else LogLevel.ERROR,
            metadata={"duration_ms": duration_ms}
        )
    
    def step_start(self, plan_id: str, step_id: int, action_type: str):
        """Log step execution start."""
        self.log(
            event_type="step_start",
            status="started",
            message=f"Step {step_id}: {action_type}",
            plan_id=plan_id,
            step_id=step_id,
            action_type=action_type,
            level=LogLevel.DEBUG
        )
    
    def step_complete(self, plan_id: str, step_id: int, action_type: str, 
                     success: bool, duration_ms: float, error: Optional[str] = None):
        """Log step completion."""
        self.log(
            event_type="step_complete",
            status="success" if success else "failed",
            message=f"Step {step_id} {'completed' if success else 'failed'}: {action_type}",
            plan_id=plan_id,
            step_id=step_id,
            action_type=action_type,
            level=LogLevel.INFO if success else LogLevel.WARNING,
            metadata={"duration_ms": duration_ms, "error": error}
        )
    
    def recovery_attempt(self, plan_id: str, step_id: int, strategy: str, success: bool):
        """Log recovery attempt."""
        self.log(
            event_type="recovery",
            status="success" if success else "failed",
            message=f"Recovery ({strategy}) for step {step_id}",
            plan_id=plan_id,
            step_id=step_id,
            level=LogLevel.INFO if success else LogLevel.WARNING,
            metadata={"strategy": strategy}
        )
    
    # Query methods
    
    def get_plan_events(self, plan_id: str) -> List[ExecutionEvent]:
        """Get all events for a plan."""
        return [e for e in self._events if e.plan_id == plan_id]
    
    def get_recent_errors(self, limit: int = 10) -> List[ExecutionEvent]:
        """Get recent error events."""
        errors = [e for e in self._events if e.level in [LogLevel.ERROR, LogLevel.CRITICAL]]
        return errors[-limit:]
    
    def get_summary(self) -> Dict:
        """Get execution summary."""
        total = len(self._events)
        by_status = {}
        by_type = {}
        
        for event in self._events:
            by_status[event.status] = by_status.get(event.status, 0) + 1
            by_type[event.event_type] = by_type.get(event.event_type, 0) + 1
        
        return {
            "total_events": total,
            "by_status": by_status,
            "by_type": by_type,
            "log_file": str(self._current_log_file)
        }
