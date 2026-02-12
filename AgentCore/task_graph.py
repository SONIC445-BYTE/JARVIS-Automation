"""
Task Graph - Goal Decomposition and Planning
==============================================
Breaks high-level goals into subtasks with dependencies.

Sprint 3: Task Thinking
"""

import time
import uuid
from typing import List, Dict, Optional, Any, Set
from dataclasses import dataclass, field
from enum import Enum


class TaskStatus(Enum):
    """Task execution status."""
    PENDING = "pending"
    WAITING = "waiting"      # Waiting for dependencies
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"      # Needs clarification
    CANCELLED = "cancelled"


class TaskPriority(Enum):
    """Task priority levels."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class TaskNode:
    """
    Single task in the execution graph.
    
    Tasks can be:
    - Atomic (single action)
    - Composite (has subtasks)
    """
    task_id: str
    description: str
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.NORMAL
    
    # Relationships
    parent_id: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)
    subtasks: List[str] = field(default_factory=list)
    
    # Execution
    intent_text: Optional[str] = None  # For atomic tasks
    retries: int = 0
    max_retries: int = 2
    
    # Context
    context: Dict = field(default_factory=dict)
    required_slots: List[str] = field(default_factory=list)  # Missing info
    
    # Timing
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    
    # Result
    result: Any = None
    error: Optional[str] = None
    
    def is_ready(self, graph: 'TaskGraph') -> bool:
        """Check if task is ready to execute."""
        if self.status != TaskStatus.PENDING:
            return False
        
        # Check all dependencies are completed
        for dep_id in self.dependencies:
            dep_task = graph.get_task(dep_id)
            if not dep_task or dep_task.status != TaskStatus.COMPLETED:
                return False
        
        return True
    
    def has_missing_slots(self) -> bool:
        """Check if task needs clarification."""
        return len(self.required_slots) > 0
    
    @property
    def duration_ms(self) -> float:
        """Get execution duration."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at) * 1000
        return 0


@dataclass
class TaskGraph:
    """
    Directed acyclic graph of tasks.
    
    Supports:
    - Goal decomposition
    - Dependency tracking
    - Parallel execution of independent tasks
    - Status tracking
    """
    
    graph_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    goal: str = ""
    tasks: Dict[str, TaskNode] = field(default_factory=dict)
    root_task_ids: List[str] = field(default_factory=list)
    
    def add_task(self, description: str, 
                parent_id: Optional[str] = None,
                dependencies: List[str] = None,
                intent_text: Optional[str] = None,
                context: Dict = None,
                priority: TaskPriority = TaskPriority.NORMAL) -> TaskNode:
        """
        Add a task to the graph.
        
        Args:
            description: Human-readable task description
            parent_id: Parent task ID (for subtasks)
            dependencies: Task IDs that must complete first
            intent_text: Intent for atomic execution
            context: Additional context
            priority: Task priority
            
        Returns:
            Created TaskNode
        """
        task_id = f"task_{len(self.tasks) + 1}"
        
        task = TaskNode(
            task_id=task_id,
            description=description,
            parent_id=parent_id,
            dependencies=dependencies or [],
            intent_text=intent_text,
            context=context or {},
            priority=priority
        )
        
        self.tasks[task_id] = task
        
        # Track root tasks
        if not parent_id:
            self.root_task_ids.append(task_id)
        else:
            # Add to parent's subtasks
            parent = self.get_task(parent_id)
            if parent:
                parent.subtasks.append(task_id)
        
        return task
    
    def get_task(self, task_id: str) -> Optional[TaskNode]:
        """Get task by ID."""
        return self.tasks.get(task_id)
    
    def get_ready_tasks(self) -> List[TaskNode]:
        """Get all tasks ready for execution."""
        return [t for t in self.tasks.values() if t.is_ready(self)]
    
    def get_next_task(self) -> Optional[TaskNode]:
        """Get highest priority ready task."""
        ready = self.get_ready_tasks()
        if not ready:
            return None
        
        # Sort by priority (highest first)
        ready.sort(key=lambda t: t.priority.value, reverse=True)
        return ready[0]
    
    def update_status(self, task_id: str, status: TaskStatus, 
                     result: Any = None, error: Optional[str] = None):
        """Update task status."""
        task = self.get_task(task_id)
        if not task:
            return
        
        task.status = status
        task.result = result
        task.error = error
        
        if status == TaskStatus.IN_PROGRESS:
            task.started_at = time.time()
        elif status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
            task.completed_at = time.time()
    
    def is_complete(self) -> bool:
        """Check if all tasks are done."""
        return all(
            t.status in [TaskStatus.COMPLETED, TaskStatus.CANCELLED]
            for t in self.tasks.values()
        )
    
    def has_failures(self) -> bool:
        """Check for any failed tasks."""
        return any(t.status == TaskStatus.FAILED for t in self.tasks.values())
    
    def get_blocked_tasks(self) -> List[TaskNode]:
        """Get tasks needing clarification."""
        return [t for t in self.tasks.values() if t.status == TaskStatus.BLOCKED]
    
    def get_summary(self) -> Dict:
        """Get graph execution summary."""
        by_status = {}
        for task in self.tasks.values():
            status = task.status.value
            by_status[status] = by_status.get(status, 0) + 1
        
        return {
            "graph_id": self.graph_id,
            "goal": self.goal,
            "total_tasks": len(self.tasks),
            "by_status": by_status,
            "is_complete": self.is_complete(),
            "has_failures": self.has_failures()
        }
    
    def visualize(self) -> str:
        """Simple text visualization."""
        lines = [f"Task Graph: {self.goal}", "=" * 40]
        
        for task in self.tasks.values():
            indent = "  " if task.parent_id else ""
            status_icon = {
                TaskStatus.PENDING: "○",
                TaskStatus.WAITING: "◔",
                TaskStatus.IN_PROGRESS: "◐",
                TaskStatus.COMPLETED: "●",
                TaskStatus.FAILED: "✗",
                TaskStatus.BLOCKED: "?",
                TaskStatus.CANCELLED: "-"
            }.get(task.status, "?")
            
            deps = f" [deps: {task.dependencies}]" if task.dependencies else ""
            lines.append(f"{indent}{status_icon} {task.task_id}: {task.description}{deps}")
        
        return "\n".join(lines)


