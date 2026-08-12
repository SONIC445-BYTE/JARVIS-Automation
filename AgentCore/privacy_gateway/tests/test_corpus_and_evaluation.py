"""
The corpus, the measurement script, and the guarantee that the design
note's published numbers are the script's real output.

`TestDesignNoteMatchesAFreshRun` is the important one. PG-001's Detector
Assurance requirement is only worth anything if the published figures
are the measured figures. That is normally kept true by discipline; here
it is kept true by a test, so a hand-edited or stale number in
`docs/pg001_mode_c_drift_detector.md` fails the suite.
"""
import io
import json
import re
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from AgentCore.privacy_gateway import evaluate
from AgentCore.privacy_gateway.corpus import CORPUS_PATH, CorpusError, load_corpus

REPO_ROOT = Path(__file__).resolve().parents[3]
DESIGN_NOTE = REPO_ROOT / "docs" / "pg001_mode_c_drift_detector.md"

# Sections whose content is machine-dependent (latency) or run-dependent
# (timestamp). Everything else must reproduce exactly.
_VOLATILE_SECTIONS = ("7. LATENCY",)


class TestCorpusIntegrity(unittest.TestCase):
    def test_corpus_loads_and_every_annotation_resolves_to_a_real_span(self):
        segments = load_corpus()
        self.assertGreaterEqual(len(segments), 50)
        for s in segments:
            for g in s.entities:
                self.assertEqual(s.text[g.start:g.end], g.text, f"{s.id}: bad offset")

    def test_corpus_has_both_classes_and_the_hard_categories(self):
        segments = load_corpus()
        categories = {s.category for s in segments}
        for required in (
            "clinical_no_identifiers",          # clinical with nothing to find
            "non_clinical_looks_clinical",      # ordinary speech that reads clinical
            "non_clinical_with_identifiers",    # identifiers with no patient
            "clinical_colloquial",              # clinical with no clinical words
            "adversarial",
        ):
            self.assertIn(required, categories,
                          "a corpus of easy cases produces flattering numbers")
        self.assertGreaterEqual(sum(s.clinical for s in segments), 20)
        self.assertGreaterEqual(sum(not s.clinical for s in segments), 20)

    def test_every_segment_records_why_it_is_in_the_corpus(self):
        for s in load_corpus():
            self.assertTrue(s.why.strip(), f"{s.id} has no rationale")

    def test_corpus_is_declared_synthetic_in_the_data_file_itself(self):
        header = json.loads(CORPUS_PATH.read_text(encoding="utf-8").splitlines()[0])
        self.assertIn("SYNTHETIC ONLY", header["_comment"])

    def test_a_mis_annotated_corpus_fails_loudly_rather_than_scoring_wrong(self):
        bad = {"id": "x", "category": "c", "clinical": True,
               "text": "Nothing to see here.", "why": "test",
               "entities": [{"type": "PERSON_NAME", "text": "Absent Name",
                             "patient_linked": True}]}
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "bad.jsonl"
            p.write_text(json.dumps(bad) + "\n", encoding="utf-8")
            with self.assertRaises(CorpusError):
                load_corpus(p)

    def test_an_under_annotated_repeat_fails_rather_than_counting_a_hit_as_a_miss(self):
        bad = {"id": "x", "category": "c", "clinical": True,
               "text": "bed 4 and bed 4 again.", "why": "test",
               "entities": [{"type": "BED_OR_ROOM", "text": "bed 4",
                             "patient_linked": True}]}
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "bad.jsonl"
            p.write_text(json.dumps(bad) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(CorpusError, "occurs 2 time"):
                load_corpus(p)


class TestEvaluationScript(unittest.TestCase):
    def test_it_runs_as_a_module_and_exits_zero(self):
        result = subprocess.run(
            [sys.executable, "-m", "AgentCore.privacy_gateway.evaluate", "--repeats", "2"],
            cwd=REPO_ROOT, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        for section in ("1. CORPUS", "2. IDENTIFIER DETECTION", "3. PER-ENTITY-TYPE",
                        "4. ENTITY-TYPE COVERAGE", "5. CONFIDENCE CALIBRATION",
                        "6. CLINICAL-DRIFT DETECTION", "7. LATENCY",
                        "8. REPRODUCIBILITY", "9. WHAT THESE NUMBERS DO NOT MEAN"):
            self.assertIn(section, result.stdout)

    def test_it_reports_every_metric_pg001_requires(self):
        out = _capture_report()
        for required in ("recall", "precision", "FN rate", "ms", "coverage"):
            self.assertIn(required, out.lower() if required == "coverage" else out)

    def test_it_states_the_synthetic_caveat_in_its_own_output(self):
        out = _capture_report()
        self.assertIn("SYNTHETIC CORPUS", out)
        self.assertIn("not a claim of certainty", out)


class TestDesignNoteMatchesAFreshRun(unittest.TestCase):
    """
    Every deterministic line the script prints must appear verbatim in the
    design note. This is what makes "no number was written by hand" a
    checkable property rather than a promise.
    """

    def test_design_note_exists(self):
        self.assertTrue(DESIGN_NOTE.exists(), f"missing {DESIGN_NOTE}")

    def test_every_deterministic_output_line_is_present_in_the_design_note(self):
        note = DESIGN_NOTE.read_text(encoding="utf-8")
        missing = [ln for ln in _deterministic_lines(_capture_report()) if ln not in note]
        self.assertEqual(
            missing, [],
            "these measured lines are not in docs/pg001_mode_c_drift_detector.md -- "
            "re-run `python -m AgentCore.privacy_gateway.evaluate` and paste its output",
        )


def _capture_report() -> str:
    buf = io.StringIO()
    with redirect_stdout(buf):
        evaluate.run(["--repeats", "2"])
    return buf.getvalue()


def _deterministic_lines(report: str) -> list[str]:
    """Report lines excluding the run header and the machine-dependent block."""
    lines = report.splitlines()
    out: list[str] = []
    in_volatile = False
    started = False
    for line in lines:
        if re.match(r"^\d\. [A-Z]", line.strip()):
            started = True
            in_volatile = any(line.strip().startswith(v) for v in _VOLATILE_SECTIONS)
        if not started or in_volatile:
            continue
        stripped = line.strip()
        if stripped and not set(stripped) <= {"-", "="}:
            out.append(stripped)
    return out


if __name__ == "__main__":
    unittest.main()
