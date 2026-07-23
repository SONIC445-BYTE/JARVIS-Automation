"""
Phase 2d: the 11 audit-confirmed real/near-real AgentCore/platform_adapters
folders (docs/adapter_audit.md), ported onto the daemon contract.

Covers: CommandRouter resolution for each platform's key actions,
dry-run execution via UIExecutor.execute_intent(), and the two specific
extraction-logic fixes this porting work required (calculate's verb-
prefix stripping, save_file's "to"-marker + alias-fallback filtering).

play (Spotify/YouTube) is the only genuine UIScanner use case among the
11 -- element_finder is mocked here so these tests never depend on (or
are slowed by) a real screen scan, and to prove the honest-failure path
when nothing is found.
"""
import unittest
from unittest import mock

from AgentCore.command_router import CommandRouter
from AgentCore.ui_executor import UIExecutor, ExecutionStatus
from daemon.intent_parser import Intent


class TestPhase2dResolution(unittest.TestCase):
    def setUp(self):
        self.router = CommandRouter()

    def _assert_resolves(self, text, adapter, action):
        intent = self.router.resolve(text)
        self.assertIsNotNone(intent, f"{text!r} did not resolve")
        self.assertEqual(intent.adapter, adapter)
        self.assertEqual(intent.action, action)
        return intent

    def test_amazon(self):
        self._assert_resolves("open amazon", "amazon", "open_app")
        self._assert_resolves("search amazon for wireless mouse", "amazon", "send_message")

    def test_google(self):
        self._assert_resolves("open google", "google", "open_app")
        self._assert_resolves("search google for python tutorials", "google", "send_message")

    def test_chrome_new_tab_close_tab(self):
        self._assert_resolves("new tab in browser", "browser", "new_tab")
        self._assert_resolves("close tab in browser", "browser", "close_tab")
        # Regression: close_app must still win for plain "close browser",
        # not be shadowed by close_tab's more specific multi-word verb.
        self._assert_resolves("close browser", "browser", "close_app")

    def test_calculator(self):
        self._assert_resolves("open calculator", "calculator", "open_app")
        self._assert_resolves("close calculator", "calculator", "close_app")
        intent = self._assert_resolves("calculate 5 plus 3", "calculator", "calculate")
        self.assertEqual(intent.message, "5 plus 3")  # verb prefix stripped

    def test_explorer(self):
        self._assert_resolves("open explorer", "explorer", "open_app")
        self._assert_resolves("open file explorer", "explorer", "open_app")

    def test_twitter(self):
        self._assert_resolves("open twitter", "twitter", "open_app")
        intent = self._assert_resolves("post a tweet saying hello world", "twitter", "send_message")
        self.assertEqual(intent.message, "hello world")

    def test_spotify(self):
        self._assert_resolves("open spotify", "spotify", "open_app")
        self._assert_resolves("search spotify for lofi beats", "spotify", "send_message")
        self._assert_resolves("play spotify song bohemian rhapsody", "spotify", "play")

    def test_youtube(self):
        self._assert_resolves("open youtube", "youtube", "open_app")
        self._assert_resolves("search youtube for cat videos", "youtube", "send_message")
        self._assert_resolves("play youtube video funny cats", "youtube", "play")

    def test_notepad_save_file_with_filename(self):
        intent = self._assert_resolves("save notepad to report.txt", "text_editor", "save_file")
        self.assertEqual(intent.target, "report.txt")

    def test_whatsapp_gmail_unaffected_by_porting(self):
        # Regression: these two were already correct (daemon versions
        # never had the audit's coordinate/incomplete-send defects) --
        # porting the other 9 platforms must not disturb them.
        self._assert_resolves("open whatsapp", "whatsapp_desktop", "open_app")
        self._assert_resolves("open gmail", "gmail_browser", "open_app")

    def test_unrelated_text_unaffected(self):
        self.assertIsNone(self.router.resolve("what time is it"))


