"""
Task API - Public Interface for Task Management
=================================================
Entry point for goal-oriented task execution.

Sprint 3: Task Thinking
"""

import time
from typing import Dict, Optional, List
from dataclasses import dataclass

from .task_graph import TaskGraph, TaskNode, TaskStatus, TaskGraphBuilder
from .working_memory import WorkingMemory
from .clarifier import Clarifier, ClarificationRequest


@dataclass
class TaskResult:
    """Result of task execution."""
    task_id: str
    goal: str
    success: bool
    steps_completed: int
    steps_total: int
    duration_ms: float
    result: any = None
    error: Optional[str] = None
    clarifications_asked: int = 0


class TaskManager:
    """
    High-level task management interface.
    
    Public API:
    - start_task(goal) -> task_id
    - pause_task(task_id)
    - resume_task(task_id)
    - get_status(task_id)
    - provide_answer(task_id, slot, value)
    """
    
    def __init__(self):
        self._graphs: Dict[str, TaskGraph] = {}
        self._memory = WorkingMemory()
        self._clarifier = Clarifier()
        self._builder = TaskGraphBuilder()
        self._active_task: Optional[str] = None
        
        print("[TaskManager] Initialized")
    
    def start_task(self, goal: str, context: Dict = None) -> str:
        """
        Start a new task from goal.
        
        Args:
            goal: Natural language goal
            context: Initial context values
            
        Returns:
            Task ID
        """
        # Build task graph
        graph = self._builder.build_from_goal(goal)
        self._graphs[graph.graph_id] = graph
        
        # Store context if provided
        if context:
            self._memory.set_context(graph.graph_id, context)
        
        self._active_task = graph.graph_id
        
        print(f"[TaskManager] Started task {graph.graph_id}: {goal}")
        
        return graph.graph_id
    
    def get_next_action(self, task_id: str) -> Optional[Dict]:
        """
        Get next action to execute for task.
        
        Returns:
            Dict with action info, or None if blocked/done
        """
        graph = self._graphs.get(task_id)
        if not graph:
            return None
        
        # Check for blocked tasks needing clarification
        blocked = graph.get_blocked_tasks()
        if blocked:
            task = blocked[0]
            clarification = self._clarifier.generate_clarification(
                task.task_id,
                task.intent_text or task.description,
                self._memory.get_context(task_id)
            )
            if clarification:
                return {
                    "type": "clarification",
                    "task_id": task.task_id,
                    "question": clarification.question,
                    "slot": clarification.slot_name
                }
        
        # Get next ready task
        next_task = graph.get_next_task()
        if not next_task:
            if graph.is_complete():
                return {"type": "complete", "success": not graph.has_failures()}
            return None
        
        # Check if this task needs clarification
        if next_task.intent_text:
            clarification = self._clarifier.generate_clarification(
                next_task.task_id,
                next_task.intent_text,
                self._memory.get_context(task_id)
            )
            
            if clarification:
                # Mark as blocked
                graph.update_status(next_task.task_id, TaskStatus.BLOCKED)
                next_task.required_slots.append(clarification.slot_name)
                
                return {
                    "type": "clarification",
                    "task_id": next_task.task_id,
                    "question": clarification.question,
                    "slot": clarification.slot_name
                }
        
        # Return action
        return {
            "type": "action",
            "task_id": next_task.task_id,
            "intent": next_task.intent_text,
            "description": next_task.description
        }
    
    def provide_answer(self, task_id: str, slot: str, value: str):
        """
        Provide answer to clarification question.
        
        Args:
            task_id: Task ID (can be graph or node ID)
            slot: Slot name that was asked
            value: User's answer
        """
        # Find the graph
        graph = self._graphs.get(task_id)
        if not graph:
            # Maybe task_id is a node ID
            for g in self._graphs.values():
                if task_id in g.tasks:
                    graph = g
                    break
        
        if not graph:
            return
        
        # Store the slot value
        self._memory.set_slot(graph.graph_id, slot, value)
        self._memory.update_context(graph.graph_id, {slot: value})
        
        # Unblock the task
        for task in graph.tasks.values():
            if task.status == TaskStatus.BLOCKED and slot in task.required_slots:
                task.required_slots.remove(slot)
                if not task.required_slots:
                    task.status = TaskStatus.PENDING
    
    def complete_step(self, task_id: str, node_id: str, success: bool, 
                     result: any = None, error: str = None):
        """
        Mark a task step as completed.
        
        Args:
            task_id: Graph ID
            node_id: Task node ID
            success: Whether step succeeded
            result: Step result
            error: Error message if failed
        """
        graph = self._graphs.get(task_id)
        if not graph:
            return
        
        status = TaskStatus.COMPLETED if success else TaskStatus.FAILED
        graph.update_status(node_id, status, result, error)
    
    def pause_task(self, task_id: str):
        """Pause a task execution."""
        graph = self._graphs.get(task_id)
        if graph:
            # Save checkpoint
            self._memory.checkpoint(f"task_{task_id}")
            print(f"[TaskManager] Paused task {task_id}")
    
    def resume_task(self, task_id: str) -> bool:
        """Resume a paused task."""
        if task_id in self._graphs:
            self._memory.restore(f"task_{task_id}")
            self._active_task = task_id
            print(f"[TaskManager] Resumed task {task_id}")
            return True
        return False
    
    def get_status(self, task_id: str) -> Optional[Dict]:
        """Get current task status."""
        graph = self._graphs.get(task_id)
        if not graph:
            return None
        
        return graph.get_summary()
    
    def cancel_task(self, task_id: str):
        """Cancel a task."""
        graph = self._graphs.get(task_id)
        if graph:
            for task in graph.tasks.values():
                if task.status not in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                    task.status = TaskStatus.CANCELLED
            
            print(f"[TaskManager] Cancelled task {task_id}")
    
    def get_active_task(self) -> Optional[str]:
        """Get currently active task ID."""
        return self._active_task


# ============ Convenience Functions ============

_manager: Optional[TaskManager] = None

def get_task_manager() -> TaskManager:
    """Get singleton TaskManager instance."""
    global _manager
    if _manager is None:
        _manager = TaskManager()
    return _manager


def start_task(goal: str) -> str:
    """Start a task from goal."""
    return get_task_manager().start_task(goal)


def get_next_action(task_id: str) -> Optional[Dict]:
    """Get next action for task."""
    return get_task_manager().get_next_action(task_id)


def test_task_api():
    """Test task API."""
    print("Task API Test")
    print("=" * 50)
    
    manager = TaskManager()
    
    # Start a task
    task_id = manager.start_task("Send message to John")
    print(f"Started task: {task_id}")
    
    # Get next action
    action = manager.get_next_action(task_id)
    print(f"Next action: {action}")
    
    # If clarification needed, provide answer
    if action and action["type"] == "clarification":
        manager.provide_answer(task_id, action["slot"], "Hello John!")
        action = manager.get_next_action(task_id)
        print(f"After answer: {action}")
    
    # Get status
    status = manager.get_status(task_id)
    print(f"Status: {status}")


if __name__ == "__main__":
    test_task_api()
