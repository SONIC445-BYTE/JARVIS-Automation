"""
Adversarial tests for the Level6 sandbox boundary (D18).

THE STANDARD THESE TESTS ARE HELD TO
------------------------------------
Every test here makes a real child process genuinely attempt an escape and
asserts the attempt genuinely failed. None of them assert that a config value
is set, that a flag is True, or that a dataclass reports a boundary -- D18
exists precisely because `JARVIS_SANDBOX_NETWORK=0` was a value nobody read,
and a test asserting that value would have passed while the boundary did not
exist.

CONTROLS ARE MANDATORY HERE. A test that says "the child could not reach the
network" proves nothing if the machine is offline; a test that says "the child
could not read the file" proves nothing if the file was never created. Each
escape test therefore also establishes that the thing being denied is
genuinely available to an uncontained process. Where the control cannot be
established the test SKIPS with a stated reason rather than passing.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import time
import unittest
from pathlib import Path

from AgentCore.level6 import sandbox_env as se
from AgentCore.level6.sandbox_isolation import (ContainedLauncher, JobLimits,
                                                minimal_env, firewall_state,
                                                verify_containment)
from AgentCore.level6.sandbox_runner import SandboxRunner

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRATCH = REPO_ROOT / "projects" / "_isolation_tests"


def run_in_sandbox(env, workspace, code, argv=(), timeout=90, **kw):
    """Run `code` as a real contained child and return (result, stdout)."""
    os.makedirs(workspace, exist_ok=True)
    script = Path(workspace) / "_probe.py"
    script.write_text(code, encoding="utf-8")
    launcher = ContainedLauncher(workspace=str(workspace),
                                 readonly_paths=[str(env.root)],
                                 stat_only_paths=[str(Path(workspace).parent)],
                                 **kw)
    res = launcher.run([str(env.python_exe), str(script), *map(str, argv)],
                       cwd=str(workspace), env=minimal_env(str(workspace)),
                       timeout=timeout)
    return res, (res.stdout or "")


class IsolationTestBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.name != "nt":
            raise unittest.SkipTest("the Level6 sandbox boundary is Windows-specific")
        cls.env = se.provision()
        if not cls.env.ok:
            raise unittest.SkipTest("sandbox environment could not be provisioned")
        SCRATCH.mkdir(parents=True, exist_ok=True)

    def workspace(self, name):
        ws = SCRATCH / name
        shutil.rmtree(ws, ignore_errors=True)
        ws.mkdir(parents=True, exist_ok=True)
        return ws


# ---------------------------------------------------------------------------
# 1. The interpreter is genuinely a different interpreter
# ---------------------------------------------------------------------------

class TestSeparateInterpreter(IsolationTestBase):

    def test_child_prefix_differs_from_host(self):
        res, out = run_in_sandbox(self.env, self.workspace("prefix"),
                                  "import sys;print(sys.prefix)")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertNotEqual(out.strip(), sys.prefix)
        self.assertTrue(out.strip().startswith(str(self.env.root)), out)

    def test_host_installed_package_is_genuinely_absent(self):
        """PyYAML is installed on the host and is on the manifest's refused list.

        Control first: if the host could not import yaml, the absence in the
        child would prove nothing at all.
        """
        import importlib.util
        if importlib.util.find_spec("yaml") is None:
            self.skipTest("control failed: yaml is not installed on the host either, "
                          "so its absence in the sandbox proves nothing")
        res, out = run_in_sandbox(
            self.env, self.workspace("noyaml"),
            "import importlib.util as u\n"
            "print('yaml:', u.find_spec('yaml') is not None)\n"
            "try:\n"
            "    import yaml; print('IMPORTED', yaml.__file__)\n"
            "except Exception as e:\n"
            "    print('import failed:', type(e).__name__)\n")
        self.assertIn("yaml: False", out)
        self.assertIn("import failed: ModuleNotFoundError", out)
        self.assertNotIn("IMPORTED", out)

    def test_vetted_package_is_present(self):
        """The boundary must not be 'nothing works'. pytest and requests are vetted."""
        res, out = run_in_sandbox(
            self.env, self.workspace("vetted"),
            "import pytest, requests, bs4, numpy\n"
            "print('ok', pytest.__version__, requests.__version__)\n")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("ok", out)

    def test_host_mocked_layer_is_a_stub_not_the_real_module(self):
        res, out = run_in_sandbox(
            self.env, self.workspace("mocked"),
            "import win32api\n"
            "print('stub:', getattr(type(win32api), '__sandbox_stub__', False))\n"
            "print('callable:', win32api.GetUserName() is not None)\n")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("stub: True", out)


# ---------------------------------------------------------------------------
# 2. Filesystem: the child cannot read the host
# ---------------------------------------------------------------------------

class TestFilesystemBoundary(IsolationTestBase):

    def setUp(self):
        self.canary = Path(os.path.expanduser("~")) / "_jarvis_d18_canary.txt"
        self.canary.write_text("CANARY-D18-SHOULD-NOT-BE-READABLE", encoding="utf-8")
        self.escape = REPO_ROOT / "_sandbox_escape_canary.txt"

    def tearDown(self):
        for p in (self.canary, self.escape):
            try:
                p.unlink()
            except OSError:
                pass

    def test_child_cannot_read_a_real_host_file(self):
        # Control: the host process can read it. If this fails the test below
        # would be vacuous.
        self.assertEqual(self.canary.read_text(encoding="utf-8"),
                         "CANARY-D18-SHOULD-NOT-BE-READABLE")

        res, out = run_in_sandbox(
            self.env, self.workspace("readhost"),
            "import sys\n"
            "try:\n"
            "    print('READ:', open(sys.argv[1], encoding='utf-8').read())\n"
            "except Exception as e:\n"
            "    print('blocked:', type(e).__name__, e)\n",
            argv=[self.canary])
        self.assertNotIn("CANARY-D18", out, "the sandbox READ a host file")
        self.assertIn("blocked: PermissionError", out)

    def test_child_cannot_list_the_user_profile(self):
        home = os.path.expanduser("~")
        self.assertGreater(len(os.listdir(home)), 0)  # control
        res, out = run_in_sandbox(
            self.env, self.workspace("listhome"),
            "import os,sys\n"
            "try:\n"
            "    print('LISTED', len(os.listdir(sys.argv[1])))\n"
            "except Exception as e:\n"
            "    print('blocked:', type(e).__name__)\n",
            argv=[home])
        self.assertNotIn("LISTED", out)
        self.assertIn("blocked: PermissionError", out)

    def test_child_cannot_read_the_immutable_tier(self):
        """4.4b's gating table: generated code may never touch the immutable tier.

        The strongest version of that is that it cannot even read the files.
        """
        gate = REPO_ROOT / "AgentCore" / "resolution_gate.py"
        if not gate.exists():
            self.skipTest("resolution_gate.py not found; nothing to prove")
        self.assertGreater(len(gate.read_text(encoding="utf-8", errors="replace")), 0)

        res, out = run_in_sandbox(
            self.env, self.workspace("immutable"),
            "import sys\n"
            "for mode in ('r', 'a'):\n"
            "    try:\n"
            "        open(sys.argv[1], mode, encoding='utf-8')\n"
            "        print('OPENED', mode)\n"
            "    except Exception as e:\n"
            "        print('blocked', mode, type(e).__name__)\n",
            argv=[gate])
        self.assertNotIn("OPENED", out)
        self.assertEqual(out.count("blocked"), 2, out)

    def test_child_cannot_write_into_the_repository(self):
        res, out = run_in_sandbox(
            self.env, self.workspace("writerepo"),
            "import sys\n"
            "try:\n"
            "    open(sys.argv[1], 'w').write('escaped')\n"
            "    print('WROTE')\n"
            "except Exception as e:\n"
            "    print('blocked:', type(e).__name__)\n",
            argv=[self.escape])
        self.assertFalse(self.escape.exists(),
                         "generated code wrote a file into the repository")
        self.assertIn("blocked:", out)

    def test_child_can_write_inside_its_own_workspace(self):
        """The boundary has to permit the sandbox's actual job, or it is useless."""
        ws = self.workspace("writeown")
        res, out = run_in_sandbox(
            self.env, ws,
            "open('inside.txt','w').write('fine')\nprint('ok')\n")
        self.assertIn("ok", out)
        self.assertTrue((ws / "inside.txt").exists())


