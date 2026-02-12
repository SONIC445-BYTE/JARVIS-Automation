# GitHub Copilot Instructions — J.A.R.V.I.S.

This file gives focused, actionable guidance for an AI coding agent working in this repository.

- Purpose: help an agent become productive quickly by explaining architecture, key workflows, conventions, and runnable commands.

## Big picture
- Entry point: `jarvis.py` — single CLI for interactive, service, and conversational modes. See state machine (SLEEP→WAKE→LISTEN→THINK→SPEAK) in `jarvis.py`.
- Daemon: `daemon/` contains the automation daemon and wake-word flow (`daemon/service.py`, `daemon/cli.py`). Use `python -m daemon.cli` to control it.
- Orchestrator: `AgentCore/agent_brain.py` implements the ODAV loop (Observe→Decide→Act→Verify). Many AgentCore modules (intent parsing, task planner, executor, validator) form the runtime.
- Platform adapters: `platform_adapters/` implements canonical adapters (browser, text editor, WhatsApp, Telegram, Gmail). Adapter interface methods to follow: `open_app()`, `close_app()`, `send_message(target, message)`, `read_unread(limit=...)`.
- Logging & audit: structured JSON-lines at `logs/jarvis_actions.log` (keys: `timestamp`, `action`, `target`, `result`, `dry_run_flag`, `meta`). Tests and tooling depend on dry-run-safe behavior.

## How to run (examples)
- Run interactive app: `python jarvis.py`
- Persistent wake service: `python jarvis.py --service` or `python -m daemon.cli run-loop` (start/stop/status via `daemon.cli`).
- Conversational mode: `python jarvis.py --convo`
- Tests: `PYTHONPATH=. pytest -q tests -p no:cacheprovider` (dry-run behaviours are required for CI tests).
- Automation audit: `PYTHONPATH=. python tools/automation_verifier.py --output logs/automation_verifier_report.json`

## Project-specific conventions & patterns
- Dry-run first: Many automation flows (daemon, platform adapters) support a dry-run mode. Use `dry_run=True` where available and avoid calling GUI automation in tests unless explicitly required.
- Feature gates: Features are guarded using `AgentCore.feature_gate` and YAML files in `feature_flags/`. Don’t assume optional engines (code engine, learning system, RAG) are always available — check imports and gates.
- CodeEngine / safe mode: `AgentCore.code_engine` is behind a feature flag and an environment toggle `JARVIS_CODE_MODE` or CLI `--enable-code` in `jarvis.py`. Enable explicitly during experiments.
- Learning system is import-guarded: wrap usage in try/except and respect `FeatureGate` flags (see `jarvis.py` lines where `LearningSystem` is imported).
- Command injection pattern: `PersistentWakeService._execute_command` writes commands to `input.txt` for `co_brain` to consume — tests and agents may use this for end-to-end triggers.
- ODAV semantics: Follow `AgentCore/agent_brain.py` for execution lifecycle; plan creation, verification, replan/retry logic are central to safe automation.

## Safety & permissions
- `ALLOW_DESTRUCTIVE` defaults to `false`. High-risk actions are blocked unless explicitly enabled — respect this flag and `feature_flags/AUTOMATION_UPGRADE_V1.yaml` when changing behavior.
- Dry-run is required for test suites; ensure `dry_run_flag` is set in logs and that actual GUI calls are gated behind the dry-run checks.

## Integration points & dependencies
- STT/TTS: `stt_integration.py`, `WakeService/` (wake detector and local STT), and `TextToSpeech/` contain audio integration. Tests may mock these.
- LLM & RAG: AgentCore provides LLM engine interfaces (`AgentCore/llm_engine`, `rag_engine`), but these may be optional and guarded by imports and feature flags.
- Platform adapters: Add or update adapters under `platform_adapters/`; new adapters should adhere to the adapter API described above and be discoverable by `tools/automation_verifier.py`.

