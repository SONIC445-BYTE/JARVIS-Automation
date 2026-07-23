"""
JARVIS ODAV Agent Engine
========================
Observe → Decide → Act → Verify (Closed Loop)

This module provides intent-driven autonomous UI execution.
Every action follows the ODAV loop to ensure verifiable execution.
"""

__all__ = [
    'AgentBrain',
    'IntentParser',
    'TaskPlanner',
    'UIScanner',
    'ActionExecutor',
    'ValidationEngine',
    'CheckpointManager',
]

__version__ = '0.1.0-mvp'

# Pulled forward from Phase 3 debt: these used to be imported eagerly
# above, which meant *every* `AgentCore.<anything>` import (e.g.
# `AgentCore.ui_executor`, the real ODAVLoop execution path) paid the
# cost of importing pyautogui (ui_perception/action_executor/checkpoint),
# since Python always runs a package's __init__.py before any of its
# submodules. On Linux/headless environments this compounds with
# AgentCore.ui_agent's mss dependency (see
# Automation/Automation_Brain.py's lazy-loading fix for that half) to
# make importing jarvis.py itself fail outside a real display -- not
# just noisier or slower, genuinely unrunnable. Nothing in this repo
# imports from the package level (`from AgentCore import AgentBrain`) --
# grepped and confirmed empty; every real caller already imports a
# specific submodule directly (`from AgentCore.ui_executor import
# UIExecutor`), which was never affected by what's declared here.
# __getattr__ (PEP 562) keeps `AgentCore.AgentBrain`-style access working
# for any future/external caller, just deferred to first actual use
# instead of paid by every import of this package.
_LAZY_ATTRS = {
    'AgentBrain': ('.agent_brain', 'AgentBrain'),
    'IntentParser': ('.intent_parser', 'IntentParser'),
    'TaskPlanner': ('.task_planner', 'TaskPlanner'),
    'UIScanner': ('.ui_perception', 'UIScanner'),
    'ActionExecutor': ('.action_executor', 'ActionExecutor'),
    'ValidationEngine': ('.validation_engine', 'ValidationEngine'),
    'CheckpointManager': ('.checkpoint', 'CheckpointManager'),
}


def __getattr__(name):
    if name in _LAZY_ATTRS:
        import importlib
        module_name, attr_name = _LAZY_ATTRS[name]
        module = importlib.import_module(module_name, __name__)
        return getattr(module, attr_name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
