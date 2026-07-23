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


class StatusBoxTestCase(unittest.TestCase):
    """Base: patches STATE_DIR and every precomputed marker path under it
    (same pattern as TestFirstRunMarker) so these tests never touch the
    real repo-root state/ directory."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        state_dir = Path(self._tmpdir.name) / "state"
        self._patches = [
            mock.patch.object(onboarding, "STATE_DIR", state_dir),
            mock.patch.object(onboarding, "ONBOARDING_MARKER", state_dir / "onboarding_complete.json"),
            mock.patch.object(onboarding, "SCAN_CACHE_MARKER", state_dir / "availability_scan_cache.json"),
            mock.patch.object(onboarding, "PENDING_STATE_MARKER", state_dir / "pending_state.json"),
        ]
        for p in self._patches:
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(self._tmpdir.cleanup)


class TestRunOnboarding(StatusBoxTestCase):

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


class TestPeriodicAvailabilityRescanner(StatusBoxTestCase):
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


class TestRescanNow(StatusBoxTestCase):
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


class TestScanCache(StatusBoxTestCase):
    def test_no_cache_returns_none(self):
        self.assertIsNone(onboarding._read_scan_cache())

    def test_write_then_read_round_trips(self):
        fake_checker = mock.Mock()
        fake_checker.is_installed.side_effect = lambda aliases: aliases[0] in ("whatsapp", "browser")
        onboarding._write_scan_cache(fake_checker)

        cache = onboarding._read_scan_cache()
        self.assertIsNotNone(cache)
        self.assertIn("installed", cache)
        self.assertIn("checked_at", cache)

    def test_run_onboarding_writes_a_usable_cache(self):
        fake_checker = mock.Mock()
        fake_checker.is_installed.return_value = True
        onboarding.run_onboarding(checker=fake_checker)
        cache = onboarding._read_scan_cache()
        self.assertIsNotNone(cache)
        self.assertTrue(all(cache["installed"].values()))

    def test_rescan_now_writes_a_usable_cache(self):
        fake_checker = mock.Mock()
        fake_checker.is_installed.return_value = False
        onboarding.rescan_now(checker=fake_checker)
        self.assertIsNotNone(onboarding._read_scan_cache())

    def test_periodic_rescanner_writes_cache_on_each_tick(self):
        fake_checker = mock.Mock()
        fake_checker.is_installed.return_value = False
        rescanner = onboarding.PeriodicAvailabilityRescanner(checker=fake_checker, interval_s=0.1)
        rescanner.start()
        time.sleep(0.25)
        rescanner.stop()
        self.assertIsNotNone(onboarding._read_scan_cache())


class TestAgeDescription(unittest.TestCase):
    def test_just_now(self):
        ts = onboarding._now_iso()
        self.assertEqual(onboarding._age_description(ts), "just now")

    def test_minutes_ago(self):
        from datetime import datetime, timedelta, timezone
        ts = (datetime.now(timezone.utc) - timedelta(minutes=4)).isoformat()
        self.assertEqual(onboarding._age_description(ts), "4 min ago")

    def test_hours_ago(self):
        from datetime import datetime, timedelta, timezone
        ts = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
        self.assertEqual(onboarding._age_description(ts), "3h ago")

    def test_days_ago(self):
        from datetime import datetime, timedelta, timezone
        ts = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
        self.assertEqual(onboarding._age_description(ts), "2d ago")

    def test_malformed_timestamp_does_not_raise(self):
        self.assertEqual(onboarding._age_description("not-a-timestamp"), "unknown")


class TestPendingStatePersistence(StatusBoxTestCase):
    def test_no_pending_state_by_default(self):
        self.assertIsNone(onboarding.read_pending_state_summary())

    def test_persist_install_then_read_summary(self):
        onboarding.persist_pending_state("install", "install Telegram")
        self.assertEqual(onboarding.read_pending_state_summary(), "1 install awaiting your confirmation")

    def test_persist_resume_then_read_summary(self):
        onboarding.persist_pending_state("resume", "please log in")
        self.assertEqual(onboarding.read_pending_state_summary(), "1 browser task waiting on you")

    def test_clear_removes_marker(self):
        onboarding.persist_pending_state("install", "x")
        onboarding.clear_pending_state()
        self.assertIsNone(onboarding.read_pending_state_summary())

    def test_clear_when_nothing_pending_does_not_raise(self):
        onboarding.clear_pending_state()  # must not raise -- no marker exists

    def test_persist_overwrites_previous_pending_state(self):
        onboarding.persist_pending_state("install", "install A")
        onboarding.persist_pending_state("resume", "blocked on B")
        self.assertEqual(onboarding.read_pending_state_summary(), "1 browser task waiting on you")


class TestModelTier(unittest.TestCase):
    def test_tinyllama_is_fast(self):
        self.assertEqual(onboarding._model_tier("tinyllama"), "Fast")

    def test_phi3_mini_is_fast(self):
        self.assertEqual(onboarding._model_tier("phi3:mini"), "Fast")

    def test_llama3_is_accurate(self):
        self.assertEqual(onboarding._model_tier("llama3:latest"), "Accurate")

    def test_mistral_is_accurate(self):
        self.assertEqual(onboarding._model_tier("mistral:7b"), "Accurate")

    def test_unknown_model_defaults_accurate(self):
        self.assertEqual(onboarding._model_tier("some-new-model:9b"), "Accurate")


class TestRenderStatusBox(StatusBoxTestCase):
    def test_box_lines_all_same_width(self):
        box = onboarding.render_status_box(wake_active=True, llm_model="tinyllama", llm_ready=True)
        lengths = {len(line) for line in box.splitlines()}
        self.assertEqual(len(lengths), 1, "every line in the box must be the same width")

    def test_box_has_top_and_bottom_border(self):
        box = onboarding.render_status_box(wake_active=True, llm_model="tinyllama", llm_ready=True)
        lines = box.splitlines()
        self.assertTrue(lines[0].startswith("+") and lines[0].endswith("+"))
        self.assertTrue(lines[-1].startswith("+") and lines[-1].endswith("+"))
        self.assertEqual(lines[0], lines[-1])

    def test_shows_wake_word_active(self):
        box = onboarding.render_status_box(wake_active=True, llm_model="tinyllama", llm_ready=True)
        self.assertIn("listening", box)

    def test_shows_wake_word_inactive(self):
        box = onboarding.render_status_box(wake_active=False, llm_model="tinyllama", llm_ready=True)
        self.assertIn("not active", box)

    def test_shows_model_name_tier_and_ready_status(self):
        box = onboarding.render_status_box(wake_active=True, llm_model="tinyllama", llm_ready=True)
        self.assertIn("tinyllama", box)
        self.assertIn("Fast", box)
        self.assertIn("ready", box)

    def test_shows_model_not_available_when_not_ready(self):
        box = onboarding.render_status_box(wake_active=True, llm_model="llama3:latest", llm_ready=False)
        self.assertIn("not available", box)

    def test_shows_no_model_when_llm_missing_entirely(self):
        box = onboarding.render_status_box(wake_active=True, llm_model=None, llm_ready=False)
        self.assertIn("Model:      not available", box)

    def test_uses_cache_for_platform_counts_when_present(self):
        fake_checker = mock.Mock()
        fake_checker.is_installed.return_value = True
        onboarding._write_scan_cache(fake_checker)

        box = onboarding.render_status_box(wake_active=True, llm_model="tinyllama", llm_ready=True)
        self.assertIn("not yet wired", box)
        self.assertNotIn("not yet checked", box)

    def test_falls_back_to_live_checker_when_no_cache(self):
        fake_checker = mock.Mock()
        fake_checker.is_installed.return_value = False
        box = onboarding.render_status_box(wake_active=True, llm_model="tinyllama", llm_ready=True, checker=fake_checker)
        self.assertIn("just now", box)

    def test_shows_not_yet_checked_when_no_cache_and_no_checker(self):
        box = onboarding.render_status_box(wake_active=True, llm_model="tinyllama", llm_ready=True, checker=None)
        self.assertIn("not yet checked", box)

    def test_not_yet_wired_count_matches_catalog_minus_daemon_adapters(self):
        from platform_adapters.platform_catalog import DAEMON_ADAPTER_FOR, PLATFORM_CATALOG
        expected = len(PLATFORM_CATALOG) - len(DAEMON_ADAPTER_FOR)
        fake_checker = mock.Mock()
        fake_checker.is_installed.return_value = True
        onboarding._write_scan_cache(fake_checker)
        box = onboarding.render_status_box(wake_active=True, llm_model="tinyllama", llm_ready=True)
        self.assertIn(f"{expected} not yet wired", box)

    def test_shows_pending_none_by_default(self):
        box = onboarding.render_status_box(wake_active=True, llm_model="tinyllama", llm_ready=True)
        self.assertIn("Pending:    none", box)

    def test_shows_pending_install_summary(self):
        onboarding.persist_pending_state("install", "install Telegram")
        box = onboarding.render_status_box(wake_active=True, llm_model="tinyllama", llm_ready=True)
        self.assertIn("1 install awaiting your confirmation", box)


if __name__ == "__main__":
    unittest.main()
