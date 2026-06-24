```text
      ___           ___           ___           ___           ___           ___
     /\  \         /\  \         /\  \         /\__\         /\  \         /\  \
     \:\  \       /::\  \       /::\  \       /:/ _/_       /::\  \       /::\  \
      \:\  \     /:/\:\  \     /:/\:\  \     /:/ /\  \     /:/\:\  \     /:/\:\  \
  ___  \:\  \   /::\~\:\  \   /::\~\:\  \   /:/ /::\  \   /::\~\:\  \   /:/ /::\  \
 /\  \  \:\__\ /:/\:\ \:\__\ /:/\:\ \:\__\ /:/_/:/\:\__\ /:/\:\ \:\__\ /:/_/:/\:\__\
 \:\  \ /:/  / \/__\:\/:/  / \/__\:\/:/  / \:\__\/|::|  | \/__\:\/:/  / \:\__\/ \/__/
  \:\  /:/  /       \::/  /       \::/  /   \/__/ |:|  |      \::/  /   \:\  \
   \:\/:/  /        /:/  /        /:/  /          |:|  |      /:/  /     \:\  \
    \::/  /        /:/  /        /:/  /           |:|  |     /:/  /       \::/  /
     \/__/         \/__/         \/__/            \|__|     \/__/         \/__/
```

