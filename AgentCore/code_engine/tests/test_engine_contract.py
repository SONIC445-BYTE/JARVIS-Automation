"""
Phase 0 safety net: pins the literal return contract of
CodeEngine.handle_command() so callers (jarvis.py) can't be "fixed" back
to a wrong assumption. See JARVIS-Automation diagnosis brief, Phase 0/1.

handle_command() returns exactly: dry_run, patch_summary, patch_diff,
file_path, sandbox_path. It NEVER returns a "success" key.
"""
import pytest
from AgentCore.code_engine.engine import CodeEngine


@pytest.fixture
def temp_workspace(tmp_path):
    flags_dir = tmp_path / "feature_flags"
    flags_dir.mkdir(parents=True, exist_ok=True)
    with open(flags_dir / "code_engine.yaml", "w") as f:
        f.write("enabled: true\nauto_write: false\nsandbox_root: 'sandbox'")

    original_init = CodeEngine.__init__

    def mock_init(self, config=None):
        self.base_path = tmp_path
        self.flag_path = flags_dir / "code_engine.yaml"
        self.config = config or self._read_flag()
        from AgentCore.code_engine.generator_helper import GeneratorHelper
        self.generator = GeneratorHelper()
        self.generator.llm = None  # Force fallback

    CodeEngine.__init__ = mock_init
    yield tmp_path
    CodeEngine.__init__ = original_init


def test_handle_command_returns_exactly_the_documented_keys(temp_workspace):
    engine = CodeEngine()
    result = engine.handle_command(
        "write a python program that prints hello world", dry_run=True
    )

    assert set(result.keys()) == {
        "dry_run",
        "patch_summary",
        "patch_diff",
        "file_path",
        "sandbox_path",
    }


def test_handle_command_never_returns_a_success_key(temp_workspace):
    engine = CodeEngine()
    result = engine.handle_command(
        "write a python program that prints hello world", dry_run=True
    )

    # This is the root cause of "Code task failed: None" in jarvis.py:
    # the caller checked result.get("success"), which is always None here.
    assert "success" not in result
    assert result.get("success") is None


def test_successful_dry_run_has_truthy_signal_fields(temp_workspace):
    """A real, successful dry-run always has a non-empty patch_summary and
    file_path -- this is what the caller should key success off of instead
    of the nonexistent "success" field."""
    engine = CodeEngine()
    result = engine.handle_command(
        "write a python program that prints hello world", dry_run=True
    )

    assert result["dry_run"] is True
    assert result["patch_summary"]
    assert result["file_path"]
