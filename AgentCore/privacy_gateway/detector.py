"""
PG-001 Mode C drift-catch detector.

**Read this before reading the code, because the ordering is the whole
design.** Mode C's safety property is *not* produced by this file. It is
produced by `gate.py`, from the physician's session-declared intent, a
hard checkable fact requiring zero inference. This detector runs only
after that gate has already allowed an utterance, and only in sessions
the physician declared non-clinical. It exists to notice that such a
session has drifted clinical, so the policy engine can react to the
*session going forward*. It cannot un-send the utterance that triggered
it, and it is never consulted about whether to allow anything.

From the blueprint, kept verbatim because it is the reason for that
ordering: *"No content classifier reaches zero false negatives. An
architecture whose safety property depends on one eventually fails
silently."*

**What this detector does not know.** It sees one utterance of text. It
cannot tell whether the person named is a patient, a colleague, or the
physician's spouse -- only that a person-name-shaped span is present.
Deciding what that means is the policy engine's job with session
context this module does not have.

**No certainty claim, ever.** Consistent with PG-001's refusal to call
tokenisation "anonymisation": this reduces the chance that clinical
drift goes unnoticed. It does not guarantee detection, and its measured
false-negative rate on a *synthetic* corpus (see
`docs/pg001_mode_c_drift_detector.md`) is an optimistic bound, not a
field number.

Runs entirely in-process on CPU. No model file, no network, no
subprocess -- see `tests/test_local_only.py`, which asserts that
importing this package pulls no HTTP client into `sys.modules`.
"""
from __future__ import annotations

import re
import time
from typing import Iterable

from . import lexicon as lex
from .findings import DriftReport, EntityType, Finding

# Confidence priors. Every number here is a stated design choice, not a
# measurement -- the evaluation script publishes what each bucket is
# empirically worth on the corpus.
CONF_EMAIL = 0.95
CONF_PATIENT_ID_CUED = 0.95
CONF_DOB = 0.93
CONF_PHONE = 0.90
CONF_NAME_TITLED = 0.90
CONF_AGE_SEX = 0.82
CONF_NAME_CUED = 0.70
CONF_NATIONAL_ID = 0.70
CONF_ADDRESS = 0.68
CONF_BED_CUED = 0.62          # the blueprint's own example: "Bed number (0.62)"
CONF_BED_CLINICAL_CTX = 0.80  # same span, clinical talk around it
CONF_BED_NONCLINICAL_CTX = 0.35
CONF_PATIENT_ID_BARE = 0.45
CONF_BED_ELIDED = 0.30
CONF_NAME_BARE = 0.32

# Clinical-topic scoring.
_NON_CLINICAL_DAMPING = 0.55   # per non-clinical marker, multiplicative
_MIN_DAMPING = 0.25            # damping floor -- markers can never veto
_ID_COOCCURRENCE_BOOST = 0.15  # patient-shaped identifier + any clinical term

# Some identifier *shapes* are themselves hospital artefacts and therefore
# topic evidence on their own, not merely identifiers. A cued UHID/MRN does
# not exist outside a health record. A bed number used as a person's
# discourse referent ("bed 9 needs to swap") is a ward idiom. An age-sex
# descriptor is the standard case-presentation opener.
#
# ADDED AFTER THE FIRST EVALUATION RUN, in response to the entire
# `clinical_identifiers_only` corpus category scoring 0.000. That makes that
# category's numbers in-sample -- disclosed in the design note's section 6
# rather than quietly folded into the headline figure.
_IDENTIFIER_AS_CLINICAL_EVIDENCE: dict[EntityType, tuple[float, float]] = {
    # entity type -> (minimum finding confidence, weight contributed)
    EntityType.PATIENT_ID: (0.90, 0.85),
    EntityType.BED_OR_ROOM: (0.60, 0.50),
    EntityType.AGE_SEX_DESCRIPTOR: (0.70, 0.50),
}


