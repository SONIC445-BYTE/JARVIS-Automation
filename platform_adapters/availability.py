"""
Phase 2c: AvailabilityChecker.

Enumerates installed applications on this machine -- registry uninstall
keys plus AppX/Store packages, both read-only, the same method used ad
hoc in Phase 2b step 5 -- and answers "is this platform installed?" by
matching declared aliases against installed display names. Cached at
construction; call refresh() to re-enumerate (no periodic refresh yet,
per Phase 2c scope -- startup-time enumeration is sufficient today).
"""
from __future__ import annotations

import subprocess
from typing import List, Optional

_REGISTRY_SCRIPT = (
    "$paths = @("
    "'HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*',"
    "'HKLM:\\SOFTWARE\\WOW6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*',"
    "'HKCU:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*'"
    ");"
    "Get-ItemProperty $paths -ErrorAction SilentlyContinue | "
    "Where-Object { $_.DisplayName -and $_.DisplayName.Trim() -ne '' } | "
    "Select-Object -ExpandProperty DisplayName -Unique"
)

_APPX_SCRIPT = "Get-AppxPackage | Select-Object -ExpandProperty Name -Unique"


class AvailabilityChecker:
    def __init__(self, installed_apps: Optional[List[str]] = None):
        """installed_apps: inject a pre-enumerated list (for tests, or a
        different machine's data). When None, enumerates this machine."""
        self._installed_lower: List[str] = []
        if installed_apps is not None:
            self._installed_lower = [a.lower() for a in installed_apps]
        else:
            self.refresh()

    def refresh(self) -> None:
        apps = _run_powershell(_REGISTRY_SCRIPT) + _run_powershell(_APPX_SCRIPT)
        self._installed_lower = [a.lower() for a in apps]

    def is_installed(self, aliases: List[str]) -> bool:
        """True if any alias appears as a substring of any installed
        app's display name (case-insensitive)."""
        for alias in aliases:
            alias_lower = alias.lower()
            if not alias_lower:
                continue
            for app in self._installed_lower:
                if alias_lower in app:
                    return True
        return False


def _run_powershell(script: str) -> List[str]:
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return []
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]
    except Exception:
        return []
