# PG-001 Mode C — drift-catch detector

**Status:** built. `AgentCore/privacy_gateway/`.
**Role:** the *secondary* layer of PG-001 Mode C. Never the primary gate.

---

## 1. What this is, and the thing it must never become

Mode C ("Strict Clinical") prevents remote clinical discussion. **The primary gate is the physician's session-declared intent** — declared at connect, checked as a hard fact, zero inference. That is settled and this detector does not touch it.

This component handles only the residual case: a session declared *non-clinical* that drifts into clinical content mid-conversation. It is a net under the primary gate.

**The blueprint's reason for that ordering is not stylistic, and §5's numbers below are the measured proof of it.** No content classifier reaches zero false negatives; an architecture whose safety property rests on one fails silently. This detector misses **35% of clinical drift at its default threshold** on a corpus its own author wrote. As a primary gate that would be indefensible. As a net behind a declared-intent gate that already caught the case deliberately, it is a real improvement over nothing — which is the only claim made for it.

Enforced structurally, not merely asserted: `ModeCGate.evaluate()` resolves the declaration first, and the detector's only outward effects are `drift_review_required` and an audit record. It cannot grant access, and there is no code path by which a detector result permits something the declaration refused. `tests/test_gate.py` pins that ordering as a test rather than prose.

## 2. Design

Rule- and lexicon-based, entirely local, no model weights and no network. Two binding reasons:

- **§3.7b.** Session content may be clinical, so it may not leave the machine. A detector that imports an HTTP client is one careless edit from being the leak it exists to prevent. `tests/test_detector.py` asserts that importing the package adds no network or ML runtime to `sys.modules` — measured as a *delta* across the import, because several stdlib network modules are already loaded at bare interpreter startup in this environment.
- **§3.1 CPU-first.** Target hardware is 8–16GB integrated-graphics laptops. §7's latency is what a rule engine buys; a transformer NER model would not fit the budget and would need its own assurance work besides.

Honest cost of that choice, visible in §6: a lexicon cannot see clinical meaning carried by ordinary words. Every `clinical_colloquial` segment is missed. A local model would likely catch several. **The choice bought locality and latency and paid in recall** — stated here rather than buried.

Output is confidence-scored findings, never a boolean, per PG-001's requirement that the policy engine threshold rather than branch on "detected: yes/no". Policy — thresholds and the action taken — is configuration (`DriftPolicy`), not hardcoded branches.

## 3. How the policy engine should read the confidences

Confidences are **evidence-strength priors chosen by hand**, not calibrated probabilities. §5 measures how well they order reality on this corpus; treat that table as the meaning of a bucket, not the number itself. Note the `[0.35,0.50)` bucket scores 0% empirical precision on 2 predictions — far too small to conclude from, and stated rather than smoothed away.

Reading a finding at 0.62 as "62% likely correct" is a misreading this note explicitly warns off.

## 4. The corpus, and why its numbers are an upper bound

**Synthetic, written by the detector's author.** This is the most important caveat here and it is not a formality: the failure modes present are the ones the author thought of, and every rule was written with knowledge of the examples. Real-world performance will be worse, by an unknown margin, on utterances nobody anticipated.

It deliberately includes hard cases rather than easy ones: clinical content with no identifiers and no clinical vocabulary (`clinical_colloquial`), non-clinical speech that superficially reads as clinical (`non_clinical_looks_clinical`), and non-clinical content that genuinely contains personal identifiers (`non_clinical_with_identifiers`). The latter two exist to make false alarms *possible*; a corpus without them would report flattering precision that means nothing.

**Not covered by any rule** — so these are not even counted as misses: biometric identifiers, vehicle numbers, insurance/TPA policy numbers, employer names, photographs, device serial numbers, and identification by circumstance ("the MLA's son in 12"). That last class is probably the most realistic gap in an Indian OPD and the hardest to rule-match.

## 5. Measured assurance — the actual script output

Reproduce with `python -m AgentCore.privacy_gateway.evaluate`. **No number in this document was typed by hand.** `tests/test_corpus_and_evaluation.py::TestDesignNoteMatchesAFreshRun` fails if any deterministic line the script prints is absent from this file, which makes "nothing here was fabricated" a checkable property rather than a promise.

