"""
Level6 sandbox runner.

WHAT CHANGED, AND WHY (D18)
---------------------------
This file used to run `subprocess.run([sys.executable, "-m", "pytest"],
cwd=temp_dir)`: the HOST interpreter, against the HOST's site-packages,
isolated by nothing but a temporary working directory. It also set
`env["JARVIS_SANDBOX_NETWORK"] = "0"` -- a name that reads like a network
control, written in exactly one place in the repo and read in none. Nothing
enforced it. That variable HAS BEEN DELETED rather than kept, because a flag
shaped like a control that enforces nothing is worse than an honest absence:
it invites the next reader to assume a boundary exists.

WHAT IS ENFORCED NOW, AND BY WHAT
---------------------------------
  separate interpreter  sandbox_env.provision() -- a standalone Python tree
                        with its own site-packages, containing only the
                        manifest's vetted set. The host's packages are
                        genuinely absent, not merely discouraged.
  filesystem            AppContainer (LowBox token) + a restricted token whose
                        user SID is deny-only. The child cannot read the user
                        profile -- including this repository, `.env`, and any
                        credential store under it.
  network               AppContainer with NO capabilities. The Windows
                        Filtering Platform denies outbound sockets because the
                        process holds neither `internetClient` nor
                        `privateNetworkClientServer`. This is OS enforcement,
                        not a Python-level monkeypatch of `socket` -- which
                        generated code owning its own process could undo in
                        one line.
  process/resource      A job object: kill-on-job-close, active-process cap,
                        per-process memory cap, CPU-time caps, UI restrictions.
  vetted set            A static AST import check that fails closed BEFORE
                        anything executes, backed by the package genuinely not
                        being present.

WHAT IS STILL NOT ISOLATED
--------------------------
  * NOT A CONTAINER. Same kernel, same filesystem namespace, same network
    stack. A kernel or WFP vulnerability defeats every layer above at once.
    Docker, WSL and Windows Sandbox are all unavailable on this machine and
    none can be installed without Administrator.
  * NO SUPPLY-CHAIN GUARANTEE. Packages are copied from the host install. No
    hashes, no digest-pinned base, no provenance. See sandbox_env.py.
  * LOOPBACK IS ALSO DENIED, which is a functional cost rather than a gap: a
    generated test that stands up a local HTTP server to exercise an adapter
    cannot work in-sandbox. Exempting loopback for an AppContainer requires
    `CheckNetIsolation`, which requires Administrator.
  * THE RESOLUTIONGATE REMAINS THE PRIMARY CONTROL (JARVIS_BLUEPRINT 4.4b).
    This is defence-in-depth. It should not be called "secure", and a green
    sandbox run is evidence, not proof.
"""

from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from .ast_fixer import ASTFixer
from . import sandbox_env as _env_mod
from .sandbox_isolation import ContainedLauncher, JobLimits, minimal_env

# The layers a run must actually have before generated code is executed.
# Missing any of them is a refusal, not a warning -- see `allow_degraded`.
REQUIRED_CONTAINMENT = ("separate_interpreter", "appcontainer",
                        "restricted_token", "job_object")

_PYTEST_INI = (
    "[pytest]\n"
    # Pins rootdir to the sandbox. Without it pytest walks upward looking for a
    # config file and reaches directories the contained child is denied, which
    # surfaces as a confusing PermissionError during collection rather than as
    # a test result.
    "testpaths = .\n"
    "addopts = -p no:cacheprovider\n"
)