class TestPhase2dDryRunExecution(unittest.TestCase):
    def setUp(self):
        self.executor = UIExecutor(adapter_dry_run=True)

    def _run(self, adapter, action, target="", message=""):
        return self.executor.execute_intent(Intent(adapter=adapter, action=action, target=target, message=message))

    def test_amazon_open_and_search(self):
        self.assertEqual(self._run("amazon", "open_app").status, ExecutionStatus.SUCCESS)
        self.assertEqual(self._run("amazon", "send_message", target="wireless mouse").status, ExecutionStatus.SUCCESS)

    def test_google_open_and_search(self):
        self.assertEqual(self._run("google", "open_app").status, ExecutionStatus.SUCCESS)
        self.assertEqual(self._run("google", "send_message", target="python").status, ExecutionStatus.SUCCESS)

    def test_chrome_new_tab_close_tab(self):
        self.assertEqual(self._run("browser", "new_tab").status, ExecutionStatus.SUCCESS)
        self.assertEqual(self._run("browser", "close_tab").status, ExecutionStatus.SUCCESS)

    def test_calculator_full_lifecycle(self):
        self.assertEqual(self._run("calculator", "open_app").status, ExecutionStatus.SUCCESS)
        self.assertEqual(self._run("calculator", "calculate", message="5 plus 3").status, ExecutionStatus.SUCCESS)
        self.assertEqual(self._run("calculator", "close_app").status, ExecutionStatus.SUCCESS)

    def test_explorer_open(self):
        self.assertEqual(self._run("explorer", "open_app").status, ExecutionStatus.SUCCESS)

    def test_twitter_post(self):
        self.assertEqual(
            self._run("twitter", "send_message", message="hello world").status, ExecutionStatus.SUCCESS
        )

    def test_spotify_search_and_play(self):
        self.assertEqual(self._run("spotify", "send_message", target="lofi").status, ExecutionStatus.SUCCESS)
        self.assertEqual(self._run("spotify", "play", message="bohemian rhapsody").status, ExecutionStatus.SUCCESS)

    def test_youtube_search_and_play(self):
        self.assertEqual(self._run("youtube", "send_message", target="cats").status, ExecutionStatus.SUCCESS)
        self.assertEqual(self._run("youtube", "play", message="funny cats").status, ExecutionStatus.SUCCESS)

    def test_notepad_save_file(self):
        self.assertEqual(
            self._run("text_editor", "save_file", target="report.txt").status, ExecutionStatus.SUCCESS
        )


class TestPlayActionHonestFailure(unittest.TestCase):
    """The one genuine UIScanner use case: play must fail honestly (not
    fake success) when the target element can't be found -- unlike the
    original AgentCore/platform_adapters/spotify and /youtube, whose
    click-through was commented out / a no-op but still returned as if
    the plan succeeded."""

    def test_spotify_play_fails_honestly_when_element_not_found(self):
        from platform_adapters.spotify_adapter import SpotifyAdapter

        class NullLogger:
            def info(self, p):
                pass

        adapter = SpotifyAdapter(logger=NullLogger(), dry_run=False)
        with mock.patch.object(adapter, "_navigate", return_value=True), \
             mock.patch("platform_adapters.spotify_adapter.find_element_center", return_value=None), \
             mock.patch("time.sleep"):
            result = adapter.play(message="some song")
        self.assertFalse(result)

    def test_youtube_play_fails_honestly_when_element_not_found(self):
        from platform_adapters.youtube_adapter import YouTubeAdapter

        class NullLogger:
            def info(self, p):
                pass

        adapter = YouTubeAdapter(logger=NullLogger(), dry_run=False)
        with mock.patch.object(adapter, "_navigate", return_value=True), \
             mock.patch("platform_adapters.youtube_adapter.find_first_clickable_center", return_value=None), \
             mock.patch("time.sleep"):
            result = adapter.play(message="some video")
        self.assertFalse(result)

    def test_calculator_normalizes_word_operators(self):
        # Found via a live end-to-end test: Windows Calculator's text
        # input doesn't understand English words -- "12 times 8" typed
        # literally does not compute. The original audit folder had this
        # same gap; fixed here since calculate is a genuinely new
        # capability, not a straight port.
        from platform_adapters.calculator_adapter import _normalize_expression

        self.assertEqual(_normalize_expression("12 times 8"), "12*8")
        self.assertEqual(_normalize_expression("5 plus 3"), "5+3")
        self.assertEqual(_normalize_expression("10 minus 4"), "10-4")
        self.assertEqual(_normalize_expression("20 divided by 5"), "20/5")

    def test_spotify_play_clicks_real_element_when_found(self):
        from platform_adapters.spotify_adapter import SpotifyAdapter

        class NullLogger:
            def info(self, p):
                pass

        adapter = SpotifyAdapter(logger=NullLogger(), dry_run=False)
        mock_backend = mock.Mock()
        adapter.backend = mock_backend
        with mock.patch.object(adapter, "_navigate", return_value=True), \
             mock.patch("platform_adapters.spotify_adapter.find_element_center", return_value=(123, 456)), \
             mock.patch("time.sleep"):
            result = adapter.play(message="some song")
        self.assertTrue(result)
        mock_backend.click.assert_called_once_with(123, 456)