## Developer workflows the agent should know
- When adding code that performs automation, include dry-run behavior and structured log entries (see `logs/jarvis_actions.log` format).
- To run the daemon locally for debugging: `python -m daemon.cli run-loop` and inspect logs under `logs/` and `log.txt`.
- For feature flags changes, update corresponding YAML in `feature_flags/` and validate with `tools/automation_verifier.py`.

## Quick references (files to inspect first)
- Core: [jarvis.py](jarvis.py)
- Daemon: [daemon/cli.py](daemon/cli.py) and [daemon/service.py](daemon/service.py)
- Orchestrator: [AgentCore/agent_brain.py](AgentCore/agent_brain.py)
- Platform adapters: [platform_adapters/](platform_adapters/)
- Logs: `logs/jarvis_actions.log`
- Feature flags: `feature_flags/`

### Adapter contract (STRICT)
- All adapter methods MUST be idempotent.
- All adapter methods MUST accept and respect a `dry_run: bool = False` parameter and MUST log the intended action instead of executing when `dry_run=True`.
- All adapter methods MUST return a dict with this shape:
	`{ "status": "ok" | "blocked" | "error", "meta": {...} }`.
- Adapters MUST NOT raise exceptions for expected/handled failures; return structured failures (`status: "error"`) instead. Only raise for truly unrecoverable states.
- Adapters MUST write structured log entries to `logs/jarvis_actions.log` containing `timestamp`, `action`, `target`, `result`, and `dry_run_flag`.

### ODAV (concrete example)
Use this canonical 4-step flow for implementing behaviors. Agents and generated code should follow this pattern exactly.
- Observe: parse transcript → detect intent (e.g., "open README.md in editor").
- Decide: map intent → adapter + action (e.g., `text_editor_adapter.open_file(path)`), build params and safety checks.
- Act: call adapter method with `dry_run` gated (e.g., `text_editor_adapter.open_file(path, dry_run=ctx.dry_run)`).
- Verify: confirm success via adapter readback or logs (e.g., `text_editor_adapter.read_open_files()` or `logs/jarvis_actions.log`); if verify fails, trigger `planner.replan()` or `validator` recovery and log the failure.

Example (pseudo):
1. Observe: `transcript = "open README.md"`
2. Decide: `action = {"adapter": "text_editor", "method": "open_file", "params": {"path": "README.md"}}`
3. Act: `result = text_editor_adapter.open_file("README.md", dry_run=True)`
4. Verify: `if result.status != "ok": planner.replan_or_retry(...)`

### Forbidden without explicit enablement
- Bulk or broadcast actions (send to many targets, mass-delete) — require explicit feature flag and review.
- Data exfiltration: exporting, forwarding, or uploading user data to external services.
- External execution: running arbitrary shell scripts, installers, or remote code.
- State-destructive actions: delete, wipe, format, overwrite operations.

### Automation Verifier — REQUIRED gate
When adding or modifying `platform_adapters`, always run `tools/automation_verifier.py` and treat it as a mandatory gate. Adapters that fail the verifier audit must NOT be enabled until findings are resolved.

### Do NOT
- Bypass `platform_adapters/` by calling GUI automation directly from other layers.
- Put automation decision or orchestration logic inside `AgentCore` (AgentCore should orchestrate, adapters implement platform effects).
- Execute real GUI actions in tests — use `dry_run` or mocks instead.
- Assume network/cloud availability in core flows; detect and fail gracefully.
- Invent adapter return shapes — adhere to the strict contract above.

If any section is unclear or you'd like more examples (unit test patterns, a runnable minimal adapter, or an example dry-run), tell me which part to expand.

## Minimal adapter example
We include a runnable template demonstrating the adapter contract and logging: [platform_adapters/minimal_adapter_template.py](platform_adapters/minimal_adapter_template.py)

Use this template as a starting point for new adapters. It shows:
- `dry_run` gating
- Structured return shape
- Idempotency considerations
- Writing JSON-lines to `logs/jarvis_actions.log`

## Automation-verifier run (example)
Run the verifier after adding or modifying adapters:

```bash
PYTHONPATH=. python tools/automation_verifier.py --output logs/automation_verifier_report.json
```

If the verifier reports failures, do not enable the adapter until issues are resolved.