```

==============================================================================
  PG-001 MODE C DRIFT-CATCH DETECTOR -- ASSURANCE RUN
==============================================================================
  detector version : pg001-modec-drift-1.0.0
  run at           : 2026-08-12 19:55:03 UTC
  python           : 3.12.10 on Windows 11
  processor        : Intel64 Family 6 Model 126 Stepping 5, GenuineIntel
  machine          : AMD64

  THIS IS A SYNTHETIC CORPUS, WRITTEN BY THE AUTHOR OF THE DETECTOR.
  Every number below is an optimistic bound on real-world behaviour, not a
  measurement of it. The failure modes present here are the ones the author
  thought of. See docs/pg001_mode_c_drift_detector.md section 6.

1. CORPUS
------------------------------------------------------------------------------
  segments                     : 75
  clinical / non-clinical      : 40 / 35
  annotated identifier spans   : 38 (26 patient-linked)

  category                          segs  clinical  gold ids
  adversarial                          7         4         3
  clinical_colloquial                  8         8         0
  clinical_identifiers_only            6         6         9
  clinical_no_identifiers             12        12         0
  clinical_overt                      10        10        15
  non_clinical_looks_clinical         12         0         0
  non_clinical_plain                  10         0         0
  non_clinical_with_identifiers       10         0        11

2. IDENTIFIER DETECTION vs CONFIDENCE THRESHOLD  (all annotated spans)
------------------------------------------------------------------------------
  thresh    TP    FP    FN  precision    recall   FN rate       F1
    0.00    36     6     2      85.7%     94.7%      5.3%    90.0%
    0.30    36     6     2      85.7%     94.7%      5.3%    90.0%
    0.50    32     2     6      94.1%     84.2%     15.8%    88.9%
    0.62    32     2     6      94.1%     84.2%     15.8%    88.9%
    0.70    28     2    10      93.3%     73.7%     26.3%    82.4%
    0.90    15     0    23     100.0%     39.5%     60.5%    56.6%

  PATIENT-LINKED identifiers only (PG-001's high-priority recall target).
  FP is omitted: whether a detected identifier belongs to a patient is not
  something this detector can know, so patient-linked precision is undefined.
  thresh    TP    FN    recall   FN rate
    0.00    25     1     96.2%      3.8%
    0.30    25     1     96.2%      3.8%
    0.50    23     3     88.5%     11.5%
    0.62    23     3     88.5%     11.5%
    0.70    20     6     76.9%     23.1%
    0.90     9    17     34.6%     65.4%

3. PER-ENTITY-TYPE, at the default policy threshold 0.70
------------------------------------------------------------------------------
  entity type             gold   TP   FP   FN  precision    recall   FN rate
  ADDRESS                    2    0    0    2        n/a      0.0%    100.0%
  AGE_SEX_DESCRIPTOR         3    3    1    0      75.0%    100.0%      0.0%
  BED_OR_ROOM               10    6    0    4     100.0%     60.0%     40.0%
  DATE_OF_BIRTH              1    1    0    0     100.0%    100.0%      0.0%
  EMAIL                      2    2    0    0     100.0%    100.0%      0.0%
  NATIONAL_ID                2    2    0    0     100.0%    100.0%      0.0%
  PATIENT_ID                 3    3    0    0     100.0%    100.0%      0.0%
  PERSON_NAME               11    7    1    4      87.5%     63.6%     36.4%
  PHONE_NUMBER               4    4    0    0     100.0%    100.0%      0.0%

  Recall at threshold 0.00 (maximum recall the rules can reach at any setting):
    ADDRESS                 100.0%   (2/2)
    AGE_SEX_DESCRIPTOR      100.0%   (3/3)
    BED_OR_ROOM             100.0%   (10/10)
    DATE_OF_BIRTH           100.0%   (1/1)
    EMAIL                   100.0%   (2/2)
    NATIONAL_ID             100.0%   (2/2)
    PATIENT_ID              100.0%   (3/3)
    PERSON_NAME              81.8%   (9/11)
    PHONE_NUMBER            100.0%   (4/4)

4. ENTITY-TYPE COVERAGE
------------------------------------------------------------------------------
  types the detector can emit    : 9
    ADDRESS, AGE_SEX_DESCRIPTOR, BED_OR_ROOM, DATE_OF_BIRTH, EMAIL, NATIONAL_ID, PATIENT_ID, PERSON_NAME, PHONE_NUMBER
  types present in this corpus   : 9
    ADDRESS, AGE_SEX_DESCRIPTOR, BED_OR_ROOM, DATE_OF_BIRTH, EMAIL, NATIONAL_ID, PATIENT_ID, PERSON_NAME, PHONE_NUMBER
  emittable but UNTESTED here    : none
  never emitted on this corpus   : none
  Not covered by any rule (known gaps, no rule exists to miss them):
    biometric identifiers, vehicle numbers, insurance/TPA policy numbers,
    employer names, photographs, device serial numbers, free-text
    descriptions that identify by circumstance ('the MLA's son in 12').

5. CONFIDENCE CALIBRATION -- what each bucket is empirically worth
------------------------------------------------------------------------------
  Confidences are evidence-strength priors chosen by hand. This table is the
  measurement of how well they order reality on this corpus.
          bucket  preds  correct  empirical precision
     [0.00,0.35)      6        4                66.7%
     [0.35,0.50)      2        0                 0.0%
     [0.50,0.70)      4        4               100.0%
     [0.70,0.90)     15       13                86.7%
     [0.90,1.00)     15       15               100.0%

6. CLINICAL-DRIFT DETECTION (segment level)
------------------------------------------------------------------------------
  The question Mode C actually asks: has a session declared non-clinical
  drifted into clinical content? A false negative here is the failure that
  matters -- drift happened and nothing noticed.
  thresh    TP    FP    FN  precision    recall   FN rate       F1
    0.00    28    11    12      71.8%     70.0%     30.0%    70.9%
    0.30    28     5    12      84.8%     70.0%     30.0%    76.7%
    0.50    28     4    12      87.5%     70.0%     30.0%    77.8%
    0.62    26     3    14      89.7%     65.0%     35.0%    75.4%
    0.70    26     3    14      89.7%     65.0%     35.0%    75.4%
    0.90    22     3    18      88.0%     55.0%     45.0%    67.7%

  Per category at the default policy threshold 0.60:
  category                            n  flagged                     outcome
  adversarial                         7        6         6/7 flagged (mixed)
  clinical_colloquial                 8        0         0/8 caught (recall)
  clinical_identifiers_only           6        3         3/6 caught (recall)
  clinical_no_identifiers            12       11       11/12 caught (recall)
  clinical_overt                     10        9        9/10 caught (recall)
  non_clinical_looks_clinical        12        0           0/12 false alarms
  non_clinical_plain                 10        0           0/10 false alarms
  non_clinical_with_identifiers      10        0           0/10 false alarms

  Every MISSED clinical segment at threshold 0.60 -- the false negatives,
  listed individually because an aggregate rate hides what kind of thing is
  being missed:
    [co-10] score=0.000  Aadhaar on the form is 4321 8765 2109 and the family lives at 14 Nehru Road, so follow-up is easy.
    [cn-03] score=0.550  If the saturation drops below ninety again we should think about intubating.
    [cc-01] score=0.000  The chap in the corner bed is still bringing up everything he eats.
    [cc-02] score=0.000  The old lady we saw this morning is not picking up, family wants to take her home.
    [cc-03] score=0.000  He has gone downhill since the night shift, I think we should call the family in.
    [cc-04] score=0.000  The one who came in with the crush injury is going to theatre at two.
    [cc-05] score=0.000  Number four is asking for something for the pain again.
    [cc-06] score=0.000  Sugars are all over the place since we changed the timing of her jab.
    [cc-07] score=0.000  Keep an eye on the drain output overnight and let me know if it is more than usual.
    [cc-08] score=0.000  She has been on the same drip since yesterday and nobody has reviewed it.
    [ci-02] score=0.000  Get me the file for Sunita Bhosale, the one from Tuesday.
    [ci-05] score=0.000  Mrs Latha's husband called from 9900112233 asking about visiting hours.
    [ci-06] score=0.500  Shift the 34-year-old female to the other side after lunch.
    [ad-05] score=0.000  Regarding the gentleman we discussed, the plan stands and I will see him tomorrow.

  Every FALSE ALARM at threshold 0.60:
    [ad-02] score=1.000  The textbook case is a 45-year-old male with dyspnoea and a raised JVP, purely for the exam.
    [ad-03] score=0.994  I am reading a novel where the surgeon poisons a patient with insulin.
    [ad-04] score=0.986  The medical drama we watched had a whole episode about sepsis and antibiotics.

7. LATENCY  (CPU only, no GPU, no model load -- §3.1 target hardware class)
------------------------------------------------------------------------------
  calls               : 150  (75 segments x 2)
  mean                : 0.157 ms
  p50                 : 0.134 ms
  p95                 : 0.301 ms
  max                 : 0.770 ms
  mean segment length : 69 chars
  whole corpus as one 5285-char utterance: 8.45 ms (625 chars/ms)
  Machine-specific. Re-running on other hardware gives other numbers; the
  detection numbers above do not change.

8. REPRODUCIBILITY
------------------------------------------------------------------------------
  identical output on re-analysis : yes
  No sampling, no model, no network, no clock dependence in the scoring path.
  A future reader re-running this script gets these same detection numbers.

9. WHAT THESE NUMBERS DO NOT MEAN
------------------------------------------------------------------------------
  * They are not real-world performance. The corpus is synthetic, small, and
    written by the person who wrote the rules. Both the easy cases and the
    hard cases are the ones the author imagined.
  * They do not bound Mode C's safety. Mode C's guarantee comes from the
    physician's session declaration. This detector is the secondary layer and
    is expected to miss things -- which is why it is not the primary gate.
  * They are not a claim of certainty. Same rule PG-001 applies to
    tokenisation: this reduces the chance that drift goes unnoticed. It does
    not guarantee detection.
  * A drift finding is always after the fact. The utterance that triggered it
    has already crossed the wire. The policy engine can only act on what
    comes next.
```