# J.A.R.V.I.S - Just A Rather Very Intelligent System

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Status: Stable](https://img.shields.io/badge/Status-Stable-green.svg)](#)
[![Maintenance: Passive](https://img.shields.io/badge/Maintained%3F-Yes%20(Passive)-yellow.svg)](#)

> **SYSTEM STATUS:** STABLE. PASSIVE MAINTENANCE. FULLY OPERATIONAL.

J.A.R.V.I.S is a local-first autonomous assistant powered by a custom AgentCore, featuring a Level-6 Self-Debugging Engine and a sophisticated Learning System. Designed for privacy and speed, it operates 100% offline using Ollama, Vosk, and Piper.

---

## [01] QUICK START

1.  **Clone the Repository**
    ```bash
    git clone https://github.com/SONIC445-BYTE/JARVIS-Automation.git
    cd JARVIS-Automation
    ```

2.  **Install Dependencies**
    Ensure you have Python 3.10 or higher installed.
    ```bash
    pip install -r requirements.txt
    ```

3.  **Launch JARVIS**
    *   **Interactive Mode:** `python jarvis.py`
    *   **Wake-Word Service:** `python jarvis.py --service`
    *   **Automation Daemon:** `python -m daemon.cli start`

---

## [02] CORE CAPABILITIES

| MODULE | DESCRIPTION |
| :--- | :--- |
| **Wake-Word Standby** | Ultra-low CPU standby mode listening for "JARVIS". |
| **Level-6 Engine** | Autonomous coding engine that plans, tests, and self-debugs in sandboxes. |
| **Learning System** | Shadow-mode discovery of user patterns to propose new automations. |
| **UI Agent** | Vision-based GUI interaction for apps without native APIs. |
| **Hybrid Execution** | Seamless switching between native adapters and UI automation. |

---

## [03] ARCHITECTURAL DEEP DIVES

### LEVEL-6 SELF-DEBUGGING ENGINE
The Level-6 Engine is the peak of JARVIS's coding capability. It doesn't just write code; it ensures it works through an iterative verification loop.

*   **PLANNER:** Analyzes requests and maps out multi-file refactors using context-aware dependency trees.
*   **SANDBOX:** Executes code in an isolated environment (`projects/sandbox/`) to prevent host contamination.
*   **DEBUG LOOP:** Automatically interprets traceback errors and applies AST-based fixes.
*   **VERIFIER:** Performs static and dynamic safety checks before merging patches.

### LEARNING SYSTEM (SHADOW MODE)
The Learning System operates in the background, observing your interactions to identify repetitive workflows without manual configuration.

*   **ACTION DISCOVERY:** Clusters repeated sequences of UI events into potential automations.
*   **CONFIDENCE ENGINE:** Scores discovered patterns based on frequency, success rate, and causal consistency.
*   **HUMAN-IN-THE-LOOP:** Proposed automations are saved to `data/action_templates/` for your review before activation.

---

## [04] REAL-WORLD USAGE EXAMPLES

### VOICE COMMAND EXECUTION
JARVIS listens for "Jarvis" and transitions through a robust state machine: `SLEEP` → `WAKE` → `LISTEN` → `THINK` → `EXECUTE`.

```python
# Location: jarvis.py
def _on_wake_detected(self):
    if self.state != JarvisState.SLEEP: return
    self._set_state(JarvisState.WAKE)
    self._stop_wake_detection()
    self._speak("Yes?")
    self._listen_for_command()
```

### AUTONOMOUS CODE GENERATION
Triggered by keywords like "write", "create", or "build".

```python
# Example: "Jarvis, write a python script to monitor my battery"
# Location: AgentCore/code_engine/engine.py
result = CODE_ENGINE.handle_command(text, context={"cwd": os.getcwd()}, dry_run=True)
print(f"PLAN PREPARED: {result['patch_summary']}")
```

### LEARNING FROM PATTERNS
```python
# Location: AgentCore/learning_system/action_discovery.py
discovery = ActionDiscovery()
candidates = discovery.find_repeated_sequences(traces)
proposal = discovery.propose_action(candidates[0])
discovery.export_proposed_action(proposal)
# -> Saved to data/action_templates/auto_whatsapp_report.json
```

---

## [05] PLATFORM ADAPTERS

JARVIS uses a modular adapter system to interact with applications.

*   **BROWSER:** Chrome, Edge, Brave (via Selenium)
*   **COMMUNICATION:** WhatsApp Desktop, Telegram Desktop, Gmail
*   **TOOLS:** Text Editors (Notepad, VS Code), WinRAR
*   **SYSTEM:** Battery, Volume, Brightness, Weather

### CUSTOM ADAPTER TEMPLATE
```python
from platform_adapters.adapter_base import BaseAdapter

class MyCustomAdapter(BaseAdapter):
    def open_app(self, dry_run=False):
        return {"status": "ok", "meta": {"msg": "App opened"}}

    def send_message(self, target, message, dry_run=False):
        # Implementation logic here
        pass
```

---

## [06] DIRECTORY STRUCTURE

```text
.
├── AgentCore/                     # Core intelligence and routing
│   ├── code_engine/               # Level-1 to Level-5 coding logic
│   │   ├── tier1/                 # Direct generation
│   │   ├── tier2/                 # Multi-file refactor
│   │   ├── sandbox/               # Code execution jail
│   │   ├── engine.py              # Main engine logic
│   │   └── generator_helper.py    # LLM code prompting
│   ├── learning_system/           # Pattern discovery and confidence scoring
│   │   ├── action_discovery.py    # Trace analysis
│   │   ├── confidence_engine.py   # Proposal scoring
│   │   ├── intent_graph.py        # Semantic mapping
│   │   ├── flow_instrumentation.py# UI telemetry
│   │   └── human_loop.py          # Approval workflow
│   ├── level6/                    # Self-debugging orchestrator
│   │   ├── orchestrator.py        # Coordinator
│   │   ├── planner.py             # Refactor strategy
│   │   ├── sandbox_runner.py      # Isolated execution
│   │   └── debug_loop.py          # AST iteration
│   └── ui_agent/                  # Vision-based GUI automation
│       ├── vision/                # Screen analysis
│       └── planner/               # Action sequencing
├── Automation/                    # Legacy automation scripts
├── Brain/                         # Core NLP and logic processing
├── daemon/                        # Background automation service
│   ├── service.py                 # Loop implementation
│   ├── dispatcher.py              # Command routing
│   └── supervisor.py              # Process health
├── platform_adapters/             # App-specific interaction layers
│   ├── browser_adapter.py
│   ├── whatsapp_desktop_adapter.py
│   ├── telegram_desktop_adapter.py
│   ├── gmail_browser_adapter.py
│   ├── text_editor_adapter.py
│   └── generated/                 # Scaffolds created by Learning System
├── platform_summary/              # Capability metadata for 100+ apps
├── WakeService/                   # Offline STT and wake-word detection
│   ├── wake_detector.py           # Vosk implementation
│   ├── local_stt.py               # Offline transcription
│   └── jarvis_service.py          # Windows service wrapper
├── jarvis.py                      # Main entry point
└── requirements.txt               # Project dependencies
```

---

## [07] CONTRIBUTION GUIDELINES

This project follows strict architectural invariants. All contributions **must** adhere to:

1.  **RESPECT DRY-RUN:** All automation methods must accept a `dry_run` parameter.
2.  **AUDIT LOGS:** Every action must be logged to `logs/jarvis_actions.log`.
3.  **SAFETY FIRST:** Destructive commands must be gated behind the `ALLOW_DESTRUCTIVE` flag.
4.  **TEST COVERAGE:** New features require integration tests in `tests/`.

### PR PROCESS
1.  Fork the repository.
2.  Ensure `pytest` passes locally.
3.  Submit PR with a detailed description of changes and safety impact.

---

## [08] FAQ

**Q: Why is my wake word not detecting?**
A: Check your microphone sensitivity in `WakeService/audio_helper.py` and ensure the `Vosk` model is correctly downloaded in `Data/`.

**Q: How do I add a custom adapter?**
A: Use the template in `platform_adapters/minimal_adapter_template.py` or see the **PLATFORM ADAPTERS** section.

**Q: Can I run this on [OS]?**
A: Yes. Use `tools/installer.sh` for Linux or `tools/macos/com.jarvis.automation.plist` for macOS. Windows users can use `tools/installer.ps1`.

---

## [09] LICENSE

This project is licensed under the **GNU General Public License v3 (GPL-3.0)**.

> Copyright (C) 2007 Free Software Foundation, Inc.

See the [LICENSE](LICENSE) file for full details.