class NullLogger:
    def info(self, p):
        pass


class TestExtractQueryGuard(unittest.TestCase):
    """Adversarial-testing bugs found after Phase 2d: 'search google for
    X' and 'play X on spotify' resolved to a garbage query (the platform
    alias, or the entire raw phrase with the verb still attached) instead
    of failing or extracting correctly. This is worse than a clean
    failure -- it's an "I did something" outcome that did the wrong
    thing. extract_query() (platform_adapters/adapter_base.py) is the
    shared guard; these tests exercise it through the real adapter
    methods, not just in isolation."""

    def test_google_search_for_extracts_real_query(self):
        from platform_adapters.google_adapter import GoogleAdapter

        adapter = GoogleAdapter(logger=NullLogger(), dry_run=True)
        with mock.patch.object(adapter, "_navigate", return_value=True) as mock_navigate:
            result = adapter.send_message(target="google", message="python tutorials")
        self.assertTrue(result)
        self.assertIn("python%20tutorials", mock_navigate.call_args[0][0])

    def test_google_search_with_only_alias_fails_honestly(self):
        from platform_adapters.google_adapter import GoogleAdapter

        adapter = GoogleAdapter(logger=NullLogger(), dry_run=True)
        result = adapter.send_message(target="google", message="")
        self.assertFalse(result)

    def test_spotify_play_with_trailing_platform_name_extracts_real_query(self):
        # "play despacito on spotify" -- message correctly holds
        # "despacito" (trimmed of "on spotify") once resolved by
        # CommandRouter; play() must use that, not fall back to target
        # (which would be the "spotify" alias).
        from platform_adapters.spotify_adapter import SpotifyAdapter

        adapter = SpotifyAdapter(logger=NullLogger(), dry_run=False)
        with mock.patch.object(adapter, "_navigate", return_value=True) as mock_navigate, \
             mock.patch("platform_adapters.spotify_adapter.find_element_center", return_value=(1, 1)), \
             mock.patch("time.sleep"):
            result = adapter.play(target="spotify", message="despacito")
        self.assertTrue(result)
        self.assertIn("despacito", mock_navigate.call_args[0][0])

    def test_calculator_bare_verb_fails_honestly_not_garbage_expression(self):
        # "calculate" alone must not type the literal word "calculate"
        # into the Calculator app.
        from platform_adapters.calculator_adapter import CalculatorAdapter

        adapter = CalculatorAdapter(logger=NullLogger(), dry_run=True)
        result = adapter.calculate(target="calculate", message="calculate")
        self.assertFalse(result)

    def test_twitter_post_with_trailing_platform_name_extracts_real_text(self):
        from platform_adapters.twitter_adapter import TwitterAdapter

        adapter = TwitterAdapter(logger=NullLogger(), dry_run=True)
        with mock.patch.object(adapter, "_navigate", return_value=True) as mock_navigate:
            result = adapter.send_message(target="twitter", message="hello world")
        self.assertTrue(result)
        self.assertIn("hello%20world", mock_navigate.call_args[0][0])


if __name__ == "__main__":
    unittest.main()
