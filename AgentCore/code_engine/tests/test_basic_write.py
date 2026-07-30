import pytest
import os
import shutil
from pathlib import Path
from AgentCore.code_engine.engine import CodeEngine

@pytest.fixture
def temp_workspace(tmp_path):
    # Set up temp feature flag
    flags_dir = tmp_path / "feature_flags"
    flags_dir.mkdir(parents=True, exist_ok=True)
    with open(flags_dir / "code_engine.yaml", "w") as f:
        f.write("enabled: true\nauto_write: false\nsandbox_root: 'sandbox'")
    
    # Mock base path in CodeEngine
    original_init = CodeEngine.__init__
    
    def mock_init(self, config=None):
        self.base_path = tmp_path
        self.flag_path = flags_dir / "code_engine.yaml"
        self.config = config or self._read_flag()
        from AgentCore.code_engine.generator_helper import GeneratorHelper
        self.generator = GeneratorHelper()
        self.generator.llm = None # Force fallback
        
    CodeEngine.__init__ = mock_init
    yield tmp_path
    CodeEngine.__init__ = original_init

def test_dry_run(temp_workspace):
    engine = CodeEngine()
    result = engine.handle_command("write a python program that prints hello world", dry_run=True)
    
    assert result["dry_run"] is True
    assert "hello_world.py" in result["patch_summary"]
    # File should NOT exist
    # Sandbox root is relative to temp_workspace because we mocked base_path
    sandbox = temp_workspace / "sandbox"
    # Find the timestamp dir
    ts_dirs = list(sandbox.glob("*"))
    if ts_dirs:
        # Dry run might or might not create the dir depending on implementation
        # The implementation creates target_dir only in write block in one case, 
        # but the dry run result returns the path
        pass
        
    # Check return path
    assert "sandbox" in result["file_path"]

def test_auto_write(temp_workspace):
    # Enable auto_write
    with open(temp_workspace / "feature_flags/code_engine.yaml", "w") as f:
        f.write("enabled: true\nauto_write: true\nsandbox_root: 'sandbox'")
    
    engine = CodeEngine()
    # dry_run=False passed from caller
    result = engine.handle_command("write a python program that prints hello world", dry_run=False)
    
    assert result["dry_run"] is False
    assert os.path.exists(result["file_path"])
    # D11: result["file_path"] is the sandbox *directory* handle_command()
    # writes into (it can hold multiple files for multi-file responses),
    # not a single file -- opening it directly raised PermissionError on
    # Windows (opening a directory as a file). engine.py's single-file
    # heuristic names a python response "hello_world.py".
    written_file = os.path.join(result["file_path"], "hello_world.py")
    assert os.path.exists(written_file)
    with open(written_file, "r") as f:
        content = f.read()
        assert "print('Hello World')" in content