class Detector:
    """
    Stateless. Construct once, call `analyse()` per utterance.

    Deterministic: identical input yields an identical report (barring
    `elapsed_ms`). That property is what makes a published metric stay
    true after the fact -- re-running the evaluation script reproduces
    the numbers exactly.
    """

    version = lex.DETECTOR_VERSION

    def analyse(self, text: str) -> DriftReport:
        started = time.perf_counter()
        try:
            findings = self._find_entities(text)
            clinical, basis = self._score_clinical(text, findings)
            return DriftReport(
                findings=findings,
                clinical_confidence=clinical,
                elapsed_ms=(time.perf_counter() - started) * 1000.0,
                detector_version=self.version,
                clinical_basis=basis,
            )
        except Exception as e:  # noqa: BLE001 -- see below
            # A crashing safety net must not read as a clean one. The gate
            # turns FAILED into "review required"; it never turns it into
            # "nothing found". Mirrors secure_key's refusal to have a
            # return value meaning "no real result, proceed anyway".
            return DriftReport.failed(
                error=f"{type(e).__name__}: {e}",
                elapsed_ms=(time.perf_counter() - started) * 1000.0,
                detector_version=self.version,
            )

    # -- entities -----------------------------------------------------------

    def _find_entities(self, text: str) -> tuple[Finding, ...]:
        clinical_hits = lex.clinical_matches(text)
        has_clinical_ctx = any(w >= lex.MEDIUM for _, _, _, w in clinical_hits)
        has_non_clinical_ctx = bool(lex.non_clinical_matches(text))

        raw: list[Finding] = []

        for m in lex.RE_EMAIL.finditer(text):
            raw.append(self._f(EntityType.EMAIL, m, 1, CONF_EMAIL, "email address pattern"))

        for m in lex.RE_PATIENT_ID_CUED.finditer(text):
            raw.append(self._f(EntityType.PATIENT_ID, m, 1, CONF_PATIENT_ID_CUED,
                               "record-number keyword immediately followed by an identifier"))
        for m in lex.RE_PATIENT_ID_BARE.finditer(text):
            raw.append(self._f(EntityType.PATIENT_ID, m, 1, CONF_PATIENT_ID_BARE,
                               "record-number shape (letters+digits) with no keyword cue"))

        for m in lex.RE_PHONE.finditer(text):
            raw.append(self._f(EntityType.PHONE_NUMBER, m, 1, CONF_PHONE, "telephone number pattern"))

        for m in lex.RE_DOB.finditer(text):
            raw.append(self._f(EntityType.DATE_OF_BIRTH, m, 1, CONF_DOB,
                               "date preceded by a date-of-birth cue"))

        for m in lex.RE_AGE_SEX.finditer(text):
            raw.append(self._f(EntityType.AGE_SEX_DESCRIPTOR, m, 1, CONF_AGE_SEX,
                               "age + sex descriptor, the standard case-presentation opener"))

        for m in lex.RE_NATIONAL_ID.finditer(text):
            raw.append(self._f(EntityType.NATIONAL_ID, m, 1, CONF_NATIONAL_ID,
                               "12-digit national-ID shape; a bare digit run is not exclusively an ID"))

        for m in lex.RE_ADDRESS.finditer(text):
            raw.append(self._f(EntityType.ADDRESS, m, 1, CONF_ADDRESS,
                               "house number followed by a street/locality noun"))

        # Bed/room: the one place context genuinely moves the number, and the
        # blueprint's own illustration of why confidence must be graded.
        if has_clinical_ctx and not has_non_clinical_ctx:
            bed_conf, bed_why = CONF_BED_CLINICAL_CTX, "bed/room number amid clinical vocabulary"
        elif has_non_clinical_ctx and not has_clinical_ctx:
            bed_conf, bed_why = CONF_BED_NONCLINICAL_CTX, "bed/room-shaped span in non-clinical talk"
        else:
            bed_conf, bed_why = CONF_BED_CUED, "bed/room noun followed by a number"
        for m in lex.RE_BED.finditer(text):
            raw.append(self._f(EntityType.BED_OR_ROOM, m, 1, bed_conf, bed_why))
        if has_clinical_ctx:
            for m in lex.RE_BED_ELIDED.finditer(text):
                raw.append(self._f(EntityType.BED_OR_ROOM, m, 1, CONF_BED_ELIDED,
                                   "bare number after a locative preposition, clinical context"))

        raw.extend(self._find_names(text))

        for term, s, e, _w in clinical_hits:
            raw.append(Finding(EntityType.CLINICAL_TERM, text[s:e], s, e,
                               round(lex.CLINICAL_TERMS[term], 2),
                               "clinical vocabulary term"))

        return self._resolve_overlaps(raw)

    def _find_names(self, text: str) -> list[Finding]:
        out: list[Finding] = []
        for m in lex.RE_NAME_TITLED.finditer(text):
            out.append(self._f(EntityType.PERSON_NAME, m, 1, CONF_NAME_TITLED,
                               "capitalised token(s) following an honorific"))
        for m in lex.RE_NAME_CUED.finditer(text):
            if self._all_non_names(m.group(1)):
                continue
            out.append(self._f(EntityType.PERSON_NAME, m, 1, CONF_NAME_CUED,
                               "capitalised token(s) in a person-referring syntactic slot"))
        for m in lex.RE_NAME_BARE.finditer(text):
            if self._all_non_names(m.group(1)):
                continue
            if m.start(1) == 0 or text[max(0, m.start(1) - 2):m.start(1)].strip() in {".", "!", "?"}:
                # Sentence-initial capitalisation carries no evidence. Skipping
                # it is a deliberate, published false-negative source: a name
                # opening a sentence with no other cue is invisible to this
                # detector.
                continue
            out.append(self._f(EntityType.PERSON_NAME, m, 1, CONF_NAME_BARE,
                               "mid-sentence capitalised token not in the generic stoplist"))
        return out

    @staticmethod
    def _all_non_names(phrase: str) -> bool:
        return all(lex.is_probable_non_name(tok) for tok in phrase.split())

    @staticmethod
    def _f(etype: EntityType, m: re.Match, group: int, conf: float, basis: str) -> Finding:
        return Finding(etype, m.group(group), m.start(group), m.end(group), conf, basis)

    @staticmethod
    def _resolve_overlaps(findings: Iterable[Finding]) -> tuple[Finding, ...]:
        """
        Identifier spans that overlap collapse to the highest-confidence
        one; CLINICAL_TERM findings are kept alongside identifiers because
        they answer a different question.
        """
        ids = sorted(
            (f for f in findings if f.entity_type is not EntityType.CLINICAL_TERM),
            key=lambda f: (-f.confidence, f.start, -(f.end - f.start)),
        )
        kept: list[Finding] = []
        for f in ids:
            if any(f.start < k.end and k.start < f.end for k in kept):
                continue
            kept.append(f)
        terms = [f for f in findings if f.entity_type is EntityType.CLINICAL_TERM]
        return tuple(sorted(kept + terms, key=lambda f: (f.start, f.entity_type.value)))

    # -- clinical topic score ------------------------------------------------

    def _score_clinical(
        self, text: str, findings: tuple[Finding, ...]
    ) -> tuple[float, tuple[str, ...]]:
        """
        Noisy-OR over clinical vocabulary weights, damped by non-clinical
        context markers, with a small boost when a patient-shaped
        identifier co-occurs with at least one clinical term.

        Noisy-OR rather than a count threshold so that one unambiguous
        term ("ceftriaxone") can carry a short utterance, while a pile of
        weak ambiguous ones ("critical", "stable", "monitor") accumulates
        slowly instead of tripping on the third word -- which is what the
        corpus's IT-and-household segments are there to test.
        """
        hits = lex.clinical_matches(text)
        basis: list[str] = []
        product = 1.0
        for term, _s, _e, weight in hits:
            product *= (1.0 - weight)

        # Hospital-artefact identifiers join the same noisy-OR. They are
        # damped by non-clinical markers exactly like vocabulary is, which is
        # what keeps "the printer in room 12" and "book meeting room 4" out.
        for f in findings:
            spec = _IDENTIFIER_AS_CLINICAL_EVIDENCE.get(f.entity_type)
            if spec is not None and f.confidence >= spec[0]:
                product *= (1.0 - spec[1])
                basis.append(f"hospital-artefact identifier: {f.entity_type.value} ({spec[1]:.2f})")

        score = 1.0 - product
        if hits:
            top = sorted({(t, w) for t, _s, _e, w in hits}, key=lambda x: -x[1])[:4]
            basis.insert(0, "clinical terms: " + ", ".join(f"{t} ({w:.2f})" for t, w in top))

        markers = lex.non_clinical_matches(text)
        if markers:
            damping = max(_MIN_DAMPING, _NON_CLINICAL_DAMPING ** len(set(markers)))
            score *= damping
            basis.append(
                f"damped x{damping:.2f} by non-clinical markers: {', '.join(sorted(set(markers)))}"
            )

        patientish = {EntityType.PATIENT_ID, EntityType.BED_OR_ROOM,
                      EntityType.AGE_SEX_DESCRIPTOR, EntityType.DATE_OF_BIRTH}
        if hits and any(f.entity_type in patientish and f.confidence >= 0.5 for f in findings):
            score = min(1.0, score + _ID_COOCCURRENCE_BOOST)
            basis.append(f"+{_ID_COOCCURRENCE_BOOST:.2f} patient-shaped identifier alongside clinical vocabulary")

        return round(min(1.0, max(0.0, score)), 4), tuple(basis)


_DEFAULT = Detector()


def analyse(text: str) -> DriftReport:
    """Module-level convenience over the shared stateless detector."""
    return _DEFAULT.analyse(text)
