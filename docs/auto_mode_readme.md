# Automatic Mode Selector (AMS)

AMS allows JARVIS to switch between modes based on intent.

## Modes
- **Normal**: Standard conversational mode.
- **Service**: Low-power wake word listener.
- **Code**: Routes commands to `CodeEngine`.
- **Conversation**: Force conversational LLM.

## Configuration
Controlled by `feature_flags/auto_mode.yaml`.
```yaml
enabled: false
auto_switch_confidence_threshold: 0.75
```

## How to Test
1. **Enable**: Set `enabled: true` in `feature_flags/auto_mode.yaml`.
2. **Simulate**:
   ```bash
   python AgentCore/mode_manager/run_mode_sim.py "write a python script"
   ```
   Output should show `action: switch`, `target_mode: code`.

## Constraints
- Destructive actions require owner confirmation.
- Mic ownership is arbitrated.
