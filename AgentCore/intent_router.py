"""
Intent Router - Action vs Conversation Classification
=======================================================
Routes commands to appropriate handlers.

Sprint 6: Conversational Intelligence
"""

import re
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class IntentType(Enum):
    """Types of user intent."""
    ACTION = "action"           # Execute something (open, send, search)
    QUESTION = "question"       # Ask for information
    CHAT = "chat"              # Casual conversation
    CONFIRM = "confirm"        # Yes/no response
    ABORT = "abort"            # Cancel/stop
    FOLLOWUP = "followup"      # Related to previous command
    UNKNOWN = "unknown"


@dataclass
class RoutedIntent:
    """Result of intent classification."""
    intent_type: IntentType
    confidence: float
    original_text: str
    processed_text: str
    handler: str  # "action", "llm", "canned"
    extracted_entities: Dict = None
    
    def __post_init__(self):
        if self.extracted_entities is None:
            self.extracted_entities = {}


class IntentRouter:
    """
    Routes user input to appropriate handler.
    
    Classification:
    - ACTION: Goes to UI executor / automation
    - QUESTION: Goes to LLM
    - CHAT: Goes to LLM
    - CONFIRM/ABORT: Handled directly
    - FOLLOWUP: Uses context
    """
    
    # Action keywords (high priority)
    ACTION_PATTERNS = [
        r"^open\s+",
        r"^close\s+",
        r"^launch\s+",
        r"^start\s+",
        r"^run\s+",
        r"^search\s+(?:for\s+)?",
        r"^go\s+to\s+",
        r"^navigate\s+to\s+",
        r"^send\s+",
        r"^upload\s+",
        r"^download\s+",
        r"^play\s+",
        r"^stop\s+",
        r"^pause\s+",
        r"^type\s+",
        r"^click\s+",
        r"^scroll\s+",
        r"^minimize\s+",
        r"^maximize\s+",
        r"^shut\s*down",
        r"^restart\s+",
        r"^set\s+.+\s+to\s+",
        r"^turn\s+(?:on|off)\s+",
    ]
    
    # Question indicators
    QUESTION_PATTERNS = [
        r"^what\s+(?:is|are|was|were)",
        r"^who\s+(?:is|are|was|were)",
        r"^where\s+(?:is|are|was|were)",
        r"^when\s+(?:is|are|was|were|did|do)",
        r"^why\s+(?:is|are|was|were|did|do)",
        r"^how\s+(?:do|does|did|is|are|can|could|would)",
        r"^can\s+you\s+explain",
        r"^explain\s+",
        r"^tell\s+me\s+about",
        r"^describe\s+",
        r"\?$",  # Ends with question mark
    ]
    
    # Confirmation patterns
    CONFIRM_PATTERNS = [
        r"^yes\b",
        r"^yeah\b",
        r"^yep\b",
        r"^correct\b",
        r"^right\b",
        r"^ok\b",
        r"^okay\b",
        r"^sure\b",
        r"^do\s+it\b",
        r"^go\s+ahead\b",
        r"^confirm\b",
    ]
    
    # Abort patterns
    ABORT_PATTERNS = [
        r"^no\b",
        r"^nope\b",
        r"^cancel\b",
        r"^stop\b",
        r"^abort\b",
        r"^never\s*mind\b",
        r"^forget\s+it\b",
        r"^don'?t\b",
    ]
    
    # Followup patterns
    FOLLOWUP_PATTERNS = [
        r"^(?:and\s+)?(?:then|also|next)\s+",
        r"^do\s+(?:it|that)\s+again",
        r"^(?:one\s+)?more\s+time",
        r"^repeat\s+(?:that|it)",
        r"^again\b",
        r"^same\s+thing",
        r"^why\s+did\s+you",
        r"^what\s+did\s+you",
    ]
    
    
    # Coding Patterns (Sprint: Two-Tier Coding Engine)
    #
    # Each pattern tolerates an optional article ("a"/"an"/"the") and a
    # single filler word (e.g. "python") between the trigger verb and the
    # target noun, since real phrasing is rarely "write script" -- it's
    # "write a python script that ...". See Phase 1 of the JARVIS
    # diagnosis brief: the old anchored patterns missed most natural
    # coding requests, including the phrasings used in its own DoD.
    _FILLER = r"(?:a\s+|an\s+|the\s+)?(?:\w+\s+)?"
    CODE_PATTERNS = [
        rf"^create\s+{_FILLER}(?:file|module|class|function|script)\b",
        r"^refactor\s+",
        rf"^add\s+{_FILLER}(?:function|method|class|import)\b",
        rf"^fix\s+{_FILLER}(?:bug|error|issue)\b",
        r"^implement\s+",
        rf"^write\s+{_FILLER}(?:test|code|script|function|module|class)\b",
        r"^run\s+(?:the\s+)?(?:tests|checks)\b",
        rf"^propose\s+{_FILLER}(?:patch|change)\b",
        rf"^build\s+{_FILLER}(?:script|app|function|program|tool)\b",
        rf"^generate\s+{_FILLER}(?:script|function|code|program|class|module)\b",
    ]

    def __init__(self, use_llm_classifier: bool = False, resolution_gate=None):
        self.use_llm_classifier = use_llm_classifier
        self._compile_patterns()
        self._resolution_gate = resolution_gate or self._init_resolution_gate()

    @staticmethod
    def _init_resolution_gate():
        """ResolutionGate (Phase 2c) resolves platform+action commands
        (e.g. "send a whatsapp message to X saying Y") against
        adapter-declared aliases/actions (Phase 2a's CommandRouter), then
        checks the platform is actually installed before handing back a
        RESOLVED intent -- see AgentCore/resolution_gate.py. Optional: if
        platform_adapters isn't importable in this context, fall back to
        the pre-2a ACTION_PATTERNS-only behavior."""
        try:
            from .resolution_gate import ResolutionGate
            return ResolutionGate()
        except ImportError as e:
            print(f"[IntentRouter] ResolutionGate unavailable: {e}")
            return None
    
    def _compile_patterns(self):
        """Compile regex patterns."""
        self._action_re = [re.compile(p, re.IGNORECASE) for p in self.ACTION_PATTERNS]
        self._question_re = [re.compile(p, re.IGNORECASE) for p in self.QUESTION_PATTERNS]
        self._confirm_re = [re.compile(p, re.IGNORECASE) for p in self.CONFIRM_PATTERNS]
        self._abort_re = [re.compile(p, re.IGNORECASE) for p in self.ABORT_PATTERNS]
        self._confirm_re = [re.compile(p, re.IGNORECASE) for p in self.CONFIRM_PATTERNS]
        self._abort_re = [re.compile(p, re.IGNORECASE) for p in self.ABORT_PATTERNS]
        self._followup_re = [re.compile(p, re.IGNORECASE) for p in self.FOLLOWUP_PATTERNS]
        # Code patterns
        self._code_re = [re.compile(p, re.IGNORECASE) for p in self.CODE_PATTERNS]
    
    def classify(self, text: str, context: Dict = None) -> RoutedIntent:
        """
        Classify user intent and determine handler.
        
        Args:
            text: User input text
            context: Conversation context
            
        Returns:
            RoutedIntent with classification
        """
        text = text.strip()
        text_lower = text.lower()
        context = context or {}
        
        # Check confirmation/abort first (high priority)
        if self._matches_any(text_lower, self._confirm_re):
            return RoutedIntent(
                intent_type=IntentType.CONFIRM,
                confidence=0.95,
                original_text=text,
                processed_text=text_lower,
                handler="canned"
            )
        
        if self._matches_any(text_lower, self._abort_re):
            return RoutedIntent(
                intent_type=IntentType.ABORT,
                confidence=0.95,
                original_text=text,
                processed_text=text_lower,
                handler="canned"
            )
        
        # Check followup
        if self._matches_any(text_lower, self._followup_re):
            return RoutedIntent(
                intent_type=IntentType.FOLLOWUP,
                confidence=0.8,
                original_text=text,
                processed_text=text_lower,
                handler="context"
            )
        
        # Check adapter-declared platform+action commands, gated on
        # adapter existence + installation (Phase 2a + 2c). More specific
        # than the generic ACTION_PATTERNS below, so it takes priority
        # when it resolves.
        if self._resolution_gate:
            from .resolution_gate import GateOutcome
            gate_result = self._resolution_gate.check(text)
            if gate_result.outcome == GateOutcome.RESOLVED:
                return RoutedIntent(
                    intent_type=IntentType.ACTION,
                    confidence=0.95,
                    original_text=text,
                    processed_text=text_lower,
                    handler="action",
                    extracted_entities={"resolved_intent": gate_result.intent}
                )
            if gate_result.outcome == GateOutcome.NO_ADAPTER:
                return RoutedIntent(
                    intent_type=IntentType.ACTION,
                    confidence=0.9,
                    original_text=text,
                    processed_text=text_lower,
                    handler="action_no_adapter",
                    extracted_entities={"gate_result": gate_result}
                )
            if gate_result.outcome == GateOutcome.NOT_INSTALLED:
                return RoutedIntent(
                    intent_type=IntentType.ACTION,
                    confidence=0.9,
                    original_text=text,
                    processed_text=text_lower,
                    handler="action_not_installed",
                    extracted_entities={"gate_result": gate_result}
                )
            # PLATFORM_UNKNOWN: fall through to existing patterns below.

        # Check code patterns
        if self._matches_any(text_lower, self._code_re):
            return RoutedIntent(
                intent_type=IntentType.ACTION, # Map to ACTION but with special handler
                confidence=0.95,
                original_text=text,
                processed_text=text_lower,
                handler="code_engine"
            )

        # Check action patterns
        if self._matches_any(text_lower, self._action_re):
            entities = self._extract_action_entities(text)
            return RoutedIntent(
                intent_type=IntentType.ACTION,
                confidence=0.9,
                original_text=text,
                processed_text=text_lower,
                handler="action",
                extracted_entities=entities
            )
        
        # Check question patterns
        if self._matches_any(text_lower, self._question_re):
            return RoutedIntent(
                intent_type=IntentType.QUESTION,
                confidence=0.85,
                original_text=text,
                processed_text=text_lower,
                handler="llm"
            )
        
        # Default to chat
        return RoutedIntent(
            intent_type=IntentType.CHAT,
            confidence=0.6,
            original_text=text,
            processed_text=text_lower,
            handler="llm"
        )
    
    def _matches_any(self, text: str, patterns: list) -> bool:
        """Check if text matches any pattern."""
        return any(p.search(text) for p in patterns)
    
    def _extract_action_entities(self, text: str) -> Dict:
        """Extract entities from action text."""
        entities = {}
        
        # Extract app names
        app_match = re.search(r"(?:open|launch|start|close)\s+(\w+)", text, re.I)
        if app_match:
            entities["app"] = app_match.group(1)
        
        # Extract URLs
        url_match = re.search(r"(?:go\s+to|navigate\s+to|visit)\s+(\S+)", text, re.I)
        if url_match:
            entities["url"] = url_match.group(1)
        
        # Extract search query
        search_match = re.search(r"search\s+(?:for\s+)?(.+)$", text, re.I)
        if search_match:
            entities["query"] = search_match.group(1)
        
        return entities
    
    def get_handler(self, text: str) -> Tuple[str, RoutedIntent]:
        """
        Get handler and intent for text.
        
        Returns:
            (handler_name, RoutedIntent)
        """
        intent = self.classify(text)
        return (intent.handler, intent)


def test_intent_router():
    """Test intent router."""
    print("Intent Router Test")
    print("=" * 50)
    
    router = IntentRouter()
    
    tests = [
        "open notepad",
        "what is the capital of France?",
        "hello jarvis",
        "yes",
        "no, cancel that",
        "do it again",
        "search for python tutorials",
        "explain how photosynthesis works",
        "go to google.com",
    ]
    
    for text in tests:
        intent = router.classify(text)
        print(f"'{text}'")
        print(f"  → {intent.intent_type.value} ({intent.confidence:.0%}) → {intent.handler}")
        if intent.extracted_entities:
            print(f"  Entities: {intent.extracted_entities}")


if __name__ == "__main__":
    test_intent_router()
