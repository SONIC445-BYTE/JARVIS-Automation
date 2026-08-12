"""
Mode C ("Strict Clinical") gate -- the primary mechanism, and the only
place the allow/block decision is made.

PG-001's Mode C row, kept exact:

    | C -- Strict Clinical | Prevent remote clinical discussion |
      **Session-declared intent** + deployment policy |
      **Secondary** -- safety net for accidental drift, never the
      primary gate |

**The ordering is enforced by structure, not by comment.** Three things
make it hard to accidentally invert:

1.  `GateDecision.allowed` is computed and returned from
    `_decide_from_declaration()`, which takes a `SessionDeclaration`
    and nothing else. It has no parameter through which a detector
    result could reach it. There is no code path where `allowed` is
    assigned from anything derived from `DriftReport`.

2.  In a session declared clinical (or undeclared), `evaluate()`
    returns before the detector is constructed or called at all. Not
    "calls it and ignores it" -- never calls it. `tests/test_gate.py`
    asserts this with a mock, so an edit that starts consulting the
    detector on that branch fails a test rather than passing review.

3.  The detector's *only* outward effects are `drift_review_required`
    and, if the deployment's policy says so, a **forward-looking**
    session suspension. It cannot allow, and it cannot retroactively
    block the utterance that triggered it -- because that utterance
    has, by then, already crossed the wire. That is a real limitation
    of any after-the-fact detector and it is modelled here rather than
    papered over.

**Fail-closed on the declaration, not on the classifier.** A session
that never declared is treated exactly as clinical: remote blocked.
That is the cheap, deterministic, zero-inference default, and it is the
one this project's `secure_key` idiom points at -- no return value
means "unknown, proceed anyway."
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from .detector import Detector
from .findings import DetectorStatus, DriftReport


class SessionType(str, Enum):
    """
    What the physician declared at connection time.

    UNDECLARED is not a third policy -- it is handled identically to
    CLINICAL. It exists as its own value so an audit can distinguish
    "declared clinical" from "never declared", which are different
    facts about the deployment even though they produce the same block.
    """

    CLINICAL = "clinical"
    NON_CLINICAL = "non_clinical"
    UNDECLARED = "undeclared"


class DriftAction(str, Enum):
    """What the deployment's policy does when drift is detected."""

    LOG_ONLY = "log_only"
    FLAG_FOR_REVIEW = "flag_for_review"
    SUSPEND_REMOTE = "suspend_remote"


class BlockBasis(str, Enum):
    """
    Why an utterance was blocked. Kept as an enum so an audit can
    separate the primary gate from the safety net -- if
    DRIFT_SUSPENSION ever starts outnumbering SESSION_DECLARATION in a
    deployment's logs, the declaration step is not working and that is
    a process problem, not a detector-tuning problem.
    """

    SESSION_DECLARATION = "session_declaration"
    DRIFT_SUSPENSION = "drift_suspension"


@dataclass(frozen=True)
class SessionDeclaration:
    """
    A hard, checkable fact supplied by a human at connection time. It is
    never inferred from content -- there is no constructor here that
    takes text.
    """

    session_id: str
    declared_type: SessionType
    declared_by: str
    declared_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def undeclared(cls, session_id: str) -> "SessionDeclaration":
        return cls(session_id=session_id, declared_type=SessionType.UNDECLARED,
                   declared_by="<none>")


@dataclass(frozen=True)
class DriftPolicy:
    """
    Deployment configuration, per PG-001's "policy is configuration,
    loaded per deployment, not hardcoded branches". A hospital's YAML
    supplies these; the defaults below are a starting point, not a
    recommendation, because the right threshold depends on how costly a
    false suspension is in that ward.

    `clinical_confidence_threshold` and `identifier_confidence_threshold`
    are separate on purpose: "someone said ceftriaxone" and "someone
    said an MRN" are different events with different responses, and the
    blueprint's requirement for confidence-scored findings exists
    precisely so a policy engine can threshold them independently
    instead of collapsing both into one boolean.
    """

    clinical_confidence_threshold: float = 0.60
    identifier_confidence_threshold: float = 0.70
    action: DriftAction = DriftAction.FLAG_FOR_REVIEW
    # A detector that crashed is treated as drift, not as clean.
    treat_detector_failure_as_drift: bool = True


@dataclass(frozen=True)
class GateDecision:
    allowed: bool
    basis: BlockBasis
    reason: str
    session_id: str
    drift_review_required: bool = False
    drift_report: Optional[DriftReport] = None
    session_suspended: bool = False


@dataclass
class _SuspensionRecord:
    reason: str
    at: datetime
    clinical_confidence: float


