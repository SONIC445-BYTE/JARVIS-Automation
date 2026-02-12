# Learning System — Module Documentation
=========================================

## Overview

The learning system adds action discovery, intent-vs-command separation,
confidence-weighted autonomy, a critic, causal memory, and human-in-the-loop
self-training to J.A.R.V.I.S.

**All features are behind feature flags (default OFF).** Enable via
`feature_flags/learning_system.yaml`.

## Modules

| Module | Purpose |
|--------|---------|
| `feature_gate.py` | Load and check feature flags |
| `policy_store.py` | Execution thresholds (auto/confirm/reject) |
| `audit_log.py` | HMAC-chained append-only audit trail |
| `flow_instrumentation.py` | Structured interaction traces (opt-in) |
| `confidence_engine.py` | Score actions by freq/success/context |
| `pattern_extractor.py` | Cluster + generalise action sequences |
| `action_discovery.py` | Find repeated patterns → propose automations |
| `adapter_generator.py` | Generate platform adapter stubs |
| `intent_graph.py` | Classify intent: command / goal / question |
| `critic_engine.py` | Evaluate plans for risk + suggest alternatives |
| `causal_memory.py` | SQLite store for cause→effect relationships |
| `human_loop.py` | Approval workflow for proposed actions |

## Data Directories

| Path | Contents |
|------|----------|
| `data/traces/` | Interaction trace JSON files |
| `data/action_templates/` | Discovered action template JSON |
| `data/audit/learning_audit.log` | HMAC-signed audit log |
| `data/approvals/` | Pending + decided approval records |
| `data/intent_logs/` | Intent classification logs (JSONL) |
| `data/causal_memory.sqlite` | Causal link database |

## DB Schema — `causal_memory.sqlite`

```sql
CREATE TABLE causal_links (
    id TEXT PRIMARY KEY,
    cause_hash TEXT NOT NULL,
    effect_hash TEXT NOT NULL,
    context_hash TEXT,
    confidence REAL DEFAULT 0.0,
    evidence_count INTEGER DEFAULT 1,
    first_observed REAL,
    last_observed REAL,
    notes TEXT DEFAULT ''
);
```

## Enabling Features

1. Edit `feature_flags/learning_system.yaml`
2. Set `enabled: true` and individual module flags
3. Restart Jarvis
4. Check status: `python jarvis.py --health`

## Rollback

Run `rollback.ps1` to disable all flags and clear loaded adapters.
