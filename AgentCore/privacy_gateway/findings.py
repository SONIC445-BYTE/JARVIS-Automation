"""
Structured output types for the PG-001 Mode C drift-catch detector.

PG-001 requires findings carry confidence, never a bare boolean:

    "Findings must be structured with confidence, not binary -- e.g.
     `Person name (0.99)`, `Bed number (0.62)` -- so the policy engine
     can threshold, not just branch on 'detected: yes/no'."

Two deliberate shape decisions live here, both load-bearing:

1.  `DriftReport` has no field that can mean "allow". It carries
    evidence and nothing else. The Mode C allow/block decision is
    computed in `gate.py` from the physician's session declaration
    *before* a report exists, so there is no assignment a future edit
    could make that would let a classifier score become the gate.

2.  A detector that fails does not produce an empty (i.e. reassuring)
    report. `DetectorStatus.FAILED` is a distinct state and the gate
    treats it as "review required", not as "nothing found". Same
    fail-closed discipline as `secure_key.resolve_key()`: there is no
    return value meaning "no real result, proceed as if clean."
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class EntityType(str, Enum):
    """
    Entity types this detector is capable of emitting.

    Coverage is a published number, not an implied one -- the
    evaluation script prints this set against the set actually present
    in the corpus, so a type the detector cannot emit shows up as a
    coverage gap rather than silently scoring zero recall.
    """

    PERSON_NAME = "PERSON_NAME"
    PATIENT_ID = "PATIENT_ID"
    BED_OR_ROOM = "BED_OR_ROOM"
    PHONE_NUMBER = "PHONE_NUMBER"
    EMAIL = "EMAIL"
    DATE_OF_BIRTH = "DATE_OF_BIRTH"
    AGE_SEX_DESCRIPTOR = "AGE_SEX_DESCRIPTOR"
    NATIONAL_ID = "NATIONAL_ID"
    ADDRESS = "ADDRESS"
    # Not an identifier. Evidence that the *topic* is clinical.
    CLINICAL_TERM = "CLINICAL_TERM"


IDENTIFIER_TYPES = frozenset(t for t in EntityType if t is not EntityType.CLINICAL_TERM)


class DetectorStatus(str, Enum):
    OK = "ok"
    FAILED = "failed"


@dataclass(frozen=True)
class Finding:
    """
    One span of evidence.

    `confidence` is an **evidence-strength prior, not a calibrated
    posterior probability.** It is a documented function of which rule
    fired (see `lexicon.py` and `detector.py`), and the evaluation
    script publishes the empirical precision of each confidence bucket
    so a reader can see how far the prior is from the measurement
    rather than having to trust the number. Do not read 0.62 as "62%
    of the time this is right" unless the calibration table on this
    corpus says so.

    `basis` is the human-readable reason the rule fired. It exists so
    a flagged session can be reviewed without re-running the detector,
    and so a wrong finding is diagnosable rather than mysterious.
    """

    entity_type: EntityType
    text: str
    start: int
    end: int
    confidence: float
    basis: str

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence out of range: {self.confidence!r}")
        if self.start < 0 or self.end <= self.start:
            raise ValueError(f"bad span: [{self.start}, {self.end})")

    def __str__(self) -> str:  # the blueprint's own rendering: "Bed number (0.62)"
        return f"{self.entity_type.value} '{self.text}' ({self.confidence:.2f})"


@dataclass(frozen=True)
class DriftReport:
    """
    Everything the detector observed about one utterance. Advisory by
    construction -- see the module docstring.
    """

    findings: tuple[Finding, ...] = ()
    clinical_confidence: float = 0.0
    status: DetectorStatus = DetectorStatus.OK
    error: Optional[str] = None
    elapsed_ms: float = 0.0
    detector_version: str = ""
    clinical_basis: tuple[str, ...] = field(default_factory=tuple)

    def identifier_findings(self, min_confidence: float = 0.0) -> tuple[Finding, ...]:
        return tuple(
            f
            for f in self.findings
            if f.entity_type in IDENTIFIER_TYPES and f.confidence >= min_confidence
        )

    def max_identifier_confidence(self) -> float:
        ids = self.identifier_findings()
        return max((f.confidence for f in ids), default=0.0)

    @staticmethod
    def failed(error: str, elapsed_ms: float, detector_version: str) -> "DriftReport":
        """
        A failure is not an empty report. Constructed through a named
        factory so no caller can accidentally build a FAILED report
        that looks clean.
        """
        return DriftReport(
            findings=(),
            clinical_confidence=0.0,
            status=DetectorStatus.FAILED,
            error=error,
            elapsed_ms=elapsed_ms,
            detector_version=detector_version,
        )
