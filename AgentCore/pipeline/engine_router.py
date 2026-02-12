from typing import Dict, Any, Callable

# Engine Imports (Lazy loaded in methods to avoid circular imports if possible,
# but usually engines are independent)
# For now we will assume global names or imports will be provided/available

class EngineRouter:
    """
    Maps intents to Engine handlers.
    """
    def __init__(self):
        pass

    def select(self, intent_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Select the appropriate engine for the intent.
        Returns: {
            "engine_name": str,
            "handler": Callable,
            "reason": str
        }
        """
        intent = intent_data.get("intent")
        
        if intent == "CODE_REQUEST":
            return {
                "engine_name": "CodeEngine",
                "handler": self._handle_code,
                "reason": "Intent was CODE_REQUEST"
            }
        
        elif intent == "AUTOMATION":
            return {
                "engine_name": "Auto_main_brain",
                "handler": self._handle_auto,
                "reason": "Intent was AUTOMATION"
            }
            
        else:
            return {
                "engine_name": "Main_Brain",
                "handler": self._handle_main,
                "reason": "Default conversational fallback"
            }

    # Wrapper handlers to normalize engine signatures
    def _handle_code(self, text: str, context: Any):
        from AgentCore.code_engine.engine import CodeEngine
        import os
        engine = CodeEngine()
        # CodeEngine expects: text, context, dry_run
        return engine.handle_command(text, context={"user":"owner", "cwd": os.getcwd()}, dry_run=False)

    def _handle_auto(self, text: str, context: Any):
        # Auto_main_brain is function in co_brain.py usually, 
        # but we might need to import it carefully or use a wrapper.
        # For this implementation, we will assume it returns a status string.
        # Ideally, we should import the actual function.
        # Since co_brain.py is the caller, this might be tricky. 
        # We will use a proxy or expect it to be passed?
        # Actually, let's just interpret it here.
        # The legacy Auto_main_brain doesn't return much.
        from AgentCore.agent_brain import AgentBrain
        agent = AgentBrain()
        return agent.execute_command(text)

    def _handle_main(self, text: str, context: Any):
        # Main_Brain (LLM)
        # We can implement the logic directly here or call Brain/brain.py
        from Brain.brain import Main_Brain
        return Main_Brain(text)
