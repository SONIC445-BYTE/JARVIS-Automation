"""
DEC-002: AgentCore/audit_trail.py -- AppendOnlyAuditLog (the generalized
engine) and emit_clinical_action() (the who/what/when/why/source/
consent record shape).

Two failure modes get two treatments, tested separately: configuration-
class (key resolution) is a hard stop at construction; transient write
failures during a session must never block the caller and must be
recoverable via the fallback queue.
"""
import base64
import json
import secrets
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from AgentCore.audit_trail import (
    AppendOnlyAuditLog,
    AuditWriteResult,
    emit_clinical_action,
    GENESIS_HMAC,
)
from AgentCore.secure_key import KeyConfigurationError


def _real_key_b64():
    return base64.b64encode(secrets.token_bytes(32)).decode()


class _WithRealKey:
    """
    Sets a real, valid JARVIS_TEST_AUDIT_KEY env var for the duration of
    the block. Also clears JARVIS_INSECURE_DEV_KEY -- the autouse
    conftest.py fixture that isolates the *clinical* audit log from
    tests sets this globally, which would otherwise collide with an
    explicit env-var key here as "ambiguous configuration" (see
    secure_key.resolve_key()'s deliberate refusal to pick one silently).
    """

    def __enter__(self):
        import os
        self._prior_key = os.environ.get("JARVIS_TEST_AUDIT_KEY")
        self._prior_dev = os.environ.get("JARVIS_INSECURE_DEV_KEY")
        os.environ["JARVIS_TEST_AUDIT_KEY"] = _real_key_b64()
        os.environ.pop("JARVIS_INSECURE_DEV_KEY", None)
        return self

    def __exit__(self, *a):
        import os
        if self._prior_key is None:
            os.environ.pop("JARVIS_TEST_AUDIT_KEY", None)
        else:
            os.environ["JARVIS_TEST_AUDIT_KEY"] = self._prior_key
        if self._prior_dev is not None:
            os.environ["JARVIS_INSECURE_DEV_KEY"] = self._prior_dev


class TestConfigurationClassFailure(unittest.TestCase):
    """Hard stop at construction -- matches D2, no insecure fallback."""

    def test_no_key_source_configured_and_keyring_fails_refuses_to_construct(self):
        with tempfile.TemporaryDirectory() as tmp:
            import os
            for v in ("JARVIS_TEST_AUDIT_KEY", "JARVIS_INSECURE_DEV_KEY"):
                os.environ.pop(v, None)
            with mock.patch("keyring.get_password", side_effect=RuntimeError("vault locked")):
                with self.assertRaises(KeyConfigurationError):
                    AppendOnlyAuditLog(
                        log_path=Path(tmp) / "test.log",
                        key_purpose="test_audit",
                        key_env_var="JARVIS_TEST_AUDIT_KEY",
                    )


class TestRealAppendAndChain(unittest.TestCase):
    def test_append_writes_a_real_verifiable_chain(self):
        with _WithRealKey(), tempfile.TemporaryDirectory() as tmp:
            log = AppendOnlyAuditLog(
                log_path=Path(tmp) / "test.log",
                key_purpose="test_audit",
                key_env_var="JARVIS_TEST_AUDIT_KEY",
            )
            r1 = log.append({"who": "alice", "what": "opened notepad"})
            r2 = log.append({"who": "alice", "what": "closed notepad"})

            self.assertTrue(r1.ok)
            self.assertTrue(r2.ok)
            self.assertEqual(r1.entry["seq"], 0)
            self.assertEqual(r2.entry["seq"], 1)
            self.assertEqual(r2.entry["prev_hmac"], r1.entry["hmac"])
            self.assertTrue(log.verify_integrity())

    def test_tampering_with_a_written_line_breaks_verification(self):
        with _WithRealKey(), tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "test.log"
            log = AppendOnlyAuditLog(log_path=log_path, key_purpose="test_audit", key_env_var="JARVIS_TEST_AUDIT_KEY")
            log.append({"who": "alice", "what": "did something"})

            # Tamper: rewrite the entry's "what" field without recomputing the hmac.
            lines = log_path.read_text(encoding="utf-8").strip().splitlines()
            entry = json.loads(lines[0])
            entry["what"] = "did something else entirely"
            log_path.write_text(json.dumps(entry) + "\n", encoding="utf-8")

            log2 = AppendOnlyAuditLog(log_path=log_path, key_purpose="test_audit", key_env_var="JARVIS_TEST_AUDIT_KEY")
            self.assertFalse(log2.verify_integrity())

    def test_resumes_the_chain_correctly_across_separate_instances(self):
        with _WithRealKey(), tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "test.log"
            log1 = AppendOnlyAuditLog(log_path=log_path, key_purpose="test_audit", key_env_var="JARVIS_TEST_AUDIT_KEY")
            log1.append({"who": "alice", "what": "first"})

            log2 = AppendOnlyAuditLog(log_path=log_path, key_purpose="test_audit", key_env_var="JARVIS_TEST_AUDIT_KEY")
            r2 = log2.append({"who": "alice", "what": "second"})

            self.assertEqual(r2.entry["seq"], 1)
            self.assertTrue(log2.verify_integrity())


