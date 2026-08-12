# Action Trust Tiers — resolving §4.4c principle 5's open sub-question

**Status:** design resolution, nothing built. The subsystem this governs (Communication Gateway,
PG-001, Stage 1c remote access) is parked and developer-only. This document exists so that when it
*is* built, the tiering is a decision someone made rather than a default that happened.

**Decided by the owner, not re-litigated here:** hospital record modification gets its own top tier,
always requiring explicit confirmation regardless of channel, removed from the generic "higher-risk"
bucket it currently shares with email and file deletion. This document works out what that means
concretely, and says plainly where the instruction needs a refinement to be workable.

**Do not read this as clearing UNK-03′.** It builds the trail a liability determination would need.
It does not answer who carries the liability. Stage 1a's gate is untouched.

---

## 1. The scheme

**Action Trust Tiers (ATT).** Four tiers, ordered by *irreversibility and liability exposure* — not
by sensitivity. Sensitivity is PG-001's axis and is handled separately; see §7.

| Tier | Name | Membership rule | Gate |
|---|---|---|---|
| **T3** | **Clinical write** | The action's effect lands in a system that **someone other than the physician will later read as an authoritative statement about a patient's care** — or causes physical work on a patient. | **Per-action explicit confirmation. Every time. No channel exemption, no session pre-authorization, no "approve all."** |
| **T2** | Consequential | Irreversible or externally-visible effect with no clinical-record status: outbound email/message, file deletion, payment, credential use, RHINAL vault writes (see §2.3). | Confirmation required, but **may be scoped**: a session can pre-authorize a bounded class for a bounded time under deployment policy. Security Broker's checkpoint table is the existing mechanism. |
| **T1** | Disclosing read | Reads clinical or personal data into a channel. Changes nothing. | **No per-action confirmation.** Governed by Capability Negotiation + PG-001 data classification at session start. Audited. |
| **T0** | Local | Effect is confined to JARVIS's own state, reversible, and invisible outside the machine: UI navigation, cached coordinates, logging verbosity, non-propagating queue state. | None. |

**The load-bearing claim in T3's membership rule is "someone other than the physician will later read
it as authoritative."** That is the property that produces liability. It is not "the action feels
clinical," not "the word patient appears," and not "it touches the EMR" — a read touches the EMR too.

**T3 sits above bank transfer, and that is deliberate.** The Security Broker entry treats financial
actions as its ceiling. Money moved in error is recoverable through mechanisms that exist and are
routinely used. A discharge executed in error is not, and UNK-03′ is specifically about the case
where it is not. **Financial actions stay at T2.**

### Relationship to §4.6's Phase 3d immutable tier

**These are different axes and must not be collapsed.** Phase 3d's three tiers govern *what JARVIS
may change about itself*. ATT governs *what JARVIS may do to the world at runtime*. An action's ATT
tier says nothing about whether the code implementing it is self-modifiable, and vice versa.

They touch at exactly one point, and it is a hard requirement:

> **The T3 classification table, the confirmation mechanism, and the T3 gate's call-site policy all
> belong in the Phase 3d immutable tier.** §4.6 already places "the approval mechanism itself" there.
> A gate JARVIS can propose an amendment to is not a gate — the same reasoning that makes
> `secure_key.py` refuse ambiguous configuration rather than picking a default.

Crosswalk, to make the independence concrete:

| | Immutable | Approval-gated | Free |
|---|---|---|---|
| **T3** | the gate and the classification table | *(empty by construction — no self-authored code may perform a T3 write)* | *(empty)* |
| **T2** | — | a generated adapter that sends email | — |
| **T1/T0** | — | a new read-only adapter | cached UI coordinates |

The empty T3/approval-gated cell is a real constraint, not a formatting artifact: **Adaptive Adapter
Generation and Phase 3d skill-writing may not produce code that performs a T3 write.** Generated
code may prepare a T3 payload; committing it goes through the human-written gate. This falls
straight out of §4.6's existing "approval routes to the developer, not the physician" reasoning —
a physician cannot review generated adapter code, and a generated adapter writing to a chart is
exactly the compounding of two weak links §4.6 exists to prevent.

---

## 2. What counts as a hospital record modification

The boundary is the point of this document. Three rules, then the cases.

