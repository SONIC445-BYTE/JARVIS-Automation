"""
Detector Assurance measurement script.

    python -m AgentCore.privacy_gateway.evaluate

**Every performance number in `docs/pg001_mode_c_drift_detector.md` is
this script's output.** Nothing in that document is estimated, rounded
by hand, or written from memory. Re-run this and the identifier and
drift numbers reproduce exactly -- the detector is deterministic. Only
the latency block varies, because it measures the machine it runs on.

PG-001 requires this to publish: recall on patient identifiers,
precision, false-negative rate (flagged critical), latency, and
entity-type coverage. Each has its own section below, plus two the
blueprint did not ask for and this detector needs anyway: empirical
precision per confidence bucket (because shipping confidence scores
without showing what they are worth is the same failure as shipping a
boolean), and a per-category breakdown (because an aggregate over a
corpus containing deliberately easy cases flatters).

Matching rule for identifier spans: a prediction counts as a true
positive when its entity type equals a gold entity's type and the two
spans overlap by at least one character. Each gold span may be matched
once; each prediction may match once. Predictions are consumed
highest-confidence first. Overlap rather than exact boundaries because
a finding that flags the right entity with a one-character boundary
slip has done its job for a policy engine.
"""
from __future__ import annotations

import argparse
import platform
import statistics
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone

from .corpus import Segment, load_corpus
from .detector import Detector
from .findings import IDENTIFIER_TYPES, DriftReport, EntityType, Finding
from .gate import DriftPolicy

THRESHOLDS = (0.0, 0.30, 0.50, 0.62, 0.70, 0.90)
CALIBRATION_BUCKETS = ((0.0, 0.35), (0.35, 0.50), (0.50, 0.70), (0.70, 0.90), (0.90, 1.01))
LATENCY_REPEATS = 25


@dataclass
class Counts:
    tp: int = 0
    fp: int = 0
    fn: int = 0

    @property
    def precision(self) -> float:
        return self.tp / (self.tp + self.fp) if (self.tp + self.fp) else float("nan")

    @property
    def recall(self) -> float:
        return self.tp / (self.tp + self.fn) if (self.tp + self.fn) else float("nan")

    @property
    def fn_rate(self) -> float:
        return self.fn / (self.tp + self.fn) if (self.tp + self.fn) else float("nan")

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        if p != p or r != r or (p + r) == 0:
            return float("nan")
        return 2 * p * r / (p + r)


def _pct(x: float) -> str:
    return "   n/a" if x != x else f"{x * 100:5.1f}%"


def _match(
    segment: Segment, findings: tuple[Finding, ...], threshold: float
) -> tuple[list[tuple[Finding, object]], list[Finding], list[object]]:
    """Return (matched pairs, unmatched predictions, unmatched gold)."""
    preds = sorted(
        (f for f in findings if f.entity_type in IDENTIFIER_TYPES and f.confidence >= threshold),
        key=lambda f: -f.confidence,
    )
    gold = list(segment.entities)
    used_gold: set[int] = set()
    matched: list[tuple[Finding, object]] = []
    unmatched_pred: list[Finding] = []
    for p in preds:
        hit = None
        for gi, g in enumerate(gold):
            if gi in used_gold:
                continue
            if g.entity_type is p.entity_type and p.start < g.end and g.start < p.end:
                hit = gi
                break
        if hit is None:
            unmatched_pred.append(p)
        else:
            used_gold.add(hit)
            matched.append((p, gold[hit]))
    unmatched_gold = [g for gi, g in enumerate(gold) if gi not in used_gold]
    return matched, unmatched_pred, unmatched_gold


