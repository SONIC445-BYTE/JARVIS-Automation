"""
D14 (second half): AgentCore/ui_agent/utils/ui_audit.py's HMAC key
resolution -- was os.environ.get("JARVIS_HMAC_KEY", "JARVIS_UI_SECRET"),
the identical hardcoded-default-key weakness D2 fixed in
memory_store.py/mode_manager/audit.py, and that DEC-002 fixed in
learning_system/audit_log.py as a byproduct. Now shares
AgentCore.secure_key.resolve_key(), same fail-closed contract, own
purpose namespace ("ui_audit"/JARVIS_UI_AUDIT_KEY) so it can't collide
with the other two HMAC key uses already in this codebase.

Log-directory isolation comes from the autouse fixture in this
directory's conftest.py. An earlier version of these tests set
`audit.log_dir` *after* construction -- too late, since
UIAudit.__init__ mkdir's the directory eagerly, so the real repo
directory was still being created on every run. Redirecting via the
env var happens before construction and actually works.
"""
import base64
import hashlib
import hmac
import json
import os
import secrets
import time
import unittest
from pathlib import Path
from unittest import mock

from AgentCore.secure_key import KeyConfigurationError
from AgentCore.ui_agent.utils import ui_audit
from AgentCore.ui_agent.utils.ui_audit import UIAudit


def _real_key_b64():
    return base64.b64encode(secrets.token_bytes(32)).decode()


def _isolated_log_dir() -> Path:
    """The per-test directory conftest.py's autouse fixture redirected to."""
    return Path(os.environ[ui_audit.LOG_DIR_ENV_VAR])


def _todays_log(log_dir: Path) -> Path:
    return log_dir / f"audit_{time.strftime('%Y%m%d')}.jsonl"


class _CleanUiAuditEnv:
    """Clears this key's env var and the dev-key opt-in for the duration of the block."""

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
        real_key_b64 = _real_key_b64()
        with _CleanUiAuditEnv(), mock.patch.dict(os.environ, {"JARVIS_UI_AUDIT_KEY": real_key_b64}), \
             mock.patch("builtins.print"):
            audit = UIAudit()
            audit.log_action("req-1", {"action": "click"}, "ok")
            entry = json.loads(_todays_log(_isolated_log_dir()).read_text(encoding="utf-8").strip())

        real_key = base64.b64decode(real_key_b64)
        entry_without_sig = {k: v for k, v in entry.items() if k != "sig"}
        expected_sig = hmac.new(
            real_key, json.dumps(entry_without_sig, sort_keys=True).encode(), hashlib.sha256
        ).hexdigest()
        self.assertEqual(entry["sig"], expected_sig)

    def test_wrong_key_produces_a_different_signature_not_silently_matching(self):
        sigs = []
        for key_b64 in (_real_key_b64(), _real_key_b64()):
            with _CleanUiAuditEnv(), mock.patch.dict(os.environ, {"JARVIS_UI_AUDIT_KEY": key_b64}), \
                 mock.patch("builtins.print"):
                log_file = _todays_log(_isolated_log_dir())
                if log_file.exists():
                    log_file.unlink()  # same tmp dir across both loop passes
                audit = UIAudit()
                audit.log_action("req-1", {"action": "click"}, "ok")
                entry = json.loads(log_file.read_text(encoding="utf-8").strip())
                sigs.append(entry["sig"])
        self.assertNotEqual(sigs[0], sigs[1])

    def test_old_hardcoded_default_literal_no_longer_produces_a_matching_signature(self):
        """
        Regression guard for the actual D14 weakness: a signature computed
        with the retired literal "JARVIS_UI_SECRET" must never match a
        signature produced by a real, properly-resolved key.
        """
        with _CleanUiAuditEnv(), mock.patch.dict(os.environ, {"JARVIS_UI_AUDIT_KEY": _real_key_b64()}), \
             mock.patch("builtins.print"):
            audit = UIAudit()
            audit.log_action("req-1", {"action": "click"}, "ok")
            entry = json.loads(_todays_log(_isolated_log_dir()).read_text(encoding="utf-8").strip())

        entry_without_sig = {k: v for k, v in entry.items() if k != "sig"}
        old_default_sig = hmac.new(
            b"JARVIS_UI_SECRET", json.dumps(entry_without_sig, sort_keys=True).encode(), hashlib.sha256
        ).hexdigest()
        self.assertNotEqual(entry["sig"], old_default_sig)


class TestUiAuditLogDirIsolation(unittest.TestCase):
    """
    The isolation mechanism itself, tested rather than assumed -- a
    fixture that silently stopped working would return this subsystem
    to writing into the real repo without anything failing.
    """

    def test_log_dir_honors_the_env_var_override(self):
        with _CleanUiAuditEnv(), mock.patch.dict(os.environ, {"JARVIS_UI_AUDIT_KEY": _real_key_b64()}), \
             mock.patch("builtins.print"):
            audit = UIAudit()
            self.assertEqual(audit.log_dir, _isolated_log_dir())

    def test_writes_land_in_the_isolated_dir_not_the_repo_default(self):
        with _CleanUiAuditEnv(), mock.patch.dict(os.environ, {"JARVIS_UI_AUDIT_KEY": _real_key_b64()}), \
             mock.patch("builtins.print"):
            audit = UIAudit()
            audit.log_action("req-iso", {"action": "click"}, "ok")

        written = _todays_log(_isolated_log_dir())
        self.assertTrue(written.exists())
        self.assertIn("req-iso", written.read_text(encoding="utf-8"))
        # The isolated path must genuinely not be the production one.
        self.assertNotEqual(
            _isolated_log_dir().resolve(),
            Path(ui_audit.DEFAULT_LOG_DIR).resolve(),
        )


if __name__ == "__main__":
    unittest.main()
