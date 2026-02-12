from __future__ import annotations

import argparse
import importlib
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


REPO_ROOT = Path(__file__).resolve().parent.parent
ROOT_ADAPTERS = REPO_ROOT / "platform_adapters"
AGENTCORE_ADAPTERS = REPO_ROOT / "AgentCore" / "platform_adapters"
GENERATED_ADAPTERS = ROOT_ADAPTERS / "generated"

SYSTEM_PROCESS_PATTERNS = (
    "system",
    "registry",
    "smss",
    "csrss",
    "wininit",
    "winlogon",
    "svchost",
    "services",
    "lsass",
    "dwm",
    "runtimebroker",
    "fontdrvhost",
    "sihost",
    "taskhostw",
    "searchhost",
    "applicationframehost",
    "startmenuexperiencehost",
    "securityhealthservice",
    "ctfmon",
    "spoolsv",
)

UI_NOISE_TITLES = {
    "restore pages?",
    "program manager",
    "search bar",
    "settings",
}

ACTIONABLE_HINTS = (
    "chrome",
    "brave",
    "edge",
    "firefox",
    "code",
    "vscode",
    "whatsapp",
    "telegram",
    "gmail",
    "notepad",
    "editor",
    "slack",
    "discord",
    "teams",
    "outlook",
    "explorer",
)


@dataclass
class PlatformObservation:
    platform_key: str
    visible_name: str
    platform_type: str
    process_or_package: str
    source: str


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def detect_visible_windows() -> List[Tuple[str, str]]:
    windows: List[Tuple[str, str]] = []
    try:
        import pyautogui  # type: ignore

        for win in pyautogui.getAllWindows():
            title = (getattr(win, "title", "") or "").strip()
            if title and not is_noise_window(title):
                windows.append((title, "window"))
    except Exception:
        pass
    return windows


def detect_running_processes() -> List[str]:
    names: List[str] = []
    try:
        import psutil  # type: ignore

        for proc in psutil.process_iter(attrs=["name"]):
            name = (proc.info.get("name") or "").strip()
            if name and not is_system_process(name):
                names.append(name)
    except Exception:
        pass
    return names


def infer_platform_type(name: str) -> str:
    lower = name.lower()
    if "chrome" in lower or "firefox" in lower or "edge" in lower or "browser" in lower:
        return "web"
    if "terminal" in lower or "powershell" in lower or "cmd" in lower:
        return "terminal"
    if "android" in lower:
        return "android"
    if "ios" in lower:
        return "ios"
    if "vmware" in lower or "virtualbox" in lower:
        return "vm"
    if "electron" in lower or "slack" in lower or "discord" in lower:
        return "electron"
    return "native"


def normalize_platform_key(name: str) -> str:
    key = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return key or "unknown"


def is_system_process(name: str) -> bool:
    lower = name.lower().replace(".exe", "").strip()
    return any(lower.startswith(p) for p in SYSTEM_PROCESS_PATTERNS)


def is_noise_window(title: str) -> bool:
    lower = title.lower().strip()
    if lower in UI_NOISE_TITLES:
        return True
    if len(lower) < 3:
        return True
    return False


def is_actionable_name(name: str) -> bool:
    lower = name.lower()
    return any(hint in lower for hint in ACTIONABLE_HINTS)


def discover_platforms() -> List[PlatformObservation]:
    out: Dict[str, PlatformObservation] = {}

    for title, source in detect_visible_windows():
        if not is_actionable_name(title):
            continue
        key = normalize_platform_key(title.split("-")[0].strip())
        out[key] = PlatformObservation(
            platform_key=key,
            visible_name=title,
            platform_type=infer_platform_type(title),
            process_or_package="unknown_process",
            source=source,
        )

    for proc_name in detect_running_processes():
        if not is_actionable_name(proc_name):
            continue
        key = normalize_platform_key(proc_name.replace(".exe", ""))
        if key in out:
            if out[key].process_or_package == "unknown_process":
                out[key].process_or_package = proc_name
            continue
        out[key] = PlatformObservation(
            platform_key=key,
            visible_name=proc_name,
            platform_type=infer_platform_type(proc_name),
            process_or_package=proc_name,
            source="process_scan",
        )

    return list(out.values())