def _line(width: int = 78) -> str:
    return "-" * width


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="PG-001 Mode C drift detector assurance run")
    parser.add_argument("--repeats", type=int, default=LATENCY_REPEATS,
                        help="latency samples per segment (default %(default)s)")
    args = parser.parse_args(argv)

    detector = Detector()
    segments = load_corpus()
    reports: dict[str, DriftReport] = {s.id: detector.analyse(s.text) for s in segments}

    out: list[str] = []
    w = out.append

    # ---------------------------------------------------------------- header
    w("")
    w("=" * 78)
    w("  PG-001 MODE C DRIFT-CATCH DETECTOR -- ASSURANCE RUN")
    w("=" * 78)
    w(f"  detector version : {detector.version}")
    w(f"  run at           : {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    w(f"  python           : {platform.python_version()} on {platform.system()} {platform.release()}")
    w(f"  processor        : {platform.processor() or 'unknown'}")
    w(f"  machine          : {platform.machine()}")
    w("")
    w("  THIS IS A SYNTHETIC CORPUS, WRITTEN BY THE AUTHOR OF THE DETECTOR.")
    w("  Every number below is an optimistic bound on real-world behaviour, not a")
    w("  measurement of it. The failure modes present here are the ones the author")
    w("  thought of. See docs/pg001_mode_c_drift_detector.md section 6.")

    # -------------------------------------------------------------- corpus
    by_cat: dict[str, list[Segment]] = defaultdict(list)
    for s in segments:
        by_cat[s.category].append(s)
    gold_by_type: dict[EntityType, int] = defaultdict(int)
    patient_gold = 0
    for s in segments:
        for g in s.entities:
            gold_by_type[g.entity_type] += 1
            if g.patient_linked:
                patient_gold += 1

    w("")
    w("1. CORPUS")
    w(_line())
    w(f"  segments                     : {len(segments)}")
    w(f"  clinical / non-clinical      : {sum(s.clinical for s in segments)} / "
      f"{sum(not s.clinical for s in segments)}")
    w(f"  annotated identifier spans   : {sum(len(s.entities) for s in segments)} "
      f"({patient_gold} patient-linked)")
    w("")
    w(f"  {'category':32}  {'segs':>4}  {'clinical':>8}  {'gold ids':>8}")
    for cat in sorted(by_cat):
        segs = by_cat[cat]
        w(f"  {cat:32}  {len(segs):>4}  {sum(s.clinical for s in segs):>8}  "
          f"{sum(len(s.entities) for s in segs):>8}")

    # ----------------------------------------------- 2. identifier detection
    w("")
    w("2. IDENTIFIER DETECTION vs CONFIDENCE THRESHOLD  (all annotated spans)")
    w(_line())
    w(f"  {'thresh':>6}  {'TP':>4}  {'FP':>4}  {'FN':>4}  {'precision':>9}  "
      f"{'recall':>8}  {'FN rate':>8}  {'F1':>7}")
    for t in THRESHOLDS:
        c = Counts()
        for s in segments:
            m, up, ug = _match(s, reports[s.id].findings, t)
            c.tp += len(m)
            c.fp += len(up)
            c.fn += len(ug)
        w(f"  {t:>6.2f}  {c.tp:>4}  {c.fp:>4}  {c.fn:>4}  {_pct(c.precision):>9}  "
          f"{_pct(c.recall):>8}  {_pct(c.fn_rate):>8}  {_pct(c.f1):>7}")

    w("")
    w("  PATIENT-LINKED identifiers only (PG-001's high-priority recall target).")
    w("  FP is omitted: whether a detected identifier belongs to a patient is not")
    w("  something this detector can know, so patient-linked precision is undefined.")
    w(f"  {'thresh':>6}  {'TP':>4}  {'FN':>4}  {'recall':>8}  {'FN rate':>8}")
    for t in THRESHOLDS:
        tp = fn = 0
        for s in segments:
            m, _up, ug = _match(s, reports[s.id].findings, t)
            tp += sum(1 for _p, g in m if g.patient_linked)
            fn += sum(1 for g in ug if g.patient_linked)
        c = Counts(tp=tp, fn=fn)
        w(f"  {t:>6.2f}  {tp:>4}  {fn:>4}  {_pct(c.recall):>8}  {_pct(c.fn_rate):>8}")

    # ------------------------------------------------------ 3. per-type
    default_t = DriftPolicy().identifier_confidence_threshold
    w("")
    w(f"3. PER-ENTITY-TYPE, at the default policy threshold {default_t:.2f}")
    w(_line())
    w(f"  {'entity type':22}  {'gold':>4}  {'TP':>3}  {'FP':>3}  {'FN':>3}  "
      f"{'precision':>9}  {'recall':>8}  {'FN rate':>8}")
    per_type: dict[EntityType, Counts] = defaultdict(Counts)
    for s in segments:
        m, up, ug = _match(s, reports[s.id].findings, default_t)
        for p, _g in m:
            per_type[p.entity_type].tp += 1
        for p in up:
            per_type[p.entity_type].fp += 1
        for g in ug:
            per_type[g.entity_type].fn += 1
    for etype in sorted(IDENTIFIER_TYPES, key=lambda t: t.value):
        c = per_type[etype]
        if not (c.tp or c.fp or c.fn or gold_by_type[etype]):
            continue
        w(f"  {etype.value:22}  {gold_by_type[etype]:>4}  {c.tp:>3}  {c.fp:>3}  {c.fn:>3}  "
          f"{_pct(c.precision):>9}  {_pct(c.recall):>8}  {_pct(c.fn_rate):>8}")

    w("")
    w("  Recall at threshold 0.00 (maximum recall the rules can reach at any setting):")
    per_type_max: dict[EntityType, Counts] = defaultdict(Counts)
    for s in segments:
        m, up, ug = _match(s, reports[s.id].findings, 0.0)
        for p, _g in m:
            per_type_max[p.entity_type].tp += 1
        for g in ug:
            per_type_max[g.entity_type].fn += 1
    for etype in sorted(IDENTIFIER_TYPES, key=lambda t: t.value):
        if not gold_by_type[etype]:
            continue
        c = per_type_max[etype]
        w(f"    {etype.value:22}  {_pct(c.recall)}   ({c.tp}/{gold_by_type[etype]})")

    # -------------------------------------------------- 4. entity coverage
    w("")
    w("4. ENTITY-TYPE COVERAGE")
    w(_line())
    emitted = {f.entity_type for r in reports.values() for f in r.findings}
    present = set(gold_by_type)
    w(f"  types the detector can emit    : {len(IDENTIFIER_TYPES)}")
    w("    " + ", ".join(sorted(t.value for t in IDENTIFIER_TYPES)))
    w(f"  types present in this corpus   : {len(present)}")
    w("    " + ", ".join(sorted(t.value for t in present)))
    untested = sorted(t.value for t in IDENTIFIER_TYPES if t not in present)
    w(f"  emittable but UNTESTED here    : {', '.join(untested) if untested else 'none'}")
    never = sorted(t.value for t in IDENTIFIER_TYPES if t not in emitted)
    w(f"  never emitted on this corpus   : {', '.join(never) if never else 'none'}")
    w("  Not covered by any rule (known gaps, no rule exists to miss them):")
    w("    biometric identifiers, vehicle numbers, insurance/TPA policy numbers,")
    w("    employer names, photographs, device serial numbers, free-text")
    w("    descriptions that identify by circumstance ('the MLA's son in 12').")

    # ---------------------------------------------- 5. confidence calibration
    w("")
    w("5. CONFIDENCE CALIBRATION -- what each bucket is empirically worth")
    w(_line())
    w("  Confidences are evidence-strength priors chosen by hand. This table is the")
    w("  measurement of how well they order reality on this corpus.")
    w(f"  {'bucket':>14}  {'preds':>5}  {'correct':>7}  {'empirical precision':>19}")
    bucket_counts: dict[tuple[float, float], list[bool]] = {b: [] for b in CALIBRATION_BUCKETS}
    for s in segments:
        m, up, _ug = _match(s, reports[s.id].findings, 0.0)
        for p, _g in m:
            for b in CALIBRATION_BUCKETS:
                if b[0] <= p.confidence < b[1]:
                    bucket_counts[b].append(True)
        for p in up:
            for b in CALIBRATION_BUCKETS:
                if b[0] <= p.confidence < b[1]:
                    bucket_counts[b].append(False)
    for b in CALIBRATION_BUCKETS:
        vals = bucket_counts[b]
        label = f"[{b[0]:.2f},{min(b[1], 1.0):.2f})"
        if not vals:
            w(f"  {label:>14}  {0:>5}  {0:>7}  {'n/a':>19}")
            continue
        w(f"  {label:>14}  {len(vals):>5}  {sum(vals):>7}  "
          f"{_pct(sum(vals) / len(vals)):>19}")

    # ------------------------------------------------ 6. clinical drift
    w("")
    w("6. CLINICAL-DRIFT DETECTION (segment level)")
    w(_line())
    w("  The question Mode C actually asks: has a session declared non-clinical")
    w("  drifted into clinical content? A false negative here is the failure that")
    w("  matters -- drift happened and nothing noticed.")
    w(f"  {'thresh':>6}  {'TP':>4}  {'FP':>4}  {'FN':>4}  {'precision':>9}  "
      f"{'recall':>8}  {'FN rate':>8}  {'F1':>7}")
    for t in THRESHOLDS:
        c = Counts()
        for s in segments:
            flagged = reports[s.id].clinical_confidence >= t if t > 0 else \
                reports[s.id].clinical_confidence > 0
            if s.clinical and flagged:
                c.tp += 1
            elif s.clinical and not flagged:
                c.fn += 1
            elif not s.clinical and flagged:
                c.fp += 1
        w(f"  {t:>6.2f}  {c.tp:>4}  {c.fp:>4}  {c.fn:>4}  {_pct(c.precision):>9}  "
          f"{_pct(c.recall):>8}  {_pct(c.fn_rate):>8}  {_pct(c.f1):>7}")

    dt = DriftPolicy().clinical_confidence_threshold
    w("")
    w(f"  Per category at the default policy threshold {dt:.2f}:")
    w(f"  {'category':32}  {'n':>3}  {'flagged':>7}  {'outcome':>26}")
    for cat in sorted(by_cat):
        segs = by_cat[cat]
        flagged = sum(1 for s in segs if reports[s.id].clinical_confidence >= dt)
        if all(s.clinical for s in segs):
            outcome = f"{flagged}/{len(segs)} caught (recall)"
        elif not any(s.clinical for s in segs):
            outcome = f"{flagged}/{len(segs)} false alarms"
        else:
            outcome = f"{flagged}/{len(segs)} flagged (mixed)"
        w(f"  {cat:32}  {len(segs):>3}  {flagged:>7}  {outcome:>26}")

    w("")
    w(f"  Every MISSED clinical segment at threshold {dt:.2f} -- the false negatives,")
    w("  listed individually because an aggregate rate hides what kind of thing is")
    w("  being missed:")
    for s in segments:
        if s.clinical and reports[s.id].clinical_confidence < dt:
            w(f"    [{s.id}] score={reports[s.id].clinical_confidence:.3f}  {s.text}")
    w("")
    w(f"  Every FALSE ALARM at threshold {dt:.2f}:")
    for s in segments:
        if not s.clinical and reports[s.id].clinical_confidence >= dt:
            w(f"    [{s.id}] score={reports[s.id].clinical_confidence:.3f}  {s.text}")

    # ----------------------------------------------------------- 7. latency
    w("")
    w("7. LATENCY  (CPU only, no GPU, no model load -- §3.1 target hardware class)")
    w(_line())
    samples: list[float] = []
    for s in segments:
        for _ in range(args.repeats):
            t0 = time.perf_counter()
            detector.analyse(s.text)
            samples.append((time.perf_counter() - t0) * 1000.0)
    samples.sort()
    chars = sum(len(s.text) for s in segments)
    w(f"  calls               : {len(samples)}  ({len(segments)} segments x {args.repeats})")
    w(f"  mean                : {statistics.fmean(samples):.3f} ms")
    w(f"  p50                 : {samples[len(samples) // 2]:.3f} ms")
    w(f"  p95                 : {samples[int(len(samples) * 0.95)]:.3f} ms")
    w(f"  max                 : {samples[-1]:.3f} ms")
    w(f"  mean segment length : {chars / len(segments):.0f} chars")

    long_text = " ".join(s.text for s in segments)
    t0 = time.perf_counter()
    for _ in range(5):
        detector.analyse(long_text)
    long_ms = (time.perf_counter() - t0) * 1000.0 / 5
    w(f"  whole corpus as one {len(long_text)}-char utterance: {long_ms:.2f} ms "
      f"({len(long_text) / long_ms:.0f} chars/ms)")
    w("  Machine-specific. Re-running on other hardware gives other numbers; the")
    w("  detection numbers above do not change.")

    # ------------------------------------------------------- 8. determinism
    w("")
    w("8. REPRODUCIBILITY")
    w(_line())
    identical = all(
        detector.analyse(s.text).findings == reports[s.id].findings
        and detector.analyse(s.text).clinical_confidence == reports[s.id].clinical_confidence
        for s in segments
    )
    w(f"  identical output on re-analysis : {'yes' if identical else 'NO -- INVESTIGATE'}")
    w("  No sampling, no model, no network, no clock dependence in the scoring path.")
    w("  A future reader re-running this script gets these same detection numbers.")

    # -------------------------------------------------------- 9. the caveat
    w("")
    w("9. WHAT THESE NUMBERS DO NOT MEAN")
    w(_line())
    w("  * They are not real-world performance. The corpus is synthetic, small, and")
    w("    written by the person who wrote the rules. Both the easy cases and the")
    w("    hard cases are the ones the author imagined.")
    w("  * They do not bound Mode C's safety. Mode C's guarantee comes from the")
    w("    physician's session declaration. This detector is the secondary layer and")
    w("    is expected to miss things -- which is why it is not the primary gate.")
    w("  * They are not a claim of certainty. Same rule PG-001 applies to")
    w("    tokenisation: this reduces the chance that drift goes unnoticed. It does")
    w("    not guarantee detection.")
    w("  * A drift finding is always after the fact. The utterance that triggered it")
    w("    has already crossed the wire. The policy engine can only act on what")
    w("    comes next.")
    w("")

    print("\n".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(run())