# ---------------------------------------------------------------------------
# 3. Network
# ---------------------------------------------------------------------------

class TestNetworkBoundary(IsolationTestBase):

    CODE = (
        "import socket\n"
        "socket.setdefaulttimeout(6)\n"
        "try:\n"
        "    s=socket.create_connection(('1.1.1.1',443),timeout=6); s.close()\n"
        "    print('TCP: CONNECTED')\n"
        "except Exception as e:\n"
        "    print('TCP blocked:', type(e).__name__, e)\n"
        "try:\n"
        "    print('DNS: RESOLVED', socket.gethostbyname('example.com'))\n"
        "except Exception as e:\n"
        "    print('DNS blocked:', type(e).__name__)\n"
    )

    def _control_has_network(self):
        """Run the SAME sandbox interpreter with NO AppContainer.

        This is what makes the denial test non-vacuous: it proves the machine
        has working egress and that the same binary reaches it when the
        boundary is removed.

        EITHER signal counts. Measured on this machine: outbound TCP to
        1.1.1.1:443 intermittently times out at the network level while DNS
        resolves fine. Requiring both would make the control -- and therefore
        this whole test -- flaky for a reason that has nothing to do with the
        boundary being tested.
        """
        res, out = run_in_sandbox(self.env, self.workspace("netcontrol"),
                                  self.CODE, use_appcontainer=False,
                                  use_restricted_token=False)
        return ("TCP: CONNECTED" in out or "DNS: RESOLVED" in out), out

    def test_outbound_tcp_and_dns_are_denied_by_the_os(self):
        has_net, control_out = self._control_has_network()
        if not has_net:
            self.skipTest(
                "control failed: the same interpreter could not reach the network "
                "even uncontained, so a blocked result would prove nothing. "
                f"Control output: {control_out.strip()!r}")

        res, out = run_in_sandbox(self.env, self.workspace("netdeny"), self.CODE)
        self.assertNotIn("TCP: CONNECTED", out)
        self.assertNotIn("DNS: RESOLVED", out)
        # WinError 10013 is WSAEACCES from the Windows Filtering Platform --
        # the OS refusing the socket, not a timeout or a dead route.
        self.assertIn("10013", out,
                      f"expected WFP denial (WinError 10013), got: {out!r}")

    def test_socket_denial_survives_a_deliberate_bypass_attempt(self):
        """A Python-level monkeypatch of `socket` would be undone in one line.

        This test IS that line. It rebuilds the socket from scratch through
        the lowest-level interface available and confirms the OS still refuses,
        which is the difference between a real boundary and a decorative one.
        """
        has_net, _ = self._control_has_network()
        if not has_net:
            self.skipTest("control failed: no network available uncontained")

        res, out = run_in_sandbox(
            self.env, self.workspace("netbypass"),
            "import socket, importlib\n"
            "importlib.reload(socket)\n"
            "s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)\n"
            "s.settimeout(6)\n"
            "try:\n"
            "    s.connect(('1.1.1.1', 443)); print('RAW CONNECTED')\n"
            "except Exception as e:\n"
            "    print('raw blocked:', type(e).__name__, e)\n"
            "try:\n"
            "    import urllib.request\n"
            "    urllib.request.urlopen('http://1.1.1.1', timeout=6)\n"
            "    print('URLLIB CONNECTED')\n"
            "except Exception as e:\n"
            "    print('urllib blocked:', type(e).__name__)\n")
        self.assertNotIn("RAW CONNECTED", out)
        self.assertNotIn("URLLIB CONNECTED", out)
        self.assertIn("10013", out)

    def test_loopback_is_also_denied_which_is_a_functional_cost(self):
        """Documented honestly: this is a LIMITATION, not a win.

        A generated adapter test that stands up a local HTTP server cannot work
        in-sandbox. Exempting loopback for an AppContainer needs
        `CheckNetIsolation`, which needs Administrator.
        """
        srv = socket.socket()
        srv.bind(("127.0.0.1", 0))
        srv.listen(5)
        port = srv.getsockname()[1]
        try:
            # control: loopback genuinely works for an uncontained process
            c = socket.create_connection(("127.0.0.1", port), timeout=5)
            c.close()

            res, out = run_in_sandbox(
                self.env, self.workspace("loopback"),
                "import socket,sys\n"
                "try:\n"
                "    socket.create_connection(('127.0.0.1',int(sys.argv[1])),timeout=5)\n"
                "    print('LOOPBACK CONNECTED')\n"
                "except Exception as e:\n"
                "    print('loopback blocked:', type(e).__name__)\n",
                argv=[port])
            self.assertNotIn("LOOPBACK CONNECTED", out)
            self.assertIn("loopback blocked", out)
        finally:
            srv.close()


