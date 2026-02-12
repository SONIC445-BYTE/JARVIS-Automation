"""
LLM Command Parser - Natural Language to Action Sequences
========================================================
Uses local LLM to parse complex, multi-step commands into executable action sequences.
"""
import json
import re
import uuid
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict

@dataclass
class ActionStep:
    """A single action in a multi-step command."""
    action: str
    target: str
    parameters: Dict[str, Any] = None
    wait_for_ui: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'action': self.action,
            'target': self.target,
            'parameters': self.parameters or {},
            'wait_for_ui': self.wait_for_ui
        }

class LLMCommandParser:
    """Parses natural language commands into executable action sequences using LLM."""
    
    # System prompt for the LLM
    SYSTEM_PROMPT = """You are a command parser that converts natural language into structured action sequences.
    
    CRITICAL INSTRUCTIONS:
    1. You MUST return ONLY a compact JSON array of action objects.
    2. Do NOT include markdown formatting, code blocks, or explanations.
    3. If you cannot understand the command, return an empty array [].
    
    Allowed Actions (Strict Whitelist):
    - open_app: {"action": "open_app", "target": "app_name"}
    - navigate: {"action": "navigate", "target": "url"}
    - search: {"action": "search", "target": "query"}
    - click: {"action": "click", "target": "element_description"}
    - type: {"action": "type", "target": "text"}
    - wait: {"action": "wait", "target": "condition"}
    
    Example Input: "open chrome and search for python"
    Example Output: [{"action": "open_app", "target": "chrome"}, {"action": "search", "target": "python"}]
    """
    
    def __init__(self, llm_engine=None):
        """Initialize the parser with an optional LLM engine."""
        from .llm_engine import LLMEngine
        self.llm = llm_engine or LLMEngine()
        self.available_actions = ["open_app", "navigate", "search", "click", "type", "wait"]
    
    def parse(self, command: str) -> List[Dict[str, Any]]:
        """
        Parse a natural language command into a sequence of actions.
        
        Args:
            command: The natural language command to parse
            
        Returns:
            List of action dictionaries
        """
        if not command or not command.strip():
            return []
            
        # Clean the command
        command = command.strip()
        
        # Try to parse with LLM first
        if self.llm.is_available():
            try:
                return self._parse_with_llm(command)
            except Exception as e:
                print(f"[LLMCommandParser] Error parsing with LLM: {e}")
                # Fall through to rule-based parser
        
        # Fall back to rule-based parsing if LLM fails
        return self._parse_with_rules(command)
    
    def _parse_with_llm(self, command: str) -> List[Dict[str, Any]]:
        """Parse command using LLM."""
        prompt = f"Convert this command into a sequence of actions: {command}"
        
        try:
            # Get response from LLM
            response = self.llm.chat(
                messages=[{"role": "user", "content": prompt}],
                system=self.SYSTEM_PROMPT
            )
            
            # Clean and parse the response
            json_str = self._extract_json(response.text)
            actions = json.loads(json_str)
            
            # Validate and normalize actions
            return self._validate_actions(actions)
            
        except json.JSONDecodeError as e:
            print(f"[LLMCommandParser] Invalid JSON from LLM: {e}")
            print(f"Response was: {response.text}")
            raise ValueError("Failed to parse command. The response was not valid JSON.")
        except Exception as e:
            print(f"[LLMCommandParser] Error during LLM parsing: {e}")
            raise
    
    def _extract_json(self, text: str) -> str:
        """Extract JSON string from LLM response."""
        text = text.strip()
        
        # Try to extract JSON from code blocks
        json_match = re.search(r'```(?:json\n)?(.*?)```', text, re.DOTALL)
        if json_match:
            return json_match.group(1).strip()
            
        # Try to find JSON object/array
        json_match = re.search(r'[\[\{].*[\}\]]', text, re.DOTALL)
        if json_match:
            return json_match.group(0).strip()
            
        # If no JSON found, try to use the whole response
        return text
    
    def _validate_actions(self, actions) -> List[Dict[str, Any]]:
        """Validate and normalize actions from LLM. Raises ValueError on failure."""
        if not isinstance(actions, list):
            raise ValueError(f"LLM returned {type(actions)}, expected list.")
            
        validated = []
        for i, action in enumerate(actions, 1):
            if not isinstance(action, dict):
                 raise ValueError(f"Action {i} is not a dictionary.")
                
            # Ensure required fields
            action_type = action.get('action', '').lower()
            if not action_type:
                 raise ValueError(f"Action {i} is missing 'action' field.")
                
            if action_type not in self.available_actions:
                 raise ValueError(f"Unknown action type '{action_type}' in action {i}. Allowed: {self.available_actions}")
                
            # Normalize the action
            validated_action = {
                'action': action_type,
                'target': str(action.get('target', '')),
                'parameters': action.get('parameters', {}) or {},
                'wait_for_ui': bool(action.get('wait_for_ui', False))
            }
            
            # Legacy/Safety: Reject empty targets for certain actions
            if action_type in ["open_app", "navigate", "type", "search"] and not validated_action['target']:
                 raise ValueError(f"Action '{action_type}' requires a target.")

            # Add any additional parameters
            for key, value in action.items():
                if key not in ['action', 'target', 'parameters', 'wait_for_ui']:
                    validated_action['parameters'][key] = value
            
            validated.append(validated_action)
            
        return validated
    
    def _parse_with_rules(self, command: str) -> List[Dict[str, Any]]:
        """Fallback rule-based command parser."""
        command = command.lower().strip()
        actions = []
        
        # Simple rule for "open X"
        if command.startswith("open "):
            target = command[5:].strip()
            actions.append({
                "action": "open_app",
                "target": target,
                "parameters": {}
            })
        # Simple rule for "search for X"
        elif "search for " in command:
            query = command.split("search for ", 1)[1].strip()
            actions.append({
                "action": "search",
                "target": query,
                "parameters": {}
            })
        # Simple rule for "go to X"
        elif command.startswith("go to "):
            url = command[6:].strip()
            if not url.startswith(('http://', 'https://')):
                url = f'https://{url}'
            actions.append({
                "action": "navigate",
                "target": url,
                "parameters": {}
            })
        # Default action if no rules match
        else:
            # SAFETY: Do NOT return unknown action. 
            print("[LLMCommandParser] Rule-based parser found no matches. Returning empty.")
            return []
            
        return actions

    def format_actions(self, actions: List[Dict]) -> str:
        """Format actions as a human-readable string."""
        if not actions:
            return "No actions to perform"
            
        lines = ["Action Plan:"]
        for i, action in enumerate(actions, 1):
            action_type = action.get('action', 'unknown').upper()
            target = action.get('target', '')
            params = action.get('parameters', {})
            
            line = f"  {i}. {action_type}"
            if target:
                line += f" -> {target}"
            if params:
                line += f" ({', '.join(f'{k}={v}' for k, v in params.items())})"
                
            lines.append(line)
            
        return '\n'.join(lines)
