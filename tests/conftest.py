"""
Shared pytest fixtures for tests/.

autouse cleanup for the repo-root state/ directory: most tests that
touch onboarding.py's persistence explicitly patch STATE_DIR to a temp
directory, but jarvis.py's conversation-loop methods (_handle_resume,
_handle_install_confirmation, the dispatch-loop branches) call
onboarding.persist_pending_state()/clear_pending_state() directly, and
several pre-existing tests in tests/test_pending_resume_flow.py and
tests/test_install_confirmation_flow.py exercise those methods for real
without mocking those specific calls (they predate the persistence
hooks and test other things). Rather than adding mocks to every one of
those call sites, this fixture guarantees the real state/ directory
never survives a test run, regardless of which test wrote to it.
"""
import shutil
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _clean_state_dir_after_test():
    state_existed_before = Path("state").exists()
    yield
    if not state_existed_before and Path("state").exists():
        shutil.rmtree("state", ignore_errors=True)