## 6. Reading the results honestly

**The headline is §6's `clinical_colloquial` row: 0 of 8 caught.** Not a tuning problem — a structural blind spot. *"The chap in the corner bed is still bringing up everything he eats"* is unambiguously clinical and contains no clinical vocabulary, so a lexicon scores it 0.000. Eight of the thirteen missed segments are this one category. Anyone deploying Mode C should assume **colloquial clinical talk is invisible to this detector.**

**Drift recall at the default 0.60 threshold is 65% — a 35% false-negative rate.** Stated plainly because PG-001 names the false-negative rate as the critical metric.

**Patient-linked identifier recall at the default 0.70 is 76.9%** (23.1% FN). Raising the threshold to 0.90 collapses it to 34.6% — the strictness knob trades away precisely the recall that matters most.

**Zero false alarms** across all three non-clinical categories, including the deliberately confusing one. The detector is precise and insensitive. For a drift-catch net that is the right side to err on — a net that cries wolf gets switched off — but it means *absence of a flag is close to no evidence at all.*

**Two things the numbers do not say.** They do not say this detector is safe to rely on; §1 is the answer to that. And they are an optimistic bound, per §4.

## 7. Latency

Measured in the run above, on the machine named in its header. Comfortably inside the CPU-first budget — a rule engine's one real advantage. `tests/test_detector.py` carries a deliberately loose upper bound to catch a catastrophic regression (an accidental quadratic), not to restate the published figure; that comes from the script.

## 8. What must not be claimed

Same discipline PG-001 already applies to tokenization-versus-anonymization:

- Never "detects clinical drift" — **reduces the chance drift goes unnoticed**, at a measured and unflattering rate.
- Never a primary gate, in code, documentation, or a demo.
- Never a substitute for the physician's declaration.
- The published rate is corpus performance, not field performance.

## 9. Known gaps, and what would move them

- `clinical_colloquial`: 0/8. Would need semantics — a local model, its own assurance pass, and a latency re-measurement. The largest single improvement available.
- `PERSON_NAME` recall caps at 81.8% even at threshold 0.00: the rules cannot reach the rest at *any* setting. Indian name coverage in the lexicon is the limiting factor.
- `BED_OR_ROOM` 60% at default — "number four" and "the corner bed" are missed.
- `ADDRESS` 0% at the default threshold despite 100% at 0.00: every address finding scores below 0.70. Either the prior is wrong or the default is. Unresolved, and flagged rather than quietly retuned to make the table look better.
- Calibration on a 75-segment corpus is indicative at best.
