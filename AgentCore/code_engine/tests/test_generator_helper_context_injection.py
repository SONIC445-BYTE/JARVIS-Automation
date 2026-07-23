"""
Regression tests for GeneratorHelper's context injection: context was
accepted as a parameter by generate_code() but never referenced anywhere
in the prompt -- there was no real mechanism for "editing existing code",
only the workaround of a caller manually embedding source in the
natural-language text field. Traced upstream: neither real caller
(jarvis.py, co_brain.py) populates context with file content today (both
only ever pass {"user": ..., "cwd": ...}) -- these tests cover the
plumbing (_build_context_section / generate_code), which is now correct
whenever a caller does supply content, independent of that separate,
larger, not-yet-built upstream capability.
"""
from typing import Any, Dict

from AgentCore.code_engine.generator_helper import GeneratorHelper


class _CapturingLLM:
    """Records the prompt it was called with instead of hitting a real LLM."""

    def __init__(self, response: str = "### out.py\nprint('ok')\n"):
        self.last_prompt = None
        self.response = response

    def generate_raw(self, prompt: str) -> str:
        self.last_prompt = prompt
        return self.response


def _helper_with_capturing_llm() -> tuple[GeneratorHelper, _CapturingLLM]:
    helper = GeneratorHelper()
    llm = _CapturingLLM()
    helper.llm = llm
    return helper, llm


def test_build_context_section_empty_when_no_context():
    helper = GeneratorHelper()
    assert helper._build_context_section(None) == ""
    assert helper._build_context_section({}) == ""
    assert helper._build_context_section({"user": "owner", "cwd": "/x"}) == ""


def test_build_context_section_includes_existing_code_string():
    helper = GeneratorHelper()
    section = helper._build_context_section({"existing_code": "def divide(a, b):\n    return a / b"})
    assert "def divide(a, b):" in section
    assert "Existing code" in section


def test_build_context_section_includes_files_dict():
    helper = GeneratorHelper()
    section = helper._build_context_section({
        "files": {"divide.py": "def divide(a, b):\n    return a / b"}
    })
    assert "### divide.py" in section
    assert "def divide(a, b):" in section


def test_generate_code_injects_existing_code_into_the_real_prompt():
    helper, llm = _helper_with_capturing_llm()
    existing = "def divide(a, b):\n    return a / b"

    helper.generate_code(
        "add error handling for division by zero",
        "python",
        {"existing_code": existing},
    )

    assert llm.last_prompt is not None
    assert existing in llm.last_prompt


def test_generate_code_with_no_context_does_not_inject_anything():
    helper, llm = _helper_with_capturing_llm()

    helper.generate_code("write a function that adds two numbers", "python", {})

    assert llm.last_prompt is not None
    assert "Existing code" not in llm.last_prompt
