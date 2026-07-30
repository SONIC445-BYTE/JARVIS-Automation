"""
D2: MemoryStore's real AES-256-GCM encryption, fail-closed key
resolution, and the legacy-XOR-to-AES-GCM migration path.

Real round-trip tests throughout -- a real generated key via
AgentCore.secure_key (dev-file source, so these don't touch the OS
keyring for every test run), not a mocked cipher.
"""
import base64
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from AgentCore.memory_store import MemoryStore, MemoryStoreMigrationError
from AgentCore.secure_key import KeyConfigurationError


def _real_key():
    """A real, random 32-byte key -- not a mock, not a fixed test constant."""
    import secrets
    return secrets.token_bytes(32)


class TestRealEncryptionRoundTrip(unittest.TestCase):
    def test_set_get_persist_reload_round_trips_with_a_real_key(self):
        key = _real_key()
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(store_dir=Path(tmp), encryption_key=key)
            store.set_pref("default_browser", "firefox")
            store.set("shortcut:morning", ["open outlook"], category="shortcut", tags=["morning"])

            # Fresh instance, same key -- proves real persistence + decryption, not an in-memory cache.
            reloaded = MemoryStore(store_dir=Path(tmp), encryption_key=key)
            self.assertEqual(reloaded.get_pref("default_browser"), "firefox")
            self.assertEqual(reloaded.get("shortcut:morning"), ["open outlook"])

    def test_on_disk_content_is_not_plaintext_and_is_format_marked(self):
        key = _real_key()
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(store_dir=Path(tmp), encryption_key=key)
            store.set_pref("secret_value", "should-not-appear-in-plaintext-on-disk")

            raw = (Path(tmp) / "memory_store.json").read_text()
            self.assertNotIn("should-not-appear-in-plaintext-on-disk", raw)
            envelope = json.loads(raw)
            self.assertEqual(envelope["format"], "aes-gcm-v1")

    def test_wrong_key_cannot_decrypt_another_store(self):
        # Found live while writing this test: the first version of
        # _load() caught this in a broad except-and-log, so a wrong key
        # silently produced an *empty* store instead of an error --
        # indistinguishable from "nothing was ever saved," exactly the
        # kind of silent data loss D2 exists to prevent. Fixed to
        # propagate; pinned here so it can't regress back to swallowed.
        from cryptography.exceptions import InvalidTag

        key_a = _real_key()
        key_b = _real_key()
        with tempfile.TemporaryDirectory() as tmp:
            MemoryStore(store_dir=Path(tmp), encryption_key=key_a).set_pref("x", "y")
            with self.assertRaises(InvalidTag):
                MemoryStore(store_dir=Path(tmp), encryption_key=key_b)


class TestFailClosedKeyResolution(unittest.TestCase):
    def test_refuses_to_construct_when_no_key_source_is_configured_and_keyring_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch("keyring.get_password", side_effect=RuntimeError("vault locked")), \
                 mock.patch.dict(os.environ, {}, clear=False):
                for var in ("JARVIS_MEMORY_KEY", "JARVIS_INSECURE_DEV_KEY"):
                    os.environ.pop(var, None)
                with self.assertRaises(KeyConfigurationError):
                    MemoryStore(store_dir=Path(tmp))

    def test_never_silently_substitutes_the_old_hardcoded_default(self):
        # The exact regression this fix exists to prevent: a failure in
        # key resolution must never result in the old
        # b"jarvis_default_key" (or any other insecure default) being
        # used silently.
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch("keyring.get_password", side_effect=RuntimeError("vault locked")):
                for var in ("JARVIS_MEMORY_KEY", "JARVIS_INSECURE_DEV_KEY"):
                    os.environ.pop(var, None)
                try:
                    MemoryStore(store_dir=Path(tmp))
                    self.fail("expected KeyConfigurationError, no exception was raised")
                except KeyConfigurationError:
                    pass  # correct -- fail closed, no store was constructed at all


