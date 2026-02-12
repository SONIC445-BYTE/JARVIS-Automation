
import unittest
from ..adapter import GmailAdapter

class TestGmailAdapter(unittest.TestCase):
    def setUp(self):
        self.adapter = GmailAdapter()

    def test_build_plan(self):
        plan = self.adapter.build_plan("send_email", {"to": "a", "subject": "b", "body": "c"})
        self.assertIn("mail.google.com", plan.steps[0].target)

if __name__ == '__main__':
    unittest.main()
