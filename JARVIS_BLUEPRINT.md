# JARVIS Blueprint — Canonical Reference

**Version:** 2.5 · **Date:** 2026-07-29

> ## ⚠ READ FIRST — custody and companion file
>
> **This file has a companion: `JARVIS_EXECUTION_LOG.md`.** The blueprint holds *decisions and direction*. The execution log holds *what was actually done, what was found, and how each claim was verified* — including verification failures this project already suffered and the standing rules that came from them. **An agent looping on the blueprint alone does not have enough context to work safely. Read both.**
>
> **Custody rule.** Both documents must live **inside the JARVIS-Automation repo, tracked in git.** They previously existed only in a chat-side outputs directory, which meant the reviewing agent and the implementing agent each edited a private copy and neither could see the other's — edits appeared to land and were simultaneously absent. **This is not hypothetical — it happened twice.** Once when a completed fix (S0-E8) was reported done while sitting unpushed. Again when two independently-edited copies of *this file itself* diverged in `Downloads/` before either was ever committed — see the execution log's incident record. **If these files are not tracked in the repo, fix that before doing anything else.** Never edit a copy outside version control.

**Reference of record:** the `Dissection` repository. All major architectural decisions are taken against it.
**Verified against:** commit `31939c8` on `phase-2-adapter-wiring` (JARVIS-Automation)

> **What changed in v2.0.** v1.0 was a staging document written from inside the codebase. v2.0 is rewritten against three independent external analyses (Phase R repo-dissection, a five-panel technical due-diligence, and a strategic council verdict) plus the 449-platform ABDM discovery report and the 287-report corpus synthesis. All three analyses reached the same verdict, which v1.0 did not contain: **JARVIS has no healthcare in it, and the roadmap's own discipline mechanism could not detect that.**
>
> **What changed in v2.1.** Resolves **Q1** (§3.7) — the local/cloud/hybrid question the constitution left ASSUMED. Adds §3.8 (terminal identity: banner + orb on every launch, static frame). Restores nine items dropped in the v2.0 rewrite (§4.4b) — Phase 3b/3c/3d, appointment query, Qwen3-TTS gate, emotion detection, RHINAL MCP, the `# --- ADDITION` sweep, and the orb's decision history.
>
> **What changed in v2.2.** Adopts **Cognitive Operating System** as the framing architecture (§5.0). Names the **World Model** as a cross-cutting gap in the layer map — and resolves it: it *is* the patient-journey event graph, already decided, previously unnamed. Confirms RHINAL's scope is unchanged (separate MCP-reached product, not the clinical source of truth) and records why that boundary matters legally. Separates the two "Decision Engine" concepts.
>
> **What changed in v2.3.** Extends §3.7 (Q1) into **§3.7b — two-part routing.** Splits local/cloud model selection into a deterministic data-class gate (clinical → LAN ceiling, never learned) and a smart capability/confidence router beneath it (Conifer-shaped: try local, escalate on low confidence). Adds explicit user-override behavior — physicians can force a tier for general requests; clinical requests refuse cloud with a stated reason rather than silently complying or silently ignoring. Connects "stale local knowledge" complaints to the existing knowledge-retrieval chain before reaching for a bigger model. The original §3.7 rejection of connectivity-based clinical routing is preserved as the ceiling this new router operates beneath, not replaced.
>
> **What changed in v2.4.** Adopts the companion **`JARVIS_EXECUTION_LOG.md`** — evidence for closed Stage 0 items moves there; this file keeps a status + one-line pointer, not the full trail, so the table stays scannable. Closes S0-E1, S0-E2, S0-E8 with evidence. Adds D11 (4 dead-since-inception test failures) and D12 (`AvailabilityChecker` false positive on PWA shortcuts). Marks D1 resolved.
>
> **What changed in v2.5.** **Reconciliation.** Two independently-edited copies of this file were found diverged in an untracked `Downloads/` directory — this version merges both rather than discarding either (full incident record in the execution log). Recovers from the discarded copy: the §1.5 T3 row (v2.4 marked D1 resolved in §1.6 but left T3 at CONTRADICTED in §1.5 — an internal inconsistency, now fixed), D13 (a live `IntentRouter` misclassification bug found during S0-E1, absent from v2.4), and the §1.3 layer-map lines for L6/L7 (v2.4 left both stale despite S0-E2/S0-E8 having resolved what they described). Both files now committed inside the JARVIS-Automation repo — the custody rule above is satisfied, not just stated.

---

# PART 1 — WHAT JARVIS IS TODAY

## 1.1 One-sentence honest description

> A well-engineered, honest, local desktop automation agent with a strong planning/execution core and a self-coding subsystem. It contains **zero healthcare functionality of any kind.**

Not partial. Not prototype. Zero: no FHIR, no HL7, no ABDM/ABHA, no patient or encounter model, no OPD queue, no clinical vocabulary, no consent primitives.

## 1.2 Capability states — definitions

| State | Meaning |
|---|---|
| **VERIFIED** | Built, tested, confirmed working by documented live verification |
| **BUILT** | Code exists and is tested, not confirmed in the live path |
| **WIRED** | Reachable in the normal user path |
| **DARK** | Built but unreachable — no caller, or flag-disabled. *Inventory, not output.* |
| **DESIGNED** | Documented only. No runtime code. |
| **ABSENT** | Does not exist |

## 1.3 Layer map (L0–L15 canonical taxonomy)

