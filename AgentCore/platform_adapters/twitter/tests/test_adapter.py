
import unittest
from ..adapter import TwitterAdapter

class TestTwitterAdapter(unittest.TestCase):
    def setUp(self):
        self.adapter = TwitterAdapter()

    def test_build_plan(self):
        plan = self.adapter.build_plan("post_tweet", {"text": "hello"})
        self.assertIn("twitter.com", plan.steps[0].target)

if __name__ == '__main__':
    unittest.main()
