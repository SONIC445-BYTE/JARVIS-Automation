"""
First-run onboarding + periodic/on-demand AvailabilityChecker re-scan
(see onboarding.py). Absorbs Phase 2c's AvailabilityChecker (previously
silent, startup-only) and Phase 2b's installed-app coverage report
(previously doc-only) rather than duplicating either -- these tests
exercise that reuse (CommandRouter's real adapter registry, the shared
AvailabilityChecker singleton), not a parallel implementation.
"""
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import onboarding


class TestFirstRunMarker(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._patch_dir = mock.patch.object(onboarding, "STATE_DIR", Path(self._tmpdir.name) / "state")
        self._patch_marker = mock.patch.object(
            onboarding, "ONBOARDING_MARKER", Path(self._tmpdir.name) / "state" / "onboarding_complete.json"
        )
        self._patch_dir.start()
        self._patch_marker.start()
        self.addCleanup(self._patch_dir.stop)
        self.addCleanup(self._patch_marker.stop)
        self.addCleanup(self._tmpdir.cleanup)

    def test_first_run_true_when_no_marker(self):
        self.assertTrue(onboarding.is_first_run())

    def test_mark_complete_creates_marker_and_flips_is_first_run(self):
        self.assertTrue(onboarding.is_first_run())
        onboarding.mark_onboarding_complete()
        self.assertFalse(onboarding.is_first_run())
        self.assertTrue(onboarding.ONBOARDING_MARKER.exists())

    def test_marker_contains_a_timestamp(self):
        import json
        onboarding.mark_onboarding_complete()
        data = json.loads(onboarding.ONBOARDING_MARKER.read_text(encoding="utf-8"))
        self.assertIn("completed_at", data)


class TestCoverageScan(unittest.TestCase):
    def test_coverage_lines_reuses_real_adapter_registry(self):
        # Every real adapter (whatever CommandRouter's registry currently
        # has) must appear -- this must track the registry, not a
        # separately hardcoded platform list.
        from AgentCore.command_router import CommandRouter
        router = CommandRouter()
        expected_count = len(router._adapter_classes)

        fake_checker = mock.Mock()
        fake_checker.is_installed.return_value = False
        lines = onboarding._coverage_lines(fake_checker)

        summary = [l for l in lines if "controllable platforms found" in l][0]
        self.assertIn(f"0 of {expected_count}", summary)

    def test_coverage_lines_reflects_installed_count(self):
        fake_checker = mock.Mock()
        fake_checker.is_installed.return_value = True
        lines = onboarding._coverage_lines(fake_checker)
        summary = [l for l in lines if "controllable platforms found" in l][0]
        # all "found" when is_installed always True
        self.assertRegex(summary, r"(\d+) of \1 controllable")


class TestRunOnboarding(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._patch_dir = mock.patch.object(onboarding, "STATE_DIR", Path(self._tmpdir.name) / "state")
        self._patch_marker = mock.patch.object(
            onboarding, "ONBOARDING_MARKER", Path(self._tmpdir.name) / "state" / "onboarding_complete.json"
        )
        self._patch_dir.start()
        self._patch_marker.start()
        self.addCleanup(self._patch_dir.stop)
        self.addCleanup(self._patch_marker.stop)
        self.addCleanup(self._tmpdir.cleanup)

    def test_run_onboarding_marks_complete(self):
        fake_checker = mock.Mock()
        fake_checker.is_installed.return_value = False
        self.assertTrue(onboarding.is_first_run())
        onboarding.run_onboarding(checker=fake_checker)
        self.assertFalse(onboarding.is_first_run())

    def test_run_onboarding_speaks_key_lines_when_speak_fn_given(self):
        fake_checker = mock.Mock()
        fake_checker.is_installed.return_value = False
        spoken = []
        onboarding.run_onboarding(checker=fake_checker, speak_fn=spoken.append)
        self.assertTrue(any("setup" in s.lower() for s in spoken))

    def test_run_onboarding_survives_speak_fn_exception(self):
        # TTS hiccuping must never abort onboarding or leave the marker
        # unwritten.
        fake_checker = mock.Mock()
        fake_checker.is_installed.return_value = False

        def broken_speak(_text):
            raise RuntimeError("tts backend down")

        onboarding.run_onboarding(checker=fake_checker, speak_fn=broken_speak)
        self.assertFalse(onboarding.is_first_run())

    def test_run_onboarding_uses_injected_checker_not_shared_singleton(self):
        fake_checker = mock.Mock()
        fake_checker.is_installed.return_value = False
        onboarding.run_onboarding(checker=fake_checker)
        fake_checker.refresh.assert_not_called()  # only the shared-singleton path force-refreshes
        fake_checker.is_installed.assert_called()


class TestRescanInterval(unittest.TestCase):
    def test_default_when_no_env_var(self):
        with mock.patch.dict("os.environ", {}, clear=False):
            import os
            os.environ.pop("JARVIS_AVAILABILITY_RESCAN_INTERVAL_S", None)
            self.assertEqual(onboarding.rescan_interval_seconds(), onboarding._DEFAULT_RESCAN_INTERVAL_S)

    def test_default_is_within_requested_15_to_30_minute_range(self):
        self.assertGreaterEqual(onboarding._DEFAULT_RESCAN_INTERVAL_S, 15 * 60)
        self.assertLessEqual(onboarding._DEFAULT_RESCAN_INTERVAL_S, 30 * 60)

    def test_env_var_override(self):
        with mock.patch.dict("os.environ", {"JARVIS_AVAILABILITY_RESCAN_INTERVAL_S": "42"}):
            self.assertEqual(onboarding.rescan_interval_seconds(), 42.0)

    def test_invalid_env_var_falls_back_to_default(self):
        with mock.patch.dict("os.environ", {"JARVIS_AVAILABILITY_RESCAN_INTERVAL_S": "not-a-number"}):
            self.assertEqual(onboarding.rescan_interval_seconds(), onboarding._DEFAULT_RESCAN_INTERVAL_S)

    def test_zero_or_negative_env_var_falls_back_to_default(self):
        with mock.patch.dict("os.environ", {"JARVIS_AVAILABILITY_RESCAN_INTERVAL_S": "-5"}):
            self.assertEqual(onboarding.rescan_interval_seconds(), onboarding._DEFAULT_RESCAN_INTERVAL_S)


class TestPeriodicAvailabilityRescanner(unittest.TestCase):
    def test_calls_refresh_repeatedly_on_interval(self):
        fake_checker = mock.Mock()
        rescanner = onboarding.PeriodicAvailabilityRescanner(checker=fake_checker, interval_s=0.1)
        rescanner.start()
        time.sleep(0.45)
        rescanner.stop()
        self.assertGreaterEqual(fake_checker.refresh.call_count, 2)

    def test_stop_prevents_further_refresh_calls(self):
        fake_checker = mock.Mock()
        rescanner = onboarding.PeriodicAvailabilityRescanner(checker=fake_checker, interval_s=0.1)
        rescanner.start()
        time.sleep(0.15)
        rescanner.stop()
        count_after_stop = fake_checker.refresh.call_count
        time.sleep(0.3)
        self.assertEqual(fake_checker.refresh.call_count, count_after_stop)

    def test_start_is_idempotent(self):
        fake_checker = mock.Mock()
        rescanner = onboarding.PeriodicAvailabilityRescanner(checker=fake_checker, interval_s=5.0)
        rescanner.start()
        first_thread = rescanner._thread
        rescanner.start()  # must not spawn a second thread
        self.assertIs(rescanner._thread, first_thread)
        rescanner.stop()

    def test_refresh_exception_does_not_kill_the_loop(self):
        fake_checker = mock.Mock()
        fake_checker.refresh.side_effect = [RuntimeError("registry busy"), None, None]
        rescanner = onboarding.PeriodicAvailabilityRescanner(checker=fake_checker, interval_s=0.1)
        rescanner.start()
        time.sleep(0.45)
        rescanner.stop()
        # A raised exception on one tick must not stop later ticks.
        self.assertGreaterEqual(fake_checker.refresh.call_count, 2)


class TestRescanNow(unittest.TestCase):
    def test_calls_refresh_and_reports_no_new_apps(self):
        fake_checker = mock.Mock()
        fake_checker.is_installed.return_value = False
        result = onboarding.rescan_now(checker=fake_checker)
        fake_checker.refresh.assert_called_once()
        self.assertIn("no new apps found", result)

    def test_reports_newly_found_platforms_by_name(self):
        # Simulate: nothing installed before refresh, one alias's worth
        # of apps becomes installed after refresh() runs.
        from AgentCore.command_router import CommandRouter
        router = CommandRouter()
        first_key, first_cls = next(iter(sorted(router._adapter_classes.items())))
        target_alias = (first_cls.PLATFORM_ALIASES or [first_key])[0]

        fake_checker = mock.Mock()
        call_state = {"refreshed": False}

        def is_installed(aliases):
            if not call_state["refreshed"]:
                return False
            return target_alias in [a.lower() for a in aliases]

        def refresh():
            call_state["refreshed"] = True

        fake_checker.is_installed.side_effect = is_installed
        fake_checker.refresh.side_effect = refresh

        result = onboarding.rescan_now(checker=fake_checker)
        self.assertIn("newly installed", result)
        self.assertIn(target_alias.title(), result)


class TestJarvisOnboardingWiring(unittest.TestCase):
    """Light checks on jarvis.py's plumbing to onboarding.py -- not
    re-testing onboarding.py's own logic (covered above), just that
    PersistentWakeService actually wires force_setup and stops its
    rescanner thread."""

    def test_force_setup_flag_stored(self):
        import jarvis
        service = jarvis.PersistentWakeService(conversation_mode=True, force_setup=True)
        self.assertTrue(service._force_setup)

    def test_force_setup_defaults_false(self):
        import jarvis
        service = jarvis.PersistentWakeService(conversation_mode=True)
        self.assertFalse(service._force_setup)

    def test_stop_stops_availability_rescanner_if_present(self):
        import jarvis
        service = jarvis.PersistentWakeService(conversation_mode=True)
        fake_rescanner = mock.Mock()
        service._availability_rescanner = fake_rescanner
        service.stop()
        fake_rescanner.stop.assert_called_once()

    def test_stop_safe_when_no_rescanner_started(self):
        import jarvis
        service = jarvis.PersistentWakeService(conversation_mode=True)
        service.stop()  # must not raise -- _availability_rescanner is None

    def test_run_setup_phrases_and_rescan_phrases_are_disjoint(self):
        import jarvis
        setup_set = set(jarvis.RUN_SETUP_PHRASES)
        rescan_set = set(jarvis.RESCAN_PHRASES)
        self.assertEqual(setup_set & rescan_set, set())


if __name__ == "__main__":
    unittest.main()