**Rule 1 — the tier follows the destination, not the verb.** "Mark done" is T0 in JARVIS's own
queue and T3 the moment that queue writes through to the HIS. The button is identical; the tier is
not. This is the only rule that survives Stage 1a, where the dummy OPD UI's status transitions
become bidirectional with a real system.

**Rule 2 — the boundary is the signature, not the keystroke.** Composing, drafting, structuring,
pre-filling, and staging are **T2 at most**. The single act that commits a draft into the record is
T3. Everything before it is reversible by deleting a draft nobody has read.

**Rule 3 — ordering physical work is a write.** An order is not a note about the world; it causes
the world to change. It is T3 even though nothing about the chart's prose changed.

### 2.1 The cases, decided

| Action | Tier | Why |
|---|---|---|
| Discharge, admit, transfer | **T3** | UNK-03′'s literal case. |
| Prescribe / modify / stop a medication | **T3** | Physical effect on the patient; authoritative to the pharmacist. |
| **Order a lab or imaging study** | **T3** | Rule 3. Causes a needle, a scan, a bill, and a result someone must act on. The "is ordering a *modification*?" framing is the wrong question — it is more consequential than editing prose, not less. |
| Sign/close an encounter note | **T3** | Rule 2 — the signature is the boundary. |
| Draft that note, restructure it, pre-fill fields | **T2** | Rule 2. This is where the paperwork burden actually lives; see §4. |
| Acknowledge / act on a critical result | **T3** | Acknowledgement is a legally-read assertion that the physician saw it. |
| Amend or retract an existing entry | **T3** | Amendment carries its own liability profile; some systems make it non-reversible. |
| **Mark a queue entry `DONE` in JARVIS's own surface** | **T0** *(until Stage 1a)* | Rule 1. Operational state in JARVIS's event graph, which §5 already establishes is *not* the clinical source of truth. **Becomes T3 the day it syncs to the HIS**, and the surface must visibly mark which entries write through — a physician cannot see the difference between the two buttons, and that is a real UX hazard, not a theoretical one. |
| Print / export / display a record | **T1** | Not a modification. It is a disclosure, on PG-001's axis. See §7. |
| Send a referral letter to another clinician | **T3** | It becomes part of another clinician's record and is read as authoritative. Note this is an *email* by transport — which is exactly why principle 5's original bucket was wrong. |
| Bank transfer, UPI payment, bulk file deletion | **T2** | Recoverable in the sense that matters. Security Broker's existing multi-step approval applies. |
| Any write JARVIS makes to its own audit trail | **n/a** | Append-only, hash-chained, immutable tier. Not an action a tier can authorize. |

### 2.2 Genuinely ambiguous, flagged rather than decided

- **Correcting an obvious typo in a signed note.** Formally an amendment (T3); practically the kind
  of thing that will make the gate feel absurd on its tenth firing. **Left at T3** because "obvious"
  is a judgment JARVIS makes and Rule 2 exists precisely to stop JARVIS from making it. Revisit with
  a physician, not with more design.
- **Batch sign-off on ten normal results.** Real clinical practice, and a single confirmation
  covering ten T3 writes. Handled in §4.2 with a hard constraint on how batching may work — not by
  demoting the individual writes.
- **A vitals entry typed by a nurse that JARVIS relays.** Whose confirmation counts? The design
  currently, silently, assumes the physician's. See §8.
- **An order placed against a *simulated* patient in the dummy OPD UI.** Tier follows the
  destination, so T0. But if the gate is only ever exercised against synthetic data during Stage
  0.5, its real-world firing rate is never measured — which is §4.4's whole failure mode. The gate
  should run in the dummy UI as if real, counting confirmations it does not actually need.

### 2.3 RHINAL — decided T2, with two escalations, and this is a judgment call

RHINAL is explicitly **not** the clinical source of truth (§5, "RHINAL's scope — unchanged"). A
capture into the physician's own vault is structurally closer to a personal notebook than a chart
entry: nobody else reads it as authoritative. Under T3's membership rule it does not qualify.
**RHINAL writes are T2.**

Two escalations to T3:
1. A deploying organization's policy declares the vault part of the medical record. That is their
   call to make, not this project's — the same posture as PG-001's "the gateway does not decide what
   is compliant."
