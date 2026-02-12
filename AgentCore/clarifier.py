"""
Clarifier - Minimal Question Generator
========================================
Identifies missing slot values and generates clarification questions.

Sprint 3: Task Thinking
"""

import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass


@dataclass
class ClarificationRequest:
    """Request for clarification."""
    task_id: str
    slot_name: str
    question: str
    options: List[str] = None
    required: bool = True
    
    def to_prompt(self) -> str:
        """Get prompt for user."""
        if self.options:
            opts = ", ".join(self.options[:-1]) + f", or {self.options[-1]}"
            return f"{self.question} ({opts})"
        return self.question


class Clarifier:
    """
    Identifies missing information and generates questions.
    
    Principles:
    - Minimal questions (only ask what's missing)
    - Provide options when possible
    - Never ask more than needed
    """
    
    # Slot patterns: what to look for in intent
    SLOT_PATTERNS = {
        "recipient": [
            r"(?:to|for)\s+([a-zA-Z]+(?:\s+[a-zA-Z]+)?)",
            r"message\s+([a-zA-Z]+(?:\s+[a-zA-Z]+)?)"
        ],
        "file": [
            r"(?:upload|download|open|send)\s+(?:the\s+)?([^\s]+\.[a-z]+)",
            r"file\s+(?:named?\s+)?([^\s]+)"
        ],
        "destination": [
            r"to\s+(.+)$",
            r"on\s+(.+)$"
        ],
        "query": [
            r"search\s+(?:for\s+)?['\"]?(.+?)['\"]?(?:\s+on|\s*$)",
            r"find\s+(.+)"
        ],
        "app": [
            r"(?:open|close|use)\s+([a-zA-Z]+)"
        ]
    }
    
    # Questions for each slot
    SLOT_QUESTIONS = {
        "recipient": "Who should I send this to?",
        "file": "Which file?",
        "destination": "Where should I put it?",
        "query": "What should I search for?",
        "app": "Which app?",
        "message": "What message?",
        "folder": "Which folder?"
    }
    
    # Required slots for command types
    REQUIRED_SLOTS = {
        "send": ["recipient", "message"],
        "upload": ["file", "destination"],
        "download": ["file"],
        "search": ["query"],
        "email": ["recipient", "subject"],
        "message": ["recipient", "message"]
    }
    
    def extract_slots(self, intent: str) -> Dict[str, str]:
        """
        Extract slot values from intent.
        
        Returns:
            Dict of slot_name -> extracted_value
        """
        slots = {}
        intent_lower = intent.lower()
        
        for slot_name, patterns in self.SLOT_PATTERNS.items():
            for pattern in patterns:
                match = re.search(pattern, intent_lower)
                if match:
                    slots[slot_name] = match.group(1).strip()
                    break
        
        return slots
    
    def get_missing_slots(self, intent: str, extracted: Dict[str, str]) -> List[str]:
        """
        Identify missing required slots.
        
        Args:
            intent: Original intent text
            extracted: Already extracted slots
            
        Returns:
            List of missing slot names
        """
        intent_lower = intent.lower()
        missing = []
        
        # Determine required slots based on command type
        for cmd_type, required in self.REQUIRED_SLOTS.items():
            if cmd_type in intent_lower:
                for slot in required:
                    if slot not in extracted:
                        missing.append(slot)
                break
        
        return missing
    
    def generate_clarification(self, task_id: str, intent: str,
                              context: Dict = None) -> Optional[ClarificationRequest]:
        """
        Generate clarification request if needed.
        
        Args:
            task_id: Associated task ID
            intent: Intent text
            context: Additional context
            
        Returns:
            ClarificationRequest or None if no clarification needed
        """
        context = context or {}
        
        # Extract what we can
        extracted = self.extract_slots(intent)
        extracted.update(context)  # Context may have answers
        
        # Find missing
        missing = self.get_missing_slots(intent, extracted)
        
        if not missing:
            return None
        
        # Generate question for first missing slot
        slot = missing[0]
        question = self.SLOT_QUESTIONS.get(slot, f"What is the {slot}?")
        
        # Add options if available
        options = self._get_slot_options(slot, context)
        
        return ClarificationRequest(
            task_id=task_id,
            slot_name=slot,
            question=question,
            options=options
        )
    
    def _get_slot_options(self, slot: str, context: Dict) -> Optional[List[str]]:
        """Get option suggestions for a slot."""
        # Could integrate with contact list, recent files, etc.
        # For now, return None (free-form entry)
        return None
    
    def parse_answer(self, question: ClarificationRequest, answer: str) -> Tuple[str, str]:
        """
        Parse user's answer to clarification.
        
        Returns:
            (slot_name, extracted_value)
        """
        # Clean answer
        answer = answer.strip()
        
        # If options were given, check for match
        if question.options:
            answer_lower = answer.lower()
            for opt in question.options:
                if opt.lower() in answer_lower or answer_lower in opt.lower():
                    return (question.slot_name, opt)
        
        return (question.slot_name, answer)
    
    def is_affirmative(self, text: str) -> bool:
        """Check if text is affirmative response."""
        affirmatives = ["yes", "yeah", "yep", "ok", "okay", "sure", "correct", "right", "confirm", "do it"]
        return any(a in text.lower() for a in affirmatives)
    
    def is_negative(self, text: str) -> bool:
        """Check if text is negative response."""
        negatives = ["no", "nope", "cancel", "stop", "don't", "nevermind", "never mind"]
        return any(n in text.lower() for n in negatives)


def test_clarifier():
    """Test clarifier."""
    print("Clarifier Test")
    print("=" * 50)
    
    clarifier = Clarifier()
    
    tests = [
        "send a message to John",
        "upload the report to drive",
        "search for python tutorials",
        "send email",  # Missing recipient and subject
    ]
    
    for intent in tests:
        print(f"\nIntent: '{intent}'")
        
        extracted = clarifier.extract_slots(intent)
        print(f"  Extracted: {extracted}")
        
        clarification = clarifier.generate_clarification("test", intent)
        if clarification:
            print(f"  Needs clarification: {clarification.question}")
        else:
            print(f"  No clarification needed")


if __name__ == "__main__":
    test_clarifier()
