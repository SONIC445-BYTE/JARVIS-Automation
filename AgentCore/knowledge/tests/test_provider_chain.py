
# AgentCore/knowledge/tests/test_provider_chain.py
"""
S0-E3: tiered knowledge-discovery provider chain (SerpApi -> Serper ->
browser automation). Covers fallback ordering, honest failure, the
narration hook, config-driven provider order, and the coupling
regression that matters most here: importing this module tree must not
pull selenium/webdriver_manager into sys.modules just because the
last-resort tier exists in the same package.
"""
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

from AgentCore.knowledge.provider_chain import fetch_with_fallback
from AgentCore.knowledge.serpapi_fetcher import SerpApiCallError, SerpApiConfigError
from AgentCore.knowledge.serper_fetcher import SerperCallError, SerperConfigError

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent


class TestProviderChainOrdering(unittest.TestCase):
    def test_first_configured_tier_wins_without_touching_later_tiers(self):
        fake_results = [{"title": "T", "url": "https://x.test", "snippet": "s", "source": "serpapi"}]
        with mock.patch("AgentCore.knowledge.provider_chain.fetch_serpapi", return_value=fake_results) as m_serpapi, \
             mock.patch("AgentCore.knowledge.provider_chain.fetch_serper") as m_serper, \
             mock.patch("AgentCore.knowledge.provider_chain._fetch_browser") as m_browser:
            results, provider = fetch_with_fallback("test query", provider_order=["serpapi", "serper", "browser"])

        self.assertEqual(provider, "serpapi")
        self.assertEqual(results, fake_results)
        m_serpapi.assert_called_once()
        m_serper.assert_not_called()
        m_browser.assert_not_called()

    def test_falls_through_on_unconfigured_tier_to_the_next(self):
        fake_results = [{"title": "T", "url": "https://x.test", "snippet": "s", "source": "serper"}]
        with mock.patch("AgentCore.knowledge.provider_chain.fetch_serpapi", side_effect=SerpApiConfigError("no key")), \
             mock.patch("AgentCore.knowledge.provider_chain.fetch_serper", return_value=fake_results) as m_serper, \
             mock.patch("AgentCore.knowledge.provider_chain._fetch_browser") as m_browser:
            results, provider = fetch_with_fallback("test query", provider_order=["serpapi", "serper", "browser"])

        self.assertEqual(provider, "serper")
        self.assertEqual(results, fake_results)
        m_serper.assert_called_once()
        m_browser.assert_not_called()

    def test_falls_through_on_a_real_call_failure_not_just_missing_config(self):
        fake_results = [{"title": "T", "url": "https://x.test", "snippet": "s", "source": "duckduckgo"}]
        with mock.patch("AgentCore.knowledge.provider_chain.fetch_serpapi", side_effect=SerpApiCallError("HTTP 500")), \
             mock.patch("AgentCore.knowledge.provider_chain.fetch_serper", side_effect=SerperCallError("timeout")), \
             mock.patch("AgentCore.knowledge.provider_chain._fetch_browser", return_value=fake_results) as m_browser:
            results, provider = fetch_with_fallback("test query", provider_order=["serpapi", "serper", "browser"])

        self.assertEqual(provider, "browser")
        self.assertEqual(results, fake_results)
        m_browser.assert_called_once()

    def test_honest_failure_when_every_tier_is_exhausted(self):
        # All three configured but every one returns nothing real -- must
        # be indistinguishable from "no provider answered", not silently
        # report a fake success.
        with mock.patch("AgentCore.knowledge.provider_chain.fetch_serpapi", return_value=[]), \
             mock.patch("AgentCore.knowledge.provider_chain.fetch_serper", return_value=[]), \
             mock.patch("AgentCore.knowledge.provider_chain._fetch_browser", return_value=[]):
            results, provider = fetch_with_fallback("test query", provider_order=["serpapi", "serper", "browser"])

        self.assertEqual(results, [])
        self.assertIsNone(provider)

    def test_unknown_provider_name_in_order_is_skipped_not_fatal(self):
        fake_results = [{"title": "T", "url": "https://x.test", "snippet": "s", "source": "serper"}]
        with mock.patch("AgentCore.knowledge.provider_chain.fetch_serper", return_value=fake_results):
            results, provider = fetch_with_fallback("test query", provider_order=["not_a_real_provider", "serper"])

        self.assertEqual(provider, "serper")
        self.assertEqual(results, fake_results)