2. Any path by which RHINAL content flows *back* into the EMR. At that point the vault is a staging
   area for a record write and Rule 2 applies to the commit.

**Stated honestly: this is the weakest judgment in the document.** It rests on a boundary (§5's
event-graph/EMR/RHINAL split) that has never been tested against a hospital's actual definition of
"the record." If the answer comes back that a physician's structured notes about a patient are
discoverable and record-adjacent, RHINAL moves to T3 and §4's fatigue arithmetic gets materially
worse, because `rhinal_capture` is the one write that is already wired and already frequent.

---

## 3. "Regardless of channel" — the guarantee is invariant, the UX is not

**Reading of the owner's instruction, stated so it can be corrected:** "regardless of channel" means
**no channel exempts a T3 action from confirmation**. It does not mean every channel presents the
same dialog, and — importantly — it does not mean every channel is *capable* of carrying T3.

### 3.1 The four properties every T3 confirmation must have, on every channel

1. **The concrete effect is presented, rendered from the payload that will actually be sent** — not
   from the natural-language request. Confirming the request confirms what JARVIS *heard*; only
   rendering the payload confirms what JARVIS will *do*. This one property is the difference between
   a safety gate and a politeness ritual, and it is where a naive implementation will fail.
2. **A positive, action-specific act of consent** that inattention or ambient room noise cannot
   produce. Not a bare "yes." The consent token must contain something distinguishing drawn from the
   action itself.
3. **Bounded validity.** The confirmation authorizes exactly this payload, once. It expires. Re-use
   for a re-derived payload is forbidden even if the payload looks identical.
4. **Ambiguity is refusal.** Silence, a partial match, an unrecognized reply, a second voice, or a
   timeout all mean *not confirmed*. The action does not fire, and the non-confirmation is audited.
   **No re-ask loop** — asking twice trains the physician that the first ask is noise.

### 3.2 Per channel

