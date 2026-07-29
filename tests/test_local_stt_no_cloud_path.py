"""
Regression test for the S0-E8 fix: WakeService/local_stt.py used to call
self._fallback_listen() *first* in listen_once() -- despite the module
docstring claiming "Runs locally, no API calls" -- which shelled out to
speech_recognition's recognize_google(), a network call to Google's cloud
STT API, before ever touching the local Vosk recognizer. The exception
handler around the Vosk path also fell back to the same cloud call on any
Vosk error. Both cloud entry points (the happy-path-first call and the
error-path fallback) were deleted; listen_once() now only ever talks to
the local Vosk recognizer.

This test asserts the fix holds two ways: a static source check (no
mention of speech_recognition/recognize_google survives in the file at
all) and a dynamic check (forcing the Vosk path to raise still never
imports speech_recognition into sys.modules).
"""
import subprocess
import sys
import unittest
from pathlib import Path

LOCAL_STT_PATH = (
    Path(__file__).resolve().parent.parent / "WakeService" / "local_stt.py"
)


class TestLocalSTTNoCloudPath(unittest.TestCase):
    def test_source_has_no_reference_to_google_cloud_stt(self):
        source = LOCAL_STT_PATH.read_text(encoding="utf-8")
        self.assertNotIn(
            "speech_recognition",
            source,
            "local_stt.py must not import speech_recognition -- that "
            "package is the client for Google's cloud STT API, which "
            "contradicts this module's 'runs locally, no API calls' "
            "contract.",
        )
        self.assertNotIn(
            "recognize_google",
            source,
            "local_stt.py must not call recognize_google() anywhere -- "
            "that's a network call to Google's cloud STT service.",
        )
        self.assertNotIn(
            "_fallback_listen",
            source,
            "the cloud-STT fallback method should be deleted entirely, "
            "not just made unreachable.",
        )

    def test_vosk_error_path_does_not_import_speech_recognition(self):
        # Force the Vosk branch to raise before it ever touches real audio
        # hardware (patch sd.InputStream to blow up immediately) and
        # confirm the exception handler in listen_once() doesn't reach for
        # a cloud fallback -- it must return None and nothing else.
        script = (
            "import sys\n"
            "import sounddevice\n"
            "def _boom(*a, **kw):\n"
            "    raise RuntimeError('forced failure for regression test')\n"
            "sounddevice.InputStream = _boom\n"
            "from WakeService.local_stt import LocalSTT\n"
            "stt = LocalSTT()\n"
            "class _FakeRecognizer:\n"
            "    pass\n"
            "stt._recognizer = _FakeRecognizer()\n"
            "result = stt.listen_once(timeout=0.2)\n"
            "print(result is None)\n"
            "print('speech_recognition' in sys.modules)\n"
        )
        proc = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(LOCAL_STT_PATH.resolve().parent.parent),
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        lines = proc.stdout.strip().splitlines()[-2:]
        self.assertEqual(
            lines,
            ["True", "False"],
            "on a Vosk-path error, listen_once() must return None without "
            "ever importing speech_recognition -- if this now prints "
            "something else, the cloud fallback has been reintroduced.",
        )


if __name__ == "__main__":
    unittest.main()