class TestProviderChainNarration(unittest.TestCase):
    def test_notify_called_once_before_first_attempt(self):
        calls = []
        with mock.patch("AgentCore.knowledge.provider_chain.fetch_serpapi", return_value=[{"title": "T", "url": "u", "snippet": "s", "source": "serpapi"}]):
            fetch_with_fallback("q", provider_order=["serpapi"], notify=calls.append)

        self.assertEqual(calls, ["Let me check that..."])

    def test_notify_narrates_each_fallback(self):
        calls = []
        with mock.patch("AgentCore.knowledge.provider_chain.fetch_serpapi", side_effect=SerpApiConfigError("no key")), \
             mock.patch("AgentCore.knowledge.provider_chain.fetch_serper", return_value=[{"title": "T", "url": "u", "snippet": "s", "source": "serper"}]):
            fetch_with_fallback("q", provider_order=["serpapi", "serper"], notify=calls.append)

        self.assertEqual(calls[0], "Let me check that...")
        self.assertIn("Serper", calls[1])

    def test_notify_gets_an_honest_final_message_when_everything_fails(self):
        calls = []
        with mock.patch("AgentCore.knowledge.provider_chain.fetch_serpapi", return_value=[]):
            fetch_with_fallback("q", provider_order=["serpapi"], notify=calls.append)

        self.assertIn("couldn't find anything", calls[-1].lower())

    def test_no_notify_means_no_crash_and_no_calls(self):
        # Default path -- most callers won't pass notify at all.
        with mock.patch("AgentCore.knowledge.provider_chain.fetch_serpapi", return_value=[{"title": "T", "url": "u", "snippet": "s", "source": "serpapi"}]):
            results, provider = fetch_with_fallback("q", provider_order=["serpapi"])
        self.assertEqual(provider, "serpapi")


class TestConfigDrivenProviderOrder(unittest.TestCase):
    def test_env_var_overrides_default_order(self):
        # Fresh subprocess -- config.py reads KNOWLEDGE_PROVIDER_ORDER at
        # import time, so this must not share this test process's
        # already-imported module state.
        script = (
            "from AgentCore.knowledge.config import KNOWLEDGE_PROVIDER_ORDER\n"
            "print(','.join(KNOWLEDGE_PROVIDER_ORDER))\n"
        )
        proc = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=20,
            cwd=str(REPO_ROOT),
            env={**__import__("os").environ, "KNOWLEDGE_PROVIDER_ORDER": "serper,browser"},
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), "serper,browser")

    def test_default_order_is_serpapi_then_serper_then_browser(self):
        script = (
            "from AgentCore.knowledge.config import KNOWLEDGE_PROVIDER_ORDER\n"
            "print(','.join(KNOWLEDGE_PROVIDER_ORDER))\n"
        )
        import os
        env = {k: v for k, v in os.environ.items() if k != "KNOWLEDGE_PROVIDER_ORDER"}
        proc = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=20,
            cwd=str(REPO_ROOT),
            env=env,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), "serpapi,serper,browser")


