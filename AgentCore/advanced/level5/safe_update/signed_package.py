"""
Signed Package Manager for Level-5.
Ensures updates are signed by owner key.
"""
import hmac
import hashlib
import json
from typing import Dict, Any

class SignedPackage:
    def __init__(self):
        # In real scenario, use asymmetric crypto (RSA/Ed25519)
        # Using HMAC for MVP with shared secret
        self.signing_key = b"owner_secret_key"

    def sign_package(self, package_data: Dict[str, Any]) -> Dict[str, Any]:
        serialized = json.dumps(package_data, sort_keys=True)
        signature = hmac.new(self.signing_key, serialized.encode(), hashlib.sha256).hexdigest()
        return {
            "payload": package_data,
            "signature": signature
        }

    def verify_package(self, signed_package: Dict[str, Any]) -> bool:
        payload = signed_package.get("payload")
        signature = signed_package.get("signature")
        
        if not payload or not signature:
            return False
            
        serialized = json.dumps(payload, sort_keys=True)
        expected_sig = hmac.new(self.signing_key, serialized.encode(), hashlib.sha256).hexdigest()
        
        return hmac.compare_digest(signature, expected_sig)