class TaskGraphBuilder:
    """
    Builds task graphs from goal descriptions.
    
    Uses patterns to decompose common goals.
    """
    
    # Common goal patterns
    GOAL_PATTERNS = {
        r"(?:send|write)\s+(?:a\s+)?message": "messaging_flow",
        r"upload\s+.*\s+to": "upload_flow",
        r"download\s+.*\s+from": "download_flow",
        r"search\s+.*\s+(?:and|then)": "search_flow",
        r"open\s+.*\s+(?:and|then)": "multi_step_flow",
    }
    
    def build_from_goal(self, goal: str) -> TaskGraph:
        """
        Build task graph from goal description.
        
        Args:
            goal: Natural language goal
            
        Returns:
            TaskGraph ready for execution
        """
        graph = TaskGraph(goal=goal)
        
        # For now, create single task
        # Complex decomposition would go here
        graph.add_task(
            description=goal,
            intent_text=goal,
            priority=TaskPriority.NORMAL
        )
        
        return graph
    
    def decompose_messaging(self, goal: str, recipient: str, message: str) -> TaskGraph:
        """Example: Decompose messaging goal."""
        graph = TaskGraph(goal=goal)
        
        # Task 1: Open messaging app
        t1 = graph.add_task(
            description=f"Open messaging app",
            intent_text="open whatsapp"
        )
        
        # Task 2: Find recipient (depends on t1)
        t2 = graph.add_task(
            description=f"Find {recipient}",
            dependencies=[t1.task_id],
            intent_text=f"search for {recipient}"
        )
        
        # Task 3: Send message (depends on t2)
        t3 = graph.add_task(
            description=f"Send message",
            dependencies=[t2.task_id],
            intent_text=f"type {message}"
        )
        
        return graph


def test_task_graph():
    """Test task graph."""
    print("Task Graph Test")
    print("=" * 50)
    
    # Create graph
    graph = TaskGraph(goal="Send message to John")
    
    # Add tasks
    t1 = graph.add_task("Open WhatsApp", intent_text="open whatsapp")
    t2 = graph.add_task("Search for John", dependencies=[t1.task_id], intent_text="search john")
    t3 = graph.add_task("Type message", dependencies=[t2.task_id], intent_text="type hello")
    
    print(graph.visualize())
    print()
    
    # Get next task
    next_task = graph.get_next_task()
    print(f"Next task: {next_task.description if next_task else 'None'}")
    
    # Complete first task
    graph.update_status(t1.task_id, TaskStatus.COMPLETED)
    print(f"\nAfter completing t1:")
    print(graph.visualize())


if __name__ == "__main__":
    test_task_graph()
