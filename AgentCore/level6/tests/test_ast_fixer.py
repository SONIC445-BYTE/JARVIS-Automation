import unittest

from AgentCore.level6.ast_fixer import ASTFixer


class TestASTFixer(unittest.TestCase):
    def setUp(self):
        self.fixer = ASTFixer()

    def test_replace_full_still_works(self):
        result = self.fixer.apply_transform(
            "def old():\n    pass\n",
            {"type": "replace_full", "code": "def new():\n    pass\n"},
        )
        self.assertEqual(result, "def new():\n    pass\n")

    def test_replace_function_replaces_matching_function_in_place(self):
        original = (
            "import os\n\n"
            "def divide(a, b):\n"
            "    return a / b\n\n"
            "def unrelated():\n"
            "    return 42\n"
        )
        spec = {
            "type": "replace_function",
            "name": "divide",
            "code": "def divide(a, b):\n    if b == 0:\n        return None\n    return a / b\n",
        }

        result = self.fixer.apply_transform(original, spec)

        # The targeted function is genuinely replaced...
        self.assertIn("if b == 0:", result)
        self.assertIn("return None", result)
        # ...and everything else in the file survives untouched --
        # this is the entire point of a real AST transform over a
        # full-file rewrite.
        self.assertIn("import os", result)
        self.assertIn("def unrelated():", result)
        self.assertIn("return 42", result)

    def test_replace_function_appends_when_function_does_not_exist(self):
        original = "def existing():\n    return 1\n"
        spec = {
            "type": "replace_function",
            "name": "new_func",
            "code": "def new_func():\n    return 2\n",
        }

        result = self.fixer.apply_transform(original, spec)

        self.assertIn("def existing():", result)
        self.assertIn("def new_func():", result)

    def test_replace_function_on_empty_file_creates_it(self):
        result = self.fixer.apply_transform(
            "",
            {"type": "replace_function", "name": "add", "code": "def add(a, b):\n    return a + b\n"},
        )
        self.assertIn("def add(a, b):", result)
        compile(result, "<test>", "exec")

    def test_replace_function_result_is_valid_python(self):
        original = "def divide(a, b):\n    return a / b\n"
        spec = {
            "type": "replace_function",
            "name": "divide",
            "code": "def divide(a, b):\n    if b == 0:\n        return None\n    return a / b\n",
        }
        result = self.fixer.apply_transform(original, spec)
        compile(result, "<test>", "exec")

    def test_replace_function_with_malformed_existing_file_is_a_safe_no_op(self):
        broken = "def divide(a, b:\n    return a / b"  # missing closing paren
        spec = {"type": "replace_function", "name": "divide", "code": "def divide(a, b):\n    return 0\n"}
        result = self.fixer.apply_transform(broken, spec)
        self.assertEqual(result, broken)

    def test_replace_function_with_malformed_fix_code_is_a_safe_no_op(self):
        original = "def divide(a, b):\n    return a / b\n"
        spec = {"type": "replace_function", "name": "divide", "code": "def divide(a, b:\n    return 0"}
        result = self.fixer.apply_transform(original, spec)
        self.assertEqual(result, original)

    def test_missing_name_or_code_is_a_safe_no_op(self):
        original = "def divide(a, b):\n    return a / b\n"
        self.assertEqual(
            self.fixer.apply_transform(original, {"type": "replace_function", "name": "divide"}),
            original,
        )
        self.assertEqual(
            self.fixer.apply_transform(original, {"type": "replace_function", "code": "def x(): pass"}),
            original,
        )

    def test_unknown_transform_type_is_a_safe_no_op(self):
        original = "def divide(a, b):\n    return a / b\n"
        result = self.fixer.apply_transform(original, {"type": "something_unrecognized"})
        self.assertEqual(result, original)


if __name__ == "__main__":
    unittest.main()
