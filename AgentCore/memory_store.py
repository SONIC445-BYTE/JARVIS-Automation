"""
Memory Store - Long-Term Encrypted Preference Storage
=======================================================
Persistent storage for learned preferences and patterns.

Sprint 4: Learning & Personalization
"""

import os
import json
import time
import base64
import hashlib
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from pathlib import Path
from datetime import datetime
from threading import Lock


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
    - Simple encryption
    - Export/delete capability
    - Versioned snapshots
    """
    
    VERSION = 1
    
    def __init__(self, store_dir: Optional[Path] = None, encryption_key: str = None):
        if store_dir is None:
            store_dir = Path(__file__).parent.parent / "data" / "memory"
        
        self.store_dir = Path(store_dir)
        self.store_dir.mkdir(parents=True, exist_ok=True)
        
        self._store_file = self.store_dir / "memory_store.json"
        self._backup_dir = self.store_dir / "backups"
        self._backup_dir.mkdir(exist_ok=True)
        
        # Simple encryption key (in production, use proper key management)
        self._key = (encryption_key or "jarvis_default_key").encode()
        
        self._memory: Dict[str, MemoryRecord] = {}
        self._lock = Lock()
        
        self._load()
    
    def _encrypt(self, data: str) -> str:
        """Simple XOR encryption (for demonstration)."""
        # In production, use proper AES-256 encryption
        key_bytes = self._key * ((len(data) // len(self._key)) + 1)
        encrypted = bytes(a ^ b for a, b in zip(data.encode(), key_bytes[:len(data)]))
        return base64.b64encode(encrypted).decode()
    
    def _decrypt(self, data: str) -> str:
        """Simple XOR decryption."""
        encrypted = base64.b64decode(data.encode())
        key_bytes = self._key * ((len(encrypted) // len(self._key)) + 1)
        decrypted = bytes(a ^ b for a, b in zip(encrypted, key_bytes[:len(encrypted)]))
        return decrypted.decode()
    
    def _load(self):
        """Load store from disk."""
        if not self._store_file.exists():
            return
        
        try:
            with open(self._store_file, 'r') as f:
                data = json.load(f)
            
            if data.get("encrypted", False):
                content = self._decrypt(data["content"])
                records = json.loads(content)
            else:
                records = data.get("records", {})
            
            for key, record_data in records.items():
                self._memory[key] = MemoryRecord(**record_data)
                
        except Exception as e:
            print(f"[MemoryStore] Load error: {e}")
    
    def _save(self):
        """Save store to disk (encrypted)."""
        with self._lock:
            records = {k: asdict(v) for k, v in self._memory.items()}
            content = json.dumps(records)
            
            data = {
                "version": self.VERSION,
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
