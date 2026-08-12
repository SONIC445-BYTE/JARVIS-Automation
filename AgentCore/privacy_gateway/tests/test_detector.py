"""
Detector behaviour: confidence-scored output, determinism, locality, and
the specific claims the design note makes about it.
"""
import subprocess
import sys
import unittest
from pathlib import Path

from AgentCore.privacy_gateway import analyse
from AgentCore.privacy_gateway.detector import Detector
from AgentCore.privacy_gateway.findings import IDENTIFIER_TYPES, EntityType

REPO_ROOT = Path(__file__).resolve().parents[3]


class TestConfidenceScoredNotBinary(unittest.TestCase):
    def test_findings_carry_a_confidence_and_a_reason(self):
        report = analyse("Mr Iqbal Ahmed in bed 14 is febrile, start ceftriaxone.")
        ids = report.identifier_findings()
        self.assertTrue(ids)
        for f in ids:
            self.assertGreater(f.confidence, 0.0)
            self.assertLessEqual(f.confidence, 1.0)
            self.assertTrue(f.basis, "every finding must say why it fired")

    def test_the_blueprints_own_example_shape(self):
        """
        PG-001 illustrates the requirement with `Person name (0.99)` and
        `Bed number (0.62)` -- different confidences for different evidence
        strengths, in one report.
        """
        report = analyse("Mr Iqbal Ahmed is in bed 14.")
        by_type = {f.entity_type: f for f in report.findings}
        self.assertIn(EntityType.PERSON_NAME, by_type)
        self.assertIn(EntityType.BED_OR_ROOM, by_type)
        self.assertGreater(by_type[EntityType.PERSON_NAME].confidence,
                           by_type[EntityType.BED_OR_ROOM].confidence)
        self.assertEqual(str(by_type[EntityType.BED_OR_ROOM]),
                         "BED_OR_ROOM 'bed 14' (0.62)")

    def test_the_same_span_scores_differently_in_different_context(self):
        """
        A bed number amid clinical talk is stronger evidence than the same
        span amid printer talk. If these ever became equal, the confidence
        channel would be decoration.
        """
        clinical = analyse("The patient in bed 12 is septic and needs antibiotics.")
        office = analyse("The printer in room 12 is jammed, ask facilities.")
        c = next(f for f in clinical.findings if f.entity_type is EntityType.BED_OR_ROOM)
        o = next(f for f in office.findings if f.entity_type is EntityType.BED_OR_ROOM)
        self.assertGreater(c.confidence, o.confidence)

    def test_no_finding_ever_claims_certainty(self):
        """
        PG-001 forbids certainty claims. Nothing this detector emits may be
        1.0 -- there is no evidence in a lexicon that justifies it.
        """
        texts = [
            "Mrs Kalyani Devi, DOB is 12/03/1961, UHID MH-2291043, bed 14.",
            "Call 9845112233 or mail x@y.test, Aadhaar 4321 8765 2109, 14 Nehru Road.",
        ]
        for t in texts:
            for f in analyse(t).identifier_findings():
                self.assertLess(f.confidence, 1.0, f"{f} claims certainty")

    def test_identifier_spans_do_not_overlap_each_other(self):
        report = analyse("Patient MRN 4471029, Mr Iqbal Ahmed, 58/M, bed 22B.")
        ids = sorted(report.identifier_findings(), key=lambda f: f.start)
        for a, b in zip(ids, ids[1:]):
            self.assertLessEqual(a.end, b.start, f"{a} overlaps {b}")


