import json
import time
from pathlib import Path

from daemon.config import DaemonConfig
from daemon.service import JarvisDaemon


def test_wakeword_to_dispatch_dry_run_pipeline(tmp_path: Path):
    log_path = tmp_path / "jarvis_actions.log"
    config = DaemonConfig(
        dry_run=True,
        allow_destructive=False,
        action_log_path=log_path,
        pid_file=tmp_path / "jarvis.pid",
    )
    daemon = JarvisDaemon(config=config)
    daemon.start()

    start = time.perf_counter()
    daemon.receive_transcript("jarvis")
    result = daemon.receive_transcript("send hello world to alice on whatsapp")
    latency_ms = (time.perf_counter() - start) * 1000
    daemon.stop()

    assert result is not None
    assert result.ok is True
    # Keep CI tolerant while tracking responsiveness target.
    assert latency_ms < 1500

    lines = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    actions = [line["action"] for line in lines]
    assert "wakeword_detected" in actions
    assert "send_message" in actions
    assert "return_to_standby" in actions
