import json
import time
import hmac
import hashlib
from pathlib import Path

from AgentCore.secure_key import resolve_key

# D2: was os.environ.get("JARVIS_HMAC_KEY") falling back to a hardcoded
# b"dev_insecure_key_default" -- the identical weakness memory_store.py
# had (XOR under "jarvis_default_key"). Shares secure_key.resolve_key()
# with memory_store.py rather than a second, separately-maintained
# implementation of the same fail-closed key logic.
def _get_hmac_key() -> bytes:
    return resolve_key("audit_hmac", "JARVIS_HMAC_KEY")

def sign_entry(entry_dict):
    # Sort keys for deterministic JSON
    raw = json.dumps(entry_dict, sort_keys=True).encode()
    key = _get_hmac_key()
    sig = hmac.new(key, raw, hashlib.sha256).hexdigest()
    return sig

def write_log(path, entry):
    entry['ts'] = time.time()
    entry['sig'] = sign_entry(entry)
    
    p = Path(path)
    if not p.parent.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

def verify_line(line):
    try:
        obj = json.loads(line)
        sig = obj.pop('sig', None)
        if not sig: return False
        
        raw = json.dumps(obj, sort_keys=True).encode()
        key = _get_hmac_key()
        expect = hmac.new(key, raw, hashlib.sha256).hexdigest()
        return hmac.compare_digest(sig, expect)
    except Exception:
        return False
