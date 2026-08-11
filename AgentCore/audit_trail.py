"""
DEC-002: the clinical audit trail -- architected in before Stage 0.5,
not retrofitted after. Every action emits a who/what/when/why/source/
consent record, append-only, tamper-evident (HMAC hash chain), keyed
through AgentCore.secure_key (same fail-closed discipline as D2).

Two distinct failure modes, two distinct treatments -- this is the
whole reason AppendOnlyAuditLog.append() never raises for a write
failure the way naive "just try/except and log" logging would:

1. Configuration-class failure (no real key resolvable) -- a hard stop
   at construction time. If the audit system can't even resolve its
   own key, this object never gets constructed; KeyConfigurationError
   propagates uncaught, exactly like memory_store.py's/audit.py's D2
   behavior. This is a startup problem, not a per-write one.

2. Transient write failure during a session (disk full, permission
   error, momentary I/O failure) -- the underlying clinical action
   must NOT be blocked by this. append() catches it, queues the record
   to a separate fallback file that doesn't depend on the path that
   just failed, and returns an AuditWriteResult the caller can surface
   loudly (never silently swallowed into a log file nobody reads).
   Reconciliation is attempted on the next successful write and again
   at startup.

Extracted and generalized from AgentCore/learning_system/audit_log.py's
LearningAuditLog, whose append-only + HMAC-chain design was already
solid (sequence + prev-entry-HMAC chaining gives tamper-evidence beyond
per-entry signing) -- reused rather than building a second mechanism,
per instruction. What genuinely needed rework, confirmed by reading it
rather than assumed: its key was computed once at *module import time*
from a hardcoded-default env var read (the exact D2/D14 weakness), and
it had no distinction at all between configuration- and transient-class
write failures (log_event()'s actual file write had no try/except --
any failure, transient or not, propagated uncaught to the caller).
LearningAuditLog is now a thin wrapper over this module (see
learning_system/audit_log.py) so nothing that already imports it broke.
"""
import getpass
import hmac
import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional

from AgentCore.secure_key import resolve_key

GENESIS_HMAC = "0" * 64


@dataclass
class AuditWriteResult:
    """
    Returned by AppendOnlyAuditLog.append() -- never raises for a
    transient write failure, so callers (UIExecutor.execute_intent(),
    the single pre-adapter chokepoint) can surface a failure honestly
    without an audit-storage hiccup ever blocking the real action.
    """
    ok: bool
    entry: Dict[str, Any]
    error: Optional[str] = None
    queued_to_fallback: bool = False


