# Level-6 Self-Debugging Engine

## Overview
Autonomous coding engine capable of planning, generating tests, executing in a sandbox, and iterating on failures.

## Components
- **Orchestrator**: Cooperates components.
- **Planner**: Generates initial refactor plan.
- **TestGen**: Creates supporting tests.
- **Sandbox**: Isolated execution environment.
- **DebugLoop**: Iterates on failures using AST fixes.
- **Verifier**: Static safety checks.

## Configuration
`feature_flags/level6_engine.yaml`
```yaml
enabled: false
max_iterations: 5
```

## Usage
Currently integrated via `Level6Coordinator`.
```python
coord = Level6Coordinator()
res = coord.handle_request("Refactor auth module", {})
```
