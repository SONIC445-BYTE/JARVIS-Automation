"""
Audit Log - Tamper-Evident Logging
====================================
Secure, append-only logging with hash chaining.

Sprint 5: Trust & Identity
"""

import os
import json
import time
import hashlib
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict, fields
from pathlib import Path
from datetime import datetime
from threading import Lock


@dataclass
class AuditEntry:
    """Single audit log entry."""
    sequence: int
    timestamp: float
    event_type: str
    actor: str  # profile_id or "system"
    action: str
    resource: Optional[str]
    result: str  # success, failure, denied
    details: Dict = None
    hash: str = ""
    prev_hash: str = ""
    
    def to_dict(self) -> Dict:
        d = asdict(self)
        d["datetime"] = datetime.fromtimestamp(self.timestamp).isoformat()
        return d
    
    def compute_hash(self) -> str:
        """Compute hash of this entry."""
        content = f"{self.sequence}|{self.timestamp}|{self.event_type}|{self.actor}|{self.action}|{self.resource}|{self.result}|{json.dumps(self.details or {})}|{self.prev_hash}"
        return hashlib.sha256(content.encode()).hexdigest()[:32]


class AuditLog:
    """
    Tamper-evident audit logging.
    
    Features:
    - Append-only
    - Hash-chained entries
    - Integrity verification
    - Query by actor, action, time
    """
    
    GENESIS_HASH = "0" * 32
    
    def __init__(self, log_dir: Optional[Path] = None):
        if log_dir is None:
            log_dir = Path(__file__).parent.parent / "data" / "audit"
        
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        self._log_file = self.log_dir / "audit.jsonl"
        self._lock = Lock()
        self._sequence = 0
        self._last_hash = self.GENESIS_HASH
        
        self._load_state()
    
    def _load_state(self):
        """Load last entry to resume sequence and hash chain."""
        if not self._log_file.exists():
            return
        
        try:
            with open(self._log_file, 'r') as f:
                lines = f.readlines()
            
            if lines:
                last = json.loads(lines[-1])
                self._sequence = last.get("sequence", 0)
                self._last_hash = last.get("hash", self.GENESIS_HASH)
                
        except Exception as e:
            print(f"[AuditLog] Load error: {e}")
    
    def log(self, event_type: str, actor: str, action: str,
           resource: Optional[str] = None, result: str = "success",
           details: Dict = None) -> AuditEntry:
        """
        Log an audit event.
        
        Args:
            event_type: Type of event (auth, action, admin, etc.)
            actor: Who performed the action (profile_id or "system")
            action: What action was performed
            resource: Target resource (file, app, etc.)
            result: Outcome (success, failure, denied)
            details: Additional details
            
        Returns:
            Created AuditEntry
        """
        with self._lock:
            self._sequence += 1
            
            entry = AuditEntry(
                sequence=self._sequence,
                timestamp=time.time(),
                event_type=event_type,
                actor=actor,
                action=action,
                resource=resource,
                result=result,
                details=details or {},
                prev_hash=self._last_hash
            )
            
            entry.hash = entry.compute_hash()
            self._last_hash = entry.hash
            
            self._write_entry(entry)
            
        return entry
    
    def _write_entry(self, entry: AuditEntry):
        """Write entry to log file."""
        try:
            with open(self._log_file, 'a') as f:
                f.write(json.dumps(entry.to_dict()) + "\n")
        except Exception as e:
            print(f"[AuditLog] Write error: {e}")
    
    # Convenience logging methods
    
    def log_auth(self, actor: str, success: bool, method: str = "voice"):
        """Log authentication event."""
        return self.log(
            event_type="auth",
            actor=actor,
            action="authenticate",
            result="success" if success else "failure",
            details={"method": method}
        )
    
    def log_action(self, actor: str, action: str, resource: str, success: bool):
        """Log action execution."""
        return self.log(
            event_type="action",
            actor=actor,
            action=action,
            resource=resource,
            result="success" if success else "failure"
        )
    
    def log_denied(self, actor: str, action: str, reason: str):
        """Log permission denial."""
        return self.log(
            event_type="access",
            actor=actor,
            action=action,
            result="denied",
            details={"reason": reason}
        )
    
    def log_admin(self, actor: str, action: str, details: Dict = None):
        """Log administrative action."""
        return self.log(
            event_type="admin",
            actor=actor,
            action=action,
            result="success",
            details=details
        )
    
    # Query methods
    
    def get_entries(self, limit: int = 100, offset: int = 0) -> List[AuditEntry]:
        """Get recent entries."""
        entries = []
        
        try:
            with open(self._log_file, 'r') as f:
                lines = f.readlines()
            
            # Get from end
            for line in reversed(lines[:-offset-1] if offset else lines):
                if len(entries) >= limit:
                    break
                
                try:
                    data = json.loads(line)
                    field_names = {f.name for f in fields(AuditEntry)}
                    entries.append(AuditEntry(**{k: v for k, v in data.items() if k in field_names}))
                except:
                    continue
                    
        except Exception as e:
            print(f"[AuditLog] Read error: {e}")
        
        return entries
    
    def query_by_actor(self, actor: str, limit: int = 50) -> List[AuditEntry]:
        """Get entries for a specific actor."""
        entries = self.get_entries(limit=1000)
        return [e for e in entries if e.actor == actor][:limit]
    
    def query_by_type(self, event_type: str, limit: int = 50) -> List[AuditEntry]:
        """Get entries of a specific type."""
        entries = self.get_entries(limit=1000)
        return [e for e in entries if e.event_type == event_type][:limit]
    
    def query_denials(self, limit: int = 50) -> List[AuditEntry]:
        """Get recent permission denials."""
        entries = self.get_entries(limit=1000)
        return [e for e in entries if e.result == "denied"][:limit]
    
    # Verification
    
    def verify_integrity(self) -> tuple:
        """
        Verify log integrity by checking hash chain.
        
        Returns:
            (is_valid, first_invalid_sequence or None)
        """
        try:
            with open(self._log_file, 'r') as f:
                lines = f.readlines()
            
            expected_prev = self.GENESIS_HASH
            
            for line in lines:
                data = json.loads(line)
                field_names = {f.name for f in fields(AuditEntry)}
                entry = AuditEntry(**{k: v for k, v in data.items() if k in field_names})
                
                # Check prev hash
                if entry.prev_hash != expected_prev:
                    return (False, entry.sequence)
                
                # Check self hash
                computed = entry.compute_hash()
                if entry.hash != computed:
                    return (False, entry.sequence)
                
                expected_prev = entry.hash
            
            return (True, None)
            
        except Exception as e:
            print(f"[AuditLog] Verify error: {e}")
            return (False, -1)
    
    def get_stats(self) -> Dict:
        """Get log statistics."""
        entries = self.get_entries(limit=10000)
        
        by_type = {}
        by_result = {}
        by_actor = {}
        
        for entry in entries:
            by_type[entry.event_type] = by_type.get(entry.event_type, 0) + 1
            by_result[entry.result] = by_result.get(entry.result, 0) + 1
            by_actor[entry.actor] = by_actor.get(entry.actor, 0) + 1
        
        return {
            "total_entries": self._sequence,
            "by_type": by_type,
            "by_result": by_result,
            "top_actors": sorted(by_actor.items(), key=lambda x: x[1], reverse=True)[:5],
            "log_file": str(self._log_file)
        }


def test_audit_log():
    """Test audit log."""
    print("Audit Log Test")
    print("=" * 50)
    
    log = AuditLog()
    
    # Log some events
    log.log_auth("profile_1", True)
    log.log_action("profile_1", "open_app", "notepad", True)
    log.log_denied("profile_2", "system_command", "Insufficient permissions")
    log.log_admin("profile_1", "create_profile", {"name": "Test User"})
    
    # Get recent entries
    entries = log.get_entries(limit=10)
    print(f"Recent entries: {len(entries)}")
    for e in entries:
        print(f"  [{e.event_type}] {e.actor}: {e.action} -> {e.result}")
    
    # Verify integrity
    is_valid, invalid_seq = log.verify_integrity()
    print(f"\nIntegrity: {'VALID' if is_valid else f'INVALID at {invalid_seq}'}")
    
    # Stats
    print(f"Stats: {log.get_stats()}")


if __name__ == "__main__":
    test_audit_log()