# ---------------------------------------------------------------------------
# 4. Environment leakage
# ---------------------------------------------------------------------------

class TestEnvironmentLeakage(IsolationTestBase):

    def test_host_environment_is_not_inherited(self):
        os.environ["JARVIS_D18_SECRET"] = "sk-should-never-reach-the-sandbox"
        try:
            res, out = run_in_sandbox(
                self.env, self.workspace("envleak"),
                "import os,json\n"
                "print(json.dumps(sorted(os.environ)))\n"
                "print('SECRET' if 'JARVIS_D18_SECRET' in os.environ else 'no-secret')\n")
            self.assertIn("no-secret", out)
            self.assertNotIn("sk-should-never-reach", out)
            names = json.loads(out.strip().splitlines()[0])
            for leaky in ("USERNAME", "COMPUTERNAME", "OneDrive", "PATHEXT"):
                self.assertNotIn(leaky, names)
        finally:
            os.environ.pop("JARVIS_D18_SECRET", None)

    def test_jarvis_sandbox_network_variable_is_gone(self):
        """D18's sharpest half: a variable shaped like a control that nothing read.

        It was deleted rather than kept. This test fails if anyone reintroduces
        it, in the sandbox source or in the child's environment.
        """
        # The name is allowed -- required, even -- in prose explaining why it
        # was removed. What must never come back is an ASSIGNMENT. Checked by
        # AST rather than by substring so that documenting the defect does not
        # trip the guard against the defect.
        import ast as _ast
        offenders = []
        for src in sorted((REPO_ROOT / "AgentCore" / "level6").glob("sandbox_*.py")):
            tree = _ast.parse(src.read_text(encoding="utf-8"))
            for node in _ast.walk(tree):
                targets = []
                if isinstance(node, _ast.Assign):
                    targets = node.targets
                elif isinstance(node, _ast.AnnAssign):
                    targets = [node.target]
                for t in targets:
                    if (isinstance(t, _ast.Subscript)
                            and isinstance(t.slice, _ast.Constant)
                            and t.slice.value == "JARVIS_SANDBOX_NETWORK"):
                        offenders.append(f"{src.name}:{node.lineno}")
        self.assertEqual(offenders, [],
                         f"JARVIS_SANDBOX_NETWORK is being set again at {offenders}; "
                         "it enforced nothing and was deleted for that reason")

        res, out = run_in_sandbox(
            self.env, self.workspace("novar"),
            "import os\n"
            "print('PRESENT' if 'JARVIS_SANDBOX_NETWORK' in os.environ else 'absent')\n")
        self.assertIn("absent", out)


