"""
Test Approval Workflow.
"""
import unittest
from AgentCore.human_loop.approval_workflow import ApprovalWorkflow

class TestApprovalWorkflow(unittest.TestCase):
    def setUp(self):
        self.workflow = ApprovalWorkflow()

    def test_approval_flow(self):
        aid = self.workflow.present_for_approval("diff", {"confidence": 0.9})
        self.assertIn(aid, self.workflow.pending_approvals)
        
        success = self.workflow.approve(aid, "owner", "voice")
        self.assertTrue(success)
        self.assertEqual(self.workflow.pending_approvals[aid]['status'], "approved")

    def test_rejection_flow(self):
        aid = self.workflow.present_for_approval("diff", {"confidence": 0.5})
        success = self.workflow.reject(aid, "owner", "risk")
        self.assertTrue(success)
        self.assertEqual(self.workflow.pending_approvals[aid]['status'], "rejected")

if __name__ == "__main__":
    unittest.main()
