# J.A.R.V.I.S - Just A Rather Very Intelligent System

J.A.R.V.I.S is a local-first assistant project. This repository now includes a GUI-automation daemon stack that supports wake-word standby, transcript-driven command dispatch, dry-run safety, and structured action logs.

## Installation
1. `pip install -r requirements.txt`
2. Optional for tests: `pip install pytest`

## Existing Runtime
- Main app: `python jarvis.py`
- Existing service modes remain available in `jarvis.py` (`--service`, `--convo`, etc.)

## New Automation Daemon
The daemon implementation is additive and does not replace existing flows.

- Start: `python -m daemon.cli start`
- Stop: `python -m daemon.cli stop`
- Status: `python -m daemon.cli status`
- One-shot dry-run check: `python -m daemon.cli dry-run`
- Foreground service loop: `python -m daemon.cli run-loop`

### Wake-Word and Transcript Flow
- Standby wake-word logic is in `daemon/service.py`.
- Default wake word: `JARVIS` (configurable with `JARVIS_WAKE_WORD`).
- After wake-word detection, the next transcript is parsed and dispatched.

### STT Integration (Non-Invasive)
Use `stt_integration.py` to subscribe to existing STT transcript events:

```python
from daemon import DaemonConfig, JarvisDaemon
from stt_integration import wire_to_existing_stt

daemon = JarvisDaemon(DaemonConfig.from_env(dry_run=True))
daemon.start()
wire_to_existing_stt(existing_stt_source, daemon)
```

If preferred, call `daemon.receive_transcript(text)` directly from the STT pipeline callback.

## Canonical Root Platform Adapters
The canonical adapter package for this upgrade is `platform_adapters/`:
- `platform_adapters/adapter_base.py`
- `platform_adapters/browser_adapter.py`
- `platform_adapters/text_editor_adapter.py`
- `platform_adapters/whatsapp_desktop_adapter.py`
- `platform_adapters/telegram_desktop_adapter.py`
- `platform_adapters/gmail_browser_adapter.py`

Adapter interface methods:
- `open_app()`
- `close_app()`
- `send_message(target, message)`
- `read_unread(limit=10)`

## Logs and Action History
- Structured action history is written to `logs/jarvis_actions.log` (JSON lines).
- Event keys: `timestamp`, `action`, `target`, `result`, `dry_run_flag`, `meta`.

## Dry-Run / Safe Mode
- Dry-run is supported end-to-end and required for tests.
- In dry-run mode, actions are logged but GUI automation calls are not executed.

## Safety Flags
- `ALLOW_DESTRUCTIVE=false` by default.
- High-risk commands (delete, format, erase, wipe, run script, shutdown) are blocked unless `ALLOW_DESTRUCTIVE=true`.
- Upgrade flag: `feature_flags/AUTOMATION_UPGRADE_V1.yaml`.

## Startup Installation
- Linux installer: `tools/installer.sh`
- Windows installer: `tools/installer.ps1`
- Linux systemd example: `tools/systemd/jarvis-automation-daemon.service`
- macOS LaunchAgent example: `tools/macos/com.jarvis.automation.plist`
- Windows service wrapper example: `tools/windows/service_wrapper_example.ps1`

Installers create rollback scripts:
- Linux: `tools/rollback.sh`
- Windows: `tools/rollback.ps1`

## Testing
- Baseline tests: `PYTHONPATH=. pytest -q tests -p no:cacheprovider`
- New automation upgrade tests: `PYTHONPATH=. pytest -q tests/automation_upgrade -p no:cacheprovider`

## Automation Verifier (JSON Audit)
- Run strict audit JSON: `PYTHONPATH=. python tools/automation_verifier.py --output logs/automation_verifier_report.json`
- Run audit + scaffold missing adapters: `PYTHONPATH=. python tools/automation_verifier.py --autofix --output logs/automation_verifier_report_autofix.json`
- Generated scaffolds (when needed): `platform_adapters/generated/`

## Rollback Steps
1. Stop daemon: `python -m daemon.cli stop`
2. Run rollback:
   - Linux: `bash tools/rollback.sh`
   - Windows: `powershell -ExecutionPolicy Bypass -File tools/rollback.ps1`
3. Remove startup registration if manually installed.

## License
MIT (see `LICENSE`).
