
import os
import sys
import yaml

# Ensure we can import AgentCore
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from AgentCore.pipeline.intent_router import IntentRouter
from AgentCore.pipeline.engine_router import EngineRouter
from AgentCore.pipeline.pipeline_trace import PipelineTrace

def run_debug_matrix():
    print("="*60)
    print("ROUTING DEBUG MATRIX")
    print("="*60)
    
    # Setup
    router = IntentRouter()
    engine_router = EngineRouter()
    
    test_cases = [
        ("Who is the president of America", "CONVERSATION", "Main_Brain"),
        ("Open WhatsApp", "AUTOMATION", "Auto_main_brain"),
        ("Write a Python script to print hello world", "CODE_REQUEST", "CodeEngine"),
        ("Send a message on WhatsApp saying hello", "AUTOMATION", "Auto_main_brain")
    ]
    
    results = []
    
    for input_text, expected_intent, expected_engine in test_cases:
        print(f"\nInput: '{input_text}'")
        
        # 1. Intent
        intent_res = router.classify(input_text)
        detected_intent = intent_res["intent"]
        confidence = intent_res["confidence"]
        method = intent_res["method"]
        print(f"  -> Detected Intent: {detected_intent} (Conf: {confidence}, Method: {method})")
        
        # 2. Engine
        route = engine_router.select(intent_res)
        selected_engine = route["engine_name"]
        print(f"  -> Selected Engine: {selected_engine}")
        
        # Verify
        intent_pass = (detected_intent == expected_intent)
        engine_pass = (selected_engine == expected_engine)
        
        status = "PASS" if intent_pass and engine_pass else "FAIL"
        print(f"  -> Result: {status}")
        
        results.append({
            "input": input_text,
            "intent": detected_intent,
            "engine": selected_engine,
            "status": status
        })

    print("\n" + "="*60)
    print("FINAL VERDICT")
    print("="*60)
    
    all_pass = all(r["status"] == "PASS" for r in results)
    
    for r in results:
        print(f"Input: {r['input'][:30]}... | Intent: {r['intent']} | Engine: {r['engine']} -> {r['status']}")
        
    print(f"\nOverall System Health: {'HEALTHY' if all_pass else 'BROKEN'}")
    
    report = {
        "auto_switching_working": all_pass,
        "automation_leaks_into_conversation": any(r["intent"] == "CONVERSATION" and r["engine"] == "Main_Brain" for r in results if "WhatsApp" in r["input"]),
        "root_cause": "None" if all_pass else "Routing Misclassification",
        "fix_required": "None" if all_pass else "Adjust IntentRouter logic",
        "confidence": 1.0
    }
    
    import json
    print("\nJSON REPORT:")
    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    run_debug_matrix()