```
L0  COMPUTE            external — Ollama host
      └── GPU presence UNVERIFIED → gates all Tier-2 inference work

L1  FOUNDATION MODELS  external — via Ollama
      ├── PREFERRED_MODELS   hardcoded fallback list, no runtime tier choice
      └── DEI / LoRA         DESIGNED (may fail by design)

L2  INFERENCE RUNTIME  Ollama
      ├── llm_engine.generate()        WIRED
      ├── generate_stream()            DARK ← exists at llm_engine.py:161, uncalled
      ├── warm-up / keep-alive         ABSENT
      ├── num_gpu / device config      ABSENT
      └── capability-tier router (Q1)  DESIGNED — see §3.7

L3  MEMORY  ⭐ posture: OWN
      ├── Persistent cross-session store (3a)   BUILT
      ├── Memory ↛ confirmation-gate boundary   VERIFIED ← real asset
      ├── conversation_manager._trim_to_budget  BUILT
      ├── rag_engine → serp_fetcher             WIRED, FRAGILE (Google HTML scrape)
      ├── summarisation                         ABSENT
      ├── temporal validity                     ABSENT
      ├── consolidation / forgetting            ABSENT
      └── procedural memory                     ABSENT
          ⚠ Storage is built. The contested, defensible half is not.

L4  PLANNING  ⭐ posture: OWN — STRONGEST AREA
      ├── IntentRouter.classify()      VERIFIED  canned/context/action/code/llm
      │                                ⚠ misroutes some "search for X" informational
      │                                phrasings to action instead of llm — see D13
      ├── CommandRouter                VERIFIED  5 bug classes fixed structurally
      ├── Resolution gate (3-branch)   VERIFIED
      ├── UIExecutor.execute_intent    VERIFIED  central pre-adapter validation
      ├── ODAVLoop                     WIRED     ⚠ incomplete gate-outcome handling
      ├── Level6 debug loop            VERIFIED
      ├── Approval gates + rollback    VERIFIED  ← real asset
      ├── Sub-agent spawning (3b)      DESIGNED
      └── NL scheduling (3c)           DESIGNED

L5  PERCEPTION  posture: own abstraction
      ├── screen_capture (mss)         BUILT, decoupled
      ├── Vision/                      BUILT, unverified
      ├── text-emotion detection       DARK — wired to nothing
      └── OCR                          DARK — AgentCore/ui_agent/vision/ocr.py,
                                       Path-B tree, unreachable from live loop

L6  EXECUTION  posture: integrate ✅ correct
      ├── 12 platform adapters         VERIFIED  focus-safety-fixed
      ├── browser_automation           VERIFIED  CAPTCHA/login-wall pause-resume
      ├── desktop launch-fallback      SPLIT     Telegram VERIFIED live (real running
      │                                          app found + activated, path matches
      │                                          the fix); WhatsApp's fallback logic is
      │                                          correct but unreachable in practice —
      │                                          open_app() false-positives via a Chrome
      │                                          "WhatsApp Web" window instead (S0-E2,
      │                                          2026-07-29, commit 31939c8; see D12)
      ├── Level6 SandboxRunner         VERIFIED
      └── LibCST AST transforms        VERIFIED

L7  VOICE  posture: integrate  🔴 ARCHITECTURAL LIABILITY ⚠ origin (D1) fixed
      │    2026-07-29 — label not yet reassessed; NetHyTechSTT dead-code status and
      │    the TTS gate are the remaining open questions under this label
      ├── WakeService (Vosk, grammar-locked)  VERIFIED
      ├── LocalSTT.listen_once()              VERIFIED — cloud path deleted, Vosk-only
      │                                        (S0-E8, commit a3c91d06, confirmed on
      │                                        origin/phase-2-adapter-wiring). Fixes D1.
      │                                        T3 flips CONTRADICTED → TRUE (§1.5).
      ├── NetHyTechSTT                        imported, apparently uncalled
      └── TTS (pyttsx3)                       WIRED  on hold pending Qwen3-TTS eval

L8  OS AI                                     N/A — not contested

L9  APPLICATIONS  posture: selective
      ├── code_engine                  VERIFIED
      ├── Level6 (4 phases complete)   VERIFIED  ⚠ off the healthcare path
      ├── jarvis CLI on PATH           BUILT
      └── onboarding / status box      VERIFIED

L10 HEALTHCARE PLATFORMS  ⭐ posture: INTEGRATE
      └── 🔴 EMPTY

L11 HEALTHCARE STANDARDS  posture: conform
      └── 🔴 EMPTY

L12 AUTOMATION PLATFORMS                      N/A
L13 DEVELOPER PLATFORMS
      ├── feature_flags/               BUILT
      ├── platform_adapters/           BUILT — adapter pattern is SDK-shaped
      └── RHINAL MCP integration       `rhinal_capture` WIRED (commit 80ae8cb);
                                       13 of 14 live-verified tools not yet wired

L14 ENTERPRISE AI                             N/A
L15 FRONTIER
      └── DEI / 8-layer routing probe  DESIGNED, falsifiable

CROSS-CUTTING — WORLD MODEL  🔴 THE NAMED GAP
      └── operational state: who exists · what exists · what is
          happening · why · confidence · last-updated · evidence
          ⟹ ABSENT today. Not a taxonomy layer — which is exactly
            why L0–L15 could not surface it as missing.
          ⟹ IT IS the patient-journey event graph (Stage 2),
            emitted from Stage 0.5 onward. Already decided —
            never previously named as a world model.

CROSS-CUTTING — GOVERN  ← the genuine differentiator
      ├── Honest-failure discipline    VERIFIED  consistent across subsystems
      ├── Confirmation gates           VERIFIED  memory cannot bypass
      ├── Approval-gated apply         VERIFIED  snapshot-first, reverts on partial failure
      ├── RollbackManager              VERIFIED
      ├── guards / safety / policy     PRESENT
      ├── Audit trail (remote cmds)    DESIGNED — Stage 1
      └── Consent (ambient recording)  BLOCKED — correctly, on legal input
```

## 1.4 Four structural observations

1. **Centre of gravity is L4+L6.** Planning and execution are genuinely good. This matches "OWN L4" but leaves "OWN L3" mostly unstarted.
2. **GOVERN is the sleeper asset.** Not a taxonomy layer — cross-cutting — and the most consistently well-built part of the system. Hardest thing to retrofit into a clinical product, easiest to underrate.
3. **The stack is inverted relative to the mission.** Deepest investment at L4/L6/L9 (general automation, self-coding); L10/L11 (the mission) empty; L3's defensible half empty. **This is the vertical-drift pattern.**
4. **L13 is accidentally well-positioned.** Adapter pattern + feature flags is already SDK-shaped. Unplanned optionality.
5. **Five of seven Cognitive-OS boxes already exist** (§5.0). The system is closer to the target architecture than the layer map suggests — the single genuine gap is the World Model, and that gap is already covered by a decision made under a different name.

## 1.5 Thesis status after grounding

| Thesis | Status | Evidence |
|---|---|---|
| **T1** — own the L3+L4 loop | **HALF-TRUE** | L4 genuinely strong; L3 is storage + safety boundary |
| **T2** — healthcare depth is a moat | **UNEVIDENCED** | Zero healthcare code. Intention, not artefact. |
| **T3** — local-first/privacy differentiates | **TRUE** *(flipped 2026-07-29)* | `recognize_google()`/`_fallback_listen` deleted from `LocalSTT.listen_once()`; Vosk is now the only recognizer; live-verified with real mic input; regression test added asserting no code path in the file can reach an external speech API. Commit `a3c91d06`, confirmed on `origin/phase-2-adapter-wiring`, not local state. Fixes D1. Full trail in the execution log's S0-E8 entry. |
| **T4** — adapters over legacy systems | **PARTIALLY PROVEN** | Proven on consumer apps; untested on clinical systems |

## 1.6 Known defects (all verified)

