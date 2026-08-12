"""
Shared pytest fixtures for AgentCore/ui_agent/tests/.

Mirrors the isolation `tests/conftest.py` already does for DEC-002's
clinical audit log, applied to the UI action log. Same problem, same
shape of fix, different subsystem.
"""
import base64
import secrets

import pytest

from AgentCore.ui_agent.utils import ui_audit


@pytest.fixture(autouse=True)
def _isolate_ui_action_log(tmp_path, monkeypatch):
    """
    UIAudit's log directory was hardcoded to data/ui_actions/, and
    UIAudit.__init__ mkdir's it eagerly -- so every test that constructs
    a real UIAgentMain (test_agent_smoke.py, test_ui_fallback_unknown_app.py)
    created and wrote into the real repo's directory on every run.
    Confirmed by finding real dated audit_*.jsonl files sitting there.

    Also pins a real UI-audit key, for the same reason tests/conftest.py
    pins JARVIS_CLINICAL_AUDIT_KEY: D14's fix made UIAudit resolve its
    HMAC key fail-closed, which means every test constructing one would
    otherwise hit the real OS keyring (slow, and leaves a real
    credential-store entry behind). An explicit env-var key never
    touches disk or the keyring -- deliberately not JARVIS_INSECURE_DEV_KEY,
    whose file path is fixed and not tmp_path-aware (that mistake was
    made once already during DEC-002 and caught by finding real key
    files in the repo).
    """
    monkeypatch.setenv(ui_audit.LOG_DIR_ENV_VAR, str(tmp_path / "ui_actions"))
    monkeypatch.setenv("JARVIS_UI_AUDIT_KEY", base64.b64encode(secrets.token_bytes(32)).decode())
    monkeypatch.delenv("JARVIS_INSECURE_DEV_KEY", raising=False)
    yield
