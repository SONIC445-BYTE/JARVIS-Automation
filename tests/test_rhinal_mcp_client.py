"""
RHINAL MCP integration -- client wrapper tests.

RHINAL (github.com/SONIC445-BYTE/RHINAL) is a separate project. Verified
live before any of this was written: cloned it, read mcp-server/src/
{index,tools,config}.ts, built it (npm install && npm run build), spawned
the real built server over stdio with a real rhk_ key, and called the
real MCP tools/list -- 14 tools came back, exactly matching what's
registered in index.ts. These tests mock the MCP session (no live
process, no network) since they run in CI/without Node/without a real
key -- the live verification already happened once, directly, per
instruction; these guard the Python-side wiring against regressing.
"""
import unittest
from unittest import mock

from AgentCore.rhinal_mcp_client import (
    RhinalCallError,
    RhinalConfig,
    RhinalConfigError,
    RhinalMCPClient,
    load_rhinal_config,
)


class TestLoadRhinalConfig(unittest.TestCase):
    def test_raises_when_all_missing(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(RhinalConfigError) as ctx:
                load_rhinal_config()
        self.assertIn("RHINAL_MCP_SERVER_PATH", str(ctx.exception))
        self.assertIn("RHINAL_BASE_URL", str(ctx.exception))
        self.assertIn("RHINAL_API_KEY", str(ctx.exception))

    def test_raises_naming_only_the_missing_ones(self):
        env = {"RHINAL_MCP_SERVER_PATH": "/x/dist/index.js", "RHINAL_BASE_URL": "https://rhinal.vercel.app"}
        with mock.patch.dict("os.environ", env, clear=True):
            with self.assertRaises(RhinalConfigError) as ctx:
                load_rhinal_config()
        self.assertIn("RHINAL_API_KEY", str(ctx.exception))
        self.assertNotIn("RHINAL_MCP_SERVER_PATH is required", str(ctx.exception))

    def test_loads_successfully_when_all_present(self):
        env = {
            "RHINAL_MCP_SERVER_PATH": "/x/dist/index.js",
            "RHINAL_BASE_URL": "https://rhinal.vercel.app/",
            "RHINAL_API_KEY": "rhk_test",
        }
        with mock.patch.dict("os.environ", env, clear=True):
            cfg = load_rhinal_config()
        self.assertEqual(cfg.server_path, "/x/dist/index.js")
        self.assertEqual(cfg.base_url, "https://rhinal.vercel.app")  # trailing slash stripped
        self.assertEqual(cfg.api_key, "rhk_test")
        self.assertIsNone(cfg.model_id)

    def test_optional_model_id_and_provider_pass_through(self):
        env = {
            "RHINAL_MCP_SERVER_PATH": "/x/dist/index.js",
            "RHINAL_BASE_URL": "https://rhinal.vercel.app",
            "RHINAL_API_KEY": "rhk_test",
            "RHINAL_MODEL_ID": "gpt-5.1",
            "RHINAL_PROVIDER": "openai",
        }
        with mock.patch.dict("os.environ", env, clear=True):
            cfg = load_rhinal_config()
        self.assertEqual(cfg.model_id, "gpt-5.1")
        self.assertEqual(cfg.provider, "openai")


class TestRhinalMCPClientCapture(unittest.TestCase):
    def _config(self):
        return RhinalConfig(server_path="/x/dist/index.js", base_url="https://rhinal.vercel.app", api_key="rhk_test")

    def test_config_error_propagates_without_touching_network(self):
        client = RhinalMCPClient()  # no config injected -> loads from env
        with mock.patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(RhinalConfigError):
                client.capture("a thought")

    @mock.patch("AgentCore.rhinal_mcp_client._call_tool_async")
    def test_capture_calls_call_tool_async_with_text_and_mode(self, mock_call_tool_async):
        async def fake(cfg, name, arguments):
            return {"saved": True, "vaultWorthy": True, "_name": name, "_arguments": arguments}

        mock_call_tool_async.side_effect = fake
        client = RhinalMCPClient(config=self._config())

        result = client.capture("a thought", mode="decision")

        self.assertEqual(result["saved"], True)
        self.assertEqual(result["_name"], "rhinal_capture")
        self.assertEqual(result["_arguments"], {"text": "a thought", "mode": "decision"})

    @mock.patch("AgentCore.rhinal_mcp_client._call_tool_async")
    def test_capture_omits_mode_key_when_not_given(self, mock_call_tool_async):
        async def fake(cfg, name, arguments):
            return {"_arguments": arguments}

        mock_call_tool_async.side_effect = fake
        client = RhinalMCPClient(config=self._config())

        result = client.capture("a thought")

        self.assertEqual(result["_arguments"], {"text": "a thought"})

    def test_server_path_missing_raises_call_error_before_spawning(self):
        # _call_tool_async's own os.path.exists check -- verified directly
        # (not mocked away) since this is the exact honest-failure path a
        # not-yet-built RHINAL checkout hits.
        import asyncio
        from AgentCore.rhinal_mcp_client import _call_tool_async

        cfg = RhinalConfig(server_path="/definitely/does/not/exist/index.js", base_url="https://rhinal.vercel.app", api_key="rhk_test")
        with self.assertRaises(RhinalCallError) as ctx:
            asyncio.run(_call_tool_async(cfg, "rhinal_capture", {"text": "x"}))
        self.assertIn("isn't built", str(ctx.exception))

    def test_is_error_result_raises_call_error_with_message(self):
        # Mocks at the MCP SDK boundary (stdio_client/ClientSession), not
        # _call_tool_async itself, so the real isError-handling logic in
        # _call_tool_async actually runs and is what's being tested --
        # this is the exact shape of the real, live-confirmed "Missing
        # modelId" response this rhk_ key's account produced.
        import asyncio
        from AgentCore.rhinal_mcp_client import _call_tool_async

        fake_block = mock.Mock(text="Error: Missing modelId")
        fake_result = mock.Mock(isError=True, content=[fake_block])

        fake_session = mock.AsyncMock()
        fake_session.initialize = mock.AsyncMock()
        fake_session.call_tool = mock.AsyncMock(return_value=fake_result)
        fake_session.__aenter__ = mock.AsyncMock(return_value=fake_session)
        fake_session.__aexit__ = mock.AsyncMock(return_value=False)

        fake_stdio_ctx = mock.AsyncMock()
        fake_stdio_ctx.__aenter__ = mock.AsyncMock(return_value=(mock.Mock(), mock.Mock()))
        fake_stdio_ctx.__aexit__ = mock.AsyncMock(return_value=False)

        cfg = self._config()
        with mock.patch("os.path.exists", return_value=True), \
             mock.patch("mcp.client.stdio.stdio_client", return_value=fake_stdio_ctx), \
             mock.patch("mcp.ClientSession", return_value=fake_session):
            with self.assertRaises(RhinalCallError) as ctx:
                asyncio.run(_call_tool_async(cfg, "rhinal_capture", {"text": "x"}))
        self.assertIn("Missing modelId", str(ctx.exception))


class TestRhinalMCPClientOtherTools(unittest.TestCase):
    """The remaining 12 tools (RHINAL 13-tool wiring phase). Each test
    verifies the tool name and argument mapping this client sends -- the
    same shape of test as TestRhinalMCPClientCapture above, extended to
    every method added against a real read of mcp-server/src/{index,
    tools}.ts (see AgentCore/rhinal_mcp_client.py's own comment block for
    the risk-class re-verification this was checked against, independent
    of the earlier 14-tool verification entry). All 7 read-only tools plus
    check_contradiction were additionally called live once each against the
    real deployed backend before these mocked tests were written -- see the
    execution log's RHINAL 13-tool wiring entry for the real responses.
    """

    def _config(self):
        return RhinalConfig(server_path="/x/dist/index.js", base_url="https://rhinal.vercel.app", api_key="rhk_test")

    def _client_calling(self, mock_call_tool_async):
        async def fake(cfg, name, arguments):
            return {"_name": name, "_arguments": arguments}
        mock_call_tool_async.side_effect = fake
        return RhinalMCPClient(config=self._config())

    @mock.patch("AgentCore.rhinal_mcp_client._call_tool_async")
    def test_recall(self, m):
        r = self._client_calling(m).recall("what did I say about X")
        self.assertEqual(r["_name"], "rhinal_recall")
        self.assertEqual(r["_arguments"], {"query": "what did I say about X"})

    @mock.patch("AgentCore.rhinal_mcp_client._call_tool_async")
    def test_ask_vault(self, m):
        r = self._client_calling(m).ask_vault("what did I decide about X")
        self.assertEqual(r["_name"], "rhinal_ask_vault")
        self.assertEqual(r["_arguments"], {"question": "what did I decide about X"})

    @mock.patch("AgentCore.rhinal_mcp_client._call_tool_async")
    def test_classify_worthiness(self, m):
        r = self._client_calling(m).classify_worthiness("some observation")
        self.assertEqual(r["_name"], "rhinal_classify_worthiness")
        self.assertEqual(r["_arguments"], {"text": "some observation"})

    @mock.patch("AgentCore.rhinal_mcp_client._call_tool_async")
    def test_decision_log(self, m):
        r = self._client_calling(m).decision_log("chose X because Y")
        self.assertEqual(r["_name"], "rhinal_decision_log")
        self.assertEqual(r["_arguments"], {"text": "chose X because Y"})

    @mock.patch("AgentCore.rhinal_mcp_client._call_tool_async")
    def test_idea_to_spec(self, m):
        r = self._client_calling(m).idea_to_spec("loose notes about a feature")
        self.assertEqual(r["_name"], "rhinal_idea_to_spec")
        self.assertEqual(r["_arguments"], {"text": "loose notes about a feature"})

    @mock.patch("AgentCore.rhinal_mcp_client._call_tool_async")
    def test_confront(self, m):
        r = self._client_calling(m).confront("my understanding of X")
        self.assertEqual(r["_name"], "rhinal_confront")
        self.assertEqual(r["_arguments"], {"outline": "my understanding of X"})

    @mock.patch("AgentCore.rhinal_mcp_client._call_tool_async")
    def test_tag_prediction_with_follow_up(self, m):
        r = self._client_calling(m).tag_prediction("notion-123", 80, follow_up_at="2026-09-01")
        self.assertEqual(r["_name"], "rhinal_tag_prediction")
        self.assertEqual(r["_arguments"], {"notionId": "notion-123", "confidence": 80, "followUpAt": "2026-09-01"})

    @mock.patch("AgentCore.rhinal_mcp_client._call_tool_async")
    def test_tag_prediction_without_follow_up_omits_key(self, m):
        r = self._client_calling(m).tag_prediction("notion-123", 50)
        self.assertEqual(r["_arguments"], {"notionId": "notion-123", "confidence": 50})

    def test_tag_prediction_rejects_out_of_range_confidence(self):
        client = RhinalMCPClient(config=self._config())
        with self.assertRaises(ValueError):
            client.tag_prediction("notion-123", 101)
        with self.assertRaises(ValueError):
            client.tag_prediction("notion-123", -1)

    @mock.patch("AgentCore.rhinal_mcp_client._call_tool_async")
    def test_resolve_prediction(self, m):
        r = self._client_calling(m).resolve_prediction("notion-123", "correct")
        self.assertEqual(r["_name"], "rhinal_resolve_prediction")
        self.assertEqual(r["_arguments"], {"notionId": "notion-123", "outcome": "correct"})

    def test_resolve_prediction_rejects_invalid_outcome(self):
        client = RhinalMCPClient(config=self._config())
        with self.assertRaises(ValueError):
            client.resolve_prediction("notion-123", "definitely")

    @mock.patch("AgentCore.rhinal_mcp_client._call_tool_async")
    def test_get_calibration_score_sends_no_arguments(self, m):
        r = self._client_calling(m).get_calibration_score()
        self.assertEqual(r["_name"], "rhinal_get_calibration_score")
        self.assertEqual(r["_arguments"], {})

    @mock.patch("AgentCore.rhinal_mcp_client._call_tool_async")
    def test_start_case_with_root(self, m):
        r = self._client_calling(m).start_case("A new case", root_notion_id="notion-123")
        self.assertEqual(r["_name"], "rhinal_start_case")
        self.assertEqual(r["_arguments"], {"title": "A new case", "rootNotionId": "notion-123"})

    @mock.patch("AgentCore.rhinal_mcp_client._call_tool_async")
    def test_start_case_without_root_omits_key(self, m):
        r = self._client_calling(m).start_case("A new case")
        self.assertEqual(r["_arguments"], {"title": "A new case"})

    @mock.patch("AgentCore.rhinal_mcp_client._call_tool_async")
    def test_get_case_graph_without_case_id_lists(self, m):
        r = self._client_calling(m).get_case_graph()
        self.assertEqual(r["_name"], "rhinal_get_case_graph")
        self.assertEqual(r["_arguments"], {})

    @mock.patch("AgentCore.rhinal_mcp_client._call_tool_async")
    def test_get_case_graph_with_case_id(self, m):
        r = self._client_calling(m).get_case_graph(case_id="case-123")
        self.assertEqual(r["_arguments"], {"caseId": "case-123"})

    @mock.patch("AgentCore.rhinal_mcp_client._call_tool_async")
    def test_check_contradiction(self, m):
        r = self._client_calling(m).check_contradiction("notion-123")
        self.assertEqual(r["_name"], "rhinal_check_contradiction")
        self.assertEqual(r["_arguments"], {"notionId": "notion-123"})


if __name__ == "__main__":
    unittest.main()
