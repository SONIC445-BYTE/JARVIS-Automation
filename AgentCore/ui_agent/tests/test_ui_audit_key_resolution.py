"""
D14 (second half): AgentCore/ui_agent/utils/ui_audit.py's HMAC key
resolution -- was os.environ.get("JARVIS_HMAC_KEY", "JARVIS_UI_SECRET"),
the identical hardcoded-default-key weakness D2 fixed in
memory_store.py/mode_manager/audit.py, and that DEC-002 fixed in
learning_system/audit_log.py as a byproduct. Now shares
AgentCore.secure_key.resolve_key(), same fail-closed contract, own
purpose namespace ("ui_audit"/JARVIS_UI_AUDIT_KEY) so it can't collide
with the other two HMAC key uses already in this codebase.
"""
import base64
import hashlib
import hmac
import json
import os
import secrets
import unittest
from unittest import mock

from AgentCore.secure_key import KeyConfigurationError
from AgentCore.ui_agent.utils.ui_audit import UIAudit


def _real_key_b64():
    return base64.b64encode(secrets.token_bytes(32)).decode()


class _CleanUiAuditEnv:
    """Clears both this key's env var and the dev-key opt-in for the duration of the block."""

    def __enter__(self):
        self._saved = {
            v: os.environ.pop(v, None)
            for v in ("JARVIS_UI_AUDIT_KEY", "JARVIS_INSECURE_DEV_KEY")
        }
        return self

    def __exit__(self, *a):
        for v, val in self._saved.items():
            if val is not None:
                os.environ[v] = val
            else:
                os.environ.pop(v, None)


class TestUiAuditKeyResolution(unittest.TestCase):
    def test_no_real_key_configured_refuses_rather_than_using_the_old_insecure_default(self):
        with _CleanUiAuditEnv(), \
             mock.patch("keyring.get_password", side_effect=RuntimeError("vault locked")):
            with self.assertRaises(KeyConfigurationError):
                UIAudit()

    def test_construction_with_a_real_key_produces_a_real_verifiable_signature(self):
        import tempfile
        from pathlib import Path

        real_key_b64 = _real_key_b64()
        with _CleanUiAuditEnv(), mock.patch.dict(os.environ, {"JARVIS_UI_AUDIT_KEY": real_key_b64}), \
             mock.patch("builtins.print"), tempfile.TemporaryDirectory() as tmp:
            audit = UIAudit()
            audit.log_dir = Path(tmp)  # redirect off the real repo before any write
            audit.log_action("req-1", {"action": "click"}, "ok")

            log_file = Path(tmp) / f"audit_{__import__('time').strftime('%Y%m%d')}.jsonl"
            line = log_file.read_text(encoding="utf-8").strip()
            entry = json.loads(line)

            real_key = base64.b64decode(real_key_b64)
            entry_without_sig = {k: v for k, v in entry.items() if k != "sig"}
            expected_sig = hmac.new(
                real_key, json.dumps(entry_without_sig, sort_keys=True).encode(), hashlib.sha256
            ).hexdigest()
            self.assertEqual(entry["sig"], expected_sig)

    def test_wrong_key_produces_a_different_signature_not_silently_matching(self):
        import tempfile
        from pathlib import Path

        key_a = _real_key_b64()
        key_b = _real_key_b64()
        sigs = []
        for key_b64 in (key_a, key_b):
            with _CleanUiAuditEnv(), mock.patch.dict(os.environ, {"JARVIS_UI_AUDIT_KEY": key_b64}), \
                 mock.patch("builtins.print"), tempfile.TemporaryDirectory() as tmp:
                audit = UIAudit()
                audit.log_dir = Path(tmp)
                audit.log_action("req-1", {"action": "click"}, "ok")
                log_file = Path(tmp) / f"audit_{__import__('time').strftime('%Y%m%d')}.jsonl"
                entry = json.loads(log_file.read_text(encoding="utf-8").strip())
                sigs.append(entry["sig"])
        self.assertNotEqual(sigs[0], sigs[1])

    def test_old_hardcoded_default_literal_no_longer_produces_a_matching_signature(self):
        """
        Regression guard for the actual D14 weakness: a signature computed
        with the retired literal "JARVIS_UI_SECRET" must never match a
        signature produced by a real, properly-resolved key.
        """
        import tempfile
        from pathlib import Path

        real_key_b64 = _real_key_b64()
        with _CleanUiAuditEnv(), mock.patch.dict(os.environ, {"JARVIS_UI_AUDIT_KEY": real_key_b64}), \
             mock.patch("builtins.print"), tempfile.TemporaryDirectory() as tmp:
            audit = UIAudit()
            audit.log_dir = Path(tmp)
            audit.log_action("req-1", {"action": "click"}, "ok")
            log_file = Path(tmp) / f"audit_{__import__('time').strftime('%Y%m%d')}.jsonl"
            entry = json.loads(log_file.read_text(encoding="utf-8").strip())

        entry_without_sig = {k: v for k, v in entry.items() if k != "sig"}
        old_default_sig = hmac.new(
            b"JARVIS_UI_SECRET", json.dumps(entry_without_sig, sort_keys=True).encode(), hashlib.sha256
        ).hexdigest()
        self.assertNotEqual(entry["sig"], old_default_sig)


if __name__ == "__main__":
    unittest.main()
