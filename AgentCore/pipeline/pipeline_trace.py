import uuid
import time
import json
from datetime import datetime
from typing import Dict, Any, List, Optional

class PipelineTrace:
    """
    Structured trace for a single request through the canonical pipeline.
    """
    def __init__(self, request_id: str, input_data: Dict[str, Any]):
        self.trace_id = request_id
        self.timestamp = datetime.now().isoformat()
        self.input = input_data
        self.intent = None
        self.policy_pre = None
        self.engine_routing = None
        self.layers_traversed = []
        self.engine_result = None
        self.policy_post = None
        self.final_delivery = None
        self.fallback_used = False
        self.fallback_reason = None
        self.error = None

    @classmethod
    def new_from_input(cls, raw_input: str, normalized_input: str, metadata: Dict[str, Any] = None):
        req_id = str(uuid.uuid4())
        input_data = {
            "raw": raw_input,
            "normalized": normalized_input,
            "metadata": metadata or {},
            "ts": time.time()
        }
        return cls(req_id, input_data)

    def add_layer(self, layer_name: str):
        self.layers_traversed.append(layer_name)

    def attach_intent(self, intent_data: Dict[str, Any]):
        self.intent = intent_data
        self.add_layer("IntentRouter")

    def attach_policy_pre(self, policy_result: Dict[str, Any]):
        self.policy_pre = policy_result
        self.add_layer("PolicyGate(Pre)")

    def attach_engine_routing(self, routing_data: Dict[str, Any]):
        self.engine_routing = routing_data
        self.add_layer("EngineRouter")

    def attach_engine_result(self, engine_name: str, result: Any):
        # Sanitize result if needed (remove large blobs)
        self.engine_result = result
        self.add_layer(f"Engine({engine_name})")

    def attach_policy_post(self, policy_result: Dict[str, Any]):
        self.policy_post = policy_result
        self.add_layer("PolicyGate(Post)")

    def mark_fallback(self, reason: str):
        self.fallback_used = True
        self.fallback_reason = reason
        self.add_layer("Fallback")

    def mark_delivered(self, channel: str = "voice", outcome: str = "delivered"):
        self.final_delivery = {
            "channel": channel,
            "outcome": outcome,
            "ts": time.time()
        }
        self.add_layer("Delivery")

    def set_error(self, error_msg: str):
        self.error = error_msg
        self.final_delivery = {"outcome": "error", "error": error_msg}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "timestamp": self.timestamp,
            "input": self.input,
            "intent": self.intent,
            "policy_pre": self.policy_pre,
            "engine_routing": {k: (v if k != "handler" else str(v)) for k, v in self.engine_routing.items()} if self.engine_routing else None,
            "layers_traversed": self.layers_traversed,
            # Engine result might be complex, maybe summarize?
            "engine_result_summary": str(self.engine_result)[:200] if self.engine_result else None,
            "policy_post": self.policy_post,
            "final_delivery": self.final_delivery,
            "fallback_used": self.fallback_used,
            "fallback_reason": self.fallback_reason,
            "error": self.error
        }

    def to_json(self) -> str:
        def default_serializer(obj):
            if hasattr(obj, 'isoformat'):
                return obj.isoformat()
            return str(obj)
        return json.dumps(self.to_dict(), default=default_serializer)