class TestTransientWriteFailureNeverBlocksTheCaller(unittest.TestCase):
    def test_write_failure_returns_ok_false_but_does_not_raise(self):
        with _WithRealKey(), tempfile.TemporaryDirectory() as tmp:
            log = AppendOnlyAuditLog(log_path=Path(tmp) / "test.log", key_purpose="test_audit", key_env_var="JARVIS_TEST_AUDIT_KEY")
            with mock.patch.object(AppendOnlyAuditLog, "_write_line", side_effect=OSError("disk full")):
                result = log.append({"who": "alice", "what": "urgent action"})
            # Must not raise -- the caller (UIExecutor) gets a result object, never an exception.
            self.assertIsInstance(result, AuditWriteResult)
            self.assertFalse(result.ok)
            self.assertIsNotNone(result.error)

    def test_failed_write_is_queued_to_the_fallback_file_not_lost(self):
        with _WithRealKey(), tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "test.log"
            log = AppendOnlyAuditLog(log_path=log_path, key_purpose="test_audit", key_env_var="JARVIS_TEST_AUDIT_KEY")

            with mock.patch.object(AppendOnlyAuditLog, "_write_line", side_effect=OSError("disk full")):
                result = log.append({"who": "alice", "what": "urgent action"})

            self.assertTrue(result.queued_to_fallback)
            fallback_path = log_path.with_name("test.fallback_queue.jsonl")
            self.assertTrue(fallback_path.exists())
            queued = json.loads(fallback_path.read_text(encoding="utf-8").strip())
            self.assertEqual(queued["what"], "urgent action")

    def test_even_the_fallback_write_failing_still_does_not_raise(self):
        with _WithRealKey(), tempfile.TemporaryDirectory() as tmp:
            log = AppendOnlyAuditLog(log_path=Path(tmp) / "test.log", key_purpose="test_audit", key_env_var="JARVIS_TEST_AUDIT_KEY")
            with mock.patch.object(AppendOnlyAuditLog, "_write_line", side_effect=OSError("disk full")), \
                 mock.patch("builtins.open", side_effect=OSError("disk truly full")):
                # Both the real write AND the fallback queue write fail --
                # a physical limit, not something append() can guarantee
                # past, but it must still not raise or crash the caller.
                result = log.append({"who": "alice", "what": "urgent action"})
            self.assertFalse(result.ok)
            self.assertFalse(result.queued_to_fallback)