# ---------------------------------------------------------------------------
# 5. Job object: resources and lifetime
# ---------------------------------------------------------------------------

class TestJobObject(IsolationTestBase):

    def test_active_process_limit_stops_a_fork_bomb(self):
        ws = self.workspace("forkbomb")
        res, out = run_in_sandbox(
            self.env, ws,
            "import subprocess, sys\n"
            "n = 0\n"
            "for i in range(60):\n"
            "    try:\n"
            "        subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)'])\n"
            "        n += 1\n"
            "    except Exception as e:\n"
            "        print('spawned', n, 'then blocked:', type(e).__name__, e)\n"
            "        break\n"
            "else:\n"
            "    print('spawned all', n, 'NO LIMIT')\n",
            timeout=120)
        self.assertNotIn("NO LIMIT", out)
        self.assertIn("then blocked", out)

    def test_nothing_survives_the_run(self):
        """kill-on-job-close: a grandchild outliving the run is an escape."""
        ws = self.workspace("survivor")
        marker = ws / "survivor_ran.txt"
        code = (
            "import subprocess, sys, os\n"
            "target = os.path.join(os.getcwd(), 'survivor_ran.txt')\n"
            "subprocess.Popen([sys.executable, '-c',\n"
            "  \"import time,sys;time.sleep(8);open(sys.argv[1],'w').write('survived')\",\n"
            "  target])\n"
            "print('spawned grandchild')\n")
        res, out = run_in_sandbox(self.env, ws, code, timeout=30)
        self.assertIn("spawned grandchild", out)
        time.sleep(14)
        self.assertFalse(marker.exists(),
                         "a grandchild outlived the sandbox run and wrote a file")

    def test_timeout_terminates_the_whole_tree(self):
        ws = self.workspace("timeout")
        res, out = run_in_sandbox(
            self.env, ws,
            "import time\nprint('sleeping', flush=True)\ntime.sleep(600)\n",
            timeout=6)
        self.assertTrue(res.timed_out)


