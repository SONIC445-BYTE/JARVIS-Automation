"""
Phase 2c: winget install execution.

A thin, mockable wrapper around `winget install`. Never called without
explicit user confirmation -- see AgentCore/resolution_gate.py and the
pending-install flow in jarvis.py.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass


@dataclass
class InstallResult:
    ok: bool
    message: str


def install(package_id: str, source: str, timeout_s: float = 300.0) -> InstallResult:
    """Run `winget install` for a specific, already-known-valid package id.
    Returns InstallResult with a human-readable message either way -- never
    raises, never silently no-ops."""
    try:
        proc = subprocess.run(
            [
                "winget",
                "install",
                "--id",
                package_id,
                "--source",
                source,
                "-e",
                "--silent",
                "--accept-package-agreements",
                "--accept-source-agreements",
            ],
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
        if proc.returncode == 0:
            return InstallResult(ok=True, message=f"Installed {package_id} successfully.")
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        detail_msg = detail[-1] if detail else f"exit code {proc.returncode}"
        return InstallResult(ok=False, message=f"Install failed: {detail_msg}")
    except subprocess.TimeoutExpired:
        return InstallResult(ok=False, message=f"Install of {package_id} timed out after {timeout_s:.0f}s.")
    except FileNotFoundError:
        return InstallResult(ok=False, message="winget is not available on this machine.")
    except Exception as e:
        return InstallResult(ok=False, message=f"Install failed: {e}")
