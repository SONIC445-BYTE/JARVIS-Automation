
import unittest
from ..adapter import AmazonAdapter

class TestAmazonAdapter(unittest.TestCase):
    def setUp(self):
        self.adapter = AmazonAdapter()

    def test_build_plan(self):
        plan = self.adapter.build_plan("search_product", {"query": "book"})
        self.assertIn("amazon.com", plan.steps[0].target)

if __name__ == '__main__':
    unittest.main()
