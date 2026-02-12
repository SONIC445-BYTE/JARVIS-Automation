import json

def classify_with_llm(llm, text):
    """
    Fallback to local LLM classifier.
    llm: Adapter object with a method (e.g. run_system_user or generate)
    """
    prompt = (
        "SYSTEM: classify the user's intent as one of "
        "[CODING,CONVERSATION,OPEN_IDE,EXECUTE_LOCAL,WAKE,SLEEP,SYSTEM_DELETE]. "
        "Output ONLY JSON: {\"intent\": \"...\", \"confidence\": 0.0-1.0}"
    )
    
    # Adapt to whatever method the LLM adapter exposes
    try:
        resp = ""
        if hasattr(llm, 'run_system_user'):
            resp = llm.run_system_user(prompt, text)
        elif hasattr(llm, 'generate'):
            resp = llm.generate(f"{prompt}\nUser: {text}")
        else:
            # Fallback if unknown interface
            print("[Confidence] LLM adapter has unknown interface")
            return None, 0.0, "llm_error"
            
        # Parse JSON
        # Clean potential markdown
        cleaned = resp.strip()
        if cleaned.startswith("```"):
            cleaned = "\n".join(cleaned.splitlines()[1:])
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
            
        parsed = json.loads(cleaned)
        return parsed.get("intent"), float(parsed.get("confidence", 0.0)), "llm"
    except Exception as e:
        print(f"[Confidence] Error: {e}")
        return None, 0.0, "llm_error"
