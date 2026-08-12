"""
Tests for the coding-benchmark scanner.

No test here performs a real network call -- the live-source check is a
separate, explicitly-marked test that skips when the network is
unavailable, mirroring the SerpApi live-test convention in
AgentCore/knowledge/tests/.
"""
import os
import unittest
from datetime import date, datetime, timedelta, timezone
from unittest import mock

from AgentCore.model_scanner import BenchmarkSourceError, Licensing, classify, scanner

_VALID_YAML = """
- model: gpt-5 (high)
  pass_rate_2: 88.0
  pass_rate_1: 70.0
  edit_format: diff
  date: 2025-08-23
  total_cost: 12.5
- model: DeepSeek R1
  pass_rate_2: 71.4
  edit_format: diff
  date: 2025-06-06
  total_cost: 3.1
- model: Some Unknown Model X
  pass_rate_2: 40.0
  date: 2025-01-01
"""


class TestClassification(unittest.TestCase):
    def test_known_cloud_and_open_families(self):
        self.assertIs(classify("gpt-5 (high)")[0], Licensing.CLOUD)
        self.assertIs(classify("claude-3-5-sonnet-20241022")[0], Licensing.CLOUD)
        self.assertIs(classify("gemini-2.5-pro-preview")[0], Licensing.CLOUD)
        self.assertIs(classify("DeepSeek R1 (0528)")[0], Licensing.OPEN_WEIGHTS)
        self.assertIs(classify("Qwen3 235B A22B")[0], Licensing.OPEN_WEIGHTS)
        self.assertIs(classify("Kimi K2")[0], Licensing.OPEN_WEIGHTS)

    def test_unknown_model_is_unclassified_not_guessed_into_a_bucket(self):
        licensing, basis = classify("Some Brand New Model")
        self.assertIs(licensing, Licensing.UNCLASSIFIED)
        self.assertIn("rather than guessing", basis)

    def test_combination_entry_is_unclassified_not_bucketed_by_token_length(self):
        """
        Regression guard for a real misclassification found by running
        against the live leaderboard: "DeepSeek R1 + claude-3-5-sonnet"
        landed in OPEN_WEIGHTS because "deepseek" is a longer token than
        "claude". A pairing containing a hosted model cannot be run
        locally, so that label would mislead the exact decision this
        tool informs.
        """
        licensing, basis = classify("DeepSeek R1 + claude-3-5-sonnet-20241022")
        self.assertIs(licensing, Licensing.UNCLASSIFIED)
        self.assertIn("multi-model", basis)

    def test_every_rule_carries_a_nonempty_basis(self):
        from AgentCore.model_scanner.classification import LICENSING_RULES
        for rule in LICENSING_RULES:
            self.assertTrue(rule.basis.strip(), f"{rule.token} has no stated basis")


class TestParsing(unittest.TestCase):
    def test_parses_and_ranks_by_pass_rate_descending(self):
        results = scanner.parse(_VALID_YAML)
        self.assertEqual([r.pass_rate for r in results], [88.0, 71.4, 40.0])
        self.assertEqual(results[0].model, "gpt-5 (high)")

    def test_prefers_headline_pass_rate_2_over_pass_rate_1(self):
        results = scanner.parse(_VALID_YAML)
        self.assertEqual(results[0].pass_rate, 88.0)  # not 70.0

    def test_entry_without_any_pass_rate_is_skipped_not_defaulted_to_zero(self):
        """A missing measurement is not a measurement of zero -- defaulting
        would silently rank a model last on the basis of absent data."""
        results = scanner.parse(_VALID_YAML + "\n- model: No Rate Model\n  date: 2025-02-02\n")
        self.assertNotIn("No Rate Model", [r.model for r in results])

    def test_empty_result_set_raises_rather_than_reporting_an_empty_ranking(self):
        with self.assertRaises(BenchmarkSourceError) as ctx:
            scanner.parse("- notamodel: true\n")
        self.assertIn("zero usable entries", str(ctx.exception))

    def test_non_list_yaml_raises_schema_error(self):
        with self.assertRaises(BenchmarkSourceError) as ctx:
            scanner.parse("model: not-a-list\n")
        self.assertIn("expected a list", str(ctx.exception))

    def test_malformed_yaml_raises_source_error_not_a_raw_yaml_exception(self):
        with self.assertRaises(BenchmarkSourceError):
            scanner.parse("::: not : valid : yaml : [")