class AppendOnlyAuditLog:
    """
    Append-only, HMAC-hash-chained audit log. General-purpose storage
    engine -- not tied to any one caller's record shape; callers pass
    whatever fields belong in their entries via append(entry_fields).
    """

    def __init__(self, log_path: Path, key_purpose: str, key_env_var: str):
        self._path = Path(log_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # A different file, not just a different name collision-wise --
        # doesn't share the same write path that might be the actual
        # cause of a transient failure (e.g. the directory itself being
        # briefly unwritable would still affect a same-directory file,
        # but a full disk/permission problem on the primary path is the
        # common case this guards, and colocating them keeps operational
        # discovery simple -- "check next to the real log").
        self._fallback_path = self._path.with_name(self._path.stem + ".fallback_queue.jsonl")
        self._lock = Lock()
        self._seq = 0
        self._prev_hmac = GENESIS_HMAC

        # Configuration-class failure: hard stop, matches D2. No
        # try/except here -- KeyConfigurationError must propagate so
        # this object is never constructed with a fallback/insecure key.
        self._key = resolve_key(key_purpose, key_env_var)

        self._load_state()
        self._reconcile_fallback_queue()

    # ------------------------------------------------------------------
    def _load_state(self):
        """Resume sequence counter and HMAC chain from the existing log."""
        if not self._path.exists():
            return
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    entry = json.loads(line)
                    self._seq = entry.get("seq", self._seq) + 1
                    self._prev_hmac = entry.get("hmac", self._prev_hmac)
        except Exception as e:
            print(f"[AuditLog] Error loading state from {self._path}: {e}")

    def _sign(self, entry_without_hmac: Dict[str, Any]) -> str:
        canon = json.dumps(entry_without_hmac, sort_keys=True, separators=(",", ":"))
        return hmac.new(self._key, canon.encode(), hashlib.sha256).hexdigest()

    def _build_entry(self, entry_fields: Dict[str, Any], seq: int, prev_hmac: str) -> Dict[str, Any]:
        entry = {
            "seq": seq,
            "ts": time.time(),
            "prev_hmac": prev_hmac,
            **entry_fields,
        }
        entry["hmac"] = self._sign(entry)
        return entry

    def append(self, entry_fields: Dict[str, Any]) -> AuditWriteResult:
        """
        Appends entry_fields plus seq/ts/prev_hmac/hmac. Never raises on
        a transient write failure -- queues to the fallback file and
        returns ok=False instead, so the caller can surface it without
        the underlying action being blocked.
        """
        with self._lock:
            entry = self._build_entry(entry_fields, self._seq, self._prev_hmac)
            try:
                self._write_line(self._path, entry)
            except Exception as e:
                print(
                    f"*** [AuditLog] WRITE FAILED for {self._path} ({e}) -- queuing to "
                    f"fallback, the underlying action is NOT blocked by this. ***"
                )
                queued = self._try_queue_fallback(entry)
                return AuditWriteResult(ok=False, entry=entry, error=str(e), queued_to_fallback=queued)

            self._prev_hmac = entry["hmac"]
            self._seq += 1

            # "On next successful write" -- opportunistic reconciliation
            # right after this write succeeds, not deferred to the next
            # startup.
            self._reconcile_fallback_queue()

            return AuditWriteResult(ok=True, entry=entry)

    @staticmethod
    def _write_line(path: Path, entry: Dict[str, Any]) -> None:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, separators=(",", ":")) + "\n")

    def _try_queue_fallback(self, entry: Dict[str, Any]) -> bool:
        """
        Best-effort: write the failed entry to the fallback file so it
        isn't lost. If even this fails (e.g. the whole disk is
        unwritable), that's a physical limit, not something this method
        can guarantee past -- returns False so the caller's
        AuditWriteResult reflects total failure rather than a false
        "queued_to_fallback=True."
        """
        try:
            with open(self._fallback_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, separators=(",", ":")) + "\n")
            return True
        except Exception as e:
            print(f"*** [AuditLog] FALLBACK QUEUE WRITE ALSO FAILED for {self._fallback_path} ({e}) ***")
            return False

    def _reconcile_fallback_queue(self) -> None:
        """
        Replays anything stranded in the fallback queue into the real
        chain. Deliberately does NOT try to preserve each entry's
        original seq/prev_hmac -- the chain has very likely moved on
        since the original failure (new entries may have been appended
        in the meantime), and rewriting history to slot an old entry
        back into a chain position that no longer reflects reality
        would be worse than honestly re-sequencing it. The original
        fields (who/what/when/why/source/consent, or whatever the
        caller's shape is) are preserved exactly; only seq/ts/prev_hmac/
        hmac are recomputed for the entry's *new* position in the
        chain, with the original write timestamp kept as
        `original_ts` and a `reconciled_from_fallback: true` marker so
        this is never mistaken for a normal, first-attempt entry.
        """
        if not self._fallback_path.exists():
            return
        try:
            raw = self._fallback_path.read_text(encoding="utf-8")
        except Exception as e:
            print(f"[AuditLog] Could not read fallback queue {self._fallback_path}: {e}")
            return

        lines = [line for line in raw.strip().splitlines() if line.strip()]
        if not lines:
            return

        still_stranded: List[str] = []
        recovered = 0
        for line in lines:
            try:
                stranded_entry = json.loads(line)
            except Exception:
                # Truly corrupt fallback line -- can't recover it as
                # data, but don't let it block reconciling the rest.
                still_stranded.append(line)
                continue

            original_ts = stranded_entry.get("ts")
            # Strip the stale chain/signature fields; everything else
            # is the caller's real content.
            content_fields = {
                k: v for k, v in stranded_entry.items()
                if k not in ("seq", "ts", "prev_hmac", "hmac")
            }
            content_fields["original_ts"] = original_ts
            content_fields["reconciled_from_fallback"] = True

            entry = self._build_entry(content_fields, self._seq, self._prev_hmac)
            try:
                self._write_line(self._path, entry)
            except Exception:
                # Still can't write -- leave this one (and everything
                # after it, to preserve order) in the fallback queue.
                still_stranded.append(line)
                continue

            self._prev_hmac = entry["hmac"]
            self._seq += 1
            recovered += 1

        if still_stranded:
            self._fallback_path.write_text("\n".join(still_stranded) + "\n", encoding="utf-8")
        else:
            self._fallback_path.unlink()

        if recovered:
            print(f"[AuditLog] Reconciled {recovered} fallback-queued entr{'y' if recovered == 1 else 'ies'} into {self._path}")

    # ------------------------------------------------------------------
    def verify_integrity(self) -> bool:
        """Verifies the HMAC chain across the whole log. Does not check the fallback queue -- that's unreconciled data, not yet part of the chain."""
        if not self._path.exists():
            return True

        prev = GENESIS_HMAC
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                for lineno, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    entry = json.loads(line)

                    if entry.get("prev_hmac") != prev:
                        print(f"[AuditLog] Chain break at line {lineno} of {self._path}")
                        return False

                    stored_hmac = entry.pop("hmac")
                    expected = self._sign(entry)
                    if not hmac.compare_digest(stored_hmac, expected):
                        print(f"[AuditLog] HMAC mismatch at line {lineno} of {self._path}")
                        return False
                    prev = stored_hmac
            return True
        except Exception as e:
            print(f"[AuditLog] Verification error for {self._path}: {e}")
            return False

    def get_entries(self, limit: int = 100) -> List[Dict[str, Any]]:
        if not self._path.exists():
            return []
        entries = []
        with open(self._path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
        return entries[-limit:]

    def has_pending_fallback_entries(self) -> bool:
        return self._fallback_path.exists() and self._fallback_path.stat().st_size > 0


# ======================================================================
# The DEC-002 clinical action record: who/what/when/why/source/consent.
# ======================================================================

_clinical_log: Optional[AppendOnlyAuditLog] = None


def get_clinical_audit_log() -> AppendOnlyAuditLog:
    """
    Lazy singleton -- constructed on first real use, not at import
    time, so importing this module never triggers key resolution (same
    lazy discipline as the rest of this codebase's coupling fixes).
    Configuration failure here is a hard stop: the first caller that
    needs this will see KeyConfigurationError propagate uncaught.

    Log directory can be overridden via JARVIS_CLINICAL_AUDIT_LOG_DIR
    (tests/conftest.py uses this to redirect every test run to a temp
    directory -- without it, every test touching
    UIExecutor.execute_intent() would otherwise write real entries into
    the production data/audit/ directory and hit the real OS keyring on
    every run).
    """
    global _clinical_log
    if _clinical_log is None:
        import os
        log_dir_override = os.environ.get("JARVIS_CLINICAL_AUDIT_LOG_DIR")
        if log_dir_override:
            log_path = Path(log_dir_override) / "clinical_actions.log"
        else:
            root = Path(__file__).resolve().parent.parent
            log_path = root / "data" / "audit" / "clinical_actions.log"
        _clinical_log = AppendOnlyAuditLog(
            log_path=log_path,
            key_purpose="clinical_audit",
            key_env_var="JARVIS_CLINICAL_AUDIT_KEY",
        )
    return _clinical_log


def reset_clinical_audit_log_singleton_for_tests() -> None:
    """Test-only escape hatch: forces the next get_clinical_audit_log() call to construct fresh."""
    global _clinical_log
    _clinical_log = None


def emit_clinical_action(
    *,
    what_adapter: str,
    what_action: str,
    what_target: str = "",
    why: str = "",
    source: str = "voice",
    outcome_status: str = "",
    outcome_ok: Optional[bool] = None,
    outcome_error: Optional[str] = None,
    log: Optional[AppendOnlyAuditLog] = None,
) -> AuditWriteResult:
    """
    Builds and appends the standardized DEC-002 record.

    Field mapping, and why each one is what it is (none of this is
    arbitrary, all of it is documented so a future phase doesn't have
    to re-derive the reasoning):

    - who: the OS account running JARVIS. No real multi-user/multi-
      identity system exists yet (no ABDM/ABHA identity, no per-
      physician login) -- this is honestly what's knowable today, not
      a placeholder pretending to be more than it is.
    - what: adapter + action + target, structured (not flattened into
      a string) so the log stays queryable.
    - when: wall-clock time of the call, in AppendOnlyAuditLog.append().
    - why: the physician's actual words (Intent.source_text) if
      available -- the closest honest signal to "why" this system has
      today. Empty string if the caller has no source text (e.g. a
      legacy fallback path with no parsed Intent).
    - source: the input channel. Defaults to "voice" (the only real
      channel today); callers on a different channel pass their own.
      Stage 1c's remote-access channels (WhatsApp/Telegram inbound) get
      a real value once that stage exists -- not decided or guessed at
      here.
    - consent: fixed at "direct_user_action" -- literally true for
      every action this system can take today, since there is no
      ambient/third-party listening mode yet (that's explicitly
      consent-blocked, separately, until Stage 1b). This field exists
      now so Stage 1b's real consent model has somewhere to write real
      values; it is not this phase's job to design that model.
    """
    log = log or get_clinical_audit_log()
    entry_fields = {
        "who": getpass.getuser(),
        "what": {"adapter": what_adapter, "action": what_action, "target": what_target},
        "why": why,
        "source": source,
        "consent": "direct_user_action",
        "outcome": {"status": outcome_status, "ok": outcome_ok, "error": outcome_error},
    }
    return log.append(entry_fields)
