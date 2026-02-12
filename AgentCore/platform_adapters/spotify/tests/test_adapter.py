
import unittest
from ..adapter import SpotifyAdapter

class TestSpotifyAdapter(unittest.TestCase):
    def setUp(self):
        self.adapter = SpotifyAdapter()

    def test_detect_ui(self):
        self.assertTrue(self.adapter.detect_ui({"active_window": "Spotify - Web Player"}))
        self.assertFalse(self.adapter.detect_ui({"active_window": "Calculator"}))

    def test_build_plan_play(self):
        plan = self.adapter.build_plan("play_music", {"query": "Rock"})
        self.assertTrue(len(plan.steps) > 0)
        self.assertEqual(plan.steps[0].action, "navigate")
        self.assertIn("open.spotify.com", plan.steps[0].target)

if __name__ == '__main__':
    unittest.main()
