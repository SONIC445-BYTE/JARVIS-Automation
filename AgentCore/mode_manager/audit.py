import json
import time
import hmac
import hashlib
import os
from pathlib import Path

def _get_hmac_key():
    key = os.environ.get("JARVIS_HMAC_KEY")
    if not key:
        # Fallback for dev/test without crashing, but warn
        # In production this should raise
        return b"dev_insecure_key_default"
    return key.encode()

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
