import sys
import json
import os
from AgentCore.mode_manager.mode_engine import ModeEngine

def main():
    if len(sys.argv) < 2:
        print("Usage: python run_mode_sim.py 'command text'")
        return

    text = sys.argv[1]
    
    # D2: secure_key.resolve_key()'s env-var path expects a real,
    # base64-encoded 32-byte key -- a plain "dev_key" string is no
    # longer valid. This is a manual CLI dev tool, so opt into the
    # explicit dev-key path instead of fabricating a fake env-var key.
    os.environ["JARVIS_INSECURE_DEV_KEY"] = "1"
    
    # Force enable
    config_path = "feature_flags/sim_config.yaml"
    with open(config_path, "w") as f:
        f.write("enabled: true\nauto_switch_confidence_threshold: 0.7\n")
        
    engine = ModeEngine(config_path)
    res = engine.decide_and_transition(text, {"user": "sim", "stt": text})
    print(json.dumps(res, indent=2))
    
    if os.path.exists(config_path):
        os.remove(config_path)

if __name__ == "__main__":
    main()
