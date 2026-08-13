"""
Live smoke-test finding: a single spoken "jarvis" can make Vosk's
PartialResult() stabilize on the exact text "jarvis" across more than
one 250ms audio chunk before AcceptWaveform finalizes it. WakeDetector's
_listen_loop() called self.callback() on every stable partial match with
no guard against re-firing for the same utterance -- reported live as
"if I say the wake word once, two agents get activated."

_try_fire() (WakeService/wake_detector.py) is the extracted fix: a single
cooldown-gated call site used by both the partial and AcceptWaveform-final
branches. Tested directly here rather than through _listen_loop(), since
_listen_loop() needs a real audio stream.
"""
import time
import unittest
from unittest import mock

from WakeService.wake_detector import WakeDetector


class TestWakeDetectorDebounce(unittest.TestCase):
    def _detector(self):
        # __init__ tries to load the real Vosk model (present on this
        # machine) -- fine for these tests, they never touch audio.
        callback = mock.Mock()
        detector = WakeDetector(callback=callback)
        return detector, callback

    def test_second_fire_within_cooldown_is_suppressed(self):
        detector, callback = self._detector()

        fired_first = detector._try_fire()
        fired_second = detector._try_fire()

        self.assertTrue(fired_first)
        self.assertFalse(fired_second)
        callback.assert_called_once()

    def test_fire_after_cooldown_elapses_is_allowed(self):
        detector, callback = self._detector()

        self.assertTrue(detector._try_fire())
        # Simulate cooldown having elapsed without a real sleep.
        detector._last_fire_time = time.time() - detector._WAKE_FIRE_COOLDOWN_S - 0.1
        self.assertTrue(detector._try_fire())

        self.assertEqual(callback.call_count, 2)

    def test_no_callback_configured_does_not_raise(self):
        detector = WakeDetector(callback=None)
        # Must not raise even though there's nothing to call.
        self.assertTrue(detector._try_fire())


if __name__ == "__main__":
    unittest.main()
