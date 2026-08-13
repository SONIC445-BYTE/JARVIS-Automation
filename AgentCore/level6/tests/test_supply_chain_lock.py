"""
Adversarial tests for D19's provisioned-file hash-pin lock.

SAME STANDARD AS D18's test_sandbox_isolation.py: a test that says "tampering
is detected" proves nothing unless a genuine, real host-file mutation is made
and genuinely fails without the check. Every tamper test here mutates a real
file under the host's own site-packages (never a copy, never a mock) and
restores it in `finally`, verifying the restoration too -- a test that leaves
the developer's environment corrupted on failure would be its own defect.
"""

from __future__ import annotations

import importlib.metadata as md
import json
import unittest
from pathlib import Path

from AgentCore.level6 import sandbox_env as se


class TestLockMatchesCurrentHost(unittest.TestCase):
    """The control every tamper test below depends on: a clean bill of health
    BEFORE anything is mutated. If this fails, the tamper tests below prove
    nothing -- they would be "detecting" a mismatch that was already there.
    """

    def test_committed_lock_exists_and_is_readable(self):
        self.assertTrue(se.DEFAULT_LOCK_PATH.exists(),
                        f"no lock committed at {se.DEFAULT_LOCK_PATH}; "
                        f"run generate_lock()+write_lock() and commit it")
        lock = se.load_lock()
        self.assertEqual(lock["schema_version"], se.LOCK_SCHEMA_VERSION)

    def test_lock_matches_host_with_zero_mismatches(self):
        man = se.load_manifest()
        roots = [p["name"] for p in man.image_packages]
        resolved, _missing = se.resolve_closure(roots)
        lock = se.load_lock()
        mismatches = se.verify_lock(resolved, lock)
        self.assertEqual(mismatches, [],
                         "committed lock disagrees with the current host; "
                         "regenerate with generate_lock()+write_lock() if "
                         "this drift is reviewed and intentional")


class TestProvisionRefusesOnMissingOrMalformedLock(unittest.TestCase):

    def test_provision_refuses_when_lock_path_does_not_exist(self):
        with self.assertRaises(se.SupplyChainIntegrityError):
            se.provision(force=True, lock_path=Path(
                "C:/does/not/exist/nowhere.json"))

    def test_load_lock_refuses_a_malformed_lock_file(self, ):
        import tempfile, os
        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        try:
            Path(path).write_text("{not valid json", encoding="utf-8")
            with self.assertRaises(se.SupplyChainIntegrityError):
                se.load_lock(path)
        finally:
            os.remove(path)

    def test_provision_refuses_when_a_resolved_package_is_absent_from_lock(self):
        lock = se.load_lock()
        lock = dict(lock)
        lock["packages"] = dict(lock["packages"])
        removed_key = next(iter(lock["packages"]))
        del lock["packages"][removed_key]

        import tempfile, os
        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        try:
            Path(path).write_text(json.dumps(lock), encoding="utf-8")
            with self.assertRaises(se.SupplyChainIntegrityError) as ctx:
                se.provision(force=True, lock_path=path)
            self.assertIn("not present in the lock", str(ctx.exception))
        finally:
            os.remove(path)


class TestProvisionRefusesOnRealHostTamper(unittest.TestCase):
    """The real control-arm test: mutate an actual file under the host's own
    site-packages (not a copy), confirm `provision()` genuinely refuses
    BEFORE building or copying anything, then restore the original bytes and
    confirm the restoration is exact.
    """

    def test_tampering_a_real_installed_dist_info_file_is_detected(self):
        dist = md.distribution("packaging")
        base = Path(dist.locate_file(""))
        target = base / "packaging-25.0.dist-info" / "INSTALLER"
        self.assertTrue(target.exists(),
                        "test targets a file that must exist on this host; "
                        "if packaging's dist-info layout changed, point this "
                        "at another real file rather than skip silently")
        original = target.read_bytes()
        try:
            target.write_bytes(b"tampered-by-adversarial-test\n")
            with self.assertRaises(se.SupplyChainIntegrityError) as ctx:
                se.provision(force=True)
            self.assertIn("packaging", str(ctx.exception))
            self.assertIn("hash mismatch", str(ctx.exception))
        finally:
            target.write_bytes(original)
            self.assertEqual(target.read_bytes(), original,
                             "restoration failed -- host site-packages left "
                             "mutated by this test")

    def test_after_restoration_provision_succeeds_again(self):
        # Depends on the previous test having restored the file; run
        # independently-verifiable by re-checking mismatches are empty.
        man = se.load_manifest()
        roots = [p["name"] for p in man.image_packages]
        resolved, _missing = se.resolve_closure(roots)
        lock = se.load_lock()
        mismatches = se.verify_lock(resolved, lock)
        self.assertEqual(mismatches, [])


if __name__ == "__main__":
    unittest.main()
