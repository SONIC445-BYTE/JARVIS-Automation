"""
The ordering property, as tests rather than as prose.

PG-001 Mode C: the physician's **session-declared intent is the primary
gate**; the drift detector is **secondary, never the primary gate**.
Every test in `TestOrderingProperty` fails if a future edit inverts or
blurs that. They are the reason this file exists -- the rest is
supporting behaviour.
"""
import unittest
from unittest import mock

from AgentCore.privacy_gateway.detector import Detector
from AgentCore.privacy_gateway.findings import (
    DetectorStatus,
    DriftReport,
    EntityType,
    Finding,
)
from AgentCore.privacy_gateway.gate import (
    BlockBasis,
    DriftAction,
    DriftPolicy,
    ModeCGate,
    SessionDeclaration,
    SessionType,
)

CLINICAL_UTTERANCE = "Mrs Kalyani Devi in bed 14 is febrile, start ceftriaxone."
ORDINARY_UTTERANCE = "Book me a taxi to the airport at five in the morning."


def _declaration(kind: SessionType, session_id: str = "s-1") -> SessionDeclaration:
    return SessionDeclaration(session_id=session_id, declared_type=kind,
                              declared_by="dr.test@example.test")


class TestOrderingProperty(unittest.TestCase):
    """Declared intent primary, detector secondary -- enforced, not asserted."""

    def test_declared_clinical_blocks_without_the_detector_ever_running(self):
        detector = mock.Mock(spec=Detector)
        gate = ModeCGate(detector=detector)

        decision = gate.evaluate(_declaration(SessionType.CLINICAL), ORDINARY_UTTERANCE)

        self.assertFalse(decision.allowed)
        self.assertIs(decision.basis, BlockBasis.SESSION_DECLARATION)
        # Not "called and ignored" -- never called. An edit that starts
        # consulting the classifier on the blocked branch fails here.
        detector.analyse.assert_not_called()
        self.assertIsNone(decision.drift_report)

    def test_undeclared_session_is_treated_exactly_as_clinical(self):
        detector = mock.Mock(spec=Detector)
        gate = ModeCGate(detector=detector)

        decision = gate.evaluate(SessionDeclaration.undeclared("s-2"), ORDINARY_UTTERANCE)

        self.assertFalse(decision.allowed)
        self.assertIs(decision.basis, BlockBasis.SESSION_DECLARATION)
        detector.analyse.assert_not_called()
        self.assertIn("never declared", decision.reason)

    def test_detector_certainty_cannot_block_the_declared_non_clinical_session(self):
        """
        The detector at maximum confidence, finding a patient identifier at
        0.99, still does not flip `allowed`. If it could, Mode C's safety
        property would rest on a classifier -- the exact architecture the
        blueprint says eventually fails silently.
        """
        screaming = mock.Mock(spec=Detector)
        screaming.analyse.return_value = DriftReport(
            findings=(Finding(EntityType.PATIENT_ID, "4471029", 0, 7, 0.99, "test"),),
            clinical_confidence=1.0,
        )
        gate = ModeCGate(detector=screaming, policy=DriftPolicy(action=DriftAction.FLAG_FOR_REVIEW))

        decision = gate.evaluate(_declaration(SessionType.NON_CLINICAL), CLINICAL_UTTERANCE)

        self.assertTrue(decision.allowed)
        self.assertTrue(decision.drift_review_required)
        self.assertIs(decision.basis, BlockBasis.SESSION_DECLARATION)

    def test_detector_silence_cannot_unblock_a_declared_clinical_session(self):
        silent = mock.Mock(spec=Detector)
        silent.analyse.return_value = DriftReport(findings=(), clinical_confidence=0.0)
        gate = ModeCGate(detector=silent)

        decision = gate.evaluate(_declaration(SessionType.CLINICAL), CLINICAL_UTTERANCE)

        self.assertFalse(decision.allowed)

    def test_the_primary_decision_function_cannot_see_content_or_detector_output(self):
        """
        Structural guard. `_decide_from_declaration` takes one argument, a
        declaration. Widening it to accept text or a report is how this
        design would rot, so the signature itself is pinned.
        """
        import inspect

        params = list(inspect.signature(ModeCGate._decide_from_declaration).parameters)
        self.assertEqual(params, ["declaration"])

    def test_drift_suspension_is_forward_looking_not_retroactive(self):
        """
        The utterance that triggered drift was already allowed -- in a live
        deployment it has already crossed the wire. Only what comes next can
        be blocked, and it is blocked under a *different* basis so an audit
        can tell the two mechanisms apart.
        """
        gate = ModeCGate(policy=DriftPolicy(action=DriftAction.SUSPEND_REMOTE))
        decl = _declaration(SessionType.NON_CLINICAL, "s-3")

        first = gate.evaluate(decl, CLINICAL_UTTERANCE)
        self.assertTrue(first.allowed, "the triggering utterance is not retroactively blocked")
        self.assertTrue(first.session_suspended)

        second = gate.evaluate(decl, ORDINARY_UTTERANCE)
        self.assertFalse(second.allowed)
        self.assertIs(second.basis, BlockBasis.DRIFT_SUSPENSION)


