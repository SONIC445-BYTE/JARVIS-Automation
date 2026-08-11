"""
Shared pytest fixtures for tests/.

autouse cleanup for the repo-root state/ directory: most tests that
touch onboarding.py's persistence explicitly patch STATE_DIR to a temp
directory, but jarvis.py's conversation-loop methods (_handle_resume,
_handle_install_confirmation, the dispatch-loop branches) call
onboarding.persist_pending_state()/clear_pending_state() directly, and
several pre-existing tests in tests/test_pending_resume_flow.py and
tests/test_install_confirmation_flow.py exercise those methods for real
without mocking those specific calls (they predate the persistence
hooks and test other things). Rather than adding mocks to every one of
those call sites, this fixture guarantees the real state/ directory
never survives a test run, regardless of which test wrote to it.
"""
import os
import shutil
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _clean_state_dir_after_test():
    state_existed_before = Path("state").exists()
    yield
    if not state_existed_before and Path("state").exists():
        shutil.rmtree("state", ignore_errors=True)


@pytest.fixture(autouse=True)
def _isolate_clinical_audit_log(tmp_path, monkeypatch):
    """
    DEC-002: UIExecutor.execute_intent() (the single pre-adapter
    chokepoint) now calls AgentCore.audit_trail.get_clinical_audit_log()
    on every call. Without this fixture, every test that touches
    execute_intent() -- directly or via ODAVLoop/CommandRouter -- would
    hit the real OS keyring (slow, and leaves a real credential-store
    entry behind) and write real entries into the production
    data/audit/ directory on every test run. Redirects the log dir to a
    per-test temp location and forces the module-level singleton to
    rebuild, so no state leaks between tests.

    Key resolution is redirected the same way tests/test_audit_trail.py's
    _WithRealKey() does it: an explicit, purpose-specific env-var key
    (JARVIS_CLINICAL_AUDIT_KEY), not JARVIS_INSECURE_DEV_KEY=1. An
    earlier version of this fixture used the dev-key-file path instead --
    caught by reading secure_key.py's _dev_file_key(), which writes to a
    fixed, non-overridable directory (repo_root/data/dev_keys/) with no
    tmp_path awareness at all. That meant every test run touching this
    fixture was writing a real key file into the actual repo on disk,
    every single time -- not test data, a real (if dev-marked) credential
    landing outside any sandbox. Confirmed by finding clinical_audit.key
    and learning_audit.key already sitting in the real data/dev_keys/
    after a routine test run. The explicit-env-var path never touches
    disk for the key at all.
    """
    import base64
    import secrets

    import AgentCore.audit_trail as audit_trail_module

    monkeypatch.setenv("JARVIS_CLINICAL_AUDIT_LOG_DIR", str(tmp_path / "audit"))
    monkeypatch.setenv("JARVIS_CLINICAL_AUDIT_KEY", base64.b64encode(secrets.token_bytes(32)).decode())
    monkeypatch.delenv("JARVIS_INSECURE_DEV_KEY", raising=False)
    audit_trail_module.reset_clinical_audit_log_singleton_for_tests()
    yield
    audit_trail_module.reset_clinical_audit_log_singleton_for_tests()
