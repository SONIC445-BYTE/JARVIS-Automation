"""
Test Formal Verification Logic.
"""
import unittest
from AgentCore.advanced.level6.architect.spec_synthesizer import SpecSynthesizer
from AgentCore.advanced.level6.architect.verification_runner import VerificationRunner

class TestFormalVerification(unittest.TestCase):
    def test_verify_tla(self):
        synth = SpecSynthesizer()
        runner = VerificationRunner()
        
        spec = synth.to_tla({})
        res = runner.run_verification(spec)
        self.assertTrue(res['success'])

if __name__ == "__main__":
    unittest.main()