class ModeCGate:
    """
    Stateful only in that it remembers which sessions drift has
    suspended. Everything else is a pure function of the declaration.
    """

    def __init__(
        self,
        policy: Optional[DriftPolicy] = None,
        detector: Optional[Detector] = None,
    ) -> None:
        self.policy = policy or DriftPolicy()
        self._detector = detector or Detector()
        self._suspended: dict[str, _SuspensionRecord] = {}

    # -- primary gate --------------------------------------------------------

    @staticmethod
    def _decide_from_declaration(declaration: SessionDeclaration) -> GateDecision:
        """
        The whole of Mode C's safety property. Takes a declaration and
        nothing else -- deliberately not given access to the utterance
        text or to any detector output, so that no future edit can make
        the decision depend on inference without changing this
        signature and failing `test_gate.py`.
        """
        if declaration.declared_type is SessionType.NON_CLINICAL:
            return GateDecision(
                allowed=True,
                basis=BlockBasis.SESSION_DECLARATION,
                reason="Session was declared non-clinical at connection time.",
                session_id=declaration.session_id,
            )
        if declaration.declared_type is SessionType.CLINICAL:
            reason = ("Session was declared clinical at connection time; this "
                      "deployment's Mode C policy blocks remote clinical use.")
        else:
            reason = ("Session type was never declared. Mode C treats an "
                      "undeclared session as clinical and blocks remote use.")
        return GateDecision(
            allowed=False,
            basis=BlockBasis.SESSION_DECLARATION,
            reason=reason,
            session_id=declaration.session_id,
        )

    # -- full evaluation -----------------------------------------------------

    def evaluate(self, declaration: SessionDeclaration, utterance: str) -> GateDecision:
        """
        Order of operations, and it matters:

          1. forward-looking suspension from earlier detected drift
          2. the session declaration -- the primary gate
          3. only then, and only on the allowed branch, the detector
        """
        suspension = self._suspended.get(declaration.session_id)
        if suspension is not None:
            return GateDecision(
                allowed=False,
                basis=BlockBasis.DRIFT_SUSPENSION,
                reason=(f"Remote use suspended for this session after clinical drift "
                        f"was detected ({suspension.reason}). Re-declare the session "
                        f"type to continue."),
                session_id=declaration.session_id,
                session_suspended=True,
            )

        decision = self._decide_from_declaration(declaration)
        if not decision.allowed:
            # The detector is not consulted here. Not called and its result
            # discarded -- never called. Asserted by test.
            return decision

        report = self._detector.analyse(utterance)
        return self._attach_drift_advice(decision, report)

    def _attach_drift_advice(
        self, decision: GateDecision, report: DriftReport
    ) -> GateDecision:
        """
        Reads `report`; writes `drift_review_required` and possibly a
        forward suspension. Never writes `decision.allowed` -- the
        utterance under evaluation was already permitted by the
        declaration and has, in a live deployment, already been sent.
        """
        drifted = self._is_drift(report)
        suspended_now = False
        if drifted and self.policy.action is DriftAction.SUSPEND_REMOTE:
            self._suspended[decision.session_id] = _SuspensionRecord(
                reason=f"clinical_confidence={report.clinical_confidence:.2f}",
                at=datetime.now(timezone.utc),
                clinical_confidence=report.clinical_confidence,
            )
            suspended_now = True

        return replace(
            decision,
            drift_review_required=drifted and self.policy.action is not DriftAction.LOG_ONLY,
            drift_report=report,
            session_suspended=suspended_now,
        )

    def _is_drift(self, report: DriftReport) -> bool:
        if report.status is DetectorStatus.FAILED:
            return self.policy.treat_detector_failure_as_drift
        if report.clinical_confidence >= self.policy.clinical_confidence_threshold:
            return True
        # An identifier alone is not clinical drift -- a colleague's phone
        # number in a non-clinical session is not a patient. It only counts
        # when there is also some clinical signal, which is why this reads
        # the clinical score too rather than tripping on identifiers alone.
        return bool(
            report.identifier_findings(self.policy.identifier_confidence_threshold)
            and report.clinical_confidence >= self.policy.clinical_confidence_threshold / 2
        )

    # -- suspension management -----------------------------------------------

    def is_suspended(self, session_id: str) -> bool:
        return session_id in self._suspended

    def clear_suspension(self, session_id: str, redeclaration: SessionDeclaration) -> None:
        """
        Lifting a suspension requires a fresh human declaration -- the
        same kind of fact that opened the session. It is not something
        the detector, or a timeout, can do on its own.
        """
        if redeclaration.session_id != session_id:
            raise ValueError("re-declaration is for a different session")
        self._suspended.pop(session_id, None)
