import sys
import os
from AgentCore.code_engine.engine import CodeEngine

def main():
    if len(sys.argv) < 2:
        print("Usage: python run_test_cli.py 'command text'")
        return

    text = sys.argv[1]
    print(f"Running command: {text}")
    
    # Force auto_write for testing if env var set
    config = None
    if os.environ.get("FORCE_WRITE"):
        config = {"auto_write": True, "sandbox_root": "projects/sandbox"}
        
    engine = CodeEngine(config)
    result = engine.handle_command(text, dry_run=False if config else True)
    
    import json
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
