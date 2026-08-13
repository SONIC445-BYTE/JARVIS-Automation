"""
Security Broker checkpoint-classification table (§4.4c), scaffolded as
an interface. SynchronousTestApprover is the Track-A double -- these
tests also pin that it is a double, not something that could be
mistaken for a real companion device.
"""
import unittest

from AgentCore.comm_gateway.approval import ApprovalGate, ApprovalRequest, SynchronousTestApprover


class TestApprovalGateMatchesTheBlueprintTable(unittest.TestCase):
    def test_all_seven_checkpoint_gates_are_present(self):
        expected = {
            "password_field", "otp_received", "captcha", "payment_confirmation",
            "delete_files", "bank_transfer", "admin_privilege",
        }
        self.assertEqual({g.value for g in ApprovalGate}, expected)


class TestSynchronousTestApprover(unittest.TestCase):
    def test_records_every_request_it_decides(self):
        approver = SynchronousTestApprover(decision=True)
        req = ApprovalRequest(
            gate=ApprovalGate.PAYMENT_CONFIRMATION,
            rendered_description="JARVIS wants to send Rs.2,000 via UPI",
            session_id="sess-1",
        )
        result = approver.request_approval(req)
        self.assertTrue(result)
        self.assertEqual(approver.requests_seen, [req])

    def test_denial_is_a_real_false_not_an_exception(self):
        approver = SynchronousTestApprover(decision=False)
        req = ApprovalRequest(gate=ApprovalGate.DELETE_FILES, rendered_description="delete 500 files", session_id="s")
        self.assertFalse(approver.request_approval(req))


if __name__ == "__main__":
    unittest.main()
