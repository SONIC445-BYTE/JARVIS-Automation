# Migration — Learning System
================================

## New Files Added

### Modules (AgentCore/learning_system/)
- `__init__.py`, `feature_gate.py`, `policy_store.py`, `audit_log.py`
- `flow_instrumentation.py`, `confidence_engine.py`, `pattern_extractor.py`
- `action_discovery.py`, `adapter_generator.py`, `intent_graph.py`
- `critic_engine.py`, `causal_memory.py`, `human_loop.py`

### Tests (AgentCore/learning_system/tests/)
- `test_feature_gate.py`, `test_confidence_engine.py`
- `test_action_discovery.py`, `test_causal_memory.py`
- `test_intent_graph.py`, `test_critic_engine.py`

### Data Directories (created on demand)
- `data/traces/`
- `data/action_templates/`
- `data/audit/`
- `data/approvals/`
- `data/intent_logs/`

### Database
- `data/causal_memory.sqlite` — created automatically on first use

### Feature Flags
- `feature_flags/learning_system.yaml` — master flag (default: OFF)

## Backup Before Enabling

```powershell
# Backup existing data/
xcopy data\ data_backup_%date:~-4,4%%date:~-7,2%%date:~-10,2%\ /E /I /Y

# Backup feature flags
copy feature_flags\learning_system.yaml feature_flags\learning_system.yaml.bak
```

## Rollback

```powershell
.\rollback.ps1
```
This sets `learning_system.yaml` to `enabled: false` and preserves all generated artifacts.
