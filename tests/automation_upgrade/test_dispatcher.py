from pathlib import Path
from unittest.mock import MagicMock

from daemon.config import DaemonConfig
from daemon.dispatcher import CommandDispatcher
from daemon.intent_parser import Intent
from daemon.logging_utils import ActionLogger


class DummyAdapter:
    def __init__(self):
        self.sent = []

    def open_app(self):
        return True

    def close_app(self):
        return True

    def send_message(self, target, message):
        self.sent.append((target, message))
        return True

    def read_unread(self, limit=10):
        return []


def test_dispatcher_blocks_destructive_when_flag_off(tmp_path: Path):
    config = DaemonConfig(dry_run=True, allow_destructive=False, action_log_path=tmp_path / "actions.log")
    config.ensure_paths()
    logger = ActionLogger(config.action_log_path)
    dispatcher = CommandDispatcher(logger=logger, config=config, adapters={})

    result = dispatcher.dispatch(
        Intent(adapter="system", action="dangerous_command", target="system", message="delete all", destructive=True)
    )

    assert result.ok is False
    assert "ALLOW_DESTRUCTIVE=false" in result.reason
    contents = (tmp_path / "actions.log").read_text(encoding="utf-8")
    assert "blocked_destructive" in contents


def test_dispatcher_routes_send_message(tmp_path: Path):
    adapter = DummyAdapter()
    config = DaemonConfig(dry_run=True, allow_destructive=False, action_log_path=tmp_path / "actions.log")
    config.ensure_paths()
    logger = ActionLogger(config.action_log_path)
    dispatcher = CommandDispatcher(logger=logger, config=config, adapters={"text_editor": adapter})

    result = dispatcher.dispatch(Intent(adapter="text_editor", action="send_message", target="bob", message="hello"))

    assert result.ok is True
    assert adapter.sent == [("bob", "hello")]
