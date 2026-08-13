"""
Shared fixtures for AgentCore/comm_gateway/tests/.

Isolation built correctly the first time here, learning from two prior
mistakes THIS session: DEC-002's fixture originally used
JARVIS_INSECURE_DEV_KEY, which writes a real key file into the real repo
(data/dev_keys/) with no tmp_path awareness -- caught only after real key
files were found sitting in the repo. And D14's own first-draft test
redirected UIAudit.log_dir AFTER construction, too late, because
__init__ had already mkdir'd the real path -- the isolation test was
itself creating the directory it existed to avoid. Both mistakes are the
same shape: redirect BEFORE construction, via an explicit env var with a
real generated key, never the dev-key-file path.
"""
import base64
import secrets

import pytest

from AgentCore.comm_gateway import audit as gw_audit


@pytest.fixture(autouse=True)
def _isolate_comm_gateway_audit_log(tmp_path, monkeypatch):
    monkeypatch.setenv(gw_audit.LOG_DIR_ENV_VAR, str(tmp_path / "comm_gateway"))
    monkeypatch.setenv(gw_audit.KEY_ENV_VAR, base64.b64encode(secrets.token_bytes(32)).decode())
    monkeypatch.setenv("JARVIS_COMM_GATEWAY_PAIRING_KEY", base64.b64encode(secrets.token_bytes(32)).decode())
    monkeypatch.delenv("JARVIS_INSECURE_DEV_KEY", raising=False)
    gw_audit.reset_gateway_audit_log_singleton_for_tests()
    yield
    gw_audit.reset_gateway_audit_log_singleton_for_tests()
