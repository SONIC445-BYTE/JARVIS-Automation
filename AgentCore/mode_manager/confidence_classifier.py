import random

class ConfidenceClassifier:
    def __init__(self):
        pass
        
    def classify(self, text: str):
        # Mock logic or simple keyword heuristics beyond regex
        # In real impl, call local LLM
        return {
            "intent": "unknown",
            "confidence": 0.5
        }