class TestFailClosed(unittest.TestCase):
    def test_a_crashed_detector_reads_as_drift_not_as_clean(self):
        exploding = mock.Mock(spec=Detector)
        exploding.analyse.return_value = DriftReport.failed("boom", 0.1, "v")
        gate = ModeCGate(detector=exploding)

        decision = gate.evaluate(_declaration(SessionType.NON_CLINICAL), ORDINARY_UTTERANCE)

        self.assertTrue(decision.allowed)  # declaration still governs
        self.assertTrue(decision.drift_review_required)
        self.assertIs(decision.drift_report.status, DetectorStatus.FAILED)

    def test_detector_exceptions_never_escape_analyse(self):
        class Broken(Detector):
            def _find_entities(self, text):  # noqa: ARG002
                raise RuntimeError("regex engine on fire")

        report = Broken().analyse("anything")
        self.assertIs(report.status, DetectorStatus.FAILED)
        self.assertIn("RuntimeError", report.error)
        self.assertEqual(report.findings, ())

    def test_lifting_a_suspension_needs_a_fresh_human_declaration(self):
        gate = ModeCGate(policy=DriftPolicy(action=DriftAction.SUSPEND_REMOTE))
        decl = _declaration(SessionType.NON_CLINICAL, "s-4")
        gate.evaluate(decl, CLINICAL_UTTERANCE)
        self.assertTrue(gate.is_suspended("s-4"))

        with self.assertRaises(ValueError):
            gate.clear_suspension("s-4", _declaration(SessionType.NON_CLINICAL, "other-session"))

        gate.clear_suspension("s-4", _declaration(SessionType.NON_CLINICAL, "s-4"))
        self.assertFalse(gate.is_suspended("s-4"))


class TestPolicyIsConfiguration(unittest.TestCase):
    """
    PG-001: "Policy is configuration, loaded per deployment, not hardcoded
    branches." The same detector output must produce different reactions
    under different policies without touching detector code.
    """

    def _decide(self, policy: DriftPolicy):
        return ModeCGate(policy=policy).evaluate(
            _declaration(SessionType.NON_CLINICAL), CLINICAL_UTTERANCE
        )

    def test_log_only_never_asks_for_review(self):
        d = self._decide(DriftPolicy(action=DriftAction.LOG_ONLY))
        self.assertFalse(d.drift_review_required)
        self.assertGreater(d.drift_report.clinical_confidence, 0.6)

    def test_flag_for_review_asks_but_does_not_suspend(self):
        d = self._decide(DriftPolicy(action=DriftAction.FLAG_FOR_REVIEW))
        self.assertTrue(d.drift_review_required)
        self.assertFalse(d.session_suspended)

    def test_a_higher_threshold_lets_a_mid_scoring_utterance_through_unflagged(self):
        """
        The real "policy is configuration" property: the same detector
        output, two policies, two reactions, no detector change.

        Uses a mid-scoring utterance (clinical_confidence 0.88 -- clinical
        language, no identifiers) rather than CLINICAL_UTTERANCE. An earlier
        version of this test used CLINICAL_UTTERANCE with a threshold of
        0.999999 on the assumption that no score could reach it, and failed:
        that utterance scores exactly 1.0, because clinical_confidence
        saturates. See the companion test below -- the saturation is the
        interesting finding, and thresholding it away is not something the
        policy knob can or should do.
        """
        mid = "He is febrile."
        flagged = ModeCGate(policy=DriftPolicy()).evaluate(
            _declaration(SessionType.NON_CLINICAL), mid
        )
        self.assertTrue(
            flagged.drift_review_required,
            "0.88 should clear the 0.60 default -- if not, this test's premise moved",
        )

        unflagged = ModeCGate(
            policy=DriftPolicy(clinical_confidence_threshold=0.95,
                               identifier_confidence_threshold=1.0)
        ).evaluate(_declaration(SessionType.NON_CLINICAL), mid)
        self.assertFalse(unflagged.drift_review_required)

    def test_clinical_confidence_saturates_and_cannot_be_thresholded_away(self):
        """
        Pins a real property found while fixing the test above: an
        unambiguous clinical utterance scores exactly 1.0, so no threshold
        in [0, 1] excludes it under a `>=` comparison.

        Recorded as intended behaviour rather than quietly worked around.
        A deployment can tune where the *boundary* sits; it cannot configure
        the detector into ignoring a maximally-confident hit. If that is ever
        wanted, it is `DriftAction.LOG_ONLY`, which is an explicit and
        auditable choice -- not a threshold set to 1.0, which would look like
        tuning while actually disabling the safety net.
        """
        report = ModeCGate().evaluate(
            _declaration(SessionType.NON_CLINICAL), CLINICAL_UTTERANCE
        ).drift_report
        self.assertEqual(report.clinical_confidence, 1.0)

        still_flagged = self._decide(
            DriftPolicy(clinical_confidence_threshold=1.0,
                        identifier_confidence_threshold=1.0)
        )
        self.assertTrue(still_flagged.drift_review_required)

    def test_ordinary_speech_in_a_non_clinical_session_raises_nothing(self):
        d = ModeCGate().evaluate(_declaration(SessionType.NON_CLINICAL), ORDINARY_UTTERANCE)
        self.assertTrue(d.allowed)
        self.assertFalse(d.drift_review_required)


if __name__ == "__main__":
    unittest.main()