# ---------------------------------------------------------------------------
# 6. Vetted dependency set enforcement
# ---------------------------------------------------------------------------

class TestVettedSetEnforcement(IsolationTestBase):

    def setUp(self):
        self.base = SCRATCH / "runner"
        shutil.rmtree(self.base, ignore_errors=True)
        self.runner = SandboxRunner(str(self.base))

    def test_unvetted_import_fails_closed_before_any_execution(self):
        """The generated code must not run at all -- not run and then fail."""
        plan = [{"type": "create_file", "target": "adapter.py",
                 "content": "import yaml\n\ndef go():\n    return yaml\n"}]
        tests = [{"path": "test_adapter.py",
                  "content": ("import pathlib\n"
                              "pathlib.Path('EXECUTED.txt').write_text('ran')\n"
                              "def test_go():\n    assert True\n")}]
        result = self.runner.run_plan(plan, tests, "blocked")

        self.assertFalse(result["passed"])
        self.assertTrue(result.get("blocked"))
        self.assertFalse(result.get("executed"))
        self.assertEqual(result["block_reason"], "unvetted_import")
        self.assertIn("yaml", result["stderr"])
        self.assertIn("refused list", result["stderr"])
        marker = Path(result["sandbox_dir"]) / "EXECUTED.txt"
        self.assertFalse(marker.exists(),
                         "the blocked plan's test file executed anyway")

    def test_unavailable_vetted_package_is_not_substituted(self):
        """opencv-python-headless is vetted but absent from the host.

        The host HAS opencv-python, which provides the same `cv2` import. The
        sandbox must not quietly substitute it -- 'no substituting a similar
        package' is an explicit rule in the design note.
        """
        if "opencv-python-headless" not in self.runner.environment().unavailable:
            self.skipTest("opencv-python-headless is available on this host")
        import importlib.util
        self.assertIsNotNone(importlib.util.find_spec("cv2"),
                             "control: host must have cv2 for this to mean anything")

        plan = [{"type": "create_file", "target": "vision.py", "content": "import cv2\n"}]
        result = self.runner.run_plan(plan, [{"path": "test_v.py",
                                              "content": "def test_x():\n    assert True\n"}],
                                      "nocv")
        self.assertTrue(result.get("blocked"))
        self.assertIn("cv2", result["stderr"])
        self.assertIn("NOT installed on this host", result["stderr"])

    def test_vetted_imports_are_allowed_through(self):
        plan = [{"type": "create_file", "target": "api.py",
                 "content": "import requests, bs4, json\n\ndef ok():\n    return True\n"}]
        tests = [{"path": "test_api.py",
                  "content": "from api import ok\n\ndef test_ok():\n    assert ok()\n"}]
        result = self.runner.run_plan(plan, tests, "allowed")
        self.assertTrue(result["passed"], result.get("stderr"))
        self.assertTrue(result["executed"])
        self.assertTrue(result["containment"]["network_denied"])

    def test_static_check_is_evadable_but_the_absence_is_not(self):
        """The honest limitation, pinned by a test so it cannot be forgotten.

        `importlib.import_module("yaml")` is invisible to an AST import scan.
        It passes the static check -- and then fails anyway, because the
        package is genuinely not in the sandbox. The scanner is a diagnostic;
        the absence is the boundary.
        """
        plan = [{"type": "create_file", "target": "sneaky.py",
                 "content": ("import importlib\n\n"
                             "def load():\n"
                             "    return importlib.import_module('ya' + 'ml')\n")}]
        tests = [{"path": "test_sneaky.py",
                  "content": ("from sneaky import load\n\n"
                              "def test_load():\n"
                              "    try:\n"
                              "        load()\n"
                              "        assert False, 'IMPORTED YAML'\n"
                              "    except ModuleNotFoundError:\n"
                              "        pass\n")}]
        result = self.runner.run_plan(plan, tests, "sneaky")
        # It got past the static check...
        self.assertFalse(result.get("blocked"), "static check unexpectedly caught it")
        self.assertTrue(result["executed"])
        # ...and still could not import the package.
        self.assertTrue(result["passed"], result.get("stdout", "") + result.get("stderr", ""))


