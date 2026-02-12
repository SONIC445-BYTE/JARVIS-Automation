import sys
import json
import os
from AgentCore.mode_manager.mode_engine import ModeEngine

def main():
    if len(sys.argv) < 2:
        print("Usage: python run_mode_sim.py 'command text'")
        return

    text = sys.argv[1]
    
    # Mock Key
    os.environ["JARVIS_HMAC_KEY"] = "dev_key"
    
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
