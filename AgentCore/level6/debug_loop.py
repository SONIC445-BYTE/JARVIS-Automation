import re
import time
from typing import Dict, Any, List, Optional

class DebugLoop:
    def __init__(self, llm_adapter, sandbox_runner, ast_fixer):
        self.llm = llm_adapter
        self.runner = sandbox_runner
        self.fixer = ast_fixer
        self.max_iterations = 5

    def iterate(self, initial_plan: List[Dict], tests: List[Dict], snapshot_id: str) -> Dict[str, Any]:
        """
        Run the auto-debug loop: execute the plan, and on failure, ask
        the LLM for a corrected full-file replacement for the failing
        implementation file(s), apply it, and retry -- up to
        max_iterations.

        Design decisions:
        - Fixes only ever replace `plan` (implementation) step content,
          never `tests` -- tests are the specification/oracle for this
          request; rewriting them to match broken code would defeat
          their purpose.
        - Fixes are full-file replacements (plan step type
          "update_file" with real `content`), not "ast_edit". ASTFixer
          is still a placeholder (Phase C, not built yet) that only
          handles a trivial "replace_full" case -- routing through it
          here would silently no-op for anything else. Full-file
          replacement is something SandboxRunner already handles
          correctly today, so this doesn't block on Phase C.
        - If a fix iteration doesn't actually change anything in the
          plan (the LLM's response didn't parse, or named a file that
          isn't part of the current plan), the loop stops immediately
          with an honest failure instead of burning the remaining
          iteration budget retrying an unchanged plan against the same
          failure.
        """
        current_plan = [dict(step) for step in initial_plan]
        iterations = 0
        history = []

        while iterations < self.max_iterations:
            iterations += 1

            result = self.runner.run_plan(current_plan, tests, snapshot_id)
            if result.get("passed"):
                return {
                    "status": "success",
                    "iterations": iterations,
                    "final_plan": current_plan,
                    "evidence": result,
                    "history": history,
                }

            failure_log = (result.get("stdout", "") or "") + (result.get("stderr", "") or "")
            history.append({"iteration": iterations, "failure_log": failure_log})

            if iterations >= self.max_iterations:
                break

            fix_content = self._generate_fix(current_plan, tests, failure_log)
            new_plan, changed = self._apply_fix(current_plan, fix_content)
            if not changed:
                return {
                    "status": "failed",
                    "iterations": iterations,
                    "reason": "No usable fix produced",
                    "final_plan": current_plan,
                    "evidence": result,
                    "history": history,
                }
            current_plan = new_plan

        return {
            "status": "failed",
            "iterations": iterations,
            "reason": "Budget exhausted",
            "final_plan": current_plan,
            # Last real attempt's result, for consistency with the
            # other two return paths -- without this, orchestrator.py's
            # sandbox_result went empty specifically on this path (the
            # data existed, just only under "history").
            "evidence": result,
            "history": history,
        }

    def _generate_fix(self, plan: List[Dict], tests: List[Dict], failure_log: str) -> Dict[str, str]:
        """
        Ask the LLM for corrected full-file content for the failing
        implementation file(s). Returns {filename: new_content}, or {}
        if the LLM is unavailable or nothing usable came back.
        """
        if not self.llm:
            return {}

        current_files = "\n".join(
            f"### {step.get('target')}\n{step.get('content', '')}"
            for step in plan
            if step.get("type") in ("create_file", "update_file") and step.get("target")
        )
        test_files = "\n".join(
            f"### {t.get('path')}\n{t.get('content', '')}" for t in tests
        )

        prompt = (
            "The following code failed its tests. Fix the implementation "
            "file(s) so the tests pass. Do not change the tests -- they "
            "are the specification.\n\n"
            f"Current implementation file(s):\n{current_files}\n\n"
            f"Test file(s) (do not modify):\n{test_files}\n\n"
            f"Test failure output:\n{failure_log[-2000:]}\n\n"
            "Respond with ONLY the corrected implementation file(s), using "
            "this exact format for each file:\n"
            "### filename.ext\n"
            "full corrected file content\n"
            "Do not include markdown backticks or explanations."
        )

        try:
            response = self.llm.generate_raw(prompt)
        except Exception as e:
            print(f"[DebugLoop] LLM error generating fix: {e}")
            return {}

        return self._parse_fix_response(response)

    # Same fence-stripping shape as GeneratorHelper._clean_code() and
    # Planner._parse_json() -- a bare fence-marker line, wherever it
    # occurs, not just at the start/end.
    _FENCE_LINE_RE = re.compile(r"(?m)^[ \t]*```[a-zA-Z0-9_+-]*[ \t]*\r?\n?")

    @staticmethod
    def _normalize_path(path: str) -> str:
        return (path or "").strip().replace("\\", "/").lstrip("./")

    def _parse_fix_response(self, response: str) -> Dict[str, str]:
        cleaned = self._FENCE_LINE_RE.sub("", response or "").strip()
        parts = re.split(r"(^|\n)###\s+([^\n]+)\n", cleaned)
        files = {}
        i = 1
        while i < len(parts) - 1:
            fname = self._normalize_path(parts[i + 1])
            content = parts[i + 2] if i + 2 < len(parts) else ""
            if fname:
                files[fname] = content.strip("\n")
            i += 3
        return files

    def _apply_fix(self, plan: List[Dict], fix_content: Dict[str, str]):
        """
        Applies fix_content onto plan, updating only steps whose target
        (path-normalized) matches a fixed filename. Never adds a new
        step for a filename the fix mentions that wasn't already part
        of the plan -- avoids acting on a possibly-hallucinated new
        file. Returns (new_plan, changed: bool).
        """
        new_plan = []
        changed = False
        for step in plan:
            target = self._normalize_path(step.get("target", ""))
            if target in fix_content:
                step = dict(step)
                step["type"] = "update_file"
                step["content"] = fix_content[target]
                changed = True
            new_plan.append(step)
        return new_plan, changed
