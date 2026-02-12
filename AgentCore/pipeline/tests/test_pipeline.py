import pytest
import os
import json
from unittest.mock import MagicMock, patch
from AgentCore.pipeline.intent_router import IntentRouter, IntentRouterError
from AgentCore.pipeline.policy_gate import PolicyGate
from AgentCore.pipeline.engine_router import EngineRouter
from AgentCore.pipeline.pipeline_trace import PipelineTrace
from AgentCore.llm_engine import LLMEngine

# Mock LLM response
class MockLLMResponse:
    def __init__(self, text):
        self.text = text

@pytest.fixture
def mock_llm():
    llm = MagicMock(spec=LLMEngine)
    llm.is_available.return_value = True
    return llm

@pytest.fixture
def router(mock_llm):
    return IntentRouter(llm=mock_llm)

@pytest.fixture
def policy():
    return PolicyGate()

@pytest.fixture
def engine_router():
    return EngineRouter()

def test_intent_router_rule_priority(router):
    # Automation keyword
    res = router.classify("open chrome")
    assert res["intent"] == "AUTOMATION"
    assert res["method"] == "rule_based"

    # Code keyword
    res = router.classify("write a python script")
    assert res["intent"] == "CODE_REQUEST"
    assert res["method"] == "rule_based"

def test_intent_router_llm_fallback(router, mock_llm):
    # Conversational but ambiguous rule
    mock_llm.generate.return_value = MockLLMResponse('{"intent": "CONVERSATION", "confidence": 0.9}')
    
    res = router.classify("who is the president")
    
    # Rule parser might catch "president" as unknown action, low confidence
    # But let's see if our mock LLM kicks in. 
    # Actually "who is the president" has no "action" in ACTION_PATTERNS so rule confidence is low (0.5).
    # Threshold is 0.7. So it should hit LLM.
    
    # Wait, IntentParser might not have "who" as action. 
    # Let's verify if 'classify' calls LLM.
    assert res["intent"] == "CONVERSATION"
    assert res["method"] == "llm"

def test_policy_gate_blocks_destructive(policy):
    intent = {"intent": "DESTRUCTIVE"}
    res = policy.pre_check(intent, {})
    assert res["allowed"] is False
    assert res["require_confirm"] is True

def test_policy_gate_allows_code(policy):
    intent = {"intent": "CODE_REQUEST"}
    res = policy.pre_check(intent, {})
    assert res["allowed"] is True

def test_engine_router_correct_mapping(engine_router):
    res = engine_router.select({"intent": "CODE_REQUEST"})
    assert res["engine_name"] == "CodeEngine"
    
    res = engine_router.select({"intent": "AUTOMATION"})
    assert res["engine_name"] == "Auto_main_brain"

    res = engine_router.select({"intent": "CONVERSATION"})
    assert res["engine_name"] == "Main_Brain"

def test_pipeline_trace_serialization():
    trace = PipelineTrace.new_from_input("test input", "test input")
    trace.attach_intent({"intent": "TEST"})
    trace.add_layer("Layer1")
    
    json_out = trace.to_json()
    data = json.loads(json_out)
    
    assert data["input"]["raw"] == "test input"
    assert data["intent"]["intent"] == "TEST"
    assert "Layer1" in data["layers_traversed"]

