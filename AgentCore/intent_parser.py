"""
Intent Parser - Rule-First with TurboSeek Fallback
===================================================
Converts natural language → structured Intent JSON.

ODAV Role: "Decide" layer - determines what action to take.
"""

import re
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple, Union
from dataclasses import dataclass, field, asdict


@dataclass
class Intent:
    """Structured intent extracted from natural language."""
    intent_id: str
    raw_command: str
    action: str
    target_app: Optional[str] = None
    source_app: Optional[str] = None
    object_type: Optional[str] = None
    object_selector: Optional[str] = None  # "top-right", "first", "latest", etc.
    destination: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    is_deterministic: bool = True
    confidence: float = 1.0
    mode: str = "standard"  # standard, ui_followup, ui_wait
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class IntentParser:
    """
    Parse natural language commands into structured intents.
    
    Strategy: Rule-first parsing with pattern templates.
    Fallback to TurboSeek only if confidence < threshold.
    """
    
    # Action verbs and their synonyms
    ACTION_PATTERNS = {
        "open": ["open", "launch", "start", "run"],
        "close": ["close", "exit", "quit", "terminate", "kill"],
        "click": ["click", "tap", "press", "select"],
        "type": ["type", "write", "enter", "input", "paste"],
        "search": ["search", "find", "look for", "google"],
        "download": ["download", "save", "get"],
        "upload": ["upload", "post", "share"],
        "scroll": ["scroll", "swipe"],
        "navigate": ["go to", "navigate", "visit", "browse"],
        "create": ["create", "make", "new"],
        "delete": ["delete", "remove", "trash"],
        "rename": ["rename", "change name"],
        "copy": ["copy", "duplicate"],
        "move": ["move", "transfer"],
        "screenshot": ["screenshot", "capture", "snap"],
        "send": ["send", "msg", "message", "email"],
        "turn": ["turn", "switch", "toggle"],
    }
    
    # Known applications
    KNOWN_APPS = {
        "chrome": ["chrome", "google chrome", "browser"],
        "firefox": ["firefox", "mozilla"],
        "edge": ["edge", "microsoft edge"],
        "notepad": ["notepad", "text editor"],
        "explorer": ["explorer", "file explorer", "files", "folder"],
        "whatsapp": ["whatsapp", "wa"],
        "gallery": ["gallery", "photos", "images"],
        "spotify": ["spotify", "music"],
        "discord": ["discord"],
        "vscode": ["vscode", "vs code", "visual studio code", "code"],
        "youtube": ["youtube", "yt"],
        "instagram": ["instagram", "insta", "ig"],
        "facebook": ["facebook", "fb"],
        "twitter": ["twitter", "x"],
    }
    
    # Position selectors
    POSITION_PATTERNS = {
        "top-right": ["top-right", "top right", "upper right"],
        "top-left": ["top-left", "top left", "upper left"],
        "bottom-right": ["bottom-right", "bottom right", "lower right"],
        "bottom-left": ["bottom-left", "bottom left", "lower left"],
        "center": ["center", "middle"],
        "first": ["first", "1st", "top"],
        "last": ["last", "bottom", "final"],
        "latest": ["latest", "newest", "recent", "most recent"],
        "second": ["second", "2nd"],
        "third": ["third", "3rd"],
    }
    
    # Patterns that indicate non-deterministic (requires UI reasoning)
    NON_DETERMINISTIC_PATTERNS = [
        r"(\d+)(st|nd|rd|th)\s+(pdf|file|image|photo|result)",
        r"(download|upload|select)\s+.*(from|to)\s+",
        r"(top|bottom|left|right)\s*-?\s*(left|right|top|bottom)?",
        r"(latest|newest|recent|first|last)\s+(file|photo|image|result)",
        r"(search|find)\s+.*\s+and\s+(click|select|download)",
    ]
    
    def __init__(self, confidence_threshold: float = 0.7, ui_context=None):
        self.confidence_threshold = confidence_threshold
        self.ui_context = ui_context
        self._compile_patterns()
        
    def _compile_patterns(self):
        """Pre-compile regex patterns for efficiency."""
        self.action_regex = {}
        for action, synonyms in self.ACTION_PATTERNS.items():
            pattern = r'\b(' + '|'.join(re.escape(s) for s in synonyms) + r')\b'
            self.action_regex[action] = re.compile(pattern, re.IGNORECASE)
            
        self.app_regex = {}
        for app, synonyms in self.KNOWN_APPS.items():
            pattern = r'\b(' + '|'.join(re.escape(s) for s in synonyms) + r')\b'
            self.app_regex[app] = re.compile(pattern, re.IGNORECASE)
            
        self.position_regex = {}
        for pos, synonyms in self.POSITION_PATTERNS.items():
            pattern = r'\b(' + '|'.join(re.escape(s) for s in synonyms) + r')\b'
            self.position_regex[pos] = re.compile(pattern, re.IGNORECASE)
            
        self.non_det_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.NON_DETERMINISTIC_PATTERNS
        ]
    
    def parse(self, raw_command: str) -> Intent:
        """
        Parse a natural language command into structured Intent.
        
        Args:
            raw_command: The raw voice/text command
            
        Returns:
            Structured Intent object
        """
        command = raw_command.lower().strip()
        
        # Extract components
        action = self._extract_action(command)
        target_app = self._extract_app(command, is_target=True)
        source_app = self._extract_app(command, is_target=False)
        obj_type, obj_selector = self._extract_object(command)
        destination = self._extract_destination(command)
        is_deterministic = self._check_determinism(command)
        confidence = self._calculate_confidence(action, target_app, command)
        
        intent = Intent(
            intent_id=str(uuid.uuid4())[:8],
            raw_command=raw_command,
            action=action,
            target_app=target_app,
            source_app=source_app,
            object_type=obj_type,
            object_selector=obj_selector,
            destination=destination,
            is_deterministic=is_deterministic,
            confidence=confidence,
        )
        
        # Extract additional parameters
        intent.parameters = self._extract_parameters(command, intent)
        
        print(f"DEBUG IntentParser: {intent.to_dict()}")
        return intent
    
    def _extract_action(self, command: str) -> str:
        """Extract the primary action from command."""
        for action, regex in self.action_regex.items():
            if regex.search(command):
                return action
        return "unknown"
    
    def _extract_app(self, command: str, is_target: bool = True) -> Optional[str]:
        """
        Extract application name from command.
        
        For target: looks after action verb
        For source: looks after 'from'
        """
        for app, regex in self.app_regex.items():
            match = regex.search(command)
            if match:
                # Check context
                if is_target:
                    # Target apps appear after action or "to"
                    if "from my " + app not in command and "from " + app not in command:
                        return app
                else:
                    # Source apps appear after "from"
                    if f"from my {app}" in command or f"from {app}" in command:
                        return app
        return None
    
    def _extract_object(self, command: str) -> Tuple[Optional[str], Optional[str]]:
        """Extract object type and selector (position/order)."""
        obj_type = None
        obj_selector = None
        
        # Object types
        obj_patterns = {
            "photo": r'\b(photo|image|picture|pic)\b',
            "file": r'\b(file|document|doc)\b',
            "pdf": r'\b(pdf)\b',
            "folder": r'\b(folder|directory)\b',
            "text": r'\b(text|message)\b',
            "video": r'\b(video|clip)\b',
        }
        
        for obj, pattern in obj_patterns.items():
            if re.search(pattern, command, re.IGNORECASE):
                obj_type = obj
                break
        
        # Position selector
        for pos, regex in self.position_regex.items():
            if regex.search(command):
                obj_selector = pos
                break
                
        return obj_type, obj_selector
    
    def _extract_destination(self, command: str) -> Optional[str]:
        """Extract destination (for uploads, shares, etc.)."""
        # Patterns like "to status", "to stories", "to desktop"
        dest_match = re.search(r'\bto\s+(my\s+)?(\w+)', command, re.IGNORECASE)
        if dest_match:
            return dest_match.group(2).lower()
        return None
    
    def _extract_parameters(self, command: str, intent: Intent) -> Dict[str, Any]:
        """Extract additional parameters based on action type."""
        params = {}
        
        if intent.action == "type":
            # Extract what to type - look for quoted text or text after "type"
            quoted = re.search(r'["\'](.+?)["\']', command)
            if quoted:
                params["text"] = quoted.group(1)
            else:
                # Text after "type" or "write"
                type_match = re.search(r'\b(type|write|enter)\s+(.+?)(?:\s+in|\s+on|$)', command)
                if type_match:
                    params["text"] = type_match.group(2).strip()
                    
        elif intent.action == "search":
            # Extract search query
            search_match = re.search(r'\b(search|find|google)\s+(.+?)(?:\s+on|\s+in|$)', command)
            if search_match:
                params["query"] = search_match.group(2).strip()
                
        elif intent.action == "create":
            # Extract what to create and name
            create_match = re.search(r'create\s+(?:a\s+)?(\w+)\s+(?:called|named)\s+(.+?)(?:\s+in|$)', command)
            if create_match:
                params["create_type"] = create_match.group(1)
                params["name"] = create_match.group(2).strip()
                
        elif intent.action == "navigate":
            # Extract URL or location
            url_match = re.search(r'go\s+to\s+(.+?)(?:\s+and|$)', command)
            if url_match:
                params["destination"] = url_match.group(1).strip()
                
        elif intent.action == "send":
            # Extract what to send and to whom
            # e.g., "send 'hello' to myself on whatsapp"
            
            # 1. Look for quoted text
            quoted = re.search(r'["\'](.+?)["\']', command)
            if quoted:
                params["text"] = quoted.group(1)
            else:
                # 2. Extract message text
                # We want to find the text between "send [a message [saying]]" and "to/on"
                # Pattern: send -> optional(a message) -> optional(saying) -> TEXT -> optional(to/on ...)
                text_match = re.search(r'\bsend\s+(?:a\s+)?(?:message\s+)?(?:saying\s+)?(.+?)(?:\s+(?:to|on)\b|$)', command)
                if text_match:
                    text = text_match.group(1).strip()
                    # Filter out common garbage
                    if text not in ["a", "message", "the"]:
                        params["text"] = text
            
            # 3. Look for recipient after "to"
            to_match = re.search(r'\bto\s+(.+?)(?:\s+on\b|$)', command)
            if to_match:
                params["recipient"] = to_match.group(1).strip()
                
        return params
    
    def _check_determinism(self, command: str) -> bool:
        """
        Check if command is deterministic (legacy) or requires UI reasoning.
        
        Deterministic: Direct app control (open/close/basic)
        Non-deterministic: Requires element selection, position logic, multi-step
        """
        # Simple deterministic commands
        simple_patterns = [
            r'^(open|close|launch)\s+(chrome|notepad|explorer|firefox|edge)$',
            r'^(open|close)\s+\w+$',
            r'^screenshot$',
            r'^(minimize|maximize)\s+window$',
        ]
        
        for pattern in simple_patterns:
            if re.match(pattern, command.strip(), re.IGNORECASE):
                return True
        
        # Check for non-deterministic patterns
        for pattern in self.non_det_patterns:
            if pattern.search(command):
                return False
                
        # Multi-step commands are non-deterministic
        if ' and ' in command or ' then ' in command:
            return False
            
        # Default: if we found action + app, it's likely deterministic
        return True
    
    def _calculate_confidence(self, action: str, app: Optional[str], command: str) -> float:
        """Calculate parsing confidence score."""
        confidence = 0.5  # Base
        
        if action != "unknown":
            confidence += 0.3
        if app:
            confidence += 0.2
            
        # Reduce confidence for complex commands
        if len(command.split()) > 10:
            confidence -= 0.1
        if ' and ' in command:
            confidence -= 0.1
            
        return max(0.1, min(1.0, confidence))
    
    def requires_agent_core(self, intent: Union[Intent, Dict]) -> bool:
        """
        Determine if this intent should go to AgentCore or legacy system.
        
        Rule: Route based on DETERMINISM, not complexity.
        """
        # normalize to dict access or object access
        if isinstance(intent, dict):
            # Create temporary Intent object for logic if needed, or just access fields
            # Better to rely on helper that can handle both
            raw_command = intent.get("raw_command", "")
            is_deterministic = intent.get("is_deterministic", True)
            confidence = intent.get("confidence", 1.0)
            # Reconstruct intent object for FollowupGuard since it might expect typed object
            if self.ui_context:
                 # We need to reconstruct a minimal intent object for the guard
                 # or make guard handle dicts too. 
                 # Let's reconstruct for safety
                 from dataclasses import fields
                 # This is tricky without full params. 
                 # Let's access dict fields directly in this method for the check.
                 pass
        else:
            raw_command = intent.raw_command
            is_deterministic = intent.is_deterministic
            confidence = intent.confidence

        # Check UI Follow-up Guard
        if self.ui_context:
            from AgentCore.ui_agent.planner.followup_guard import FollowupGuard
            # Ensure guard can handle dict or object. 
            # Looking at FollowupGuard: likely expects object. 
            # Let's convert dict to object if it is a dict
            if isinstance(intent, dict):
                # Construct minimal intent
                try:
                    intent_obj = Intent(**intent) 
                except:
                    # Fallback if dict has extra keys or missing required
                    intent_obj = Intent(
                        intent_id=intent.get("intent_id", "unknown"),
                        raw_command=intent.get("raw_command", ""),
                        action=intent.get("action", "unknown"),
                        target_app=intent.get("target_app"),
                        parameters=intent.get("parameters", {}),
                        mode=intent.get("mode", "standard")
                    )
            else:
                intent_obj = intent
                
            if FollowupGuard.is_followup(intent_obj, self.ui_context):
                print(f"[IntentParser] Follow-up detected -> AgentCore")
                if isinstance(intent, dict):
                    intent["mode"] = "ui_followup"
                else:
                    intent.mode = "ui_followup"
                return True

        # Check for INCOMPLETE BROWSER INTENTS (e.g. "google", "youtube")
        raw_lower = raw_command.lower().strip()
        browser_shortcuts = {
            "google": "https://www.google.com",
            "youtube": "https://www.youtube.com",
            "gmail": "https://mail.google.com",
            "chrome": "chrome", 
            "browser": "chrome"
        }
        
        if raw_lower in browser_shortcuts:
            print(f"[IntentParser] Incomplete Browser Intent detected: '{raw_lower}'")
            # Transform to navigation intent
            target_url = browser_shortcuts[raw_lower]
            is_nav = "http" in target_url
            
            if isinstance(intent, dict):
                intent["action"] = "navigate" if is_nav else "open_app"
                intent["target_app"] = "chrome"
                if is_nav:
                    intent["parameters"] = intent.get("parameters", {})
                    intent["parameters"]["destination"] = target_url
                    intent["destination"] = target_url
                
                intent["mode"] = "ui_wait"
                intent["is_deterministic"] = False
            else:
                intent.action = "navigate" if is_nav else "open_app"
                intent.target_app = "chrome"
                if is_nav:
                     intent.parameters["destination"] = target_url
                     intent.destination = target_url
                
                intent.mode = "ui_wait"
                intent.is_deterministic = False 
                
            return True
            
        return not is_deterministic or confidence < self.confidence_threshold
