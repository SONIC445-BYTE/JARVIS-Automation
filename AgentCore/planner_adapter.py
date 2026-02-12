"""
Planner Adapter - Maps Task Graph to Intent Plans
===================================================
Connects task graph nodes to intent planner execution.

Sprint 3: Task Thinking
"""

from typing import Optional, Dict, List

from .task_graph import TaskGraph, TaskNode, TaskStatus
from .intent_planner import IntentPlanner, ActionPlan
from .working_memory import WorkingMemory


class PlannerAdapter:
    """
    Adapts task graph nodes to executable intent plans.
    
    Responsibilities:
    - Converts task descriptions to intents
    - Substitutes slot values from memory
    - Chains multi-step plans
    - Handles dependencies
    """
    
    def __init__(self, memory: WorkingMemory):
        self.planner = IntentPlanner()
        self.memory = memory
    
    def node_to_plan(self, task: TaskNode, graph_id: str) -> Optional[ActionPlan]:
        """
        Convert a task node to an executable plan.
        
        Args:
            task: TaskNode to convert
            graph_id: Parent graph ID for memory access
            
        Returns:
            ActionPlan or None if cannot plan
        """
        if not task.intent_text:
            return None
        
        # Get intent text, substituting any slot values
        intent = self._substitute_slots(task.intent_text, graph_id)
        
        # Add context
        context = self.memory.get_context(graph_id)
        intent = self._add_context(intent, context)
        
        # Generate plan
        plan = self.planner.plan(intent)
        
        if plan:
            # Store reference back to task
            plan.confirm_required = task.context.get("confirm_required", False)
        
        return plan
    
    def _substitute_slots(self, intent: str, graph_id: str) -> str:
        """
        Substitute slot placeholders with values from memory.
        
        Placeholders: {slot_name}
        """
        import re
        
        def replace_slot(match):
            slot_name = match.group(1)
            value = self.memory.get_slot(graph_id, slot_name)
            return value if value else match.group(0)
        
        return re.sub(r'\{(\w+)\}', replace_slot, intent)
    
    def _add_context(self, intent: str, context: Dict) -> str:
        """
        Add context values to intent if relevant.
        
        E.g., if context has 'recipient' and intent mentions 'message',
        add the recipient.
        """
        # Simple version: just substitute any mentioned context keys
        for key, value in context.items():
            if f"{{{key}}}" in intent:
                intent = intent.replace(f"{{{key}}}", str(value))
        
        return intent
    
    def get_ready_plans(self, graph: TaskGraph) -> List[tuple]:
        """
        Get executable plans for all ready tasks.
        
        Returns:
            List of (TaskNode, ActionPlan) tuples
        """
        plans = []
        
        for task in graph.get_ready_tasks():
            plan = self.node_to_plan(task, graph.graph_id)
            if plan:
                plans.append((task, plan))
        
        return plans
    
    def chain_plans(self, plans: List[ActionPlan]) -> ActionPlan:
        """
        Chain multiple plans into a single sequential plan.
        
        Args:
            plans: List of ActionPlans to chain
            
        Returns:
            Combined ActionPlan
        """
        if not plans:
            return None
        
        if len(plans) == 1:
            return plans[0]
        
        # Create combined plan
        combined = ActionPlan(
            plan_id=f"chain_{plans[0].plan_id}",
            intent_text=" then ".join(p.intent_text for p in plans),
            steps=[],
            risk_level="standard",
            confirm_required=any(p.confirm_required for p in plans)
        )
        
        step_id = 1
        for plan in plans:
            for step in plan.steps:
                step.step_id = step_id
                combined.steps.append(step)
                step_id += 1
        
        return combined


def test_planner_adapter():
    """Test planner adapter."""
    print("Planner Adapter Test")
    print("=" * 50)
    
    memory = WorkingMemory()
    adapter = PlannerAdapter(memory)
    
    # Set up memory
    graph_id = "test_graph"
    memory.set_slot(graph_id, "recipient", "John")
    memory.set_context(graph_id, {"recipient": "John", "app": "whatsapp"})
    
    # Create a mock task
    from .task_graph import TaskNode
    task = TaskNode(
        task_id="task_1",
        description="Send message",
        intent_text="send message to {recipient}"
    )
    
    # Generate plan
    plan = adapter.node_to_plan(task, graph_id)
    
    if plan:
        print(f"Generated plan: {plan.plan_id}")
        print(f"Intent: {plan.intent_text}")
        print(f"Steps: {len(plan.steps)}")
    else:
        print("Could not generate plan")


if __name__ == "__main__":
    test_planner_adapter()