def scan_adapter_catalog() -> Tuple[Set[str], Dict[str, str]]:
    keys: Set[str] = set()
    names: Dict[str, str] = {}

    if ROOT_ADAPTERS.exists():
        for py_file in ROOT_ADAPTERS.glob("*_adapter.py"):
            key = py_file.stem.replace("_adapter", "")
            keys.add(key)
            names[key] = py_file.stem

    if AGENTCORE_ADAPTERS.exists():
        for folder in AGENTCORE_ADAPTERS.iterdir():
            if not folder.is_dir():
                continue
            if (folder / "adapter.py").exists():
                key = normalize_platform_key(folder.name)
                keys.add(key)
                names.setdefault(key, f"AgentCore.{folder.name}.adapter")
    return keys, names


def probe_required_methods(adapter_key: str, adapter_name: Optional[str]) -> Tuple[bool, List[Dict[str, str]]]:
    evidence: List[Dict[str, str]] = []
    if not adapter_name:
        return False, evidence

    if adapter_name.startswith("AgentCore."):
        evidence.append({"kind": "cli_command", "value": f"ls AgentCore/platform_adapters/{adapter_key}/adapter.py"})
        return True, evidence

    module_name = f"platform_adapters.{adapter_name}"
    try:
        mod = importlib.import_module(module_name)
        required = ["open_app", "close_app", "send_message", "read_unread"]
        ok = True
        for r in required:
            if not any(callable(getattr(obj, r, None)) for obj in mod.__dict__.values() if isinstance(obj, type)):
                ok = False
        evidence.append({"kind": "cli_command", "value": f"python -c \"import {module_name}\""})
        return ok, evidence
    except Exception:
        return False, evidence


def confidence_from_evidence(items: List[Dict[str, str]], automatable: str) -> int:
    kinds = {item["kind"] for item in items}
    score = 0
    if "process" in kinds:
        score += 35
    if "accessibility_node" in kinds:
        score += 35
    if "dom_selector" in kinds:
        score += 25
    if "api_endpoint" in kinds:
        score += 20
    if "cli_command" in kinds:
        score += 10
    if automatable == "none":
        return min(score, 50)
    if automatable == "partial":
        return min(max(score, 55), 90)
    return min(max(score, 80), 100)


def minimal_adapter_scaffold(platform_key: str) -> str:
    class_name = "".join(part.capitalize() for part in platform_key.split("_")) + "Adapter"
    return f"""from typing import Any, Dict, List
from platform_adapters.adapter_base import AdapterBase


class {class_name}(AdapterBase):
    def open_app(self) -> bool:
        self.log_action("open_app", {{"target": "{platform_key}", "dry_run": self.dry_run}})
        return True

    def close_app(self) -> bool:
        self.log_action("close_app", {{"target": "{platform_key}", "dry_run": self.dry_run}})
        return True

    def send_message(self, target: str, message: str) -> bool:
        self.log_action("send_message", {{"target": target, "message": message, "dry_run": self.dry_run}})
        return True

    def read_unread(self, limit: int = 10) -> List[Dict[str, Any]]:
        self.log_action("read_unread", {{"target": "{platform_key}", "limit": limit, "dry_run": self.dry_run}})
        return []
"""


def safe_scaffold_key(platform_key: str) -> str:
    cleaned = re.sub(r"[^a-z0-9_]+", "_", platform_key.lower()).strip("_")
    if not cleaned:
        cleaned = "unknown_platform"
    return cleaned[:48]


def create_missing_adapter(platform_key: str) -> str:
    GENERATED_ADAPTERS.mkdir(parents=True, exist_ok=True)
    init_path = GENERATED_ADAPTERS / "__init__.py"
    if not init_path.exists():
        init_path.write_text("", encoding="utf-8")
    safe_key = safe_scaffold_key(platform_key)
    path = GENERATED_ADAPTERS / f"{safe_key}_adapter.py"
    if not path.exists():
        path.write_text(minimal_adapter_scaffold(safe_key), encoding="utf-8")
    return str(path.relative_to(REPO_ROOT))


