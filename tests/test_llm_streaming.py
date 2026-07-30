"""
S0-E9: LLMEngine streaming/warm-up/token-budget wins, and jarvis.py's
sentence-buffered speak-while-streaming path.

Real numbers measured live before writing any of this (2026-07-30):
cold Ollama call ~10.4s vs ~2.8s once loaded (warm_up() exists because
of this); a real 3-sentence chat_stream() answer's first chunk arrived
at ~2.3s vs ~23.7s for the full response (the whole reason to stream
at all).
"""
import unittest
from unittest import mock

from AgentCore.llm_engine import LLMEngine


class TestWarmUp(unittest.TestCase):
    def test_constructor_does_not_warm_up_by_default(self):
        # Deliberately False by default -- dozens of call sites construct
        # LLMEngine() across this codebase (tests, code_engine, level6,
        # CLI utilities); warming every single one would add a real
        # blocking network call to all of them, not just the live
        # conversational path this is meant to help.
        with mock.patch.object(LLMEngine, "_check_ollama", lambda self: setattr(self, "_ollama_available", True)), \
             mock.patch.object(LLMEngine, "warm_up") as m_warm:
            LLMEngine()
        m_warm.assert_not_called()

    def test_constructor_warms_up_when_explicitly_requested_and_available(self):
        with mock.patch.object(LLMEngine, "_check_ollama", lambda self: setattr(self, "_ollama_available", True)), \
             mock.patch.object(LLMEngine, "warm_up") as m_warm:
            LLMEngine(warm_up=True)
        m_warm.assert_called_once()

    def test_constructor_does_not_warm_up_when_unavailable_even_if_requested(self):
        with mock.patch.object(LLMEngine, "_check_ollama", lambda self: setattr(self, "_ollama_available", False)), \
             mock.patch.object(LLMEngine, "warm_up") as m_warm:
            LLMEngine(warm_up=True)
        m_warm.assert_not_called()

    def test_warm_up_posts_with_keep_alive_and_never_raises(self):
        engine = LLMEngine.__new__(LLMEngine)
        engine.model = "llama3:latest"
        with mock.patch("requests.post") as m_post:
            engine.warm_up()
        m_post.assert_called_once()
        _, kwargs = m_post.call_args
        self.assertEqual(kwargs["json"]["model"], "llama3:latest")
        self.assertIn("keep_alive", kwargs["json"])

    def test_warm_up_failure_is_non_fatal(self):
        engine = LLMEngine.__new__(LLMEngine)
        engine.model = "llama3:latest"
        with mock.patch("requests.post", side_effect=Exception("network down")):
            engine.warm_up()  # must not raise


class TestChatTaskAwareTokenBudget(unittest.TestCase):
    def test_chat_respects_a_lower_max_tokens_than_the_class_default(self):
        engine = LLMEngine.__new__(LLMEngine)
        engine.model = "llama3:latest"
        engine._ollama_available = True

        captured = {}

        def fake_run(cmd, **kwargs):
            import json as _json
            payload = _json.loads(cmd[-1])
            captured["num_predict"] = payload["options"]["num_predict"]
            result = mock.Mock(returncode=0, stdout=_json.dumps({"message": {"content": "ok"}, "eval_count": 1}))
            return result

        with mock.patch("subprocess.run", side_effect=fake_run):
            engine.chat([{"role": "user", "content": "hi"}], max_tokens=50)

        self.assertEqual(captured["num_predict"], 50)

    def test_chat_default_still_caps_at_class_max_tokens(self):
        engine = LLMEngine.__new__(LLMEngine)
        engine.model = "llama3:latest"
        engine._ollama_available = True

        captured = {}

        def fake_run(cmd, **kwargs):
            import json as _json
            payload = _json.loads(cmd[-1])
            captured["num_predict"] = payload["options"]["num_predict"]
            result = mock.Mock(returncode=0, stdout=_json.dumps({"message": {"content": "ok"}, "eval_count": 1}))
            return result

        with mock.patch("subprocess.run", side_effect=fake_run):
            engine.chat([{"role": "user", "content": "hi"}])

        self.assertEqual(captured["num_predict"], LLMEngine.MAX_TOKENS)

    def test_chat_max_tokens_cannot_exceed_the_class_ceiling(self):
        # Same clamping behavior generate() already had -- a caller
        # asking for more than MAX_TOKENS is capped, not honored blindly.
        engine = LLMEngine.__new__(LLMEngine)
        engine.model = "llama3:latest"
        engine._ollama_available = True

        captured = {}

        def fake_run(cmd, **kwargs):
            import json as _json
            payload = _json.loads(cmd[-1])
            captured["num_predict"] = payload["options"]["num_predict"]
            result = mock.Mock(returncode=0, stdout=_json.dumps({"message": {"content": "ok"}, "eval_count": 1}))
            return result

        with mock.patch("subprocess.run", side_effect=fake_run):
            engine.chat([{"role": "user", "content": "hi"}], max_tokens=99999)

        self.assertEqual(captured["num_predict"], LLMEngine.MAX_TOKENS)