class TestFallbackQueueReconciliation(unittest.TestCase):
    def test_reconciles_on_next_successful_write(self):
        with _WithRealKey(), tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "test.log"
            log = AppendOnlyAuditLog(log_path=log_path, key_purpose="test_audit", key_env_var="JARVIS_TEST_AUDIT_KEY")

            with mock.patch.object(AppendOnlyAuditLog, "_write_line", side_effect=OSError("disk full")):
                log.append({"who": "alice", "what": "stranded action"})

            fallback_path = log_path.with_name("test.fallback_queue.jsonl")
            self.assertTrue(fallback_path.exists())

            # Next successful write should reconcile the stranded entry too.
            log.append({"who": "alice", "what": "normal action"})

            self.assertFalse(fallback_path.exists())
            entries = log.get_entries(limit=10)
            whats = [e["what"] for e in entries]
            self.assertIn("stranded action", whats)
            self.assertIn("normal action", whats)
            reconciled = next(e for e in entries if e["what"] == "stranded action")
            self.assertTrue(reconciled["reconciled_from_fallback"])
            self.assertIn("original_ts", reconciled)
            self.assertTrue(log.verify_integrity())

    def test_reconciles_at_startup_of_a_fresh_instance(self):
        with _WithRealKey(), tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "test.log"
            log1 = AppendOnlyAuditLog(log_path=log_path, key_purpose="test_audit", key_env_var="JARVIS_TEST_AUDIT_KEY")
            with mock.patch.object(AppendOnlyAuditLog, "_write_line", side_effect=OSError("disk full")):
                log1.append({"who": "alice", "what": "stranded before restart"})

            fallback_path = log_path.with_name("test.fallback_queue.jsonl")
            self.assertTrue(fallback_path.exists())

            # Fresh instance (simulating a restart) -- reconciliation
            # happens in __init__, before any new append() is even called.
            log2 = AppendOnlyAuditLog(log_path=log_path, key_purpose="test_audit", key_env_var="JARVIS_TEST_AUDIT_KEY")
            self.assertFalse(fallback_path.exists())
            entries = log2.get_entries(limit=10)
            self.assertEqual(entries[0]["what"], "stranded before restart")
            self.assertTrue(entries[0]["reconciled_from_fallback"])
            self.assertTrue(log2.verify_integrity())

    def test_has_pending_fallback_entries_reports_correctly(self):
        with _WithRealKey(), tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "test.log"
            log = AppendOnlyAuditLog(log_path=log_path, key_purpose="test_audit", key_env_var="JARVIS_TEST_AUDIT_KEY")
            self.assertFalse(log.has_pending_fallback_entries())

            with mock.patch.object(AppendOnlyAuditLog, "_write_line", side_effect=OSError("disk full")):
                log.append({"who": "alice", "what": "stranded"})
            self.assertTrue(log.has_pending_fallback_entries())


class TestEmitClinicalAction(unittest.TestCase):
    def test_builds_the_standardized_who_what_when_why_source_consent_shape(self):
        with _WithRealKey(), tempfile.TemporaryDirectory() as tmp:
            log = AppendOnlyAuditLog(log_path=Path(tmp) / "clinical.log", key_purpose="test_audit", key_env_var="JARVIS_TEST_AUDIT_KEY")
            result = emit_clinical_action(
                what_adapter="whatsapp_desktop",
                what_action="send_message",
                what_target="mom",
                why="send whatsapp message to mom saying hello",
                source="voice",
                outcome_status="success",
                outcome_ok=True,
                log=log,
            )

            self.assertTrue(result.ok)
            entry = result.entry
            for field in ("who", "what", "when" if "when" in entry else "ts", "why", "source", "consent", "outcome"):
                pass  # placeholder, real assertions below
            self.assertIn("who", entry)
            self.assertEqual(entry["what"], {"adapter": "whatsapp_desktop", "action": "send_message", "target": "mom"})
            self.assertIn("ts", entry)  # "when"
            self.assertEqual(entry["why"], "send whatsapp message to mom saying hello")
            self.assertEqual(entry["source"], "voice")
            self.assertEqual(entry["consent"], "direct_user_action")
            self.assertEqual(entry["outcome"], {"status": "success", "ok": True, "error": None})

    def test_who_is_the_real_os_user(self):
        import getpass
        with _WithRealKey(), tempfile.TemporaryDirectory() as tmp:
            log = AppendOnlyAuditLog(log_path=Path(tmp) / "clinical.log", key_purpose="test_audit", key_env_var="JARVIS_TEST_AUDIT_KEY")
            result = emit_clinical_action(what_adapter="x", what_action="y", log=log)
            self.assertEqual(result.entry["who"], getpass.getuser())


if __name__ == "__main__":
    unittest.main()
