"""
Test AST Editor.
"""
import os
import unittest
from AgentCore.code_engine.tier1.ast_editor import ASTEditor

class TestASTEditor(unittest.TestCase):
    def setUp(self):
        self.editor = ASTEditor()
        self.test_file = "test_code.py"
        with open(self.test_file, "w") as f:
            f.write("import os\n\ndef old_func():\n    pass\n")

    def tearDown(self):
        if os.path.exists(self.test_file):
            os.remove(self.test_file)

    def test_add_import(self):
        spec = {"type": "add_import", "line": "import sys"}
        self.editor.apply_edit(self.test_file, spec)
        
        with open(self.test_file, "r") as f:
            content = f.read()
            self.assertIn("import sys", content)

    def test_add_function(self):
        spec = {
            "type": "add_function",
            "code": "def new_func():\n    return True",
            "target_class": None
        }
        self.editor.apply_edit(self.test_file, spec)
        
        with open(self.test_file, "r") as f:
            content = f.read()
            self.assertIn("def new_func():", content)

if __name__ == "__main__":
    unittest.main()
