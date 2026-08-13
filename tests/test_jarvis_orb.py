"""
jarvis_orb.py -- the startup orb (SS3.8). Provided directly by the project
owner after the file was found to not exist anywhere in this repository
(see the execution log's "orb wiring declined" entry) -- these tests cover
the module's own contract and confirm it is actually wired into
PersistentWakeService.start(), not just present on disk.
"""
import re
import unittest

from jarvis_orb import CHARS, render_frame, play


class TestRenderFrame(unittest.TestCase):
    def test_default_dimensions(self):
        frame = render_frame(0.6, 0.3)
        lines = frame.split("\n")
        self.assertEqual(len(lines), 12)
        for line in lines:
            self.assertEqual(len(line), 28)

    def test_custom_dimensions(self):
        frame = render_frame(0.0, 0.0, width=20, height=8)
        lines = frame.split("\n")
        self.assertEqual(len(lines), 8)
        for line in lines:
            self.assertEqual(len(line), 20)

    def test_only_contains_declared_charset_and_space(self):
        frame = render_frame(1.2, 2.4)
        allowed = set(CHARS) | {" ", "\n"}
        self.assertTrue(set(frame) <= allowed, set(frame) - allowed)

    def test_is_deterministic_for_the_same_angles(self):
        # No randomness anywhere in the renderer -- same (A, B) must
        # produce byte-identical output, which matters for using one
        # fixed angle as a stable "at rest" startup frame.
        self.assertEqual(render_frame(0.6, 0.3), render_frame(0.6, 0.3))

    def test_different_angles_produce_different_frames(self):
        self.assertNotEqual(render_frame(0.0, 0.0), render_frame(1.5, 2.0))

    def test_renders_something_not_just_blank_space(self):
        frame = render_frame(0.6, 0.3)
        self.assertTrue(any(c != " " and c != "\n" for c in frame))


class TestPlay(unittest.TestCase):
    def test_bounded_and_returns(self):
        # delay=0 so this stays fast; frames=2 is enough to prove it
        # doesn't hang the way the original's `while True` would have.
        import io
        buf = io.StringIO()
        result = play(frames=2, delay=0, clear=False, stream=buf)
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)
        # Each frame is 12 lines joined by 11 "\n"s, plus one trailing
        # "\n" play() appends per frame -- 12 newlines per frame written.
        self.assertEqual(buf.getvalue().count("\n"), 2 * 12)


class TestWiredIntoBootSequence(unittest.TestCase):
    """Static source check that PersistentWakeService.start() actually
    prints the orb above the status box, mirroring how this project checks
    other boot-sequence wiring (e.g. render_status_box's own call site).
    A unit test on jarvis_orb.py alone cannot catch "the module exists but
    nothing calls it" -- that was the actual defect being closed here."""

    def test_start_calls_render_frame_before_render_status_box(self):
        import jarvis

        source = jarvis.__file__
        with open(source, "r", encoding="utf-8") as fh:
            text = fh.read()

        self.assertIn("from jarvis_orb import render_frame", text)

        orb_call = text.index("render_frame(")
        status_box_call = text.index("render_status_box(wake_active=")
        self.assertLess(
            orb_call, status_box_call,
            "the orb must print above the status box, not after it",
        )

    def test_play_is_not_called_from_the_every_launch_path(self):
        # The animated intro stays reserved for first-run onboarding,
        # not wired into the every-launch path by this change. Comment
        # lines are stripped first -- the wiring comment itself legitimately
        # mentions "play()" in prose, which isn't a call and shouldn't
        # trip this check.
        import jarvis
        with open(jarvis.__file__, "r", encoding="utf-8") as fh:
            text = fh.read()
        start_method = re.search(r"def start\(self\):.*?(?=\n    def )", text, re.DOTALL)
        self.assertIsNotNone(start_method)
        code_only = "\n".join(
            line for line in start_method.group(0).splitlines()
            if not line.strip().startswith("#")
        )
        self.assertNotIn("play(", code_only)
        self.assertNotIn("from jarvis_orb import play", code_only)


if __name__ == "__main__":
    unittest.main()
