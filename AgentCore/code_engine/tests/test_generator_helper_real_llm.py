"""
Regression test for a "looks like it works, silently doesn't" bug:
GeneratorHelper.generate_code() checked hasattr(self.llm, 'generate') /
hasattr(self.llm, 'call_llm') -- neither is a real method on LLMAdapter
(AgentCore/code_engine/tier2/llm_adapter.py only exposes generate_raw/
suggest_code/plan_refactor/verify_safety), so both checks always failed
and every request silently fell through to the hardcoded stub
("print('Hello World')" for Python, etc.) regardless of task or Ollama's
real availability. A test that only checks "did generation return
non-empty output" would not catch this -- the stub output is non-empty.
This test specifically asserts the output is NOT one of the known
fallback strings, i.e. that the real LLM path was actually engaged.

Requires a real, locally-available Ollama -- skipped otherwise rather
than failing, since this is exercising real LLM engagement by design,
not something mockable without defeating the point of the test.
"""
import pytest

from AgentCore.code_engine.generator_helper import GeneratorHelper

FALLBACK_STRINGS = {
    "python": "print('Hello World')",
    "javascript": "console.log('Hello World');",
    "html": "<html><body>Hello World</body></html>",
}


def _ollama_available(helper: GeneratorHelper) -> bool:
    return bool(helper.llm and getattr(helper.llm.engine, "_ollama_available", False))


def test_generate_code_uses_real_llm_not_hardcoded_fallback():
    helper = GeneratorHelper()
    if not _ollama_available(helper):
        pytest.skip("Ollama not available on this machine -- cannot verify real LLM engagement")

    result = helper.generate_code(
        "write a function that checks if a string is a palindrome",
        "python",
        {},
    )

    assert result.strip() != FALLBACK_STRINGS["python"], (
        "generate_code() returned the exact hardcoded fallback string with "
        "Ollama available -- the real LLM path (LLMAdapter.generate_raw) "
        "was not actually engaged. This is the exact regression this test "
        "guards against: GeneratorHelper silently falling through to the "
        "stub via a hasattr() check against methods that don't exist on "
        "LLMAdapter."
    )
    # A genuine LLM response for a real coding task is not a one-liner.
    assert len(result.strip().splitlines()) > 1


def test_generate_code_produces_different_output_for_different_tasks():
    helper = GeneratorHelper()
    if not _ollama_available(helper):
        pytest.skip("Ollama not available on this machine -- cannot verify real LLM engagement")

    palindrome = helper.generate_code(
        "write a function that checks if a string is a palindrome", "python", {}
    )
    adder = helper.generate_code(
        "write a function that adds two numbers", "python", {}
    )

    # The pre-fix bug produced byte-identical stub output for every task,
    # regardless of what was actually asked for.
    assert palindrome.strip() != adder.strip()
