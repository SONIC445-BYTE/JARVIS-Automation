"""
Trust Engine - Command Classification and Confirmation
========================================================
Classifies commands by risk level and requires confirmation for dangerous ones.
"""

from enum import Enum
from typing import Tuple, Optional
import re


class CommandRisk(Enum):
    """Command risk classification."""
    HARMLESS = "harmless"       # "What time is it"
    STANDARD = "standard"       # "Open notepad"
    DESTRUCTIVE = "destructive" # "Delete files", "Close all"
    SYSTEM = "system"           # "Shut down", "Restart"


class TrustEngine:
    """
    Classifies commands and determines if confirmation required.
    
    Trust levels mirror Siri/Alexa skill sandboxes.
    """
    
    # Patterns for each risk level
    SYSTEM_PATTERNS = [
        r"\bshut\s*down\b",
        r"\brestart\b",
        r"\breboot\b",
        r"\blog\s*off\b",
        r"\blog\s*out\b",
        r"\bhibernate\b",
        r"\bsleep\s*(the\s*)?(computer|system|pc)\b",
    ]
    
    DESTRUCTIVE_PATTERNS = [
        r"\bdelete\b",
        r"\bremove\b",
        r"\berase\b",
        r"\bformat\b",
        r"\bclose\s*all\b",
        r"\bkill\s*all\b",
        r"\bterminate\b",
        r"\buninstall\b",
        r"\bclear\s*(all|everything)\b",
    ]
    
    STANDARD_PATTERNS = [
        r"\bopen\b",
        r"\bclose\b",
        r"\bplay\b",
        r"\bsearch\b",
        r"\bfind\b",
        r"\bgo\s*to\b",
        r"\bnavigate\b",
        r"\btype\b",
        r"\bclick\b",
        r"\bscroll\b",
        r"\bset\s*(volume|brightness)\b",
    ]
    
    # Confirmation phrases
    CONFIRMATION_PHRASES = ["yes", "confirm", "do it", "proceed", "go ahead", "affirmative"]
    DENIAL_PHRASES = ["no", "cancel", "stop", "abort", "never mind", "don't"]
    
    def __init__(self):
        # Compile patterns for performance
        self._system_re = [re.compile(p, re.IGNORECASE) for p in self.SYSTEM_PATTERNS]
        self._destructive_re = [re.compile(p, re.IGNORECASE) for p in self.DESTRUCTIVE_PATTERNS]
        self._standard_re = [re.compile(p, re.IGNORECASE) for p in self.STANDARD_PATTERNS]
    
    def classify(self, command: str) -> CommandRisk:
        """
        Classify command by risk level.
        
        Args:
            command: User command text
            
        Returns:
            CommandRisk level
        """
        command = command.strip()
        
        # Check system-level (highest priority)
        for pattern in self._system_re:
            if pattern.search(command):
                return CommandRisk.SYSTEM
        
        # Check destructive
        for pattern in self._destructive_re:
            if pattern.search(command):
                return CommandRisk.DESTRUCTIVE
        
        # Check standard
        for pattern in self._standard_re:
            if pattern.search(command):
                return CommandRisk.STANDARD
        
        # Default to harmless
        return CommandRisk.HARMLESS
    
    def requires_confirmation(self, risk: CommandRisk) -> bool:
        """Check if risk level requires confirmation."""
        return risk in [CommandRisk.DESTRUCTIVE, CommandRisk.SYSTEM]
    
    def get_confirmation_prompt(self, command: str, risk: CommandRisk) -> str:
        """Get appropriate confirmation prompt."""
        if risk == CommandRisk.SYSTEM:
            return f"This will affect your system. Are you sure you want to {self._extract_action(command)}?"
        elif risk == CommandRisk.DESTRUCTIVE:
            return f"This action cannot be undone. Confirm {self._extract_action(command)}?"
        return "Please confirm."
    
    def _extract_action(self, command: str) -> str:
        """Extract action verb from command."""
        words = command.lower().split()
        action_verbs = ["shut", "restart", "delete", "remove", "close", "kill", "format", "erase"]
        for word in words:
            if word in action_verbs:
                return word
        return "proceed"
    
    def is_confirmation(self, response: str) -> bool:
        """Check if response is a confirmation."""
        response_lower = response.lower().strip()
        return any(phrase in response_lower for phrase in self.CONFIRMATION_PHRASES)
    
    def is_denial(self, response: str) -> bool:
        """Check if response is a denial."""
        response_lower = response.lower().strip()
        return any(phrase in response_lower for phrase in self.DENIAL_PHRASES)
    
    def evaluate_response(self, response: str) -> Tuple[bool, str]:
        """
        Evaluate confirmation response.
        
        Returns:
            (allowed, message)
        """
        if self.is_confirmation(response):
            return True, "Confirmed"
        elif self.is_denial(response):
            return False, "Cancelled"
        else:
            return False, "Please say yes or no"


def test_trust_engine():
    """Test trust engine classification."""
    engine = TrustEngine()
    
    tests = [
        ("what time is it", CommandRisk.HARMLESS),
        ("open notepad", CommandRisk.STANDARD),
        ("play music", CommandRisk.STANDARD),
        ("delete all files", CommandRisk.DESTRUCTIVE),
        ("close all windows", CommandRisk.DESTRUCTIVE),
        ("shut down the computer", CommandRisk.SYSTEM),
        ("restart", CommandRisk.SYSTEM),
    ]
    
    print("Trust Engine Classification Test")
    print("=" * 50)
    
    for command, expected in tests:
        result = engine.classify(command)
        status = "✓" if result == expected else "✗"
        print(f"{status} '{command}' -> {result.value} (expected: {expected.value})")


if __name__ == "__main__":
    test_trust_engine()