| Channel | Presentation | Consent act | Timeout |
|---|---|---|---|
| **Desk-side voice** (the only real channel today) | Spoken back **and** shown on screen, both from the payload. | Spoken phrase containing a distinguishing token from the action — *"confirm discharge, bed twelve"* — not *"yes."* | 60s → expire |
| **Desk-side keyboard/screen** | Payload rendered, diff-shaped where the target has a prior value. | Deliberate click with the payload text visible and unscrolled. | 60s → expire |
| **Companion phone** (Security Broker's Approval Engine) | Full payload pushed to the device. | Device unlock + Approve. Exactly the existing pattern; **reuse it, do not build a second one.** | 5 min → expire |
| **Remote inbound** (WhatsApp/Telegram, Stage 1c) | — | — | **Cannot carry T3.** |

### 3.3 The recommendation that goes slightly beyond the instruction

**A channel that cannot satisfy all four properties must not carry T3 at all — the action is
refused, not downgraded.** For remote inbound specifically: JARVIS cannot verify who holds the
phone, the transport is exactly the one §4.4c's own closing line says should default to Strict Local
for clinical deployments, and a confirmation obtained over it is a text message from an
authenticated *number*, which Stage 1c already says is insufficient identity on its own. Blocking
T3 over remote is the stricter reading of the owner's decision, not a loophole in it.

**This creates a genuine contradiction inside the six principles that the parent must resolve.**
Principle 4, Channel Independence, says the same local engine executes regardless of channel.
**T3 is a deliberate exception to principle 4.** Either principle 4 gains a T3 carve-out or the two
principles disagree in the same document. The replacement text in §9 states the exception inside
principle 5; principle 4 should get a pointer to it.

### 3.4 The honest weak point

**Desk-side voice is the weakest of the confirmation channels, and it is the primary one.** The
audio channel is shared with everyone in the room including the patient; JARVIS cannot verify the
speaker; speaker verification is not built and must not be assumed as a free primitive — the same
error PG-001's Detector Assurance principle exists to prevent. The distinguishing-token requirement
in property 2 reduces accidental confirmation. It does nothing against a deliberate one by another
person in the room. If that matters to a deploying hospital, the answer is the companion device,
not a better phrase.

---

## 4. Approval fatigue — the part that decides whether this works

§4.6 already names approval fatigue as a real failure mode, in the specific form *"a physician
clicking approve for the twentieth time that day is not a meaningful safety gate."* T3 is exposed to
exactly this, worse.

### 4.1 The arithmetic, stated before the mitigations

A busy OPD session is 40–100 patients. If every prescription, every lab order, and every encounter
close is T3, that is plausibly **150–400 confirmations per session**. At 3–5 seconds each that is
**10–30 minutes of pure confirmation added to the session.**

**Applied naively, this tier fails the north star.** "A physician's capacity is limited by their
judgment, not by their paperwork" is not served by a system that adds twenty minutes of clicking.
The tier as literally specified — top tier, always confirm — is correct about the irreversible edge
and, on its own, a net loss to the physician. That is not a reason to weaken it. It is the reason
the draft/commit split below is load-bearing rather than a convenience.

### 4.2 What actually fixes it

1. **The draft/commit split (Rule 2) is the mitigation, not a side effect.** The paperwork burden is
   in composing, structuring, transcribing, finding the right field, and re-typing what was already
   said — all T2 or below, all fully automatable, all where the north star's value is. The gate
   fires only on the commit. A physician who reviews and commits ten drafted orders in one screen
   has had their paperwork removed and their authority preserved. **This is the design; the gate is
   the smaller half of it.**
2. **Batch confirmation, with a hard constraint.** One confirmation may cover multiple T3 writes
   **only if every item is individually rendered from its own payload and individually removable
   before commit.** Forbidden: a summarized batch (*"commit 10 orders"*), a collapsed list, and any
   scroll-hidden item counted as presented. The physician's eyes must have had the opportunity to
   land on each payload. This is honest about what it buys: it collapses N consent acts into one,
   not N presentations into one.
3. **Session-scoped pre-authorization for T3 is rejected outright.** *"Approve all discharges this
   session"* is the single change that would convert this tier into theatre. It is not offered, not
   configurable, and not available to deployment policy.
4. **Measure the gate instead of declaring it works.** The Boundary Ledger is already the instrument
   and already being built. Every T3 confirmation logs its **dwell time** and its outcome.
   **Proposed failure criterion: if >95% of T3 confirmations are approved with dwell time under one
   second, the gate is not being read and must be reported as not working** — regardless of the fact
   that it fired correctly every time. This is PG-001's Detector Assurance discipline applied to a
   human component: a safety property that rests on "the physician is probably reading it" must be
   measurable or it is an assumption.
5. **Residual, unresolved:** the real per-session T3 count is unknown and unknowable from this desk.
   Stage 0.5 measures it. Nothing in this section should be treated as settled before it does.

---

## 5. Composition with Capability Negotiation

**The tier is a property of the action. The capability set is a property of the session.
Enforcement is the pair — but only one direction is negotiable.**

- `action → tier` is a **static, code-side classification in the immutable tier**. A session cannot
  negotiate an action's tier down. If the tier were session-negotiable, every weak channel would
  become an argument for a lower tier, which is precisely the silent default this sub-question was
  logged to prevent.
- `session → (max tier, available confirmation modalities)` comes from **Capability Negotiation at
  connect time**, from deployment policy. This is the existing mechanism and needs no new one.
- Enforcement is `min(action requirement, session capability)`, with one rule: **if the session
  cannot satisfy the action's requirement, the action is refused, not downgraded.** Silent tier
  collapse over a weak channel is the failure mode this rule names and blocks.
- **The capability set is fixed for the lifetime of the session.** It is negotiated at connect and
  never re-negotiated upward mid-session — otherwise "negotiation" becomes a request JARVIS makes
  whenever it is blocked. Same shape as PG-001 Mode C's declared-intent primacy: a hard, checkable
  declaration made before the work starts beats an inference made during it.

The capability set's rendering gains a tier, because `RHINAL Writes: ✗` does not carry enough
information once tiers exist:

```
Remote Voice:        ✓
Patient Discussion:  ✗   (deployment policy: clinical_notes.allow_remote = false)
Clinical Writes:     ✗   (T3 — channel cannot satisfy confirmation properties 2 and 4)
RHINAL Writes:       ✓   (T2 — confirmation required, session-scopable)
Email:               ✓   (T2 — confirmation required)
```

**Where the gate physically sits.** Not a new central chokepoint. D15/D16 already proved that not
everything reaches `UIExecutor.execute_intent()`, and `AgentCore/mcp_audit.py` already establishes
the right shape for that reality: **a shared mechanism, applied as call-site policy per class of
write.** A T3 build should follow it exactly — a `clinical_write_gate` module standing in the same
relation to the confirmation mechanism as `mcp_audit.py` stands to `audit_trail.py`. Wrapping a
clinical write in the gate is how a call site opts in; there is no path that reaches a T3 adapter
without passing through it. New machinery is justified only for the confirmation-state handling
itself, because nothing existing does multi-turn payload-bound consent — `ResolutionGate`'s
`PendingInstall` is the nearest pattern in the codebase and is worth reading before writing it.

---

## 6. What gets audited

**Yes — the confirmation is its own audited event, separate from the action.** A record showing that
a discharge was executed does not establish that a human authorized it; that is the entire point of
the tier, and it has to be in the log or it did not happen.

`mcp_audit.py`'s two-record shape extends to **three** for T3:

| # | Record | When | Why it is separate |
|---|---|---|---|
| 1 | `t3_confirmation_requested` | Before presentation, carrying the payload identity | Establishes *what was shown*, which is the fact a dispute turns on |
| 2 | `attempted` | After consent, before the wire | `mcp_audit.py`'s existing reasoning applies unchanged: a remote effect can persist even if this process dies |
| 3 | `success` / `failed` | After | JARVIS's *view* of the outcome, which can be wrong |

**A refused, expired, or ambiguous confirmation emits a record too**, and it is one of the most
valuable lines in the log: a compliance fact and a Boundary Ledger entry at once — the system tried
to do something clinical and the physician said no, or was not there to say yes.

Two concrete blockers a T3 build inherits, both already flagged in existing code:

1. **`mcp_audit.py`'s pairing-by-adjacency limitation gets worse.** It is sound today only because
   `jarvis.py`'s loop is strictly one-command-at-a-time and synchronous. Three records with a human
   pause in the middle breaks that assumption immediately — the physician can be interrupted between
   presentation and consent. **The additive correlation-id field on `emit_clinical_action()` that
   `mcp_audit.py` explicitly flagged as "a decision someone makes, not an assumption that quietly
   rots" is a hard prerequisite for T3, not an improvement.**
2. **The `consent` field is currently hardcoded `"direct_user_action"`.** `audit_trail.py`'s docstring
   says it exists so a real consent model has somewhere to write real values. **T3 is the first thing
   that makes it carry information** — it should record the confirmation modality and the id of the
   confirmation record. Also additive; also required.

Both are additive fields on an immutable-tier module. That is a deliberate, human-reviewed, git-only
change, exactly as §4.6 requires — flagged here so the T3 phase budgets for it rather than
discovering it.

---

## 7. Read-only access vs. writes — different tiers, and different axes

**Not the same tier. Reads are T1.** Two defences, in both directions:

**Why reads must not be T3.** A read changes nothing about the patient's care. UNK-03′'s question
does not arise — there is no version of "JARVIS read the chart and the patient died." And gating
reads at T3 would fire constantly: reading is the most common thing a clinical assistant does, so a
T3 read requirement would produce hundreds of confirmations per session and destroy the write gate
by association. That is not a hypothetical trade; it is §4's failure mode arriving through the
side door.

**Why reads are not free either.** A read is a **disclosure**, and disclosure has real
consequences — a read over a remote channel, into a room containing people who are not the patient,
is a bigger privacy event than many writes. This is not an argument for raising reads' ATT tier.
It is the evidence for the structural claim:

> **ATT orders actions by irreversibility and liability. PG-001 orders data by sensitivity. Neither
> subsumes the other, and a complete authorization decision is the conjunction of both.**

A T1 read of a Clinical Narrative over a Mode-C session is blocked — by PG-001, on the data axis,
not by ATT. A T3 write of a value containing no patient identifier at all is still gated — by ATT,
on the liability axis, not by PG-001. Collapsing these into one number is the mistake principle 5's
original single "higher-risk" bucket was making at a smaller scale.

---

## 8. What this does not settle

Design cannot answer these. Each needs a named human.

1. **UNK-03′ itself — unchanged.** This produces evidence that a physician authorized an action. It
   does not establish that the authorization transfers malpractice liability from JARVIS's vendor to
   the physician, and a "click to confirm" record may or may not be worth anything in an Indian
   medical-negligence proceeding. **Needs: legal counsel.** Stage 1a's gate remains closed.
2. **Whether a hospital accepts JARVIS-mediated confirmation as authorization at all.** Some will
   require the write to occur inside the physician's own authenticated HIS session, which would make
   certain T3 actions structurally impossible for JARVIS regardless of how good the confirmation is
   — the tier would be moot for those actions. **Needs: a hospital's policy authority.** This is
   plausible enough that a T3 build should not assume its own premise.
3. **The real T3 firing rate per OPD session.** All of §4 is arithmetic over guessed numbers.
   **Needs: Stage 0.5, run.**
4. **Whether the signature is really the clinical boundary.** Rule 2 is the keystone of the whole
   design and it is a claim about how physicians actually work, not about architecture. If the real
   boundary is elsewhere — if orders are placed continuously through a session rather than committed
   in batches — the fatigue mitigation weakens badly. **Needs: a physician, watched for one session.**
5. **RHINAL's status: notebook or record.** §2.3. **Needs: a deployment's policy authority.**
6. **Delegated confirmation.** A nurse or intern confirming on the physician's behalf is ordinary
   practice in an Indian OPD. This design forbids it — **silently, which is worse than forbidding it
   loudly.** Either it is permitted with the delegate recorded as a distinct `who`, or it is refused
   and the workflow has to route around it. **Needs: a physician and a hospital, together.**
7. **Speaker verification for voice confirmation.** §3.4. Unbuilt, and must be decided rather than
   assumed either necessary or unnecessary.

---

## 9. Self-test against the north star and §4.6

Required by the standing instruction, and the v3.5 audit's finding about §4.4c makes skipping it
unavailable.

**Does this move a physician closer to using JARVIS, or make JARVIS more impressive to an engineer?**

Honestly: **a tier scheme by itself is the second.** It is authorization infrastructure — the same
"one level removed" category the v3.5 audit correctly flagged PG-001 and the Communication Gateway
for, and no amount of careful tiering reduces anyone's paperwork.

**What makes it pass is Rule 2, and only Rule 2.** The draft/commit split says the entire body of
clinical paperwork — composing, structuring, transcribing, field-filling — is automatable without a
gate, and the gate applies only to the instant of commitment. That is the north star sentence
implemented rather than merely respected: the physician's judgment is what fires the write; the
paperwork around it stops being theirs. **A version of this document containing only the tier table
would fail the check and should be rejected.**

Second-order, and worth stating because it is the honest reason a tier scheme earns its place here:
the trust ceiling on autonomous action is one of the five named hurdles, and it is the one where
being more careful in a narrow place buys more autonomy in a wide one.

---

## 10. Replacement text for §4.4c principle 5 — paste verbatim

Replaces the existing numbered item 5 in the "Privacy & Data Residency Policy — six principles"
list. **Principle 4 also needs a one-clause pointer** (see §3.3): *"— except T3 clinical writes,
which some channels cannot carry at all; see principle 5."*

```markdown
5. **Trust-Based Authorization — four tiers, not one "higher-risk" bucket.** *(Sub-question resolved 2026-08-12; full working in `docs/trust_tier_clinical_writes.md`.)* Every channel gets a trust level, and every *action* gets a tier ordered by **irreversibility and liability** — not by sensitivity, which is PG-001's separate axis; neither subsumes the other and a complete decision is the conjunction of both. **T3 — clinical write:** the effect lands where **someone other than the physician will later read it as an authoritative statement about a patient's care**, or it causes physical work on a patient — discharge/admit/transfer, prescribing, **ordering a lab or scan**, signing an encounter note, acknowledging a critical result, amending an entry, a referral letter. **Per-action explicit confirmation, every time, no channel exemption, no session-scoped pre-authorization, no "approve all."** **T2 — consequential:** email, file deletion, financial actions, credential use, RHINAL vault writes — confirmation required but scopable under deployment policy; the Security Broker's checkpoint table is the existing mechanism, reused not replaced. **T1 — disclosing read:** no per-action confirmation, governed by Capability Negotiation plus PG-001's data classification, audited. **T0 — local:** reversible, non-propagating, no gate. **T3 sits above bank transfer deliberately** — money moved in error is recoverable, a discharge is not, and UNK-03′ is about the case where it is not. **Hospital record modification is removed from the bucket it shared with sending email; note that a referral letter is an email by transport and T3 by destination, which is precisely why the original grouping was wrong.**

   **Three rules fix the boundary.** (a) **The tier follows the destination, not the verb** — marking a queue entry `DONE` is T0 in JARVIS's own surface and **T3 the day that queue writes through to the HIS**; same button, different tier, and the surface must visibly mark which entries write through. (b) **The boundary is the signature, not the keystroke** — composing, structuring, transcribing and pre-filling are T2 at most, and only the act that commits a draft into the record is T3. *This is the load-bearing half, not a convenience:* the paperwork burden is entirely on the automatable side, and the gate applies to the instant of commitment. (c) **Ordering physical work is a write** even though no prose changed — an order causes a needle, a scan, a bill, and a result someone must act on.

   **"Regardless of channel" means no channel exempts the action — not that every channel can carry it.** Four properties are invariant everywhere: the effect is presented **rendered from the payload that will actually be sent, never from the natural-language request** (rendering the request confirms what JARVIS *heard*, not what it will *do*); consent is a positive act carrying a distinguishing token drawn from the action itself, never a bare "yes"; the authorization is bound to that one payload and expires; and **silence, partial matches, and timeouts are refusal — audited, with no re-ask loop**, since asking twice teaches the physician the first ask is noise. The UX differs by channel (spoken token desk-side, Approve on the Security Broker's companion device). **A channel that cannot meet all four does not carry T3, and the action is refused rather than downgraded** — silent tier collapse over a weak channel is the failure mode this rule exists to block. That blocks T3 over Stage 1c remote inbound, and makes **T3 a deliberate exception to principle 4's Channel Independence.** **Honest weak point:** desk-side voice is the weakest of these and is the primary channel — the audio is shared with the room and speaker verification is not built and must not be assumed.

   **The tier is a property of the action; the capability set is a property of the session; only one is negotiable.** `action → tier` is a static classification living in **§4.6's immutable tier along with the gate and the confirmation mechanism** — a gate JARVIS can propose an amendment to is not a gate. Capability Negotiation supplies `(max tier, available confirmation modalities)` at connect, **fixed for the session's lifetime and never re-negotiated upward mid-session**, or "negotiation" becomes a request JARVIS makes whenever it is blocked. Consequence worth stating: **no self-authored code may perform a T3 write** — Phase 3d skills and generated adapters may prepare a T3 payload, never commit it.

   **Audited separately from the action, per DEC-002 — a record that a discharge happened does not establish that a human authorized it.** Three records per T3 write, extending `AgentCore/mcp_audit.py`'s established shape rather than inventing a second one: `t3_confirmation_requested` before presentation, `attempted` before the wire, outcome after. **Refusals, expiries and ambiguous replies are recorded too** — a T3 request the physician declined is a compliance fact and a Boundary Ledger entry at once. Two prerequisites inherited and to be budgeted, both additive changes to an immutable-tier module: `mcp_audit.py`'s pairing-by-adjacency holds only because dispatch is synchronous and one-at-a-time, which **a human pause between presentation and consent breaks immediately — the correlation-id field it already flagged becomes required, not optional**; and the hardcoded `consent: "direct_user_action"` must start carrying the confirmation modality and the confirmation record's id.

   **Stated limit — approval fatigue, which §4.6 already names as a real failure mode.** At 40–100 patients per OPD session a naive T3 could fire **150–400 times, adding 10–30 minutes of pure confirmation** — which fails the north star outright. The mitigations are rule (b) above, plus batching that **renders every item from its own payload and allows each to be dropped before commit** (a summarised *"commit 10 orders"* is forbidden). **Session-scoped pre-authorization for T3 is rejected outright — it is the single change that would convert this tier into theatre.** And the gate is measured rather than assumed, in the same discipline as PG-001's Detector Assurance: log dwell time per confirmation, and **if >95% are approved in under a second the gate is not being read and must be reported as not working**, however correctly it fired. The real firing rate is unknown until Stage 0.5 runs. **None of this resolves UNK-03′** — it builds the trail a liability finding would need; whether a confirmation record transfers malpractice liability is a question for counsel, and **Stage 1a's gate stays closed.**
```
