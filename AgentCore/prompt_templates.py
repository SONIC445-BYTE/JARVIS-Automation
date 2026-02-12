"""
Prompt Templates - JARVIS Personality & Task Prompts
=====================================================
System prompts for consistent JARVIS behavior.

Sprint 6: Conversational Intelligence
"""

from typing import Dict, Optional


class PromptTemplates:
    """
    Prompt templates for JARVIS personality and tasks.
    
    All prompts are designed for small, CPU-friendly models.
    Keep prompts concise to minimize token usage.
    """
    
    # ============ System Prompts ============
    
    JARVIS_SYSTEM = """You are JARVIS, a helpful AI assistant for Windows.

Rules:
- Be concise and direct
- Answer in 1-3 sentences when possible
- For commands, confirm and execute
- For questions, explain briefly
- Never mention being an AI or language model
- Speak naturally, as if you're a capable personal assistant

You can: open apps, search the web, send messages, explain topics, remember preferences."""

    JARVIS_MINIMAL = """You are JARVIS, a personal assistant. Be brief and helpful."""

    # ============ Task-Specific Prompts ============
    
    EXPLAIN_TEMPLATE = """Explain {topic} in simple terms. Keep it under 100 words."""
    
    CLARIFY_TEMPLATE = """The user said: "{command}"
I need clarification. What ONE question should I ask to proceed?
Reply with just the question."""
    
    PLAN_TEMPLATE = """Break this into steps: "{goal}"
List 2-5 simple steps. Be brief."""
    
    CONFIRM_TEMPLATE = """Confirm this action: {action}
Reply: "Proceeding with [brief description]" or ask for clarification."""
    
    SUMMARIZE_TEMPLATE = """Summarize in one sentence: {text}"""
    
    # ============ Response Templates ============
    
    RESPONSES = {
        "wake": ["Yes?", "I'm here.", "How can I help?"],
        "confirm": ["Done.", "Completed.", "Task finished."],
        "thinking": ["Let me think...", "One moment..."],
        "error": ["I encountered an issue.", "That didn't work."],
        "clarify": ["Could you clarify?", "I need more information."],
        "goodbye": ["Goodbye.", "Standing by.", "Going to sleep."]
    }
    
    @classmethod
    def get_system(cls, minimal: bool = False) -> str:
        """Get system prompt."""
        return cls.JARVIS_MINIMAL if minimal else cls.JARVIS_SYSTEM
    
    @classmethod
    def explain(cls, topic: str) -> str:
        """Get explain prompt."""
        return cls.EXPLAIN_TEMPLATE.format(topic=topic)
    
    @classmethod
    def clarify(cls, command: str) -> str:
        """Get clarification prompt."""
        return cls.CLARIFY_TEMPLATE.format(command=command)
    
    @classmethod
    def plan(cls, goal: str) -> str:
        """Get planning prompt."""
        return cls.PLAN_TEMPLATE.format(goal=goal)
    
    @classmethod
    def confirm(cls, action: str) -> str:
        """Get confirmation prompt."""
        return cls.CONFIRM_TEMPLATE.format(action=action)
    
    @classmethod
    def summarize(cls, text: str) -> str:
        """Get summarization prompt."""
        return cls.SUMMARIZE_TEMPLATE.format(text=text)
    
    @classmethod
    def get_response(cls, category: str, index: int = 0) -> str:
        """Get canned response."""
        responses = cls.RESPONSES.get(category, ["Acknowledged."])
        return responses[index % len(responses)]


# ============ Intent Detection ============

INTENT_CLASSIFIER = """Classify this as one category:
- ACTION: user wants something done (open, send, search, play)
- QUESTION: user asks for information or explanation
- CHAT: casual conversation
- CONFIRM: yes/no response
- ABORT: user wants to cancel

User: "{text}"
Reply with ONE word: ACTION, QUESTION, CHAT, CONFIRM, or ABORT."""


# ============ Quick Templates ============

def quick_explain(topic: str) -> tuple:
    """Return (system, prompt) for explanation."""
    return (PromptTemplates.JARVIS_MINIMAL, PromptTemplates.explain(topic))


def quick_chat(user_message: str) -> tuple:
    """Return (system, prompt) for chat."""
    return (PromptTemplates.JARVIS_SYSTEM, user_message)


def classify_intent(text: str) -> str:
    """Return prompt to classify intent."""
    return INTENT_CLASSIFIER.format(text=text)