class SandboxRunner:
    def __init__(self,
                 base_path: str = "projects/sandbox_level6",
                 ast_fixer: Optional[ASTFixer] = None,
                 manifest_path: Optional[str] = None,
                 allow_degraded: bool = False,
                 timeout: float = 120.0,
                 limits: Optional[JobLimits] = None):
        # Absolute, deliberately. The runner passes this path to the child as
        # --rootdir while ALSO setting cwd to it; a relative base_path
        # double-prepends and pytest looks for
        # <sandbox>/projects/test_sandbox/<sandbox>. That is the identical
        # bug shape the Phase A comment below records, rediscovered when the
        # subprocess call was replaced -- so it is pinned here at the source
        # rather than patched at each use site.
        self.base_path = Path(base_path).resolve()
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.ast_fixer = ast_fixer or ASTFixer()
        self.manifest_path = manifest_path
        self.allow_degraded = allow_degraded
        self.timeout = timeout
        self.limits = limits or JobLimits()
        self._env = None
        self._env_error: Optional[str] = None

    # -- environment -------------------------------------------------------

    def environment(self):
        """Provision (once) the vetted sandbox interpreter. Cached across runs."""
        if self._env is None and self._env_error is None:
            try:
                man = _env_mod.load_manifest(self.manifest_path) if self.manifest_path \
                    else _env_mod.load_manifest()
                self._env = _env_mod.provision(man)
            except Exception as exc:
                self._env_error = f"{type(exc).__name__}: {exc}"
        return self._env

    # -- main entry point --------------------------------------------------

    def run_plan(self, plan: List[Dict], tests: List[Dict],
                 snapshot_id: str) -> Dict[str, Any]:
        """Execute a plan in a fresh, contained sandbox instance."""
        sandbox_id = f"{snapshot_id}_{uuid.uuid4().hex[:8]}"
        sandbox_dir = self.base_path / sandbox_id

        logs: List[str] = []
        try:
            sandbox_dir.mkdir(parents=True, exist_ok=True)

            written: Dict[str, str] = {}
            for item in plan:
                if item["type"] in ("create_file", "update_file"):
                    p = sandbox_dir / item["target"]
                    p.parent.mkdir(parents=True, exist_ok=True)
                    content = item.get("content", "")
                    p.write_text(content, encoding="utf-8")
                    written[item["target"]] = content
                    logs.append(f"Wrote {item['target']}")
                elif item["type"] == "ast_edit":
                    # Phase C: this used to be a pure no-op -- the comment
                    # claimed "handled by ASTFixer in real flow" but nothing
                    # here ever called it, so an ast_edit plan step silently
                    # did nothing at all. Reads whatever's already at the
                    # target in this sandbox (a prior create_file step in the
                    # same plan, or "" if this is the first step touching that
                    # path), applies the transform, writes the result.
                    p = sandbox_dir / item["target"]
                    p.parent.mkdir(parents=True, exist_ok=True)
                    current = p.read_text(encoding="utf-8") if p.exists() else ""
                    new_content = self.ast_fixer.apply_transform(
                        current, item.get("spec", {}))
                    p.write_text(new_content, encoding="utf-8")
                    written[item["target"]] = new_content
                    logs.append(f"AST-edited {item['target']}")

            for test in tests:
                p = sandbox_dir / test["path"]
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(test["content"], encoding="utf-8")
                written[test["path"]] = test["content"]
                logs.append(f"Wrote test {test['path']}")

            env = self.environment()
            if env is None or not env.ok:
                return self._fail(
                    sandbox_dir, logs,
                    "Sandbox environment could not be provisioned: "
                    f"{self._env_error or 'unknown error'}. Refusing to run "
                    "generated code against the host interpreter.")

            # -- vetted-set check, before anything executes --------------
            local_modules = self._local_module_names(written)
            py_files = {k: v for k, v in written.items() if k.endswith(".py")}
            violations = _env_mod.check_imports(py_files, env, local_modules)
            if violations:
                block = _env_mod.format_block(violations, env)
                logs.append(block)
                return {
                    "passed": False,
                    "blocked": True,
                    "block_reason": "unvetted_import",
                    "violations": [v.__dict__ for v in violations],
                    "stdout": "",
                    "stderr": block,
                    "sandbox_dir": str(sandbox_dir),
                    "logs": logs,
                    "containment": None,
                    "executed": False,
                }

            test_files = [t["path"] for t in tests]
            if not test_files:
                return {
                    "passed": True,
                    "logs": logs,
                    "message": "No tests to run",
                    "sandbox_dir": str(sandbox_dir),
                    "executed": False,
                }

            (sandbox_dir / "pytest.ini").write_text(_PYTEST_INI, encoding="utf-8")

            launcher = ContainedLauncher(
                workspace=str(sandbox_dir),
                readonly_paths=[str(env.root)],
                stat_only_paths=[str(self.base_path)],
                limits=self.limits,
            )
            # Only the runner knows the interpreter was provisioned separately;
            # the launcher just runs whatever argv it is handed.
            launcher.plan.separate_interpreter = True
            missing = launcher.missing(
                [c for c in REQUIRED_CONTAINMENT if c != "separate_interpreter"])
            if missing and not self.allow_degraded:
                reasons = "; ".join(
                    f"{m}: {launcher.plan.reasons.get(m, 'unavailable')}"
                    for m in missing)
                return self._fail(
                    sandbox_dir, logs,
                    "Refusing to execute generated code: required containment "
                    f"layers unavailable -> {reasons}. Pass allow_degraded=True "
                    "to run anyway, which will be recorded in the result.",
                    containment=launcher.plan.as_dict())

            cmd = [str(env.python_exe), "-m", "pytest", "-c", "pytest.ini",
                   "--rootdir", str(sandbox_dir)] + test_files
            result = launcher.run(cmd, cwd=str(sandbox_dir),
                                  env=minimal_env(str(sandbox_dir)),
                                  timeout=self.timeout)

            containment = result.containment.as_dict()
            containment["degraded"] = bool(missing)
            containment["required_but_missing"] = missing

            if result.launch_error:
                return self._fail(sandbox_dir, logs,
                                  f"Contained launch failed: {result.launch_error}",
                                  containment=containment)

            # Found live (Phase B verification): the Planner's LLM sometimes
            # writes tests as bare top-level `assert` statements rather than
            # `def test_...()` functions -- valid Python, genuinely exercised
            # at import time, but not something pytest's collector recognizes
            # as a "test item". Confirmed empirically: such a file returns
            # pytest exit code 5 ("no tests ran") when the assert passes
            # cleanly at import, and exit code 2 ("error during collection")
            # when it raises. Treating 5 as a failure (the old `== 0` check)
            # was a false negative that discarded genuinely-correct fixes and
            # burned the debug loop's entire iteration budget on code that
            # already worked.
            passed = (not result.timed_out) and result.returncode in (0, 5)

            logs.append(result.stdout)
            logs.append(result.stderr)

            return {
                "passed": passed,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
                "timed_out": result.timed_out,
                "sandbox_dir": str(sandbox_dir),
                "logs": logs,
                "containment": containment,
                "executed": True,
            }

        except Exception as exc:
            return {
                "passed": False,
                "error": str(exc),
                "logs": logs,
                "sandbox_dir": str(sandbox_dir),
                "executed": False,
            }

    # -- helpers -----------------------------------------------------------

    @staticmethod
    def _local_module_names(written: Dict[str, str]) -> Set[str]:
        """Top-level importable names created by the plan itself.

        `from add import add` must not be flagged as an unvetted import when
        the same plan just wrote add.py into the sandbox.
        """
        names: Set[str] = set()
        for path in written:
            parts = Path(path).parts
            if not parts:
                continue
            head = parts[0]
            names.add(head[:-3] if head.endswith(".py") else head)
        return names

    @staticmethod
    def _fail(sandbox_dir: Path, logs: List[str], message: str,
              containment: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        logs.append(message)
        return {
            "passed": False,
            "error": message,
            "stdout": "",
            "stderr": message,
            "sandbox_dir": str(sandbox_dir),
            "logs": logs,
            "containment": containment,
            "executed": False,
        }