class TestStalenessIsAboutDataNotFetchTime(unittest.TestCase):
    def _scan_with_newest(self, newest: date) -> scanner.ScanResult:
        yaml_text = f"- model: gpt-5\n  pass_rate_2: 88.0\n  date: {newest.isoformat()}\n"
        with mock.patch.object(scanner, "fetch_raw", return_value=yaml_text):
            return scanner.scan()

    def test_freshly_fetched_but_old_data_is_reported_stale(self):
        """
        The whole point of the two-timestamp design: fetching just now
        must not make year-old data look current.
        """
        result = self._scan_with_newest(date.today() - timedelta(days=300))
        self.assertTrue(result.is_stale)
        self.assertGreater(result.data_age_days, 90)
        # Fetched moments ago, yet still stale.
        self.assertLess((datetime.now(timezone.utc) - result.fetched_at).total_seconds(), 60)

    def test_recent_data_is_not_stale(self):
        result = self._scan_with_newest(date.today() - timedelta(days=3))
        self.assertFalse(result.is_stale)

    def test_newest_entry_date_is_the_max_not_the_first(self):
        yaml_text = (
            "- model: gpt-5\n  pass_rate_2: 88.0\n  date: 2025-01-01\n"
            "- model: claude-3-5-sonnet\n  pass_rate_2: 60.0\n  date: 2025-09-09\n"
        )
        with mock.patch.object(scanner, "fetch_raw", return_value=yaml_text):
            result = scanner.scan()
        self.assertEqual(result.newest_entry_date, date(2025, 9, 9))


class TestFetchAllowList(unittest.TestCase):
    def test_refuses_urls_outside_the_allow_list(self):
        """
        The allow-list is the containment boundary for this tool's
        `general` data classification (§3.7b) -- it must not be a
        parameter a caller can widen at runtime.
        """
        with self.assertRaises(BenchmarkSourceError) as ctx:
            scanner.fetch_raw("https://example.com/anything.yml")
        self.assertIn("allow-list", str(ctx.exception))

    def test_unreachable_source_fails_honestly_with_no_substituted_data(self):
        import urllib.error
        with mock.patch("urllib.request.urlopen", side_effect=urllib.error.URLError("offline")):
            with self.assertRaises(BenchmarkSourceError) as ctx:
                scanner.fetch_raw()
        self.assertIn("No cached or substituted ranking", str(ctx.exception))


class TestSectioning(unittest.TestCase):
    def test_by_licensing_splits_cloud_and_open(self):
        with mock.patch.object(scanner, "fetch_raw", return_value=_VALID_YAML):
            result = scanner.scan()
        self.assertEqual([r.model for r in result.by_licensing(Licensing.CLOUD)], ["gpt-5 (high)"])
        self.assertEqual([r.model for r in result.by_licensing(Licensing.OPEN_WEIGHTS)], ["DeepSeek R1"])
        self.assertEqual(
            [r.model for r in result.by_licensing(Licensing.UNCLASSIFIED)],
            ["Some Unknown Model X"],
        )


@unittest.skipIf(
    os.environ.get("JARVIS_SKIP_NETWORK_TESTS") == "1",
    "network tests disabled via JARVIS_SKIP_NETWORK_TESTS",
)
class TestLiveSourceIfReachable(unittest.TestCase):
    """
    One real call against the real leaderboard, skipped cleanly when the
    network is unavailable rather than failing or fabricating a result --
    same convention as the live SerpApi test in AgentCore/knowledge/tests/.
    """

    def test_live_source_parses_and_yields_both_sections(self):
        try:
            result = scanner.scan()
        except BenchmarkSourceError as e:
            self.skipTest(f"benchmark source unreachable: {e}")
        self.assertGreater(len(result.results), 10)
        self.assertTrue(result.by_licensing(Licensing.CLOUD))
        self.assertTrue(result.by_licensing(Licensing.OPEN_WEIGHTS))
        self.assertIsNotNone(result.newest_entry_date)


if __name__ == "__main__":
    unittest.main()
