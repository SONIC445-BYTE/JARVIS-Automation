"""
Test Ethics Board.
"""
import unittest
from AgentCore.advanced.level6.governance.ethics_board import EthicsBoard

class TestEthicsBoard(unittest.TestCase):
    def test_approval_flow(self):
        board = EthicsBoard()
        ticket = board.submit_for_ethics("proposal-123")
        
        self.assertTrue(board.approve(ticket, "owner-1"))
        self.assertNotEqual(board.proposals[ticket]['status'], "approved")
        
        self.assertTrue(board.approve(ticket, "owner-2"))
        self.assertEqual(board.proposals[ticket]['status'], "approved")

if __name__ == "__main__":
    unittest.main()
