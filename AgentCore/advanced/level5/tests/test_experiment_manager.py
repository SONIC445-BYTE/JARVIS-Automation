"""
Tests for Level-5.
"""
import unittest
from AgentCore.advanced.level5.meta_learning.experiment_manager import ExperimentManager
from AgentCore.advanced.level5.safe_update.signed_package import SignedPackage

class TestLevel5(unittest.TestCase):
    def test_experiment_proposal(self):
        mgr = ExperimentManager()
        eid = mgr.propose_experiment("test_exp", "hypothesis", {}, [], {})
        self.assertTrue(eid)
        
    def test_signed_package(self):
        signer = SignedPackage()
        data = {"foo": "bar"}
        signed = signer.sign_package(data)
        self.assertTrue(signer.verify_package(signed))
        
        # Tamper
        signed['payload']['foo'] = 'baz'
        self.assertFalse(signer.verify_package(signed))

if __name__ == "__main__":
    unittest.main()
