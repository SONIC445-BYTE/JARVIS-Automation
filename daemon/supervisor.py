from __future__ import annotations

import os
import signal
import subprocess
import sys
from pathlib import Path

from daemon.config import DaemonConfig


def _is_running(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _read_pid(pid_file: Path) -> int:
    if not pid_file.exists():
        return 0
    try:
        return int(pid_file.read_text(encoding="utf-8").strip())
    except ValueError:
        return 0


def start_daemon(config: DaemonConfig) -> str:
    config.ensure_paths()
    existing = _read_pid(config.pid_file)
    if _is_running(existing):
        return f"already_running:{existing}"

    cmd = [sys.executable, "-m", "daemon.cli", "run-loop"]
    if config.dry_run:
        cmd.append("--dry-run")
    kwargs = {}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
    process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **kwargs)
    config.pid_file.write_text(str(process.pid), encoding="utf-8")
    return f"started:{process.pid}"


def stop_daemon(config: DaemonConfig) -> str:
    pid = _read_pid(config.pid_file)
    if not _is_running(pid):
        if config.pid_file.exists():
            config.pid_file.unlink()
        return "not_running"

    sig = signal.SIGTERM
    os.kill(pid, sig)
    try:
        config.pid_file.unlink()
    except FileNotFoundError:
        pass
    return f"stopped:{pid}"


def status_daemon(config: DaemonConfig) -> str:
    pid = _read_pid(config.pid_file)
    if _is_running(pid):
        return f"running:{pid}"
    return "stopped"