class TestLegacyXorMigration(unittest.TestCase):
    LEGACY_KEY = b"jarvis_default_key"

    def _xor_encrypt_legacy(self, data: str) -> str:
        key_bytes = self.LEGACY_KEY * ((len(data) // len(self.LEGACY_KEY)) + 1)
        encrypted = bytes(a ^ b for a, b in zip(data.encode(), key_bytes[: len(data)]))
        return base64.b64encode(encrypted).decode()

    def _write_legacy_file(self, tmp: Path, records: dict) -> Path:
        content = json.dumps(records)
        envelope = {
            "version": 1,
            "encrypted": True,
            "content": self._xor_encrypt_legacy(content),
            "updated_at": 1000.0,
        }
        store_file = tmp / "memory_store.json"
        store_file.write_text(json.dumps(envelope))
        return store_file

    def test_migrates_legacy_data_and_it_is_readable_afterward(self):
        records = {
            "pref:default_browser": {
                "key": "pref:default_browser", "value": "firefox", "category": "preference",
                "created_at": 1000.0, "updated_at": 1000.0, "access_count": 0,
                "last_accessed": None, "tags": [],
            }
        }
        key = _real_key()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            store_file = self._write_legacy_file(tmp_path, records)

            store = MemoryStore(store_dir=tmp_path, encryption_key=key)
            self.assertEqual(store.get_pref("default_browser"), "firefox")

            envelope = json.loads(store_file.read_text())
            self.assertEqual(envelope["format"], "aes-gcm-v1")
            self.assertEqual(envelope["migrated_from"], "xor-v1")

    def test_writes_a_backup_of_the_pre_migration_file(self):
        records = {"pref:x": {
            "key": "pref:x", "value": "y", "category": "preference",
            "created_at": 1.0, "updated_at": 1.0, "access_count": 0,
            "last_accessed": None, "tags": [],
        }}
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            self._write_legacy_file(tmp_path, records)
            MemoryStore(store_dir=tmp_path, encryption_key=_real_key())

            backup = tmp_path / "memory_store.xor-backup.json"
            self.assertTrue(backup.exists())
            backup_envelope = json.loads(backup.read_text())
            self.assertNotIn("format", backup_envelope)  # the original, pre-migration shape

    def test_reload_after_migration_does_not_re_migrate(self):
        records = {"pref:x": {
            "key": "pref:x", "value": "y", "category": "preference",
            "created_at": 1.0, "updated_at": 1.0, "access_count": 0,
            "last_accessed": None, "tags": [],
        }}
        key = _real_key()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            self._write_legacy_file(tmp_path, records)
            MemoryStore(store_dir=tmp_path, encryption_key=key)  # migrates
            # Second load: format is already aes-gcm-v1, must load normally.
            store2 = MemoryStore(store_dir=tmp_path, encryption_key=key)
            self.assertEqual(store2.get_pref("x"), "y")

    def test_corrupted_legacy_record_hard_stops_migration_not_partial(self):
        """
        Adversarial case, per instruction: a deliberately-corrupted
        legacy record must abort the whole migration, not proceed with
        a partially-migrated store.
        """
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            store_file = tmp_path / "memory_store.json"
            # Garbage that is NOT valid XOR-then-base64-then-JSON data.
            envelope = {
                "version": 1,
                "encrypted": True,
                "content": "this-is-not-valid-base64-or-decryptable-!!!",
                "updated_at": 1000.0,
            }
            store_file.write_text(json.dumps(envelope))

            with self.assertRaises(MemoryStoreMigrationError):
                MemoryStore(store_dir=tmp_path, encryption_key=_real_key())

            # Must not have touched the original file, and must not have
            # created a backup for a migration that never actually ran.
            self.assertEqual(json.loads(store_file.read_text()), envelope)
            self.assertFalse((tmp_path / "memory_store.xor-backup.json").exists())


if __name__ == "__main__":
    unittest.main()
