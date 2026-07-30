"""
D2: AgentCore/secure_key.py -- shared key resolution for memory_store.py
(AES-GCM) and mode_manager/audit.py (HMAC), replacing the hardcoded/
env-fallback insecure default key both previously used.
"""
import base64
import os
import secrets
import unittest
from pathlib import Path
from unittest import mock

from AgentCore.secure_key import KeyConfigurationError, resolve_key


class _CleanEnv:
    """Ensures the 3 key-related env vars are unset unless a test sets them."""

    VARS = ["JARVIS_INSECURE_DEV_KEY", "JARVIS_TEST_PURPOSE_KEY"]

    def __enter__(self):
        self._saved = {v: os.environ.pop(v, None) for v in self.VARS}
        return self

    def __exit__(self, *a):
        for v, val in self._saved.items():
            if val is not None:
                os.environ[v] = val
            else:
                os.environ.pop(v, None)


class TestDevKeySource(unittest.TestCase):
    def test_generates_and_persists_a_key_file(self):
        with _CleanEnv(), mock.patch.dict(os.environ, {"JARVIS_INSECURE_DEV_KEY": "1"}), \
             mock.patch("builtins.print"):
            import tempfile
            with tempfile.TemporaryDirectory() as tmp:
                key_dir = Path(tmp)
                key1 = resolve_key("test_purpose", "JARVIS_TEST_PURPOSE_KEY", dev_key_dir=key_dir)
                key2 = resolve_key("test_purpose", "JARVIS_TEST_PURPOSE_KEY", dev_key_dir=key_dir)

        self.assertEqual(len(key1), 32)
        self.assertEqual(key1, key2)  # persisted, not regenerated each call

    def test_rejects_a_corrupt_length_dev_key_file(self):
        with _CleanEnv(), mock.patch.dict(os.environ, {"JARVIS_INSECURE_DEV_KEY": "1"}), \
             mock.patch("builtins.print"):
            import tempfile
            with tempfile.TemporaryDirectory() as tmp:
                key_dir = Path(tmp)
                (key_dir / "test_purpose.key").write_bytes(b"too short")
                with self.assertRaises(KeyConfigurationError):
                    resolve_key("test_purpose", "JARVIS_TEST_PURPOSE_KEY", dev_key_dir=key_dir)


class TestEnvVarKeySource(unittest.TestCase):
    def test_valid_base64_key_is_decoded_correctly(self):
        real_key = secrets.token_bytes(32)
        encoded = base64.b64encode(real_key).decode()
        with _CleanEnv(), mock.patch.dict(os.environ, {"JARVIS_TEST_PURPOSE_KEY": encoded}), \
             mock.patch("builtins.print"):
            resolved = resolve_key("test_purpose", "JARVIS_TEST_PURPOSE_KEY")
        self.assertEqual(resolved, real_key)

    def test_rejects_invalid_base64(self):
        with _CleanEnv(), mock.patch.dict(os.environ, {"JARVIS_TEST_PURPOSE_KEY": "not-valid-base64!!!"}), \
             mock.patch("builtins.print"):
            with self.assertRaises(KeyConfigurationError):
                resolve_key("test_purpose", "JARVIS_TEST_PURPOSE_KEY")

    def test_rejects_wrong_length_key(self):
        short_key_b64 = base64.b64encode(b"tooshort").decode()
        with _CleanEnv(), mock.patch.dict(os.environ, {"JARVIS_TEST_PURPOSE_KEY": short_key_b64}), \
             mock.patch("builtins.print"):
            with self.assertRaises(KeyConfigurationError):
                resolve_key("test_purpose", "JARVIS_TEST_PURPOSE_KEY")


class TestAmbiguousConfiguration(unittest.TestCase):
    def test_both_dev_flag_and_env_var_set_is_refused(self):
        real_key_b64 = base64.b64encode(secrets.token_bytes(32)).decode()
        with _CleanEnv(), mock.patch.dict(os.environ, {
            "JARVIS_INSECURE_DEV_KEY": "1",
            "JARVIS_TEST_PURPOSE_KEY": real_key_b64,
        }), mock.patch("builtins.print"):
            with self.assertRaises(KeyConfigurationError) as ctx:
                resolve_key("test_purpose", "JARVIS_TEST_PURPOSE_KEY")
        self.assertIn("Ambiguous", str(ctx.exception))


class TestKeyringSource(unittest.TestCase):
    """
    Real keyring is used here (Windows Credential Manager on this
    machine, confirmed live) -- not mocked, so this actually proves the
    default path works, not just that the code calls the right
    functions. Cleans up after itself.
    """

    def setUp(self):
        import keyring
        self.keyring = keyring
        try:
            self.keyring.delete_password("jarvis", "test_purpose_key")
        except Exception:
            pass  # nothing stored yet -- fine

    def tearDown(self):
        try:
            self.keyring.delete_password("jarvis", "test_purpose_key")
        except Exception:
            pass

    def test_generates_and_persists_a_real_keyring_entry(self):
        with _CleanEnv(), mock.patch("builtins.print"):
            key1 = resolve_key("test_purpose", "JARVIS_TEST_PURPOSE_KEY")
            key2 = resolve_key("test_purpose", "JARVIS_TEST_PURPOSE_KEY")

        self.assertEqual(len(key1), 32)
        self.assertEqual(key1, key2)  # real keyring round-trip, not regenerated

    def test_keyring_failure_refuses_to_start_rather_than_falling_back(self):
        with _CleanEnv(), mock.patch("builtins.print"), \
             mock.patch("keyring.get_password", side_effect=RuntimeError("vault locked")):
            with self.assertRaises(KeyConfigurationError) as ctx:
                resolve_key("test_purpose", "JARVIS_TEST_PURPOSE_KEY")
        self.assertIn("keyring", str(ctx.exception).lower())

    def test_missing_keyring_package_refuses_rather_than_falling_back(self):
        with _CleanEnv(), mock.patch("builtins.print"), \
             mock.patch.dict("sys.modules", {"keyring": None}):
            with self.assertRaises(KeyConfigurationError) as ctx:
                resolve_key("test_purpose", "JARVIS_TEST_PURPOSE_KEY")
        self.assertIn("keyring", str(ctx.exception).lower())


if __name__ == "__main__":
    unittest.main()
