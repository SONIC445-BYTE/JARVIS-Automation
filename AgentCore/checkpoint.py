"""
Execution Checkpoints for ODAV Recovery
========================================
Saves state after each major step for rollback capability.
"""

import json
import hashlib
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any, List
import pyautogui


@dataclass
class Checkpoint:
    """Represents a saved execution state."""
    checkpoint_id: str
    step_number: int
    timestamp: str
    active_window: str
    cursor_position: tuple
    ui_tree_hash: str
    intent_id: str
    notes: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class CheckpointManager:
    """
    Manages execution checkpoints for recovery.
    
    ODAV Role: Enables "Verify" step to roll back on failure.
    """
    
    def __init__(self, max_checkpoints: int = 10):
        self.checkpoints: List[Checkpoint] = []
        self.max_checkpoints = max_checkpoints
        self.current_intent_id: Optional[str] = None
        
    def create_checkpoint(
        self,
        step_number: int,
        active_window: str,
        ui_tree: Dict[str, Any],
        intent_id: str,
        notes: str = ""
    ) -> Checkpoint:
        """
        Save current execution state.
        
        Args:
            step_number: Current step in execution plan
            active_window: Name of active window
            ui_tree: Current UI tree snapshot
            intent_id: ID of current intent being executed
            notes: Optional notes about this checkpoint
            
        Returns:
            Created Checkpoint object
        """
        # Get cursor position
        cursor_pos = pyautogui.position()
        
        # Hash the UI tree for comparison
        ui_hash = hashlib.md5(
            json.dumps(ui_tree, sort_keys=True, default=str).encode()
        ).hexdigest()[:12]
        
        checkpoint = Checkpoint(
            checkpoint_id=f"cp_{step_number}_{datetime.now().strftime('%H%M%S')}",
            step_number=step_number,
            timestamp=datetime.now().isoformat(),
            active_window=active_window,
            cursor_position=(cursor_pos.x, cursor_pos.y),
            ui_tree_hash=ui_hash,
            intent_id=intent_id,
            notes=notes
        )
        
        self.checkpoints.append(checkpoint)
        self.current_intent_id = intent_id
        
        # Prune old checkpoints
        if len(self.checkpoints) > self.max_checkpoints:
            self.checkpoints = self.checkpoints[-self.max_checkpoints:]
            
        print(f"DEBUG Checkpoint created: {checkpoint.checkpoint_id} at step {step_number}")
        return checkpoint
    
    def get_last_checkpoint(self) -> Optional[Checkpoint]:
        """Get the most recent checkpoint."""
        return self.checkpoints[-1] if self.checkpoints else None
    
    def get_checkpoint_at_step(self, step_number: int) -> Optional[Checkpoint]:
        """Get checkpoint for a specific step."""
        for cp in reversed(self.checkpoints):
            if cp.step_number == step_number:
                return cp
        return None
    
    def rollback_to_step(self, step_number: int) -> Optional[Checkpoint]:
        """
        Roll back to a specific step's checkpoint.
        Removes all checkpoints after that step.
        
        Returns:
            The checkpoint rolled back to, or None if not found
        """
        target_cp = None
        for i, cp in enumerate(self.checkpoints):
            if cp.step_number == step_number:
                target_cp = cp
                # Remove all checkpoints after this one
                self.checkpoints = self.checkpoints[:i+1]
                break
                
        if target_cp:
            print(f"DEBUG Rolled back to checkpoint: {target_cp.checkpoint_id}")
        return target_cp
    
    def clear_for_intent(self, intent_id: str):
        """Clear all checkpoints for a specific intent."""
        self.checkpoints = [
            cp for cp in self.checkpoints 
            if cp.intent_id != intent_id
        ]
        
    def get_execution_history(self) -> List[Dict[str, Any]]:
        """Get history of all checkpoints as dicts."""
        return [cp.to_dict() for cp in self.checkpoints]
