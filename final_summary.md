# Level-6: Self-Debugging Engine

## Overview
Implemented the **Self-Debugging, Test-First Coding Engine**. This engine can plan refactors, generate tests, run them in a sandbox, and auto-debug failures.

## Components
- **Coordinator**: `AgentCore/level6/orchestrator.py`
- **Planner**: `AgentCore/level6/planner.py` (LLM-based planning)
- **Execution**: `AgentCore/level6/sandbox_runner.py` (Isolated)
- **Testing**: `AgentCore/level6/test_generator.py`
- **Debugging**: `AgentCore/level6/debug_loop.py` & `ast_fixer.py`
- **Safety**: `AgentCore/level6/verifier.py` & `rollback_manager.py`
- **Observability**: `metrics.py` (JSONL logs)

## Verification
- **Unit Tests**: `tests/test_core.py`, `tests/test_sandbox.py`, `tests/test_debug_loop.py` PASSED.
- **Integration**: Hooked into `jarvis.py` (default: OFF).
- **Behavior**: Requires `feature_flags/level6_engine.yaml` enabled: true.

## Next Steps
1. Enable `feature_flags/level6_engine.yaml`.
2. Connect real LLM adapter to `Level6Coordinator`.