def evaluate_platforms(platforms: List[PlatformObservation], autofix: bool) -> Dict[str, Any]:
    adapter_keys, adapter_names = scan_adapter_catalog()
    out_platforms: List[Dict[str, Any]] = []

    for idx, p in enumerate(platforms, start=1):
        base_key = p.platform_key
        adapter_key = base_key
        in_adapter = adapter_key in adapter_keys
        adapter_name = adapter_names.get(adapter_key)

        evidence_items: List[Dict[str, str]] = []
        if p.process_or_package and p.process_or_package != "unknown_process":
            evidence_items.append({"kind": "process", "value": p.process_or_package})

        if p.platform_type == "web":
            evidence_items.append({"kind": "dom_selector", "value": "document.querySelector('body')"})
            evidence_items.append({"kind": "cli_command", "value": "python -m playwright codegen <url>"})
        elif p.platform_type in {"native", "electron"}:
            evidence_items.append({"kind": "accessibility_node", "value": "root/window/control (probe required)"})
            evidence_items.append({"kind": "cli_command", "value": "Inspect.exe or pywinauto print_control_identifiers()"})
        elif p.platform_type == "android":
            evidence_items.append({"kind": "cli_command", "value": "adb shell uiautomator dump /sdcard/uidump.xml && adb pull /sdcard/uidump.xml"})
        elif p.platform_type == "ios":
            evidence_items.append({"kind": "cli_command", "value": "xcrun simctl io booted screenshot screen.png"})
        elif p.platform_type == "terminal":
            evidence_items.append({"kind": "cli_command", "value": "where <command> (Windows) or command -v <command>"})

        method_ok, method_evidence = probe_required_methods(adapter_key, adapter_name)
        evidence_items.extend(method_evidence)

        if in_adapter and method_ok:
            automation_possible = "full"
            required_changes = "none"
            next_actions = ["Run adapter-specific end-to-end dry-run in daemon pipeline"]
        elif in_adapter:
            automation_possible = "partial"
            required_changes = "Adapter exists but missing required methods or importability checks; align to AdapterBase contract"
            next_actions = ["Patch adapter to implement open_app/close_app/send_message/read_unread"]
        else:
            automation_possible = "none"
            required_changes = "Create adapter scaffold and wire to dispatcher/registry"
            next_actions = ["Generate scaffold adapter", "Add dry-run integration test"]

        if automation_possible == "none" and autofix:
            scaffold_rel = create_missing_adapter(adapter_key)
            required_changes = f"Scaffold generated at {scaffold_rel}; implement UI selectors and verification logic"
            next_actions = ["Implement selectors", "Add platform-specific tests", "Register in platform_adapters/registry.py"]

        verification_steps = [
            f"Confirm process/package: {p.process_or_package or 'unknown'}",
            f"Validate platform type probe: {p.platform_type}",
            "Run listed CLI evidence commands and save outputs",
            "Execute daemon dry-run transcript flow and inspect logs/jarvis_actions.log",
        ]

        confidence = confidence_from_evidence(evidence_items, automation_possible)

        out_platforms.append(
            {
                "id": f"p-{idx}",
                "visible_name": p.visible_name,
                "type": p.platform_type,
                "process_or_package": p.process_or_package,
                "in_platforms_adapter": in_adapter,
                "adapter_name": adapter_name if in_adapter else None,
                "automation_possible": automation_possible,
                "confidence": confidence,
                "evidence": {"evidence_items": evidence_items},
                "verification_steps": verification_steps,
                "required_adapter_changes": required_changes,
                "next_actions": next_actions,
            }
        )

    summary = {
        "total_visible": len(out_platforms),
        "automatable_full": sum(1 for p in out_platforms if p["automation_possible"] == "full"),
        "automatable_partial": sum(1 for p in out_platforms if p["automation_possible"] == "partial"),
        "not_automatable": sum(1 for p in out_platforms if p["automation_possible"] == "none"),
    }
    return {"platforms": out_platforms, "summary": summary}


def build_report(screen_capture_id: Optional[str], autofix: bool) -> Dict[str, Any]:
    discovered = discover_platforms()
    evaluated = evaluate_platforms(discovered, autofix=autofix)
    return {
        "timestamp": utc_now_iso(),
        "screen_capture_id": screen_capture_id or "",
        "platforms": evaluated["platforms"],
        "summary": evaluated["summary"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="JARVIS strict automation verifier")
    parser.add_argument("--screen-capture-id", default="", help="Optional screenshot id/hash")
    parser.add_argument("--autofix", action="store_true", help="Create missing adapter scaffolds")
    parser.add_argument("--output", default="", help="Write JSON report to file")
    args = parser.parse_args()

    report = build_report(screen_capture_id=args.screen_capture_id, autofix=args.autofix)
    payload = json.dumps(report, ensure_ascii=True, indent=2)
    print(payload)
    if args.output:
        Path(args.output).write_text(payload + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