# ---------------------------------------------------------------------------
# 7. Refusal to run without the boundary
# ---------------------------------------------------------------------------

class TestFailClosed(IsolationTestBase):

    def test_launcher_reports_missing_layers_rather_than_pretending(self):
        ws = self.workspace("degraded")
        launcher = ContainedLauncher(workspace=str(ws), use_appcontainer=False)
        self.assertFalse(launcher.plan.appcontainer)
        self.assertFalse(launcher.plan.network_denied,
                         "network_denied must be False without an AppContainer")
        self.assertIn("appcontainer", launcher.missing(["appcontainer"]))
        self.assertIn("appcontainer", launcher.plan.reasons)

    def test_runner_refuses_when_the_environment_cannot_be_provisioned(self):
        base = SCRATCH / "noenv"
        shutil.rmtree(base, ignore_errors=True)
        runner = SandboxRunner(str(base), manifest_path=str(SCRATCH / "does_not_exist.yaml"))
        result = runner.run_plan(
            [{"type": "create_file", "target": "a.py", "content": "x=1\n"}],
            [{"path": "test_a.py", "content": "def test_a():\n    assert True\n"}],
            "noenv")
        self.assertFalse(result["passed"])
        self.assertFalse(result["executed"])
        self.assertIn("Refusing to run generated code against the host interpreter",
                      result["error"])


# ---------------------------------------------------------------------------
# 8. The self-test that the runner's claims are measured
# ---------------------------------------------------------------------------

class TestVerifyContainment(IsolationTestBase):

    def test_verify_containment_measures_rather_than_asserts(self):
        ws = self.workspace("verify")
        report = verify_containment(str(self.env.python_exe), str(ws),
                                    readonly_paths=[str(self.env.root)])
        self.assertTrue(report["verdict"]["measured"],
                        f"probe produced no output: {report}")
        v = report["verdict"]
        self.assertTrue(v["host_file_read_blocked"])
        self.assertTrue(v["home_listing_blocked"])
        self.assertTrue(v["separate_prefix"])
        self.assertTrue(v["host_only_package_absent"])
        print("\nverify_containment ->", json.dumps(report["verdict"], indent=2))
        print("firewall ->", report["firewall"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