class TestChatStream(unittest.TestCase):
    def test_chat_stream_yields_content_chunks_and_prepends_system(self):
        engine = LLMEngine.__new__(LLMEngine)
        engine.model = "llama3:latest"
        engine._ollama_available = True
        engine.MAX_CONTEXT = LLMEngine.MAX_CONTEXT
        engine.MAX_TOKENS = LLMEngine.MAX_TOKENS

        fake_lines = [
            b'{"message": {"content": "Hello"}, "done": false}',
            b'{"message": {"content": " world"}, "done": false}',
            b'{"message": {"content": ""}, "done": true}',
        ]
        fake_response = mock.Mock()
        fake_response.iter_lines.return_value = fake_lines

        captured = {}

        def fake_post(url, json=None, **kwargs):
            captured["url"] = url
            captured["messages"] = json["messages"]
            return fake_response

        with mock.patch("requests.post", side_effect=fake_post):
            chunks = list(engine.chat_stream([{"role": "user", "content": "hi"}], system="be brief"))

        self.assertEqual(chunks, ["Hello", " world"])
        self.assertTrue(captured["url"].endswith("/api/chat"))
        self.assertEqual(captured["messages"][0], {"role": "system", "content": "be brief"})

    def test_chat_stream_falls_back_honestly_when_unavailable(self):
        engine = LLMEngine.__new__(LLMEngine)
        engine._ollama_available = False
        chunks = list(engine.chat_stream([{"role": "user", "content": "hello there"}]))
        self.assertEqual(len(chunks), 1)
        self.assertIn("Hello", chunks[0])  # _fallback_response's greeting branch


class TestStreamAndSpeakChat(unittest.TestCase):
    """
    Real unit tests against jarvis.py's PersistentWakeService method,
    not a mirrored copy -- constructed via __new__ to skip the heavy
    __init__ (wake detection, TTS, etc.), same technique used elsewhere
    in this codebase for testing methods on classes with expensive
    constructors.
    """

    def _make_service(self, chunks):
        from jarvis import PersistentWakeService
        service = PersistentWakeService.__new__(PersistentWakeService)
        service._llm = mock.Mock()
        service._llm.chat_stream.return_value = iter(chunks)
        service.spoken = []
        service._speak = service.spoken.append
        return service

    def test_speaks_each_complete_sentence_separately(self):
        service = self._make_service([
            "First sentence. ", "Second sent", "ence! ", "Third one?"
        ])
        result = service._stream_and_speak_chat([{"role": "user", "content": "q"}], None)

        self.assertEqual(service.spoken, ["First sentence.", "Second sentence!", "Third one?"])
        self.assertEqual(result, "First sentence. Second sentence! Third one?")

    def test_speaks_trailing_text_with_no_terminal_punctuation(self):
        service = self._make_service(["No punctuation at the end"])
        service._stream_and_speak_chat([{"role": "user", "content": "q"}], None)
        self.assertEqual(service.spoken, ["No punctuation at the end"])

    def test_single_sentence_response_is_still_spoken(self):
        service = self._make_service(["Just one sentence."])
        service._stream_and_speak_chat([{"role": "user", "content": "q"}], None)
        self.assertEqual(service.spoken, ["Just one sentence."])

    def test_empty_stream_speaks_nothing_and_returns_empty_string(self):
        service = self._make_service([])
        result = service._stream_and_speak_chat([{"role": "user", "content": "q"}], None)
        self.assertEqual(service.spoken, [])
        self.assertEqual(result, "")

    def test_does_not_split_on_a_title_abbreviation_like_Dr(self):
        # Adversarial case found live while testing this feature
        # (2026-07-30): the naive version split "Dr. Smith will see the
        # patient at 3pm." into "Dr." + "Smith will see the patient at
        # 3pm." -- a bad failure mode specifically because "Dr." is
        # about as common a token as a physician-facing voice assistant
        # will ever speak.
        service = self._make_service([
            "Dr. Smith will see the patient at 3pm. ",
            "The lab results are ready.",
        ])
        service._stream_and_speak_chat([{"role": "user", "content": "q"}], None)

        self.assertEqual(
            service.spoken,
            [
                "Dr. Smith will see the patient at 3pm.",
                "The lab results are ready.",
            ],
        )

    def test_st_as_part_of_a_proper_noun_does_not_wrongly_split_mid_name(self):
        # "St." here is part of the hospital's name, not a sentence
        # ender -- the real boundary is after "hospital.", and that's
        # exactly where this must speak, as one sentence covering both.
        service = self._make_service(["Visit St. Mary's hospital. It's downtown."])
        service._stream_and_speak_chat([{"role": "user", "content": "q"}], None)
        self.assertEqual(service.spoken, ["Visit St. Mary's hospital.", "It's downtown."])

    def test_a_real_sentence_that_happens_to_start_with_no_still_splits_normally(self):
        # "no"/"fig" were deliberately left out of the abbreviation set
        # (see jarvis.py's comment) precisely because of cases like this
        # -- "No." here is a genuine one-word sentence, not "No. 5".
        service = self._make_service(["Call the front desk. No. Call the lab instead."])
        service._stream_and_speak_chat([{"role": "user", "content": "q"}], None)
        self.assertEqual(
            service.spoken,
            ["Call the front desk.", "No.", "Call the lab instead."],
        )


if __name__ == "__main__":
    unittest.main()