class TestSerpApiConfigAndQuota(unittest.TestCase):
    def test_fetch_serpapi_raises_config_error_without_a_key(self):
        from AgentCore.knowledge.serpapi_fetcher import fetch_serpapi
        with mock.patch.dict("os.environ", {}, clear=False):
            import os
            os.environ.pop("SERPAPI_KEY", None)
            with self.assertRaises(SerpApiConfigError):
                fetch_serpapi("test query")

    def test_get_quota_returns_none_without_a_key_rather_than_raising(self):
        from AgentCore.knowledge.serpapi_fetcher import get_quota
        import os
        with mock.patch.dict("os.environ", {}, clear=False):
            os.environ.pop("SERPAPI_KEY", None)
            self.assertIsNone(get_quota())

    def test_fetch_serpapi_raises_call_error_on_a_real_invalid_key_not_just_a_missing_one(self):
        # Adversarial case, live-verified against the real endpoint
        # (2026-07-30): a key that IS set but IS wrong must be distinct
        # from "not configured" -- both need to fall through to the next
        # tier, but conflating "invalid" with "missing" would hide a
        # genuinely broken deployment as if the tier were merely unused.
        from AgentCore.knowledge.serpapi_fetcher import fetch_serpapi
        with mock.patch.dict("os.environ", {"SERPAPI_KEY": "deliberately-invalid-key"}):
            with self.assertRaises(SerpApiCallError):
                fetch_serpapi("test query")

    def test_get_quota_parses_the_real_account_json_shape(self):
        # Shape confirmed live against https://serpapi.com/account.json
        # on 2026-07-30 -- this is the real response shape, not a guess.
        from AgentCore.knowledge.serpapi_fetcher import get_quota
        fake_response = mock.Mock(status_code=200)
        fake_response.json.return_value = {
            "account_id": "68cfbb4122efbda8b9b90104",
            "plan_id": "free",
            "searches_per_month": 250,
            "plan_searches_left": 249,
            "total_searches_left": 249,
            "this_month_usage": 1,
            "this_hour_searches": 1,
            "account_rate_limit_per_hour": 250,
        }
        with mock.patch.dict("os.environ", {"SERPAPI_KEY": "fake-key-for-test"}), \
             mock.patch("AgentCore.knowledge.serpapi_fetcher.requests.get", return_value=fake_response):
            quota = get_quota()

        self.assertEqual(quota["plan_searches_left"], 249)
        self.assertEqual(quota["total_searches_left"], 249)
        self.assertEqual(quota["searches_per_month"], 250)


class TestSerpFetcherImportCoupling(unittest.TestCase):
    """
    Mirrors test_nethytech_listen_import_coupling.py's discipline: the
    browser-automation tier is last-resort and must not pull selenium/
    webdriver_manager into sys.modules just because AgentCore.knowledge
    (or provider_chain, or discovery_manager) was imported.
    """

    def test_importing_knowledge_package_does_not_pull_selenium(self):
        script = (
            "import sys\n"
            "import AgentCore.knowledge\n"
            "print('selenium' in sys.modules)\n"
            "print('webdriver_manager' in sys.modules)\n"
        )
        proc = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=20,
            cwd=str(REPO_ROOT),
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        lines = proc.stdout.strip().splitlines()[-2:]
        self.assertEqual(
            lines,
            ["False", "False"],
            "importing AgentCore.knowledge should not pull selenium or "
            "webdriver_manager into sys.modules -- if either now prints "
            "True, the lazy-import fix in serp_fetcher.py has regressed.",
        )

    def test_importing_provider_chain_directly_does_not_pull_selenium(self):
        script = (
            "import sys\n"
            "import AgentCore.knowledge.provider_chain\n"
            "print('selenium' in sys.modules)\n"
        )
        proc = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=20,
            cwd=str(REPO_ROOT),
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip().splitlines()[-1], "False")


class TestSerpApiLiveIfKeyAvailable(unittest.TestCase):
    """
    Real, live verification against the actual SerpApi endpoint -- skipped
    automatically if no key is available in the environment, never
    fabricated. Run with SERPAPI_KEY set to actually exercise this.
    """

    def test_real_live_call_returns_structured_results(self):
        import os
        if not os.environ.get("SERPAPI_KEY"):
            self.skipTest("SERPAPI_KEY not set in environment -- skipping live call")

        from AgentCore.knowledge.serpapi_fetcher import fetch_serpapi
        results = fetch_serpapi("current president of the United States", max_results=3)

        self.assertGreater(len(results), 0)
        for r in results:
            self.assertIn("title", r)
            self.assertIn("url", r)
            self.assertEqual(r["source"], "serpapi")


if __name__ == "__main__":
    unittest.main()
