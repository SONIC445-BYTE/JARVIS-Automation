"""
PG-001 Privacy Gateway -- Mode C drift-catch detector.

Closes the blueprint's *"Explicit open gap"* in §4.4c: Mode C's
after-the-fact "has this non-clinical session drifted into clinical
territory" check, built with the Detector Assurance treatment PG-001
demands of it rather than assumed to be a free primitive.

**Mode C's safety property is the physician's session-declared intent
(`gate.ModeCGate`). This detector is the secondary layer.** It runs only
inside sessions already declared non-clinical, only after the gate has
allowed the utterance, and it can never allow anything. See `gate.py`
for how that ordering is enforced structurally.

Runs locally on CPU per §3.1 and §3.7b -- session content that might be
clinical cannot be sent to a cloud classifier, because the classifier
would then be the leak.

Measured performance, and the honest limits of that measurement, are in
`docs/pg001_mode_c_drift_detector.md`. Every number there is produced by
`python -m AgentCore.privacy_gateway.evaluate`.
"""
from .detector import Detector, analyse
from .findings import (
    IDENTIFIER_TYPES,
    DetectorStatus,
    DriftReport,
    EntityType,
    Finding,
)
from .gate import (
    BlockBasis,
    DriftAction,
    DriftPolicy,
    GateDecision,
    ModeCGate,
    SessionDeclaration,
    SessionType,
)

__all__ = [
    "BlockBasis",
    "DetectorStatus",
    "Detector",
    "DriftAction",
    "DriftPolicy",
    "DriftReport",
    "EntityType",
    "Finding",
    "GateDecision",
    "IDENTIFIER_TYPES",
    "ModeCGate",
    "SessionDeclaration",
    "SessionType",
    "analyse",
]
