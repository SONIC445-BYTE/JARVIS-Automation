
import unittest
from ..adapter import NotepadAdapter

class TestNotepadAdapter(unittest.TestCase):
    def setUp(self):
        self.adapter = NotepadAdapter()

    def test_detect_ui(self):
        self.assertTrue(self.adapter.detect_ui({"active_window": "Untitled - Notepad"}))
        self.assertFalse(self.adapter.detect_ui({"active_window": "Calculator"}))

    def test_build_plan_type(self):
        plan = self.adapter.build_plan("type_text", {"text": "Hello"})
        self.assertTrue(len(plan.steps) > 0)
        self.assertEqual(plan.steps[0].action, "type")

    def test_build_plan_save(self):
        plan = self.adapter.build_plan("save_file", {"filename": "test.txt"})
        self.assertTrue(len(plan.steps) > 2)

if __name__ == '__main__':
    unittest.main()
