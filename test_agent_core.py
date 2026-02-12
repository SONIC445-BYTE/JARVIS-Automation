"""
AgentCore MVP Test Script
==========================
Tests the ODAV Agent Engine with sample commands.
"""

from AgentCore.intent_parser import IntentParser
from AgentCore.task_planner import TaskPlanner
from AgentCore.agent_brain import AgentBrain

def test_intent_parser():
    """Test intent parsing for various commands."""
    print("=" * 60)
    print("Testing Intent Parser")
    print("=" * 60)
    
    parser = IntentParser()
    
    test_commands = [
        # Deterministic (should go to legacy)
        "open notepad",
        "close chrome",
        "open youtube",
        
        # Non-deterministic (should go to AgentCore)
        "open notepad and type hello world",
        "create a folder called Reports in Documents",
        "download the first pdf from search results",
        "upload the top-right photo to my status",
    ]
    
    for cmd in test_commands:
        intent = parser.parse(cmd)
        requires_agent = parser.requires_agent_core(intent)
        print(f"\nCommand: '{cmd}'")
        print(f"  Action: {intent.action}")
        print(f"  Target App: {intent.target_app}")
        print(f"  Deterministic: {intent.is_deterministic}")
        print(f"  Requires AgentCore: {requires_agent}")
        print(f"  Confidence: {intent.confidence:.2f}")


def test_task_planner():
    """Test task planning for sample intent."""
    print("\n" + "=" * 60)
    print("Testing Task Planner")
    print("=" * 60)
    
    parser = IntentParser()
    planner = TaskPlanner()
    
    intent = parser.parse("open notepad and type hello world")
    plan = planner.create_plan(intent.to_dict())
    
    print(f"\nGenerated plan for: '{intent.raw_command}'")
    print(f"Plan ID: {plan.plan_id}")
    print(f"Total Steps: {plan.total_steps}")
    
    for step in plan.steps:
        print(f"  Step {step.step_number}: {step.action} -> {step.target}")


def test_agent_execution():
    """Test full agent execution - REQUIRES USER TO OBSERVE."""
    print("\n" + "=" * 60)
    print("Testing Full Agent Execution (OBSERVE CAREFULLY)")
    print("=" * 60)
    
    agent = AgentBrain()
    
    # Simple deterministic command
    print("\nExecuting: 'open notepad'")
    result = agent.execute_command("open notepad")
    print(f"Result: {result}")


if __name__ == "__main__":
    print("\n🤖 JARVIS AgentCore MVP Test Suite\n")
    
    # Run tests
    test_intent_parser()
    test_task_planner()
    
    # Ask before running actual execution
    print("\n" + "=" * 60)
    response = input("Run full agent execution test? (y/n): ")
    if response.lower() == 'y':
        test_agent_execution()
    else:
        print("Skipping execution test.")
    
    print("\n✅ Tests complete!")
