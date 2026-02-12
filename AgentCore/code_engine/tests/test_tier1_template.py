"""
Test Tier-1 Template Manager.
"""
import os
import shutil
import unittest
from AgentCore.code_engine.tier1.template_manager import TemplateManager

class TestTier1Template(unittest.TestCase):
    def setUp(self):
        self.test_dir = "test_templates"
        self.output_dir = "test_output"
        os.makedirs(self.test_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Create a dummy template
        with open(os.path.join(self.test_dir, "test.py.j2"), "w") as f:
            f.write("def {{ func_name }}():\n    pass")
            
        self.mgr = TemplateManager(template_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir)
        shutil.rmtree(self.output_dir)

    def test_create_file(self):
        target = os.path.join(self.output_dir, "generated.py")
        result = self.mgr.create_file(target, "test.py.j2", {"func_name": "my_func"})
        
        self.assertTrue(result['success'])
        self.assertTrue(os.path.exists(target))
        
        with open(target, "r") as f:
            content = f.read()
            self.assertIn("def my_func():", content)

    def test_dry_run(self):
        target = os.path.join(self.output_dir, "dry.py")
        result = self.mgr.create_file(target, "test.py.j2", {"func_name": "dry_func"}, dry_run=True)
        
        self.assertTrue(result['dry_run'])
        self.assertFalse(os.path.exists(target))
        self.assertIn("def dry_func():", result['content_preview'])

if __name__ == "__main__":
    unittest.main()
