"""
Phase 3a: SessionMemory's read/write API, against an in-memory-backed
MemoryStore (a temp directory) so these tests never touch the real
state/memory/ directory or leave files behind.
"""
import tempfile
import unittest
from pathlib import Path

from AgentCore.memory_store import MemoryStore
from AgentCore.session_memory import SessionMemory


class TestSessionMemory(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        store = MemoryStore(store_dir=Path(self._tmpdir.name))
        self.mem = SessionMemory(store=store)

    def test_preference_round_trip(self):
        self.mem.set_preference("tts_voice", "male_1")
        self.assertEqual(self.mem.get_preference("tts_voice"), "male_1")

    def test_preference_default_when_missing(self):
        self.assertEqual(self.mem.get_preference("nope", "fallback"), "fallback")
        self.assertIsNone(self.mem.get_preference("also_nope"))

    def test_command_pattern_increments(self):
        self.mem.record_command_pattern("whatsapp_desktop.send_message")
        self.mem.record_command_pattern("whatsapp_desktop.send_message")
        self.mem.record_command_pattern("spotify.play")

        top = self.mem.top_command_patterns()
        self.assertEqual(top[0], ("whatsapp_desktop.send_message", 2))
        self.assertIn(("spotify.play", 1), top)

    def test_top_command_patterns_respects_limit(self):
        for i in range(10):
            self.mem.record_command_pattern(f"adapter.action{i}")
        self.assertEqual(len(self.mem.top_command_patterns(limit=3)), 3)

    def test_top_command_patterns_empty_when_nothing_recorded(self):
        self.assertEqual(self.mem.top_command_patterns(), [])

    def test_session_start_and_end(self):
        session_id = self.mem.start_session()
        self.assertTrue(session_id)

        sessions = self.mem.recent_sessions()
        self.assertEqual(len(sessions), 1)
        self.assertIsNone(sessions[0]["ended_at"])
        self.assertIsNone(sessions[0]["summary"])

        self.mem.end_session(session_id, "opened chrome, sent a message")

        sessions = self.mem.recent_sessions()
        self.assertEqual(sessions[0]["summary"], "opened chrome, sent a message")
        self.assertIsNotNone(sessions[0]["ended_at"])

    def test_end_session_with_unknown_id_does_not_raise(self):
        self.mem.end_session("not-a-real-session-id", "irrelevant")  # must not raise

    def test_recent_sessions_respects_limit_and_ordering(self):
        ids = [self.mem.start_session() for _ in range(5)]
        for sid in ids:
            self.mem.end_session(sid, f"summary for {sid}")

        recent = self.mem.recent_sessions(limit=2)
        self.assertEqual(len(recent), 2)
        # newest first
        self.assertGreaterEqual(recent[0]["started_at"], recent[1]["started_at"])

    def test_default_store_dir_is_under_state_not_data(self):
        # Regression check for the deliberate redirect away from
        # MemoryStore's own default (data/memory/, untracked but not
        # gitignored) to state/memory (gitignored). Constructing
        # SessionMemory() with no store= necessarily creates state/memory/
        # on disk (MemoryStore.__init__ mkdir's it) -- clean it up
        # unconditionally afterward rather than leaving repo-root debris.
        import shutil

        state_existed_before = Path("state").exists()

        def cleanup():
            if not state_existed_before:
                shutil.rmtree("state", ignore_errors=True)

        self.addCleanup(cleanup)

        mem = SessionMemory()
        self.assertEqual(mem._store.store_dir, Path("state") / "memory")


if __name__ == "__main__":
    unittest.main()
