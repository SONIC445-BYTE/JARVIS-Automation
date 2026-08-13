"""
Wake-thread concurrency fix (found during the v3.14 live smoke test,
fixed here). WakeDetector.stop() used to set _stop_event and return
immediately, without waiting for _listen_loop()'s thread to actually
exit and close its RawInputStream. jarvis.py's old _on_wake_detected()
called stop() from INSIDE that same listening thread (it was the thread
executing the callback), then _return_to_sleep() called start() again --
which could spawn a second _listen_loop() thread before the first had
unwound, giving two concurrent mic captures on one device.

These tests exercise stop()'s two new properties directly against a real
thread (not _listen_loop() itself, which needs real audio hardware --
the join/guard logic is independent of what the thread's target function
does, so a lightweight stand-in target proves the same thing without an
audio dependency):
  1. stop() actually blocks until the thread is provably dead.
  2. stop() raises rather than deadlocking if called from that thread's
     own call stack -- the exact shape of the original bug.
  3. stop() surfaces (does not hide) the case where the thread doesn't
     exit within its timeout.

jarvis.py's own signal/handle split (_signal_wake_detected /
_handle_wake_detected) is what guarantees stop() is never actually
called from the listening thread in production; see
test_wake_signal_handle_split.py for that half.
"""
import threading
import time
import unittest
from unittest import mock

from WakeService.wake_detector import WakeDetector


class TestWakeDetectorStopJoinsThread(unittest.TestCase):
    def _detector(self):
        # __init__ loads the real (small) Vosk model -- fine, these tests
        # never touch audio or _listen_loop() itself.
        return WakeDetector(callback=mock.Mock())

    def _install_fake_listen_thread(self, detector, respects_stop_event=True):
        """A stand-in for _listen_loop(): runs until _stop_event is set
        (or, for the "doesn't exit" test, ignores it entirely). Mirrors
        _listen_loop()'s own polling shape without needing real audio."""
        started = threading.Event()

        def fake_loop():
            started.set()
            while True:
                if respects_stop_event and detector._stop_event.is_set():
                    return
                if not respects_stop_event and time.time() > deadline:
                    return
                time.sleep(0.02)

        deadline = time.time() + 10  # only used by the ignores-stop variant
        t = threading.Thread(target=fake_loop, daemon=True)
        detector._listen_thread = t
        t.start()
        started.wait(timeout=2)
        return t

    def test_stop_blocks_until_the_thread_actually_exits(self):
        detector = self._detector()
        t = self._install_fake_listen_thread(detector)

        detector.stop()

        self.assertFalse(t.is_alive())
        self.assertIsNone(detector._listen_thread)

    def test_stop_raises_when_called_from_the_listening_thread_itself(self):
        # The exact shape of the original bug: the callback (running ON
        # the listening thread) eventually calling stop() on itself.
        detector = self._detector()
        caught = []

        def fake_loop():
            try:
                detector.stop()
            except RuntimeError as e:
                caught.append(e)

        t = threading.Thread(target=fake_loop, daemon=True)
        detector._listen_thread = t
        t.start()
        t.join(timeout=2)

        self.assertFalse(t.is_alive())
        self.assertEqual(len(caught), 1)
        self.assertIn("own listening thread", str(caught[0]))

    def test_stop_warns_rather_than_hangs_if_thread_never_exits(self):
        detector = self._detector()
        t = self._install_fake_listen_thread(detector, respects_stop_event=False)

        with mock.patch("builtins.print") as mock_print:
            t0 = time.time()
            detector.stop(timeout=0.3)
            elapsed = time.time() - t0

        # Bounded by the timeout, not hanging -- and not silently
        # pretending the stop succeeded.
        self.assertLess(elapsed, 2.0)
        warned = any(
            "did not exit" in str(call.args)
            for call in mock_print.call_args_list
        )
        self.assertTrue(warned, mock_print.call_args_list)


if __name__ == "__main__":
    unittest.main()
