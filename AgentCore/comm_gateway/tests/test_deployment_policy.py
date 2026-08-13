"""
"Strict Local Mode should be the enforced default until an organization's
actual policy authority says otherwise -- not a config value sitting
equal beside the others by default." (§4.4c)
"""
import unittest

from AgentCore.comm_gateway.deployment_policy import DeploymentMode, DeploymentPolicy, load_deployment_policy


class TestStrictLocalIsTheEnforcedDefault(unittest.TestCase):
    def test_missing_policy_file_defaults_to_strict_local(self):
        policy = load_deployment_policy(path="/definitely/does/not/exist.yaml")
        self.assertEqual(policy.mode, DeploymentMode.STRICT_LOCAL)
        self.assertFalse(policy.allows_remote_channels())

    def test_bare_constructor_default_is_also_strict_local(self):
        """The default isn't only enforced by the loader -- the dataclass's own default matches, so any code that forgets to load a policy still gets the safe value."""
        self.assertEqual(DeploymentPolicy().mode, DeploymentMode.STRICT_LOCAL)

    def test_strict_local_refuses_remote_channels(self):
        self.assertFalse(DeploymentPolicy(mode=DeploymentMode.STRICT_LOCAL).allows_remote_channels())

    def test_secure_remote_and_hybrid_permit_remote_channels(self):
        self.assertTrue(DeploymentPolicy(mode=DeploymentMode.SECURE_REMOTE).allows_remote_channels())
        self.assertTrue(DeploymentPolicy(mode=DeploymentMode.HYBRID).allows_remote_channels())


class TestPolicyLoading(unittest.TestCase):
    def test_a_present_but_malformed_mode_raises_rather_than_silently_defaulting(self):
        """A configured-but-broken policy must fail loudly, not quietly fall back to strict_local as if nothing were configured -- those are different facts."""
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "policy.yaml"
            p.write_text("mode: not_a_real_mode\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_deployment_policy(path=p)

    def test_a_real_policy_file_round_trips_correctly(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "policy.yaml"
            p.write_text(
                "mode: secure_remote\n"
                "remote_voice:\n  enabled: true\n"
                "patient_identifiers:\n  tokenize: false\n"
                "clinical_notes:\n  allow_remote: true\n",
                encoding="utf-8",
            )
            policy = load_deployment_policy(path=p)
            self.assertEqual(policy.mode, DeploymentMode.SECURE_REMOTE)
            self.assertTrue(policy.remote_voice_enabled)
            self.assertFalse(policy.patient_identifiers_tokenize)
            self.assertTrue(policy.clinical_notes_allow_remote)


if __name__ == "__main__":
    unittest.main()