| # | Defect | Severity |
|---|---|---|
| ~~D1~~ | ~~`LocalSTT.listen_once()` calls `recognize_google()` **first**~~ — **✅ RESOLVED**, commit `a3c91d06` (S0-E8). Both cloud entry points deleted; verified by grepping the remote git object. **T3 now TRUE.** Kept in table for trail. | ~~🔴~~ closed |
| ~~D11~~ | ~~4 pre-existing test failures, dead since initial commit~~ — **✅ RESOLVED**, commit `21c37832`. All 4 fixed (not just found): `.policy`→`.config` reference, `file_path` now opened as the real written file inside the sandbox dir, `hmac_signature`→`sig` (the real, working key). All 4 formerly-failing tests now genuinely pass. | ~~🟡 Low~~ closed |
| ~~D12~~ | ~~`AvailabilityChecker`/`WhatsappDesktopAdapter` false positive on PWA shortcuts~~ — **✅ RESOLVED**, commit `54a86665`. `GUIBackend.activate_window()`/`close_window()` gained `exclude_process_names`, wired into both whatsapp/telegram desktop adapters (open + close). Live-verified both directions: WhatsApp's `open_app()` now correctly returns `False` (was `True`); Telegram's real-app detection unaffected. | ~~🟠 Medium~~ closed |
| ~~D13~~ | ~~`IntentRouter` misroutes "search for X" to `action`~~ — **✅ RESOLVED**, commit `6053c942`. ACTION_PATTERNS' search entry restricted to phrasings with an explicit action-continuation verb; bare "search for X" now falls through to `handler="llm"`. Live-verified against both original examples plus two non-regression guards (continuation case stays action, platform-named search still reaches the resolution gate). | ~~🟡 Medium~~ closed |
| D2 | `memory_store.py` "encryption" is XOR with hardcoded default key `"jarvis_default_key"` — visible in source | 🔴 Critical before any sensitive data |
| D3 | Import time ~16s (was 29s). Target for between-patient use: **<3s** | 🟠 Product-viability number |
| D4 | `rag_engine → serp_fetcher` scrapes Google HTML; fragile + ToS exposure | 🟠 High |
| ~~D5~~ | ~~Hardcoded `C:\Users\chatu` path in `Brain/brain.py`~~ — **✅ RESOLVED**, commit `8ce7f044`. Blueprint named only one file; 3 more live occurrences found and fixed too (`Features/clap_with_music.py`, `Time_Operations/throw_alert.py`, `ui.py`). Verified zero remaining repo-wide. | ~~🟡 Medium~~ closed |
| ~~D6~~ | ~~`LLMEngine` uses `subprocess(["curl", ...])`~~ — **✅ RESOLVED**, commit `fb332247`. Both `generate()` and `chat()` switched to `requests.post()`, matching `generate_stream()`/`chat_stream()`'s existing pattern. Live-verified against the real Ollama backend. | ~~🟡 Medium~~ closed |
| D7 | `ODAVLoop.execute()` incomplete gate-outcome handling (unreachable from live loop today) | 🟡 Low |
| D8 | `co_brain.py` legacy system #1 not retired | 🟡 Low |
| D9 | Default branch is stale `feature/improve-readme-presentation-…`, 30+ commits behind | 🟡 Low |
| D10 | Level6 enablement flipped outside version control | 🟡 Low |

## 1.7 Dark capability inventory

Real engineering producing **zero user value** until wired:

- `generate_stream()` — largest available perceived-latency win, cost **xs**
- text-emotion detection — built, boundary-tested, wired to nothing
- `jarvis_orb.py` — built and **approved**, untested on Windows terminal, not yet wired. **Not merely dark — a decided asset awaiting wiring.** See §3.8.
- `AgentCore/ui_agent/vision/ocr.py` — OCR in the unreachable Path-B tree

---

# PART 2 — THE ROADMAP

**Path, as decided:** physician → administration → hospital-wide.

**Stage numbering is now unified** across all four prior schemes. EMR adapter precedes ambient mode (ambient with nothing to write into is just recording).

## Stage 0 — Reliability layer *(all 9 exit criteria closed 2026-07-30 — not renumbering the original "72%", its computation basis isn't recorded here; work item 7 (D5/D6) closed 2026-07-30; work item 8 (D2) is the one remaining item and gates Stage 0.5's real-clinical-data exit criterion — see below)*

> **Evidence for every closed row is in `JARVIS_EXECUTION_LOG.md`** — commit SHA, what verified it, and any finding it produced. A bare ✅ without that trail is not acceptable in this table.

