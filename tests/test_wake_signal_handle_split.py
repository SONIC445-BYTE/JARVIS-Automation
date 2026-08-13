"""
The other half of the wake-thread concurrency fix (see
test_wake_detector_stop_joins_thread.py for WakeDetector.stop()'s own
join/guard behavior). This half is jarvis.py's guarantee that stop() is
never actually called from WakeDetector's listening thread in the first
place: WakeDetector's callback is now the cheap _signal_wake_detected
(just sets an Event), and the real handling -- including the stop()/
start() cycle -- runs from PersistentWakeService.start()'s own main-loop
thread via _handle_wake_detected, once it observes the Event.

These tests exercise that split directly, without booting a real
service (no audio, no LLM, no TTS) -- constructing a bare instance and
poking its private state, same style as test_wake_detector_debounce.py
uses for WakeDetector itself.
"""
import threading
import unittest
from unittest import mock

import jarvis


class TestWakeSignalHandleSplit(unittest.TestCase):
    def _service(self):
        # __new__ + manual attribute set-up avoids __init__'s heavier
        # work (component initialization) -- only the attributes these
        # two methods actually touch are needed.
        service = jarvis.PersistentWakeService.__new__(jarvis.PersistentWakeService)
        service.state = jarvis.JarvisState.SLEEP
        service._state_lock = threading.Lock()
        service._wake_event = threading.Event()
        service._wake_detector = mock.Mock()
        service._conversation_mode = False
        return service

    def test_signal_only_sets_the_event_and_does_not_touch_state(self):
        service = self._service()

        service._signal_wake_detected()

        self.assertTrue(service._wake_event.is_set())
        self.assertEqual(service.state, jarvis.JarvisState.SLEEP)
        service._wake_detector.stop.assert_not_called()

    def test_signal_never_calls_stop_even_when_invoked_from_a_thread(self):
        # Mirrors how WakeDetector actually invokes the callback: from
        # inside its own listening thread. _signal_wake_detected must
        # stay callable there without ever reaching stop() -- reaching
        # stop() from this thread is exactly the deadlock/race shape
        # the fix removes.
        service = self._service()
        t = threading.Thread(target=service._signal_wake_detected)
        t.start()
        t.join(timeout=2)

        self.assertFalse(t.is_alive())
        self.assertTrue(service._wake_event.is_set())
        service._wake_detector.stop.assert_not_called()

    def test_handle_wake_detected_ignores_signal_when_not_asleep(self):
        service = self._service()
        service.state = jarvis.JarvisState.ACTIVE

        service._handle_wake_detected()

        service._wake_detector.stop.assert_not_called()

    def test_handle_wake_detected_stops_detector_and_routes_legacy_mode(self):
        service = self._service()
        service._speak = mock.Mock()
        service._listen_for_command = mock.Mock()
        service._conversation_loop = mock.Mock()

        service._handle_wake_detected()

        service._wake_detector.stop.assert_called_once()
        service._listen_for_command.assert_called_once()
        service._conversation_loop.assert_not_called()
        self.assertEqual(service.state, jarvis.JarvisState.ACTIVE)

    def test_handle_wake_detected_routes_conversation_mode(self):
        service = self._service()
        service._conversation_mode = True
        service._speak = mock.Mock()
        service._listen_for_command = mock.Mock()
        service._conversation_loop = mock.Mock()

        service._handle_wake_detected()

        service._conversation_loop.assert_called_once()
        service._listen_for_command.assert_not_called()
        self.assertEqual(service.state, jarvis.JarvisState.LISTEN)


if __name__ == "__main__":
    unittest.main()
