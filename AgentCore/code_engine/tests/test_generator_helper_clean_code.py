"""
Regression tests for GeneratorHelper._clean_code(): it used to only strip
a ``` fence at the absolute start/end of the whole response, missing a
fence appearing mid-response (e.g. between "### filename" sections in
multi-file output). Confirmed live: the palindrome-check task produced
"### palindrome.py\\n```\\ndef is_palindrome...\\n```" -- the mid-response
fence survived cleaning and made it into the written .py file, causing a
SyntaxError when run. Fixed with a regex that strips any bare fence-marker
line wherever it occurs, not just a start/end check.
"""
import re

from AgentCore.code_engine.generator_helper import GeneratorHelper


def _split_files(cleaned: str):
    parts = re.split(r"(^|\n)###\s+([^\n]+)\n", cleaned)
    files = {}
    i = 1
    while i < len(parts) - 1:
        fname = parts[i + 1].strip()
        content = parts[i + 2] if i + 2 < len(parts) else ""
        files[fname] = content
        i += 3
    return files


def test_clean_code_strips_mid_response_fence_palindrome_case():
    # The exact raw response confirmed live for the palindrome-check task.
    raw = (
        "### palindrome.py\n"
        "```\n"
        "def is_palindrome(s):\n"
        "    return s == s[::-1]\n"
        "\n"
        "print(is_palindrome('racecar'))\n"
        "```"
    )
    helper = GeneratorHelper()
    cleaned = helper._clean_code(raw)

    assert "```" not in cleaned
    files = _split_files(cleaned)
    assert "palindrome.py" in files
    compile(files["palindrome.py"], "palindrome.py", "exec")


def test_clean_code_strips_fences_in_constructed_multi_file_response():
    # Deliberately constructed, not observed live -- confirms the fix
    # generalizes rather than just patching the one observed case.
    raw = (
        "### foo.py\n"
        "```python\n"
        "def foo():\n"
        "    return 1\n"
        "```\n"
        "### bar.py\n"
        "```\n"
        "def bar():\n"
        "    return 2\n"
        "```\n"
    )
    helper = GeneratorHelper()
    cleaned = helper._clean_code(raw)

    assert "```" not in cleaned
    files = _split_files(cleaned)
    assert set(files.keys()) == {"foo.py", "bar.py"}
    for fname, content in files.items():
        compile(content, fname, "exec")


def test_clean_code_still_strips_edge_only_fence():
    # The original, simpler case must keep working.
    raw = "```python\nprint('hi')\n```"
    helper = GeneratorHelper()
    cleaned = helper._clean_code(raw)
    assert cleaned == "print('hi')"
