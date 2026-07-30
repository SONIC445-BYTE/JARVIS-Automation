"""
D2: AgentCore/mode_manager/audit.py's HMAC key resolution -- was
os.environ.get("JARVIS_HMAC_KEY") falling back to a hardcoded
b"dev_insecure_key_default" (the identical weakness memory_store.py's
XOR encryption had). Now shares AgentCore.secure_key.resolve_key(),
same fail-closed contract.
"""
import base64
import os
import secrets
import unittest
from unittest import mock

from AgentCore.mode_manager import audit
from AgentCore.secure_key import KeyConfigurationError


class _CleanHmacEnv:
    def __enter__(self):
        self._saved = {
            v: os.environ.pop(v, None)
            for v in ("JARVIS_HMAC_KEY", "JARVIS_INSECURE_DEV_KEY")
        }
        return self

    def __exit__(self, *a):
        for v, val in self._saved.items():
            if val is not None:
                os.environ[v] = val
            else:
                os.environ.pop(v, None)


class TestAuditKeyResolution(unittest.TestCase):
    def test_sign_and_verify_round_trip_with_a_real_key(self):
        real_key_b64 = base64.b64encode(secrets.token_bytes(32)).decode()
        with _CleanHmacEnv(), mock.patch.dict(os.environ, {"JARVIS_HMAC_KEY": real_key_b64}), \
             mock.patch("builtins.print"):
            entry = {"action": "test", "ts": 1.0}
            entry["sig"] = audit.sign_entry(entry)
            line = __import__("json").dumps(entry)
            self.assertTrue(audit.verify_line(line))

    def test_no_real_key_configured_refuses_rather_than_using_the_old_insecure_default(self):
        with _CleanHmacEnv(), mock.patch("builtins.print"), \
             mock.patch("keyring.get_password", side_effect=RuntimeError("vault locked")):
            with self.assertRaises(KeyConfigurationError):
                audit.sign_entry({"action": "test"})

    def test_verify_line_with_wrong_key_fails_honestly_not_silently_true(self):
        real_key_b64 = base64.b64encode(secrets.token_bytes(32)).decode()
        other_key_b64 = base64.b64encode(secrets.token_bytes(32)).decode()

        with _CleanHmacEnv(), mock.patch.dict(os.environ, {"JARVIS_HMAC_KEY": real_key_b64}), \
             mock.patch("builtins.print"):
            entry = {"action": "test", "ts": 1.0}
            entry["sig"] = audit.sign_entry(entry)
            line = __import__("json").dumps(entry)

        with _CleanHmacEnv(), mock.patch.dict(os.environ, {"JARVIS_HMAC_KEY": other_key_b64}), \
             mock.patch("builtins.print"):
            self.assertFalse(audit.verify_line(line))


if __name__ == "__main__":
    unittest.main()
