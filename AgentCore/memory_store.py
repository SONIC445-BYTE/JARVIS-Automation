"""
Memory Store - Long-Term Encrypted Preference Storage
=======================================================
Persistent storage for learned preferences and patterns.

Sprint 4: Learning & Personalization

D2 (2026-07-30): replaced XOR "encryption" under a hardcoded default
key (`"jarvis_default_key"`) with real AES-256-GCM under a key from
AgentCore.secure_key.resolve_key() -- OS keyring by default, an
explicit env var or dev-only file as deliberate alternatives, never a
silent insecure fallback. No real caller ever passed a custom
encryption_key (confirmed by reading every call site before this
change), so every record on disk under the old scheme was encrypted
with that one hardcoded key -- _migrate_legacy_xor() uses exactly that
fact to do a one-time, verified migration on first load.
"""

import os
import json
import time
import base64
import hashlib
import shutil
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from pathlib import Path
from datetime import datetime
from threading import Lock

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .secure_key import resolve_key, KeyConfigurationError

FORMAT_AES_GCM = "aes-gcm-v1"
# The only key any pre-D2 data could ever have been encrypted with --
# no real caller ever passed a custom encryption_key to MemoryStore.
_LEGACY_XOR_DEFAULT_KEY = b"jarvis_default_key"


class MemoryStoreMigrationError(Exception):
    """
    Raised when migrating legacy XOR-encrypted data to AES-GCM fails at
    any step. Must propagate, not be caught-and-ignored: a partially
    migrated store (some records under the old format, some under the
    new, with no marker distinguishing which) is a worse state than
    either end of the migration, so this refuses to leave that outcome.
    """


@dataclass
class MemoryRecord:
    """Single memory record."""
    key: str
    value: Any
    category: str  # preference, pattern, shortcut
    created_at: float
    updated_at: float
    access_count: int = 0
    last_accessed: Optional[float] = None
    tags: List[str] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []


class MemoryStore:
    """
    Encrypted, append-only preference store.
    
    Features:
    - Local-only (no cloud sync)
    - AES-256-GCM encryption, real key resolution (see secure_key.py)
    - Export/delete capability
    - Versioned snapshots
    """
    
    VERSION = 2  # D2: real key resolution + AES-GCM, replacing XOR under a hardcoded key

    def __init__(self, store_dir: Optional[Path] = None, encryption_key: Optional[bytes] = None):
        if store_dir is None:
            store_dir = Path(__file__).parent.parent / "data" / "memory"

        self.store_dir = Path(store_dir)
        self.store_dir.mkdir(parents=True, exist_ok=True)

        self._store_file = self.store_dir / "memory_store.json"
        self._backup_dir = self.store_dir / "backups"
        self._backup_dir.mkdir(exist_ok=True)

        # D2: real key resolution -- fails closed (raises
        # KeyConfigurationError) if no real key source is configured.
        # No insecure default; callers must handle or let this
        # propagate, never catch-and-substitute a weaker key.
        self._key = encryption_key or resolve_key("memory_store", "JARVIS_MEMORY_KEY")
        self._aesgcm = AESGCM(self._key)

        self._memory: Dict[str, MemoryRecord] = {}
        self._lock = Lock()

        self._load()

    def _encrypt(self, plaintext: str) -> str:
        """AES-256-GCM encryption. Nonce is regenerated per call and prepended to the ciphertext."""
        nonce = os.urandom(12)
        ciphertext = self._aesgcm.encrypt(nonce, plaintext.encode(), None)
        return base64.b64encode(nonce + ciphertext).decode()

    def _decrypt(self, blob: str) -> str:
        """AES-256-GCM decryption -- raises if the key is wrong or the data was tampered with."""
        raw = base64.b64decode(blob.encode())
        nonce, ciphertext = raw[:12], raw[12:]
        plaintext = self._aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext.decode()

    def _load(self):
        """Load store from disk, migrating legacy XOR-format data if found."""
        if not self._store_file.exists():
            return

        try:
            with open(self._store_file, 'r') as f:
                data = json.load(f)
        except Exception as e:
            # A malformed/unreadable file is treated softly (log, start
            # with an empty store) -- this is the pre-existing behavior
            # for genuinely corrupt JSON, not something D2 changes.
            print(f"[MemoryStore] Load error: {e}")
            return

        if data.get("format") == FORMAT_AES_GCM:
            # Deliberately NOT inside a broad try/except: a decryption
            # failure here (wrong key, or tampering -- raises
            # cryptography.exceptions.InvalidTag) must propagate, not be
            # silently swallowed into "started with an empty store."
            # Confirmed live during testing: the original broad
            # except-and-log here made a wrong key indistinguishable
            # from "no data was ever saved" -- the exact kind of silent
            # data loss D2 exists to prevent, not just XOR itself.
            content = self._decrypt(data["content"])
            records = json.loads(content)
        elif data.get("encrypted") and data.get("format") is None:
            # Pre-D2 files are always {"encrypted": True, ...} with no
            # "format" key at all -- that combination is the migration
            # trigger. Also not caught here: a migration failure must
            # stop __init__/_load, not be swallowed.
            records = self._migrate_legacy_xor(data)
        else:
            records = data.get("records", {})

        for key, record_data in records.items():
            self._memory[key] = MemoryRecord(**record_data)

    def _migrate_legacy_xor(self, data: dict) -> dict:
        """
        One-time migration from the pre-D2 XOR scheme to AES-GCM.
        Legacy data was always encrypted with the hardcoded default key
        -- no real caller ever configured a custom one (confirmed by
        reading every real MemoryStore() call site before writing this).
        Decrypts with that known legacy key, re-encrypts under the real
        resolved key, and verifies the round-trip BEFORE touching the
        old file. Any single failure raises MemoryStoreMigrationError
        and aborts the whole migration -- never leaves a partially
        migrated store.
        """
        try:
            legacy_content = self._xor_decrypt_legacy(data["content"])
            records = json.loads(legacy_content)
        except Exception as e:
            raise MemoryStoreMigrationError(
                f"Legacy XOR data in {self._store_file} could not be decrypted with the "
                f"known legacy default key: {e}. Refusing to proceed -- back up the file "
                f"and investigate before retrying; this store is otherwise untouched."
            ) from e

        new_content = json.dumps(records)
        try:
            encrypted = self._encrypt(new_content)
            roundtrip = self._decrypt(encrypted)
        except Exception as e:
            raise MemoryStoreMigrationError(
                f"AES-GCM re-encryption failed during migration of {self._store_file}: {e}. "
                f"Refusing to proceed; this store is otherwise untouched."
            ) from e
        if roundtrip != new_content:
            raise MemoryStoreMigrationError(
                f"AES-GCM re-encryption round-trip check failed during migration of "
                f"{self._store_file} -- decrypted content did not match what was encrypted. "
                f"Refusing to write; this store is otherwise untouched. Do not retry "
                f"without investigating."
            )

        # Only now that the new format is confirmed readable: back up the
        # old file, then overwrite it with the migrated data.
        backup_path = self._store_file.with_name(self._store_file.stem + ".xor-backup.json")
        try:
            shutil.copy2(self._store_file, backup_path)
        except Exception as e:
            raise MemoryStoreMigrationError(
                f"Could not write pre-migration backup {backup_path}: {e}. Refusing to "
                f"overwrite {self._store_file} without a backup in place."
            ) from e

        new_data = {
            "version": self.VERSION,
            "format": FORMAT_AES_GCM,
            "encrypted": True,
            "content": encrypted,
            "updated_at": time.time(),
            "migrated_from": "xor-v1",
            "migrated_at": time.time(),
        }
        with open(self._store_file, 'w') as f:
            json.dump(new_data, f)

        print(
            f"[MemoryStore] Migrated legacy XOR-encrypted data to AES-GCM "
            f"({len(records)} record(s)). Pre-migration backup: {backup_path}"
        )
        return records

    @staticmethod
    def _xor_decrypt_legacy(data: str) -> str:
        """
        Decrypts data written under the pre-D2 XOR scheme, using the
        one key it could ever have been encrypted with -- migration-only,
        never used for new data.
        """
        key = _LEGACY_XOR_DEFAULT_KEY
        encrypted = base64.b64decode(data.encode())
        key_bytes = key * ((len(encrypted) // len(key)) + 1)
        decrypted = bytes(a ^ b for a, b in zip(encrypted, key_bytes[:len(encrypted)]))
        return decrypted.decode()

    def _save(self):
        """Save store to disk (AES-GCM encrypted)."""
        with self._lock:
            records = {k: asdict(v) for k, v in self._memory.items()}
            content = json.dumps(records)

            data = {
                "version": self.VERSION,
                "format": FORMAT_AES_GCM,
                "encrypted": True,
                "content": self._encrypt(content),
                "updated_at": time.time()
            }

            try:
                with open(self._store_file, 'w') as f:
                    json.dump(data, f)
            except Exception as e:
                print(f"[MemoryStore] Save error: {e}")
    
    # ============ Public API ============
    
    def set(self, key: str, value: Any, category: str = "preference", 
           tags: List[str] = None):
        """
        Store a value.
        
        Args:
            key: Storage key
            value: Value to store
            category: preference, pattern, or shortcut
            tags: Optional tags for filtering
        """
        with self._lock:
            now = time.time()
            
            if key in self._memory:
                record = self._memory[key]
                record.value = value
                record.updated_at = now
            else:
                record = MemoryRecord(
                    key=key,
                    value=value,
                    category=category,
                    created_at=now,
                    updated_at=now,
                    tags=tags or []
                )
                self._memory[key] = record
        
        self._save()
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Retrieve a value.
        
        Args:
            key: Storage key
            default: Default if not found
            
        Returns:
            Stored value or default
        """
        with self._lock:
            record = self._memory.get(key)
            if record:
                record.access_count += 1
                record.last_accessed = time.time()
                return record.value
            return default
    
    def get_pref(self, key: str, default: Any = None) -> Any:
        """Get a preference value (convenience alias)."""
        return self.get(f"pref:{key}", default)
    
    def set_pref(self, key: str, value: Any):
        """Set a preference value (convenience alias)."""
        self.set(f"pref:{key}", value, category="preference")
    
    def delete(self, key: str) -> bool:
        """Delete a record."""
        with self._lock:
            if key in self._memory:
                del self._memory[key]
                self._save()
                return True
            return False
    
    def get_by_category(self, category: str) -> Dict[str, Any]:
        """Get all records in a category."""
        with self._lock:
            return {
                k: v.value for k, v in self._memory.items()
                if v.category == category
            }
    
    def get_by_tag(self, tag: str) -> Dict[str, Any]:
        """Get all records with a tag."""
        with self._lock:
            return {
                k: v.value for k, v in self._memory.items()
                if tag in v.tags
            }
    
    def search(self, query: str) -> List[MemoryRecord]:
        """Search records by key or value."""
        query_lower = query.lower()
        results = []
        
        with self._lock:
            for record in self._memory.values():
                if query_lower in record.key.lower():
                    results.append(record)
                elif isinstance(record.value, str) and query_lower in record.value.lower():
                    results.append(record)
        
        return results
    
    # ============ Backup & Export ============
    
    def backup(self) -> Path:
        """Create versioned backup."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = self._backup_dir / f"backup_{timestamp}.json"
        
        with self._lock:
            records = {k: asdict(v) for k, v in self._memory.items()}
            
            with open(backup_file, 'w') as f:
                json.dump({
                    "version": self.VERSION,
                    "timestamp": time.time(),
                    "records": records
                }, f, indent=2)
        
        return backup_file
    
    def export_plaintext(self, output_file: Path) -> bool:
        """Export as plaintext JSON (for user inspection)."""
        try:
            with self._lock:
                records = {k: asdict(v) for k, v in self._memory.items()}
            
            with open(output_file, 'w') as f:
                json.dump(records, f, indent=2)
            
            return True
        except Exception as e:
            print(f"[MemoryStore] Export error: {e}")
            return False
    
    def purge(self, confirm: bool = False):
        """Delete all stored data."""
        if not confirm:
            print("[MemoryStore] Purge requires confirm=True")
            return
        
        with self._lock:
            self._memory.clear()
        
        if self._store_file.exists():
            self._store_file.unlink()
        
        print("[MemoryStore] All data purged")
    
    def get_stats(self) -> Dict:
        """Get store statistics."""
        with self._lock:
            by_category = {}
            total_accesses = 0
            
            for record in self._memory.values():
                by_category[record.category] = by_category.get(record.category, 0) + 1
                total_accesses += record.access_count
        
        return {
            "total_records": len(self._memory),
            "by_category": by_category,
            "total_accesses": total_accesses,
            "store_file": str(self._store_file)
        }


def test_memory_store():
    """Test memory store."""
    print("Memory Store Test")
    print("=" * 50)
    
    store = MemoryStore()
    
    # Set preferences
    store.set_pref("default_browser", "chrome")
    store.set_pref("voice_volume", 0.8)
    
    # Get preference
    print(f"default_browser: {store.get_pref('default_browser')}")
    
    # Set with tags
    store.set("shortcut:morning_routine", ["open outlook", "play music"], 
             category="shortcut", tags=["morning", "routine"])
    
    # Stats
    print(f"Stats: {store.get_stats()}")
    
    # Search
    results = store.search("browser")
    print(f"Search 'browser': {len(results)} results")


if __name__ == "__main__":
    test_memory_store()
