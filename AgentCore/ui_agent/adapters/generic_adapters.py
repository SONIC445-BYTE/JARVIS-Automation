from .base_adapter import BasePlatformAdapter
from ..adapter_registry import registry
from typing import List, Dict, Any

class GenericDesktopAdapter(BasePlatformAdapter):
    platform = "desktop"
    # Nerfed: Only allow navigation/focus/open. No generic clicking/typing unless explicitly requested via specific intent.
    supported_actions = ["navigate", "focus", "open"]

    def can_handle(self, intent: Any, context: Dict[str, Any]) -> bool:
        action = getattr(intent, 'action', intent.get('action') if isinstance(intent, dict) else '')
        return action in self.supported_actions

    def build_plan(self, intent: Any, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        action = intent.get("action") if isinstance(intent, dict) else getattr(intent, "action", "")
        target = intent.get("target") if isinstance(intent, dict) else getattr(intent, "target", "")
        return [{"type": action, "target": target}]

    @property
    def capabilities(self) -> Dict[str, List[str]]:
         return {action: ["native"] for action in self.supported_actions}

class GenericBrowserAdapter(BasePlatformAdapter):
    platform = "web"
    supported_actions = ["navigate", "type", "click", "search"]
    
    # Common domain mappings
    DOMAIN_MAP = {
        'google': 'https://www.google.com',
        'youtube': 'https://www.youtube.com',
        'gmail': 'https://mail.google.com',
        'github': 'https://github.com'
    }

    def can_handle(self, intent: Any, context: Dict[str, Any]) -> bool:
        # Handle raw string intents (e.g., "google" or "open github")
        if isinstance(intent, str):
            intent = intent.lower()
            return (any(domain in intent for domain in self.DOMAIN_MAP.keys()) or
                   'http' in intent or 'www' in intent or 'browser' in intent or 'search' in intent)
                    
        # Handle dict/intent objects
        action = intent.get('action') if isinstance(intent, dict) else getattr(intent, 'action', '')
        target = intent.get('target', '') if isinstance(intent, dict) else getattr(intent, 'target', '')
        
        # Check if this is a browser-related action
        if action in self.supported_actions:
            return True
            
        # Check if target is a URL or domain
        if isinstance(target, str) and ('http' in target or 'www' in target or 
                                       any(domain in target.lower() for domain in self.DOMAIN_MAP)):
            return True
            
        return False

    def _resolve_url(self, target: str) -> str:
        """Resolve a domain or search term to a full URL."""
        target = target.lower().strip()
        
        # Check if it's a known domain
        if target in self.DOMAIN_MAP:
            return self.DOMAIN_MAP[target]
            
        # Check if it's a search query (no dots, multiple words)
        if '.' not in target and ' ' in target:
            return f"https://www.google.com/search?q={target.replace(' ', '+')}"
            
        # Assume it's a domain
        if not target.startswith(('http://', 'https://')):
            return f'https://{target}'
            
        return target

    def build_plan(self, intent: Any, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Build a plan for browser actions with proper validation.
        Handles both direct navigation and search intents.
        """
        if isinstance(intent, str):
            # Handle simple string commands like "google" or "search cats"
            intent = intent.lower()
            
            # Check for search intent
            if intent.startswith('search ') or ' ' in intent:
                query = intent.replace('search', '').strip()
                if query:
                    return [
                        {"action": "navigate", "target": "https://www.google.com"},
                        {"action": "wait", "duration": 2},  # Wait for page load
                        {"action": "type", "target": "input[name='q']", "value": query},
                        {"action": "click", "target": "input[name='btnK']"}
                    ]
            
            # Handle domain navigation
            url = self._resolve_url(intent)
            return [
                {"action": "navigate", "target": url},
                {"action": "wait", "duration": 2}  # Wait for page load
            ]
            
        # Handle structured intents
        action = intent.get('action') if isinstance(intent, dict) else getattr(intent, 'action', '')
        target = intent.get('target', '') if isinstance(intent, dict) else getattr(intent, 'target', '')
        value = intent.get('value', '') if isinstance(intent, dict) else getattr(intent, 'value', '')
        
        plan = []
        
        # Handle navigation
        if action == 'navigate':
            url = self._resolve_url(target)
            plan.append({"action": "navigate", "target": url})
        
        # Handle search
        elif action == 'search':
            plan.extend([
                {"action": "navigate", "target": "https://www.google.com"},
                {"action": "wait", "duration": 2},
                {"action": "type", "target": "input[name='q']", "value": value or target},
                {"action": "click", "target": "input[name='btnK']"}
            ])
        
        # Handle direct actions
        elif action in ['type', 'click']:
            plan.append({"action": action, "target": target, "value": value})
        
        # Add wait after each action for stability
        if plan and plan[-1]["action"] != "wait":
            plan.append({"action": "wait", "duration": 1})
            
        return plan

class SystemDialogAdapter(BasePlatformAdapter):
    platform = "system"
    supported_actions = ["confirm_dialog", "dismiss_dialog"]

    def can_handle(self, intent: Any, context: Dict[str, Any]) -> bool:
        raw = str(intent).lower()
        return "dialog" in raw or "popup" in raw or "alert" in raw

    def build_plan(self, intent: Any, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        return [{"type": "click", "target": "button[text~='OK']"}]

class UnknownAppFallbackAdapter(BasePlatformAdapter):
    platform = "unknown"
    supported_actions = ["any"]

    def can_handle(self, intent: Any, context: Dict[str, Any]) -> bool:
        return True # Absolute last resort

    def build_plan(self, intent: Any, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        # Heuristic: try to find the "target" text anywhere on screen via OCR
        target = intent.get("target") or intent.get("raw", "")
        return [{"type": "ocr_click", "target": target}]

# Register them with lower priority implicitly by being added last or flagged
registry.register(GenericDesktopAdapter())
registry.register(GenericBrowserAdapter())
registry.register(SystemDialogAdapter())
registry.register(UnknownAppFallbackAdapter())
