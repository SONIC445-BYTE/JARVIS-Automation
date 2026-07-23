"""
Tests for Level6Coordinator.apply() -- the Phase D approval-gated
apply-to-real-repo step. This is the highest-stakes piece of Level6: it
writes to a real directory outside the sandbox. Every test here uses an
isolated tempdir target, never the actual repo, and asserts the safety
mechanics explicitly: snapshot-before-write, revert-on-partial-failure,
and copying the exact verified sandbox bytes (not plan["content"], which
is never populated for ast_edit steps -- see PendingLevel6Apply's
docstring in orchestrator.py for why that distinction matters).
"""
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from AgentCore.level6.orchestrator import Level6Coordinator, PendingLevel6Apply


class TestApply(unittest.TestCase):
    def setUp(self):
        self.config_path = "feature_flags/test_level6_apply.yaml"
        with open(self.config_path, "w") as f:
            f.write("enabled: true\n")
        self.coord = Level6Coordinator(self.config_path)

        self.tmp = Path(tempfile.mkdtemp(prefix="level6_apply_test_"))
        self.sandbox_dir = self.tmp / "sandbox"
        self.target_dir = self.tmp / "target"
        self.sandbox_dir.mkdir()
        self.target_dir.mkdir()

    def tearDown(self):
        if os.path.exists(self.config_path):
            os.remove(self.config_path)
        shutil.rmtree(self.tmp, ignore_errors=True)
        # RollbackManager writes snapshots under its own configured
        # sandbox_base_path (default from the test config), not under
        # self.tmp -- clean that up too so tests don't leak state.
        shutil.rmtree(self.coord.rollback.sandbox_root, ignore_errors=True)

    def _pending(self, plan, request_id="req1"):
        return PendingLevel6Apply(
            request_id=request_id,
            plan=plan,
            sandbox_dir=str(self.sandbox_dir),
            target_dir=str(self.target_dir),
            explain="test",
            risk_score=0.1,
        )

    def test_apply_copies_exact_sandbox_bytes_to_target(self):
        (self.sandbox_dir / "add.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
        plan = [{"type": "create_file", "target": "add.py"}]

        result = self.coord.apply(self._pending(plan))

        self.assertEqual(result["status"], "applied")
        written = self.target_dir / "add.py"
        self.assertTrue(written.exists())
        self.assertEqual(written.read_text(encoding="utf-8"), "def add(a, b):\n    return a + b\n")

    def test_apply_ast_edit_step_uses_sandbox_content_not_plan_content(self):
        """
        The exact bug this design avoids: an ast_edit step's real final
        content only ever lands in the sandbox file (written by
        ASTFixer via SandboxRunner) -- plan[i] itself has no "content"
        key for ast_edit steps at all. Applying from plan content would
        silently write nothing/garbage; applying from the sandbox is
        correct by construction.
        """
        (self.sandbox_dir / "divide.py").write_text(
            "def divide(a, b):\n    if b == 0:\n        return None\n    return a / b\n",
            encoding="utf-8",
        )
        plan = [{
            "type": "ast_edit",
            "target": "divide.py",
            "spec": {"type": "replace_function", "name": "divide", "code": "..."},
            # deliberately no "content" key, matching real behavior
        }]

        result = self.coord.apply(self._pending(plan))

        self.assertEqual(result["status"], "applied")
        applied_content = (self.target_dir / "divide.py").read_text(encoding="utf-8")
        self.assertIn("if b == 0:", applied_content)

    def test_apply_reverts_everything_on_partial_failure(self):
        """
        Two files in the plan; the second one is missing from the
        sandbox (simulating an incomplete/corrupted verified state).
        The first file must NOT be left applied -- a partial apply is
        exactly the half-broken state the snapshot/revert exists to
        prevent.
        """
        (self.sandbox_dir / "good.py").write_text("x = 1\n", encoding="utf-8")
        # "missing.py" deliberately not created in the sandbox.
        plan = [
            {"type": "create_file", "target": "good.py"},
            {"type": "create_file", "target": "missing.py"},
        ]
        pre_existing = self.target_dir / "unrelated.txt"
        pre_existing.write_text("pre-existing content\n", encoding="utf-8")

        result = self.coord.apply(self._pending(plan))

        self.assertEqual(result["status"], "apply_failed")
        self.assertTrue(result.get("reverted"))
        # The partially-written file must be gone after revert...
        self.assertFalse((self.target_dir / "good.py").exists())
        # ...and whatever was already there before the apply attempt
        # must be exactly as it was.
        self.assertEqual(pre_existing.read_text(encoding="utf-8"), "pre-existing content\n")

    def test_apply_refuses_to_write_anything_if_snapshot_fails(self):
        (self.sandbox_dir / "add.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
        plan = [{"type": "create_file", "target": "add.py"}]
        pending = self._pending(plan)

        original_create_snapshot = self.coord.rollback.create_snapshot
        self.coord.rollback.create_snapshot = lambda *a, **k: False
        try:
            result = self.coord.apply(pending)
        finally:
            self.coord.rollback.create_snapshot = original_create_snapshot

        self.assertEqual(result["status"], "apply_failed")
        self.assertFalse((self.target_dir / "add.py").exists())

    def test_apply_skips_steps_with_no_target_or_wrong_type(self):
        (self.sandbox_dir / "add.py").write_text("x = 1\n", encoding="utf-8")
        plan = [
            {"type": "create_file", "target": "add.py"},
            {"type": "create_file"},  # no target -- must be skipped, not crash
            {"type": "read_unread", "target": "irrelevant.py"},  # not an apply-eligible type
        ]

        result = self.coord.apply(self._pending(plan))

        self.assertEqual(result["status"], "applied")
        self.assertEqual(len(result["files"]), 1)


if __name__ == "__main__":
    unittest.main()