| ID | Criterion | Status | Evidence |
|---|---|---|---|
| S0-E1 | 3-engine + installed-app audit formally closed | ✅ | Per-engine verdict; all 4 suite failures named + provenance-checked → D11; conversational-layer misroute → D13 |
| S0-E2 | Desktop adapter launch-fallback independently verified | ✅ | `31939c8` — diff read, 4 tests re-run independently, real unmocked `open_app()` run against both adapters → surfaced/sharpened D12 |
| S0-E3 | Knowledge-retrieval fix (API tiers + failover) | ✅ | `20ce0a88` — SerpApi/Serper/browser tiered chain, config-driven, live-verified against the real SerpApi endpoint (a real key was supplied for this phase). Quota tracking corrected from the original "response headers" assumption to the real `/account.json` endpoint. Serper tier built but not live-verified (no key available) — flagged, not claimed. |
| S0-E4 | Command routing verified across bug classes | ✅ | 5 bug classes fixed structurally |
| S0-E5 | Resolution gate + honest-failure discipline | ✅ | |
| S0-E6 | Level6 approval-gated apply with rollback | ✅ | |
| S0-E7 | Persistent memory storage + boundary tests | ✅ | |
| S0-E8 | **Local STT — cloud path deleted** | ✅ 🔴 | `a3c91d06` — remote git blob grepped, zero cloud refs. **T3: CONTRADICTED → TRUE** |
| S0-E9 | Tier-1 inference wins (streaming, warm-up, token budgets) | ✅ | `bc83d7ec` — real end-to-end measurement on the actual jarvis.py path: 34.04s → 9.87s to first spoken word (24.17s faster). `chat_stream()` added (`generate_stream()` alone couldn't reach the live path, which uses `/api/chat` not `/api/generate`), warm-up wired at live startup only (not the constructor default — see execution log), `chat()` gained task-aware `max_tokens`. Re-measured per §3.7b's sequencing as instructed — the 9.87s number is the new baseline; whether that's fast enough to defer routing work further is the owner's call, not decided here. |

**Work items, in order:**

1. **STT: Vosk-first, cloud path deleted.** Not deprioritised — *deleted*. Fixes D1, unblocks T3. Whisper evaluated later as an accuracy upgrade against measured CPU latency, not assumed.
2. Close the audit formally. Perpetual "in progress" hides state.
3. Verify `31939c8`.
4. ~~Knowledge retrieval: SerpApi primary → Serper secondary → browser-automation last resort.~~ **Done (S0-E3, commit `20ce0a88`).** Config-driven providers, quota tracking (corrected to the real `/account.json` endpoint, not response headers — see execution log), user-visible provider switch, "let me check that" narration wired to `self._speak`, honest failure if the whole chain fails.
5. **Wire `generate_stream()`** — cost xs, speech starts at token 1 not token 150.
6. Model warm-up; task-aware token budgets (`MAX_TOKENS` 256 default; callers already vary 50–200).
7. ~~Fix D5 (hardcoded path), D6 (curl→HTTP client).~~ **Done, commits `8ce7f044`/`fb332247`.**
8. **Fix D2 — replace XOR with real encryption** before any clinical data touches the system.

**Freeze during Stage 0:** no further Level6/L9 investment, no DEI research, no orb wiring, no emotion wiring, no new desktop adapters.

## Stage 0.5 — One workflow, one physician ⭐

*The stage everything else depends on. Nothing in Stage 1 begins until this exits.*

**Build:**
- **Dummy OPD UI first** — a simulated queue (patient, status, notes) to develop against before touching any real system. Cheapest place to make mistakes.
- OPD queue: patient list, current, next, status transitions
- Local voice → `intent_router` → verified UI action
- **Audit trail architected in from line one** (DEC-002 — P0/10.00, highest-priority item in the generated roadmap). Every action emits who/what/when/why/source/consent. Retrofit cost grows with every adapter; the decision is one-way.
- **Boundary Ledger** — log every case where a deterministic rule was wrong or ambiguous on real clinical input. This *is* the symbolic-vs-learned boundary map, and it costs one workflow instead of a research programme.
- **Event emission from day one.** Every state change writes a provenance-stamped event. This is the substrate Stage 2 needs — build it now or Stage 2 becomes a rewrite.

**Explicitly not in scope:** FHIR, ABDM, EMR integration, remote access, ambient mode, cloud anything.

**Exit criteria:**

| ID | Criterion |
|---|---|
| S05-E1 | OPD queue used by one physician in real clinic conditions |
| S05-E2 | Physician feedback captured and has visibly reshaped Stage 1 priorities |

**Parallel, zero-cost:** begin the Indic OCR corpus, Track A only (see §3.4).

## Stage 1 — Physician depth

**1a — The Adapter.** One real clinical system, bi-directional.
- **ABDM/FHIR protocol adapter is the primary path.** One well-built ABDM adapter reaches ~250 government-certified HMIS platforms — every certified vendor has already implemented FHIR R4, ABHA identity, and consent exchange.
- Bahmni/OpenMRS first as the learning target: open source, readable schema, local test harness, zero vendor cooperation needed.
- Visual/UI automation is the **long-tail fallback**, never the primary strategy (§3.2).
- **Gate: UNK-03′ liability must be resolved before any clinical write.**

> **Pending strategy input — not yet decided, do not treat as settled.** The execution log records an evidence-backed argument (the "Commit Gap" reading of the `Dissection` corpus) that ABDM belongs at **Stage 2**, not here, because standards govern inter-institutional exchange and cannot reach inside hospital workflow (LAW05). This is a **Parts 1–3 strategy rewrite, explicitly out of scope for any single phase** — it needs a deliberate review, not a queue item silently overwriting 1a above. See the execution log's "Findings that change strategy" section for the full argument before this is decided either way.

**1b — Ambient mode.** Only after 1a; ambient needs a system to write into.
- Never default-on; explicit per-session activation
- Mandatory visible/audible indicator — everyone in the room, not just the physician
- Automatic timeout, re-confirmation to continue
- **Proactive suggestions only.** Recording→RHINAL stays **consent-blocked** pending DPDP + medical council + hospital policy resolution. Not an engineering question.

**1c — Remote access.** WhatsApp/Telegram inbound, same pipeline, no new command surface.
- **Authentication is a hard prerequisite**: second factor (PIN/pairing), session-based trust with timeout, full audit trail. Phone-number identity alone is insufficient.
- Machine-off is a hard limit. Resolution: **queued delivery** — platforms hold messages; JARVIS processes on return. No always-on cloud.
- Host machine must be treated as infrastructure (kept powered on), not a laptop shut at day's end.

## Stage 2 — Administration *(this is Plan C)*

Buyer shifts: physician → **COO + CFO + CNO**, with CIO as design authority.

**Discharge-to-Claim Command Center**, for 50–300-bed Indian multi-specialty hospitals:

1. Assemble operational + documentation state for every inpatient encounter
2. Identify discharge blockers, missing documents, authorisation gaps, claim-readiness defects
3. Assign next action to the accountable role (nurse, doctor, front desk, billing, pharmacy, housekeeping, payer liaison)
4. Escalate ageing exceptions; produce an auditable, human-approved discharge/claim packet
5. Feed bottleneck analytics to COO/CFO

**Architecture:** modular Healthcare Operations Fabric, **not** a monolithic Hospital OS.

```
Existing HIS / EMR / ERP / LIS / RIS-PACS / payer portals / ABDM / PDFs / voice
                          │
           connectors + secure ingestion + OCR + mapping
                          │
   canonical patient-journey event graph (source, time, actor, confidence, consent)
                          │
   rules engine + workflow state machine + policy packs + audit ledger
                          │
   role worklists / command center / offline mobile / patient communications
                          │
   analytics: throughput, task ageing, blockers, documentation gaps, claim readiness
```

**Non-negotiable principles:**

1. System of **action**, not initial system of record
2. Human accountability — AI drafts, extracts, prioritises, explains; humans approve
3. Event provenance on every fact — source, timestamp, actor, confidence, review state
4. Configurable workflow, not hard-coded hospital dogma
5. Offline-tolerant — cache, delayed sync, expose conflicts rather than silently overwrite
6. **Integration-light first** — don't make perfect integration a precondition for value
7. Security by design — tenant isolation, least privilege, consent-aware access, local/hybrid hosting
8. **No silent automation** of diagnosis, prescription, code selection, claim submission, or risk decisions

## Stage 3 — Hospital-wide operational control

Triage dispatch, ambulance coordination, cross-department orchestration.

**Not designed. Do not begin designing until Stage 2 has real deployed usage.** A different category of system — closer to critical infrastructure — requiring domain expertise, formal safety engineering, and regulatory engagement the project does not yet have.

---

# PART 3 — TECHNOLOGY DECISIONS

## 3.1 Product thesis: CPU-first

Target hardware is **ordinary machines**: Intel i5/i7 U-series, Ryzen 5 laptops, 8–16 GB RAM, integrated graphics, no CUDA. "JARVIS runs fast on ordinary laptops" is harder to build and harder to copy than any model choice.

Consequence: GPU work drops in priority for the physician-facing loop. Streaming, warm-up, and token budgets matter *more* — on CPU they are the whole game.

**Deployment topology (resolves the GPU tension):**
- **Physician laptop** — CPU only. Voice, routing, UI automation.
- **One GPU box inside the hospital firewall** — document parsing as a batch service. Data never leaves the building; DEC-004 satisfied without a GPU per clinician.

## 3.2 UI element resolution — three-tier resolver

Adopted from Clicky (MIT, attribution required). Its author built the vision-grid approach *first*, then replaced it — that failure is inherited for free:

> *"Vision models trained on natural images don't have pixel-precise spatial reasoning, so they'd often pick a neighbouring cell or off-by-one row."*

| Tier | Method | Speed | JARVIS status |
|---|---|---|---|
| 1 | Accessibility tree (pywinauto/UIA) | ~5 ms | ✅ **has it** — `ui_perception.py` |
| 2 | Offline OCR — `PP-OCRv5_mobile` (Apache-2.0, 441K downloads) | ~300 ms | ⚠️ dark, needs wiring |
| 3 | UI grounding — `UI-TARS-2B-SFT` / `UI-TARS-1.5-7B-GGUF` (574K downloads, CPU-runnable) | ~1–3 s | ❌ absent |

**Action gating — non-negotiable.** Clicky *points*; JARVIS *clicks*. Pointing wrong costs confusion; clicking wrong modifies the wrong patient record.

> **Tier 1 → act. Tier 2 → act with verification. Tier 3 → do not act; ask.**

## 3.3 Document OCR

Off-the-shelf, permissive licences, all GPU-class → runs on the hospital box:
GLM-OCR (3.6M) · Unlimited-OCR (2.6M) · DeepSeek-OCR-2 · chandra-ocr-2 · dots.ocr

**Never use the hosted/cloud endpoints** — residency violation, re-breaks T3 the same way STT did.

**Required test before committing:** 20 real Indian clinical documents — printed discharge summaries, printed lab reports, handwritten prescriptions, mixed-script forms. Do not assume a model strong on clean PDFs handles a handwritten Hindi prescription.

## 3.4 Indic medical OCR — the unclaimed moat ⭐

**Empirically verified on HuggingFace, 2026-07-28:**

| Model | Downloads |
|---|---|
| `SHAON123/indicpage-ocr-tamil` | **16** |
| `VinitT/Indic-Ocr` | 9 |
| `SHAON123/indicpage-ocr-hindi` | **3** |
| `subhodipsaha/qwen2.5-3b-…-IndicOCR` | **0** |
| Best Indic *handwritten* (`sabaridsnfuji/Tamil_Offline_Handwritten_OCR`) | **96**, last touched 2024 |

PaddleOCR ships mobile recognition for Korean, Arabic, Latin, East Slavic, Greek — **and no Indic script.** Compare: GLM-OCR has **3.6 million** downloads.

The technology ontology called this CONTESTED. That is too generous. **It is unclaimed.**

**The recipe is already demonstrated** — Arabic handwritten OCR:
`sherif1313/Arabic-handwritten-OCR-4bit-Qwen2.5-VL-3B-v2` — **27,690 downloads.** Method: fine-tune Qwen2.5-VL-3B on handwriting → 4-bit quantise → ship GGUF for CPU. One person, non-Latin script, handwriting, real adoption.

**Corpus collection policy — two tracks, so dataset work is never blocked:**

- **Track A (start now, Stage 0.5):** non-patient documents only — blank forms, pharmacy labels, printed drug inserts, your own records, synthetic/anonymised samples, publicly available specimen forms. No consent question, no delay.
- **Track B (blocked, same gate as ambient recording):** real patient documents. Requires DPDP-compliant consent, from the patient rather than the clinician alone. Do not start Track B on assumptions.

The dataset — not the model — is the barrier. Nobody copies it by downloading weights.

## 3.5 Inference performance

**Tier 1 — cheap, certain, hours each:** `generate_stream()` wiring · model warm-up · task-aware token budgets.

**Tier 2 — measure first:** GPU config (verify hardware exists) · prefix/KV cache (**Ollama may already do this — test before building**) · context summarisation · response caching · real Fast/Accurate model tier selection (status box currently only *labels* whichever model loaded; there is no runtime choice).

**Killed on evidence — do not build:** runtime dynamic layer execution / confidence-based early exit. Wei et al. (arXiv 2603.23050) oracle experiments: **0.00% skip on Qwen2-7B, 0.10% on Qwen3-8B** at ≤5% accuracy loss *with perfect exit knowledge*. Suitability rises with scale and falls with instruction-tuning; JARVIS sits at the wrong end of both. Exit patterns are *"largely model-specific and only weakly influenced by the assigned workload"* — which specifically undercuts task-aware depth allocation. Revisit only at 20B+ dense on GPU.

**Also killed:** speculative decoding at app layer (inference-engine feature, needs runtime support not controlled here).

## 3.6 Command inference model

Local Qwen2.5, starting at 1.5B. Physician-facing label is **"Fast" / "Accurate"** — never model names or parameter counts. Currently the status box only labels; the real toggle is unbuilt.

## 3.7 Hybrid capability routing — resolves Q1 ⭐

> **Provenance note.** `08-jarvis-architecture-baseline.md` Q1 — *"Local-first/on-device, cloud, or hybrid?"* — is listed **ASSUMED and undecided**, flagged as a question that "changes everything." The corpus contains the question, not the answer. This section is that answer, decided 2026-07-28, extended 2026-07-28 to add explicit smart routing and user override — see §3.7b.

### The original decision — still the ceiling

**Route to a larger tier only for capabilities that structurally cannot run locally. Never for "same task, better model when connected," for the clinical path.**

**Rejected — connectivity-based quality routing for clinical data.** The same command returning different quality depending on network weather (good wifi at 9am, hospital dead zone at 2pm) is non-determinism in a clinical tool, and it breaks the honest-failure discipline (MOAT-001) — JARVIS could not truthfully tell a physician which tier answered. **This rejection stands.** §3.7b adds smart routing *underneath* this ceiling, not instead of it.

**Accepted — capability-based routing.** A statable, network-independent boundary: *"document parsing needs the hospital box."* True regardless of connectivity.

### The reframe that resolves the residency problem

**"Hybrid" means laptop ↔ hospital box over LAN — not laptop ↔ internet, for clinical data.**

The GPU box inside the firewall *is* the online tier for clinical work. This yields capability expansion with **zero residency exposure**, because nothing crosses the boundary DPDP governs. DEC-004 is satisfied by topology rather than by policy.

## 3.7b Two-part routing — deterministic gate + smart router *(added 2026-07-28)*

**The problem with "build a smart algorithm to decide local vs. cloud":** D1 exists precisely because a routing choice (Google STT vs. Vosk) was left to an implicit fallback heuristic rather than an explicit rule, and it silently settled on cloud-first in a file named `local_stt.py`. A learned or heuristic router choosing *whether clinical data leaves the machine* has the identical failure shape — sometimes defensible, sometimes not, and undetectable without a post-hoc log audit. **A fuzzy question ("where's the boundary between local and cloud use cases") does not require a fuzzy answer.** Whether clinical data left the machine on a given request is a fact, checkable after the fact — that part must stay deterministic even where everything downstream of it is smart.

**Design: two decisions, not one.**

1. **Data-class gate — deterministic, a lookup, never learned.** `IntentRouter`/`CommandRouter` already tag every request as clinical (OPD/patient-touching) or general (weather, search, casual) as part of existing classification — no new classifier needed. This tag sets the **ceiling**, not the choice:
   - `clinical` → ceiling is LAN (laptop or hospital box). Cloud is unreachable from this branch, full stop.
   - `general` → ceiling is internet.
2. **Capability/confidence router — smart, Conifer-shaped, operates only below the ceiling the gate already fixed.** Try local first; escalate to a larger *local-or-LAN* model on low confidence; escalate to cloud only if the gate already permitted it for this request. This is where Conifer's actual mechanism (try cheap, escalate on low confidence, hand-tuned kernels for local speed — see conifer.build) is genuinely worth adopting, and where §3.5's Tier-2 items (real Fast/Accurate model selection) plug in.

**Why the split, not one smart system:** the router being wrong costs a mediocre answer, recoverable by asking again. The gate being wrong costs patient data leaving the building, discovered only in an audit — the same shape of harm as D1, at clinical scale. One of those failure modes is fine to iterate on. The other is not allowed to be probabilistic.

### Explicit user override — a preference layer, not a bypass

A physician may explicitly ask for a specific tier ("use the smarter model," "stay local only"). This sits **above** the automatic router and is honored — for general requests only.

| Request class | User says "use cloud" | Behavior |
|---|---|---|
| General | Yes | Honored — no gate involved, cloud tier used |
| Clinical | Yes | **Refused, with an explanation** — e.g. *"I can't send that off this network — it's tied to patient data."* Never silently ignored (confusing), never silently obeyed (D1 again). |

The override changes the *default tier the router reaches for*; it never moves the data-class ceiling. If it could be talked past by request, it would be a suggestion, not a boundary, and DPDP does not accept suggestions.

**On "static knowledge" complaints specifically** — before routing a dissatisfied "that seems outdated" to a bigger cloud model, try the knowledge-retrieval chain already built for this exact complaint (Stage 0, SerpApi → Serper, §Stage 0 work items). Scoped search is cheaper, faster, and already logged/gated; reach for a bigger model only if search doesn't resolve it.

### Sequencing

| Stage | Work |
|---|---|
| **Stage 0** | `generate_stream()` · warm-up · task-aware token budgets. **These are not routing.** |
| **— measure here —** | Re-measure conversational latency after the above. |
| **Stage 1+** | Build the deterministic data-class gate first (cheap — reuses existing classification), then the capability/confidence router beneath it, then the override layer. |

**Rationale for the gate-before-router sequencing:** `generate_stream()` alone changes perceived latency from *"wait 30s, then hear everything"* to *"first word in under a second."* Warm-up removes the cold-load penalty. **Do not build routing to solve a problem a four-hour fix may already solve** — the anti-vertical-drift check (§4.6) applied to latency work itself. Once routing is warranted, build the safety-critical deterministic half before the smart half — reversing that order risks shipping the interesting part before the load-bearing part exists to constrain it.

## 3.8 Terminal identity — banner and orb

**Decision: the ASCII banner and orb are visible on every launch.**

`jarvis_orb.py` already separates `render_frame()` from `play()`, so this requires **no new code**:

| Context | Render | Cost |
|---|---|---|
| **Every launch** | single **static frame** above the status box | ~13 ms |
| **First-run onboarding** | full `play()` animation | irrelevant — one-time moment |

**Why static on every launch:** with import time at ~16s against a <3s target (D3), spending 1–2s animating on every launch is not defensible. This preserves the presence without the tax.

**Asset spec** — built, approved, awaiting wiring:
- Algorithmic orb-and-ring: solid shaded core inside a rotating ring, z-buffered so the ring correctly passes in front of and behind the core
- Adapted from the classic ASCII torus renderer with three fixes: **added the core sphere** (reference was orb-with-ring, not a bare torus), **resized to 28×12** with retuned shading and aspect correction, **replaced infinite `while True` with bounded `play(frames=N)`** that always returns — the original would have hung startup
- Plain ASCII (`.,-~:;=!*#$@`) — no UTF-8 console dependency
- ~13 ms/frame; 28×12 is the floor before detail collapses (24×10 tested, too cramped)

**Standing build decision:** any further frame work is **prototyped live in a real terminal, never specified blind.** Two hand-authored attempts failed — the first read as a face with a mouth, the second had inconsistent internal lines. Algorithmic generation succeeded because the geometry is computed, not guessed.

---

# PART 4 — DECISIONS, RISKS, MOATS

## 4.1 Open one-way decisions

| ID | Decision | Decide by | Cost of delay |
|---|---|---|---|
| **DEC-002** | Clinical audit trail — architect in vs retrofit | **Before Stage 0.5 line one** | Grows with every adapter; may block certification. **P0/10.00** |
| **DEC-004** | Data residency / extraction locality | Before any patient data | Under DPDP, moving data post-processing is a legal event, not a config change |
| **DEC-001** | Memory: vector-first vs temporal-graph-native | Before Stage 1 | 6–12 months at S2; effectively impossible at S3 under retention obligations |
| **DEC-005** | Adapter interface stability guarantee | Before any external SDK | Frozen by other people's code; breaking it forks the ecosystem |
| **DEC-003** | Pricing — differentiator inside or outside evaluation tier | Before first paid customer | *(costly, not one-way)* |

## 4.2 Unknown unknowns

| ID | Question | Priority |
|---|---|---|
| **UNK-001** | Is persistent memory the *wrong* architecture for clinical work? The EMR is authoritative; a memory layer duplicating it inherits staleness **and** consent obligations for data it needn't hold. May mean: own L4, deliberately don't own L3. | HIGH |
| **UNK-002** | If DPDP enforcement matures to GDPR levels, does LLM-extraction memory become legally unusable for clinical data regardless of residency? | HIGH |
| **UNK-003** | MCP consolidated agent-to-tool in ~16 months and erased bespoke integration advantage. Which layer is next — and is JARVIS building differentiation in it right now? | HIGH |
| **UNK-004** | Is 107 more dossier runs actually executable throughput? A research plan that can't execute leaves synthesis permanently gate-locked. | **CRITICAL** |
| **UNK-005** | Who is the buyer — clinic, hospital chain, diagnostic lab, or insurer? Materially affects every remaining dossier. | HIGH |
| **UNK-03′** | **Liability void** — if JARVIS clicks "Discharge" and the patient dies, who carries malpractice liability? | **CRITICAL — gates Stage 1a** |
| **UNK-01′** | EMR vendors actively detect and block headless RPA. A UI patch breaks the adapter. | Gates visual-automation strategy |
| **UNK-02′** | Two-party consent laws may require the *patient* to authorise ambient mode on every room entry. | Gates Stage 1b |

## 4.3 Moat register

| ID | Moat | Now → Target | Compounds | Copy time |
|---|---|---|---|---|
| MOAT-001 | Honest-failure discipline | 2 → 4 | ✅ yes | 12 mo |
| MOAT-002 | Approval gates + rollback | 3 → 4 | ❌ no — durable property, not growing | 9 mo |
| MOAT-003 | **Clinical compliance posture** | **0 → 5** | ✅ yes | **24 mo** |
| MOAT-004 | **Clinical workflow encoding** | **0 → 5** | ✅ yes | **30 mo** |
| MOAT-005 | **Indic medical OCR corpus** *(new)* | **0 → 5** | ✅ yes | unbounded — data, not weights |

MOAT-003 is *"the highest-leverage moat available, and the one most damaged by delay."* Both 003 and 004 sit at zero and depend on physician contact — exactly the validation gap Stage 0.5 closes.

## 4.4 Failure patterns to avoid

- **FAIL-003** — differentiator priced above the evaluation threshold; evaluation stalls before merit is judged. *Guard:* DEC-003.
- **FAIL-004** — rented moat mistaken for owned. *Guard:* `rented_or_owned` required on every moat entry.
- **FAIL-005** — compliance deferred until market entry is blocked. *Guard:* DEC-002, architect in now.
- **Olive AI** — horizontal scope creep, "AI workforce for healthcare," dismantled and sold for parts.
- **Forward Health** — beautiful infrastructure patients didn't want. **This is the pattern JARVIS is currently exposed to.**
- **Pear Therapeutics** — FDA clearance ≠ business model; no reimbursement path.

## 4.4b Deferred and designed-not-built *(restored from v1.0)*

Items with real prior decisions attached. None are cancelled; all are sequenced behind Stage 0.5.

| Item | State | Gate / note |
|---|---|---|
| **Phase 3b — sub-agent spawning** | DESIGNED | Parallel execution of independent, already-resolved intents. Each sub-agent still passes through the *unchanged* ResolutionGate → CommandRouter → adapter pipeline. Failure isolation required: one sub-agent failing must not mask or crash others. |
| **Phase 3c — NL scheduling** | DESIGNED | *"Remind me to check labs at 3pm."* Must produce an **inspectable** schedule, execute through the existing pipeline at fire-time (same gates), and be listable/cancellable. A schedule that can't be seen or undone isn't trustworthy on a clinical machine. |
| **Phase 3d — skill-writing proposals** | DESIGNED | JARVIS drafts a proposal (what it does, what access it needs, example I/O) and surfaces it. **Nothing runs until explicitly approved.** Non-negotiable, not a phase-1 simplification — this was walked back from full autonomy deliberately. Approved skills become versioned, reviewable code via the existing draft→review→merge workflow. |
| **Appointment / schedule query** | NOT STARTED | *"What's my next appointment," "push this patient to 3pm."* Bounded, tied to the OPD queue — not general calendar automation. Rides on 3c's mechanism. |
| **Qwen3-TTS evaluation** | GATED | Real latency measurement on target hardware **before** any commitment to replace pyttsx3. Qwen3-TTS (0.6B/1.7B, Apache-2.0, real emotion/tone control) is materially heavier than the current fixed-inflection TTS. A wrong emotional read is more jarring than a flat voice. Measure, don't assume. |
| **Text-emotion detection** | BUILT, UNWIRED | `j-hartmann/emotion-english-distilroberta-base`. Boundary-tested: may **only** influence TTS delivery, never response content or decision logic — enforced by a subprocess-level transitive-import test mirroring `test_session_memory_boundary.py`. Trained on Twitter/Reddit text; accuracy on transcribed clinical speech is unverified. Blocked on the TTS decision above. |
| **RHINAL MCP integration** | `rhinal_capture` WIRED (commit `80ae8cb`); 13 remaining tools verified live but not wired | Live `tools/list` against the real deployed server returned 14 tools — its own README claimed 4; source and live protocol agreed with each other, not with the doc. `rhinal_capture` saves unconditionally regardless of `vaultWorthy` (informational, not a save/skip gate — read from source, not inferred from the field name). Wiring the other 13 is a distinct, larger follow-up; `rhinal_attach_file` specifically needs a real non-identifying test file plus explicit approval before it can be attempted — see execution log. |
| **`# --- ADDITION` block sweep** | UNVERIFIED | Original Phase 3 cleanup scope included sweeping for undocumented `# --- ADDITION` blocks beyond those already found. Unclear from history whether ever completed. The Level-6 Engine Hook question is now resolved (it became the completed Level6 engine); the general sweep is not confirmed. |
| **`ODAVLoop` gate-outcome handling** | OPEN (D7) | Real gap, verified unreachable from the live conversation loop — `IntentRouter.classify()` only emits `handler="action"` for `GateOutcome.RESOLVED`. Contained, not physician-facing. Bundle into cleanup. |
| **`co_brain.py` retirement** | OPEN (D8) | Legacy system #1 (`input.txt` polling). Confirm nothing depends on it, then remove rather than leaving four systems as three. |

## 4.5 Never build

Foundation models · inference runtimes · browser engines · EMR replacement · generic chat interfaces · cloud STT pipelines · further Level6/L9 self-coding · runtime early-exit · vector-retrieval infrastructure · competing on STT/TTS quality.

## 4.6 The anti-vertical-drift check

At every planning point, one question:

> **Does this move a physician closer to using JARVIS, or make JARVIS more impressive to an engineer?**

Both are legitimate. But the honest count over the last cycle was heavily the second. **Stage discipline defends against expanding too fast; this defends against deepening in the wrong place.** v1.0 had the first and lacked the second — that omission is what all three external analyses independently found.

---

# PART 5 — WHAT THE FINAL VERSION LOOKS LIKE

## 5.0 Framing architecture — Cognitive Operating System

> **The organising claim:** JARVIS's brain is not a model. A model is one component. The system around the model is the moat.

```
        User · voice / screen / documents
                      │
        ┌─────────────▼─────────────┐
        │ PERCEPTION                │  L5 — partial
        │ STT · OCR · VLM · UI      │  OCR dark, VLM absent
        └─────────────┬─────────────┘
                      ▼
        ┌───────────────────────────┐
        │ WORLD MODEL               │  🔴 THE GAP
        │ "what is happening?"      │  = patient-journey event graph
        │ operational state + prov. │    (Stage 2, emitted from 0.5)
        └─────────────┬─────────────┘
                      ▼
        ┌───────────────────────────┐
        │ MEMORY                    │  L3 — storage built,
        │ context · timeline        │  defensible half absent
        │ (RHINAL via MCP — sep.    │
        │  product, note capture)   │
        └─────────────┬─────────────┘
                      ▼
        ┌───────────────────────────┐
        │ PLANNER                   │  L4 — STRONGEST AREA
        │ goals → tasks             │  IntentRouter · CommandRouter
        │ owns the workflow         │  ResolutionGate · ODAVLoop
        └─────────────┬─────────────┘
                      ▼
        ┌───────────────────────────┐
        │ REASONER — LLM router     │  L2 — §3.7 decided
        │ assists; does not decide  │  capability-tier routing
        └─────────────┬─────────────┘
                      ▼
        ┌───────────────────────────┐
        │ VALIDATOR                 │  GOVERN — VERIFIED ⭐
        │ safety · confidence       │  approval gates · rollback ·
        │                           │  honest failure · boundaries
        └─────────────┬─────────────┘
                      ▼
        ┌───────────────────────────┐
        │ ACTION ENGINE             │  L6 — VERIFIED
        │ browser · desktop · API   │  12 adapters, focus-safe
        └───────────────────────────┘
```

**Five of seven boxes already exist**, two of them (Planner, Validator) as the strongest parts of the codebase. This is the most encouraging finding in the blueprint: the architecture is closer to target than the empty L10/L11 layers suggest.

### The control-flow principle

The planner **owns** the workflow; the LLM **assists**. Never the inverse.

```
goal → planner proposes candidate actions
     → LLM evaluates / disambiguates
     → validator checks
     → executor runs
```

Already how JARVIS works: `IntentRouter` → `ResolutionGate` → `CommandRouter` → adapter, with the LLM as terminal fallback rather than orchestrator. The proposition confirms the existing design rather than replacing it.

### The World Model — resolved, not new work

The gap was real but the fix was already decided under another name.

| Question the World Model must answer | Where it lives |
|---|---|
| Who exists? (doctor, patient, nurse) | event graph entities |
| What exists? (appointments, reports, beds) | event graph entities |
| What is happening? (waiting, admitted, discharged) | event graph state |
| Why? (goal, diagnosis, intent) | event provenance |
| How certain is each fact? | `confidence` field |
| When was it last updated? | `time` field |
| What evidence supports it? | `source` field |

That is precisely the Stage 2 event-graph specification, emitted from Stage 0.5 onward. **Naming it a world model changes nothing structural — it clarifies purpose and makes the gap visible in the layer map, where it was previously invisible.**

### RHINAL's scope — unchanged

RHINAL remains a **separate product**, reached over MCP, handling note capture and structuring. It is **not** JARVIS's world model and does not become the clinical source of truth.

**Why this boundary matters:** in a hospital the EMR is the legal system of record. A layer that claimed to be "the source of truth" while diverging from the EMR would create a clinical safety question, a legal one, and a consent one simultaneously — reopening **UNK-001** and **UNK-002**. The split holds instead:

- **Event graph** — source of truth for *operational* state (who's waiting, what's blocked, who owns the next action)
- **EMR** — source of truth for *clinical* facts (diagnosis, medications, results)
- The event graph holds **references and provenance** to clinical facts, never copies

This is Plan C's principle #1 restated: *system of action, not initial system of record.*

### Naming — two different Decision Engines

Distinct concepts; do not conflate in documents:

| Name | Belongs to | Answers |
|---|---|---|
| **Research Decision Engine** | Dissection | *Given all evidence, what should JARVIS build next, refuse to build, and why?* |
| **Clinical Decision Engine** | JARVIS | *"Admit patient" → bed available? ICU? billing notified? nurse informed?* |

The second is the proprietary asset. The LLM understands the language; **the engine makes the decisions.**

## 5.1 The physician's experience

A clinician says *"next patient"* between consultations. JARVIS — running entirely on the machine already sitting on the desk, no cloud, no GPU — advances the queue, pulls the encounter state, drafts the note, flags the missing lab, and says what's blocking discharge. Nothing it does is silent; everything it does is reversible and logged. When it isn't sure, it says so rather than guessing.

## 5.2 The system

```
        ┌──────────────────────────────────────────────────┐
        │  PHYSICIAN LAPTOP — CPU only, offline-capable    │
        │                                                  │
        │  wake word (Vosk, local, grammar-locked)         │
        │        ↓                                         │
        │  local STT — nothing leaves the machine          │
        │        ↓                                         │
        │  IntentRouter → ResolutionGate → honest failure  │
        │        ↓                                         │
        │  Tier1 accessibility → Tier2 OCR → Tier3 UI-TARS │
        │  (act) ─────────── (act+verify) ──── (ask first) │
        │        ↓                                         │
        │  OPD queue · clinical actions · audit emission   │
        └────────────────────┬─────────────────────────────┘
                             │  provenance-stamped events
                             ▼
        ┌──────────────────────────────────────────────────┐
        │  HOSPITAL BOX — inside the firewall              │
        │                                                  │
        │  patient-journey event graph (source/time/actor/ │
        │      confidence/consent on every fact)           │
        │        ↓                                         │
        │  task & state engine — owner, next action, due,  │
        │      evidence, escalation as first-class objects │
        │        ↓                                         │
        │  role worklists: nurse · billing · pharmacy ·    │
        │      front desk · housekeeping · payer liaison   │
        │        ↓                                         │
        │  document intelligence (GPU) — Indic OCR,        │
        │      claim readiness, evidence extraction        │
        │        ↓                                         │
        │  ABDM/FHIR adapter ──→ ~250 certified HMIS       │
        └──────────────────────────────────────────────────┘
```

## 5.3 What is defensible at the end

Not the LLM. Not the adapters. Not the voice.

1. **The event graph** — local operational truth, used daily across departments, with provenance
2. **Workflow lock-in** — ownership and escalation embedded in every discharge; replacing it disrupts coordination habits, not a dashboard
3. **Clinical compliance posture** — slow, expensive, boring, 24 months to copy
4. **The Indic medical document corpus** — the one asset that cannot be downloaded
5. **Honest failure** — in a clinical setting this isn't a feature, it's the licence to operate

## 5.4 What it is never

Not an EMR. Not a diagnostic system. Not a chatbot. Not a general agent framework. Not a cloud service.

---

# PART 6 — IMMEDIATE NEXT ACTIONS

1. ~~**Delete the cloud STT path.**~~ **Done (S0-E8, commit `a3c91d06`).** D1 resolved, T3 flipped.
2. ~~**Fix conversational latency — reported as bad in real use.**~~ **Done for the three cheap items (S0-E9, commit `bc83d7ec`).** Streaming, warm-up, and task-aware token budgets landed; real end-to-end measurement: 34.04s → 9.87s to first spoken word. Import time (D3, ~16s) and GPU config are separate, still-open items — this phase only closed the three named here.
3. **Decide DEC-002** (audit trail) before Stage 0.5 begins. Architect in.
4. ~~Close the audit; verify `31939c8`.~~ **Done (S0-E1, S0-E2) — see Stage 0 table.**
5. Wire the orb + banner as a static frame on every launch (§3.8) — no new code required. **Frozen during Stage 0 (see Stage 0's freeze list) — do not start yet.**
6. Start Track A of the Indic corpus — costs nothing, starts the only unclaimed moat.
7. Answer **UNK-005** (who is the buyer) — it reweights everything downstream.
8. Fix the default branch (D9) so the repo's public face isn't 30 commits stale.

---

## Reading status of the reference corpus

**`jarvis-model/`** *(purpose confirmed with Ayan)* — the machine-readable model of JARVIS-the-product that `tools/route.py` consumes to emit the engineering roadmap. `stage-model.yaml` (stages + exit criteria), `routing-rules.yaml`, `subsystem-map.yaml`. The roadmap in `design-intelligence/ROADMAP.md` is **generated, not hand-written**, and regenerates on every `evolve.py` run.

**Repository separation — do not violate.** `Dissection` = research operating system (registries, evidence, strategic intelligence). `JARVIS` = product (consumes those insights). The registries do **not** move into the JARVIS codebase. Mixing them blurs evidence-gathering and product implementation — the same confusion already avoided between JARVIS and Ovexis.

**Corpus map:**
- `reports/` — **the true gem.** Healthcare-operations pain points, the problem space JARVIS exists for. Read in full where possible; at minimum `All research reports analyzed/reconnaissance/`.
- `All research report/` — competitor dissection logs; determines architecture.
- `All research report/jarvis_p2/` — snapshot of the product as it stands.
- `All research report/ovexis/` — **misnamed**; content is JARVIS, not Ovexis. Originally the Ovexis Intelligence Synthesis Engine, evolved through competitive intelligence → pattern discovery → knowledge OS → strategic decision engine. Competitors are now *inputs*, not the objective.
- `Point i can research on in future/` — 85 disease-level unsolved-problem reports; product opportunity research.

**Read in full:** `jarvis-ci` (7,544 lines — constitution, phase-R dissection, jarvis-model, all registries, design-intelligence) · PHASE0 discovery report (449 platforms) · JARVIS due-diligence assessment · reconnaissance synthesis over all 287 reports · issue #1 (20 workspace exports, already extracted in-repo) · Clicky · Unlimited-OCR · HuggingFace landscape searches.

**Not yet read:** 132 daily market-intelligence reports · 117 founder blueprints · 18 of 20 company dossiers in depth · Mem0 dossier full text · most phase RUN-PROMPTs · 85 disease-limitation reports.

*Nothing in the unread material is expected to change Parts 1–4, but it may sharpen Stage 2 and the opportunity ranking. Corpus-quality caveats and the competitor-research misdirection finding are recorded in the execution log, not yet applied here — see "Findings that change strategy."*