class TestClinicalScoring(unittest.TestCase):
    def test_ordinary_software_talk_does_not_read_as_clinical(self):
        for text in (
            "The production database is in a critical state, restore from backup.",
            "Monitor the CPU temperature, it spikes when we compile the repository.",
            "Give the intern a dose of reality about deadlines before the appraisal.",
        ):
            self.assertLess(analyse(text).clinical_confidence, 0.60, text)

    def test_unambiguous_clinical_talk_reads_as_clinical(self):
        for text in (
            "Start broad-spectrum antibiotics and repeat the creatinine in the morning.",
            "The chest x-ray shows a right lower lobe consolidation, treat as pneumonia.",
        ):
            self.assertGreaterEqual(analyse(text).clinical_confidence, 0.60, text)

    def test_the_score_explains_itself(self):
        report = analyse("Hold the heparin until the platelet count comes back.")
        self.assertTrue(report.clinical_basis)
        self.assertIn("clinical terms", report.clinical_basis[0])

    def test_a_known_and_documented_miss_stays_visible(self):
        """
        Colloquial clinical speech with no clinical vocabulary is missed.
        This is not a bug to be silently fixed later -- it is the headline
        limitation in the design note, and if a change ever fixes it the
        design note must be updated with it. Asserting the miss keeps the
        two in sync.
        """
        self.assertLess(
            analyse("The chap in the corner bed is still bringing up everything he eats.")
            .clinical_confidence,
            0.60,
        )


class TestDeterminismAndLocality(unittest.TestCase):
    def test_repeated_analysis_is_byte_identical(self):
        text = "Mrs Kalyani Devi in bed 14 is febrile, start ceftriaxone one gram BD."
        first = Detector().analyse(text)
        for _ in range(5):
            again = Detector().analyse(text)
            self.assertEqual(again.findings, first.findings)
            self.assertEqual(again.clinical_confidence, first.clinical_confidence)

    def test_importing_the_package_pulls_in_no_network_client(self):
        """
        §3.7b: session content that might be clinical must not leave the
        machine. A detector that imports an HTTP client is one careless edit
        away from being the leak. Same coupling-regression shape as
        AgentCore/knowledge/tests' selenium check.

        Measures the DELTA across the import, not absolute membership of
        sys.modules. An earlier version of this test asserted that none of
        these names appears in sys.modules at all, and could never pass:
        `urllib.request`, `http.client`, `socket` and `ssl` are already
        loaded at bare interpreter startup in this environment (verified --
        they are present before any repo module is imported), so that
        assertion measured the interpreter, not this package. A check that
        cannot pass is not a stricter check; it is one that gets deleted or
        ignored the first time someone is in a hurry, and it would have
        masked the thing it exists to catch.
        """
        probe = (
            "import sys; "
            "watch=('requests','httpx','aiohttp','urllib.request','http.client',"
            "'socket','ssl','torch','transformers','onnxruntime'); "
            "before={m for m in watch if m in sys.modules}; "
            "import AgentCore.privacy_gateway as pg; "
            "after={m for m in watch if m in sys.modules}; "
            "print(','.join(sorted(after - before)))"
        )
        result = subprocess.run(
            [sys.executable, "-c", probe],
            cwd=REPO_ROOT, capture_output=True, text=True, check=True,
        )
        self.assertEqual(
            result.stdout.strip(), "",
            "importing privacy_gateway must not ADD any network or ML runtime "
            "to sys.modules -- whatever the interpreter already loaded is not "
            "this package's doing, but anything new here is",
        )

    def test_analysing_a_long_utterance_stays_well_under_a_frame(self):
        """
        §3.1's CPU-first target. A loose bound, not the published latency
        figure -- that comes from the evaluation script. This only catches a
        catastrophic regression (e.g. an accidental quadratic).
        """
        import time

        text = "The patient in bed 14 is febrile, start ceftriaxone. " * 100
        t0 = time.perf_counter()
        analyse(text)
        self.assertLess((time.perf_counter() - t0) * 1000, 500)


class TestCoverageIsStated(unittest.TestCase):
    def test_every_emittable_type_is_an_identifier_or_the_topic_marker(self):
        self.assertEqual(
            set(EntityType) - IDENTIFIER_TYPES, {EntityType.CLINICAL_TERM}
        )


if __name__ == "__main__":
    unittest.main()
