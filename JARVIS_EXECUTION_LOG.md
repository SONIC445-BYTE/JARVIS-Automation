# JARVIS Execution Log

**Companion to `JARVIS_BLUEPRINT.md`.** The blueprint holds *decisions and direction*. This holds *what was actually done, what was found, and how each claim was verified.*

**Why this file exists.** The blueprint was a summary. An agent looping on it alone could not tell which items were genuinely verified, what evidence backed each claim, or which findings had already been investigated and resolved. That gap caused real problems — a completed fix was reported done while sitting unpushed in a working tree, and stale `OPEN` rows persisted for work that was independently confirmed complete. This file closes that gap.

**Custody rule — read this first.** This file and `JARVIS_BLUEPRINT.md` must live **inside the JARVIS-Automation repo, tracked in git.** They previously lived only in a chat-side outputs directory, which meant the reviewing agent and the implementing agent each edited a private copy and neither could see the other's. Edits appeared to land and were simultaneously absent. **If these files are not tracked in the repo, fix that before doing anything else** — commit them, and treat them as versioned artifacts exactly like code. Never edit a copy outside version control.

---

## Verification standard (applies to every entry below)

An item is only ✅ when confirmed from the **actual source of truth**, not from a report about it:

| Claim type | Acceptable evidence |
|---|---|
| Code changed | `git show origin/<branch>:<path>` — the pushed git object, not the working tree |
| Commit exists | `git log origin/<branch> --oneline` shows the SHA |
| Test passes | Suite run independently by the reviewer, not the author's report of it |
| Live service works | A real protocol call against the real endpoint, output quoted |
| Failure is "pre-existing" | `git log --follow` / `git blame` on the failing file — **a count carried forward from a prior report is not evidence** |

**Three real failures this project has caught with this standard:**

1. **The unpushed commit (S0-E8).** Work was reported complete, tests passed locally, the diff was correct — and nothing was ever committed. Caught by fetching the remote and grepping the git object directly. *Rule that came from it: `git log origin/… --oneline` must show the commit before reporting done. Local test success is not completion.*
2. **The unnamed baseline (S0-E1).** "3 pre-existing failures" was carried forward across several reports as a number, not a verified fact. When actually checked, there were 4, and all were dead-since-initial-commit rather than regressions. *Rule that came from it: name every failure individually and prove its provenance with git history.*
3. **The divergent-copy incident (this reconciliation, 2026-07-29).** While performing the custody check this file itself mandates, two independently-edited copies of `JARVIS_BLUEPRINT.md` were found sitting in an untracked `Downloads/` directory — one produced by directly editing the file in-session (which had applied the T3 flip, D1 closure, D11–D13, and layer-map updates), the other a separately-authored v2.4 (better Stage-0 table structure, the custody banner, this execution log's own genesis) that had **not** picked up the first copy's layer-map updates or its D13 finding, and had itself introduced one internal inconsistency — D1 marked resolved in §1.6 while §1.5's T3 row was still left at CONTRADICTED. Neither copy was tracked in git, so neither agent could see the other's edits: **exactly the failure this custody rule exists to prevent, caught occurring in real time rather than described hypothetically.** *Rule that came from it: reconciled explicitly by diffing both copies rather than picking one and discarding the other; both files now committed inside the JARVIS-Automation repo, which is the actual fix — stating the rule again would not have prevented this, only version control does.*

---

## Closed items — with evidence

### S0-E8 — Local STT, cloud path deleted 🔴 *thesis-critical*
**Status: ✅ CLOSED.** Commit `a3c91d06` on `phase-2-adapter-wiring`.

**The defect (was D1).** `WakeService/local_stt.py` → `LocalSTT.listen_once()` called `_fallback_listen()` **first**, which invoked `speech_recognition`'s `recognize_google()` — a network call to Google's cloud STT. Vosk, the local recognizer, was the *fallback*. The exception handler around the Vosk path also fell back to the same cloud call. Two entry points, both cloud-first.

The naming actively concealed it: file named `local_stt.py`, method named `_fallback_listen`, docstring claiming *"Runs locally, no API calls."* Every physician utterance left the machine before anything local was tried.

**Why it mattered beyond a bug.** T3 (local-first/privacy differentiates) was the standing product thesis. This made T3 **contradicted, not merely weak** — the product's core claim was false in its most sensitive data path. It was also a live instance of the exact failure loop JARVIS exists to end (see Shadow-AI loop, §Findings below).

**Fix.** Both entry points deleted. `listen_once()` now only reaches Vosk. Dead scaffolding removed (`result_text`, unused `result_event`, stale placeholder comment, stale "using fallback" log line).

**Verification (reviewer-side, independent).**
- `git log origin/phase-2-adapter-wiring --oneline` → `a3c91d06` present
- `git show origin/phase-2-adapter-wiring:WakeService/local_stt.py | grep -n "recognize_google\|_fallback_listen\|speech_recognition"` → **exit code 1, zero matches**
- `listen_once()` body inspected in the remote blob: Vosk only, docstring corrected
- Regression test `tests/test_local_stt_no_cloud_path.py` read directly — static check reads the real file (not a mock), plus a dynamic check that forcing Vosk to fail still never imports `speech_recognition` into `sys.modules`. Matches the existing coupling-test convention (`test_nethytech_listen_import_coupling.py`).

**Author-side additional verification.** Ran `LocalSTT().listen_once()` live against a real mic and the downloaded Vosk model; real transcription returned, no cloud call in path.

**Consequence: T3 moves from CONTRADICTED → TRUE.** Applied in blueprint §1.5 as of this reconciliation (2026-07-29) — a prior copy of the blueprint had closed D1 in §1.6 without also flipping T3 in §1.5, an internal inconsistency caught and fixed during the divergence reconciliation (see incident #3 above).

**Not in scope, unchanged:** `test_sr.py` at repo root still imports `speech_recognition` directly — documented in `pyproject.toml` as one of ~10 ad-hoc debug scripts outside the real test surface. Left alone deliberately.

---

### S0-E2 — Desktop adapter launch-fallback verified
**Status: ✅ CLOSED.** Commit `31939c8`.

**The defect.** `whatsapp_desktop` and `telegram_desktop` adapters' `open_app()` could not actually launch the application when it wasn't already running — only focus it if already open.

**Fix, and why its design is notable.** The WhatsApp path deliberately **does not hardcode a guessed Store package ID.** Store app identifiers vary per install, so it queries `Get-AppxPackage` live for the real `PackageFamilyName`. If the query returns nothing, `pfn` is `None` → `success=False`, reported honestly. No crash, no false success claim. This is the honest-failure discipline applied correctly to an unknowable-in-advance value.

**Verification (reviewer-side, independent).**
- Full diff of `31939c8` read directly for both adapter files
- 4 new regression tests confirmed present and passing under an independent suite run — not the author's reported count
- `FakeBackend` fixture confirmed *extended* (new `open_command_result` param) rather than a new disconnected mock being introduced alongside it
- **Real, unmocked `open_app()` run for both adapters against the actual `GUIBackend`** (not `FakeBackend`) — not just a diff read. Telegram: `Get-Process` confirmed a real, running `Telegram.exe` at `%APPDATA%\Telegram Desktop\Telegram.exe`, the exact path the fix's fallback targets — `activate_window()` correctly found and activated it. WhatsApp: `Get-AppxPackage` confirmed **no real WhatsApp Desktop UWP package installed on this machine** — yet `open_app()` still returned `True`.

**Finding produced by this work — `AvailabilityChecker`/adapter false positive on PWA shortcuts (D12).** Root-caused, not just observed: `GUIBackend.activate_window()` uses `pyautogui.getWindowsWithTitle()`, which does **substring** matching. `WhatsappDesktopAdapter.WINDOW_TITLE = "WhatsApp"` matches a real Chrome window titled *"WhatsApp Web"* — confirmed via `Get-Process` that the matched window belongs to `chrome.exe`, not any native app. `open_app()` returns `True` today by activating that browser window; it never reaches the launch-fallback path `31939c8` added, and never surfaces that the native app doesn't exist. Telegram is unaffected by this specific bug — its one matching window was independently confirmed (via the same `Get-Process` path check) to be the real app, not a PWA. This sharpens and confirms the accuracy defect `31939c8`'s own commit message first flagged for `AvailabilityChecker`'s installed-check — the same substring-match weakness affects the adapter's own `open_app()` success signal directly, not just the upstream gate. Logged as **D12** in the blueprint.

---

### S0-E1 — 3-engine + installed-app audit formally closed
**Status: ✅ CLOSED**, with findings logged rather than fixed.

Perpetual "in progress" was hiding real state. Closed with an explicit per-engine verdict, plus every suite failure named individually and provenance-checked.

**Coding engine — verified live, resolved.** `GeneratorHelper.generate_code()` used to check `hasattr(self.llm, 'generate')`/`'call_llm'` against `LLMAdapter`, which only ever exposed `.suggest_code()`/`.plan_refactor()`/`.verify_safety()` — the check never passed, so generation always fell through to a hardcoded stub (`print('Hello World')`) regardless of task or Ollama's availability. Fixed (adds `LLMAdapter.generate_raw()`, a genuine passthrough). Re-verified live during close-out: two genuinely different tasks (prime check, linked-list reversal) produced two genuinely different, correct implementations — not the stub. Level6 (`Level6Coordinator`) — previously planning-only with explicit TODOs for sandbox execution/testing/verification, self-documented "proof of concept" — is now complete through all 4 build phases; `feature_flags/level6_engine.yaml` shows `enabled: true`; `AgentCore/level6/` suite run live: **27 passed.**

**Conversational layer — partially verified, one finding unfixed (D13).** Multi-turn context retention confirmed working (real 3-turn Ollama conversation, correct recall). But `IntentRouter.classify()` misroutes informational "search for X" phrasings to `handler="action"` instead of `"llm"` — e.g. `"search for the definition of recursion and explain it"`, `"search for python tutorials"`. First found during the interim mid-session audit report, **reconfirmed live against the current `classify()` at close-out — still unfixed.** Unlike D11, this is a live-path bug, not dead scaffolding. Logged as **D13**, not fixed — out of S0-E1's declared scope (audit, not a bugfix pass).

**Automation/action engine — partially verified, rest named as genuinely open.** SessionMemory cross-process persistence live-verified: wrote a preference + session record in one Python process, read both back correctly in a fully separate process invocation. Resolution gate's coverage is inherited from Phase 2c.6's earlier 5-branch live test, not independently re-run in this pass. **Not done, named explicitly rather than folded in:** a real WhatsApp Web/Telegram Web block-and-resume cycle, a wake-word-to-conversation-loop live run, and a live re-run of onboarding's first-run walkthrough. None of these were "cheap" to close blind — the first needs an actual message-send (requires explicit go-ahead), the others need extended live interaction.

**Installed-app coverage — has a real, current result, not "still blocked."** The 160-folder cross-reference happened earlier at Phase 2b step 4 (`docs/adapter_audit.md`): 3 folders class-(a) real, 8 class-(b) real-but-incomplete, 149 class-(c) fabricated/non-functional (deliberately never wired). Of the 11 (a)+(b) plus WhatsApp Web/Telegram Web from Phase 2g, **14 platforms are wired.** Live on-demand rescan run during close-out: **7 of 14 currently detected as available**, no new apps found.

**Full suite at close: 400 passed, 4 failed, 134s.** All 4 failures investigated individually via `git log --follow`:

| Failing test | Actual cause | Provenance |
|---|---|---|
| `code_engine/tests/test_integration.py::test_routing` | `setUp()` does `self.engine.policy.config["enabled"]=True`; `CodeEngine` has **no `policy` attribute** — sets `self.config` (plain dict from feature-flag YAML) | Pinned to initial commit `dbef62f8`, never modified |
| `code_engine/tests/test_integration.py::test_tier2_flow` | Same `setUp()` failure | Same |
| `code_engine/tests/test_basic_write.py::test_auto_write` | `PermissionError` — `engine.py` returns `target_dir` (a directory) as `file_path`; test tries to `open()` a directory | Same |
| `mode_manager/tests/test_mode_engine.py::test_audit_log_created` | Asserts log contains `"hmac_signature"`; actual key written is `"sig"` | Same |

**Correction to the reviewer's own hypothesis, worth recording.** The reviewer proposed these were regressions from an earlier refactor. Wrong. `git log --follow` shows both `engine.py` and `test_integration.py` have **exactly one commit each — the initial commit.** `CodeEngine` never had a `.policy` attribute at any point in this repository's history. Both test bodies are literally `pass` with real assertions commented out. **This is dead scaffolding, broken since day one, not a regression anyone introduced.**

This distinction matters: "regression" implies something to revert; "dead since inception" implies scaffolding to delete or rewrite. Different fix, different urgency.

Confirmed this is the same baseline `31939c8`'s own commit message cites — 374 passed then vs 400 now, suite grew, failure count did not. **Logged as D11, not fixed** — audit close-out was the scope, a bugfix pass was not. Trivial-to-fix and in-scope are different questions.

---

### RHINAL MCP integration — `rhinal_capture` wired, 13/14 tools verified
**Status: ✅ CLOSED for this slice.** Commit `80ae8cb`.

**Context.** RHINAL is a separate product (note capture/structuring) reached by JARVIS over MCP as a **client**. It is deliberately *not* JARVIS's memory or world model — that boundary was considered and rejected to preserve the local-first constraint and avoid duplicating the EMR as source of truth (see UNK-001).

**Live `tools/list` returned 14 tools:** `rhinal_capture`, `rhinal_recall`, `rhinal_ask_vault`, `rhinal_classify_worthiness`, `rhinal_decision_log`, `rhinal_idea_to_spec`, `rhinal_confront`, `rhinal_tag_prediction`, `rhinal_resolve_prediction`, `rhinal_get_calibration_score`, `rhinal_start_case`, `rhinal_get_case_graph`, `rhinal_check_contradiction`, `rhinal_attach_file`.

Obtained by building RHINAL from source and spawning a real subprocess with a real key — an actual protocol response, not a description.

**Schema drift found — and this is why live verification was required.** RHINAL's own `mcp-server/README.md` documents *"Tools (Phase 1): 4 tools."* Its actual `index.ts` registers **14**. Source and live protocol agreed exactly; the *README* had drifted from its own code. A same-repo doc contradicting its own source is precisely the failure mode that makes "verify against the live interface, never the documentation" non-negotiable.

**Bug caught by reading source rather than inferring from naming.** `rhinal_capture` **saves unconditionally** once it completes — `vaultWorthy`/`worthinessReason` are *informational*, not a save/skip gate. The first client draft would have reported every borderline-but-genuinely-saved capture as a failure. Caught by reading `tools.ts` closely.

> **Standing rule from this (second occurrence of the pattern).** A field's name does not define its behavior. The `GeneratorHelper`/`LLMAdapter` mismatch was the same shape: `hasattr` checks against methods assumed from naming, never verified to exist. **Read the source; never infer contract from identifier names.**

**Built, incrementally scoped:** `rhinal_capture` only, of 14 confirmed-live tools — matching Phase 2g's browser-adapter discipline. `AgentCore/rhinal_mcp_client.py` (thin sync wrapper over the official MCP SDK), a new `IntentRouter` pattern branch for natural phrasings ("remember that…", "capture this thought:…"), and a `jarvis.py` dispatch branch shaped like the existing `code_engine` handler. 20 new tests.

**Live end-to-end confirmed** through the real conversation loop — real `PersistentWakeService`, real `IntentRouter`, real subprocess spawn, real MCP handshake, real tool call against the deployed backend, with only mic/TTS hardware stubbed:

```
[Convo] User: 'remember that the JARVIS RHINAL MCP integration happy-path test succeeded…'
[Convo] Intent: action → rhinal_capture
[Convo] JARVIS: 'Saved that to your Rhinal vault.'
```

Config required: `RHINAL_PROVIDER=groq`, `RHINAL_MODEL_ID=llama-3.1-8b-instant`. The account behind the key is not a trial account, so an explicit model/provider is mandatory; every cloud provider in RHINAL's `registry.ts` is BYOK, and `ollama` would need reachability from the deployed Vercel backend rather than the local machine. **This was correctly escalated rather than guessed** — a wrong value writes to a real vault.

**Remaining 13 tools: verified-working via real live calls, not wired.**
- 12 confirmed working through real calls, all writes using clearly-labeled test data or the agent's own earlier test records — never real user notes/cases
- `rhinal_resolve_prediction` confirmed a genuine backend mutation (calibration score moved 2→3 predictions)
- `rhinal_confront` and `rhinal_check_contradiction` were flagged as write-risks, then cleared by **reading source first** (single POST, no write path, no `saved`/`record` fields in return shape) before calling
- `rhinal_attach_file` — **correctly NOT attempted.** Unambiguous write to a real Notion page, and its own tool description requires a genuine face-detection result or real PDF/DOCX for server-side scanning. Fabricating a `scanResult` would violate the tool's own safety contract. No dry-run path exists in the schema. Classified **not-safely-testable-without-real-data**. To close: a genuinely non-identifying real test file plus explicit approval.

**Note on that judgment**, worth preserving: the distinction drawn was not merely "this writes, be careful" but "this cannot be *honestly* tested without real material." Fabricating the input would defeat the safety property the tool exists to enforce. That is a sharper read than a generic side-effect check.

**Wiring the other 13 is a distinct, larger follow-up** — 13× the scope of `rhinal_capture`'s own integration. Verification ≠ wiring. When scoped, use the now-known risk classes: read-only tools (`rhinal_recall`, `rhinal_get_case_graph`, `rhinal_classify_worthiness`) can be wired more freely than write-capable ones (`rhinal_start_case`, `rhinal_decision_log`), and `rhinal_attach_file` needs its own treatment.

---

### S0-E3 — Tiered knowledge-retrieval provider chain
**Status: ✅ CLOSED.** Commit `20ce0a88` on `phase-2-adapter-wiring`.

**Starting state, checked before building (not assumed).** `AgentCore/knowledge/` had zero SerpApi or Serper integration — no package in `requirements.txt`, no env var references anywhere. The only working discovery path was `serp_fetcher.py`'s Selenium-driven DuckDuckGo scrape, called directly by `discovery_manager.discover_sources()`. This is "browser-automation" only, with no API tier, no failover, no quota visibility, and no narration hook — confirmed by reading the actual code, not inferred from the blueprint's description of what should exist.

**Prerequisite check, escalated rather than guessed past.** Building a real SerpApi/Serper integration needs real credentials to verify against — none existed in the repo or environment. Asked before building further; the project owner supplied a real, working SerpApi key (free tier, 250 searches/month) for this phase. No Serper key was available. **Built and live-verified the SerpApi tier; built the Serper tier structurally against its published API contract, explicitly flagged as not live-verified** — the key itself is never written to any file in this repo, read only from `SERPAPI_KEY`/`SERPER_KEY` at call time, same pattern as `RHINAL_API_KEY`.

**Correction to the original ask — worth stating plainly, not silently reworded.** The blueprint's work-item text said "real quota tracking from response headers." Checked live against the real SerpApi endpoint before building anything on top of that assumption: **the search endpoint's response headers carry no quota/rate-limit fields at all.** Real quota lives at a separate `https://serpapi.com/account.json` endpoint (`plan_searches_left`, `total_searches_left`, `this_month_usage`, etc.), confirmed with a real live call. `get_quota()` in `serpapi_fetcher.py` hits that endpoint instead — a different implementation than the one line of blueprint text specified, because the specified mechanism doesn't exist on the real interface. Same discipline as the RHINAL README-vs-code and `GeneratorHelper`/`LLMAdapter` findings: verify against the live interface, not the documented assumption, even when the assumption is in this project's own blueprint.

**What was built.**
- `serpapi_fetcher.py` — primary tier. `fetch_serpapi()` (raises `SerpApiConfigError` if no key, `SerpApiCallError` on any other failure — distinct exception types so the provider chain can tell "not configured" apart from "configured but broken"). `get_quota()` — on-demand, not called per-search (would double API traffic with no benefit in the hot path).
- `serper_fetcher.py` — secondary tier, same config/exception pattern. **Not live-verified — no key available this phase.**
- `provider_chain.py` — `fetch_with_fallback()`: tries each tier in `KNOWLEDGE_PROVIDER_ORDER` (config.py, overridable via env var), skips unconfigured tiers, falls through on real call failures, returns `(results, provider_name)` — `provider_name is None` only when every tier is genuinely exhausted, which `discover_sources()`/`resolve_knowledge()` already turn into an honest `UNKNOWN` verdict rather than a fabricated answer.
- `serp_fetcher.py` — lazy-import fix applied as named in this phase's scope: `selenium`/`webdriver_manager` imports moved from module level into `get_driver_instance()`/`fetch_serp()`, so importing `AgentCore.knowledge` no longer pulls a Chrome-launching dependency in just because the last-resort tier exists in the same package. Same discipline as the `NetHyTechSTT`/`browser_automation.py` fix.
- Narration: `notify(message)` threaded through `discover_sources()` → `resolve_knowledge()` → `RAGEngine.query()` → `jarvis.py`, where it's now wired to `self._speak` at the actual RAG call site (`jarvis.py`, the `hasattr(self, '_rag')` branch). "Let me check that..." is now something JARVIS actually says during a live search, not a signature nobody calls.

**Verification (adversarial, not just the happy path).**
- 18 new tests (`AgentCore/knowledge/tests/test_provider_chain.py`): fallback ordering (first tier wins without touching later ones; unconfigured tier falls through; a *real call failure* — not just missing config — also falls through), honest failure when every tier is exhausted, narration content at each stage, config-driven provider order (subprocess-verified, since `config.py` reads the env var at import time), quota parsing against the real `account.json` shape, and the selenium import-coupling regression (subprocess-verified, mirroring `test_nethytech_listen_import_coupling.py`).
- **Adversarial case that mattered:** tried a real, live call with a key that IS set but IS wrong (not just missing) — confirmed live against the actual endpoint that this correctly raises `SerpApiCallError` (HTTP 401) rather than crashing or being indistinguishable from "not configured." Added as a permanent regression test rather than a one-off check.
- **Caught my own flawed verification once, corrected it rather than reporting the false result.** First attempt at confirming the narration wiring mocked `fetch_with_fallback` itself, which made `notify` trivially never fire — a false negative, not a real signal. Re-verified by mocking one level lower (the individual provider function), which let the real `fetch_with_fallback` logic run and actually call `notify`. Confirmed end-to-end: `resolve_knowledge(..., notify=callback)` → `["Let me check that..."]`.
- Real live call against the actual SerpApi endpoint with the supplied key: `fetch_serpapi("current president of the United States")` returned real, structured results (`title`/`url`/`snippet`, `source="serpapi"`). This same call is now a permanent test (`TestSerpApiLiveIfKeyAvailable`) that skips cleanly when no key is present rather than failing or fabricating a result.
- Full suite: **417 passed, 4 failed, 1 skipped** (153s). The 4 failures are the unchanged D11 baseline — none of those files were touched this phase. The 1 skip is the live SerpApi test, correctly skipped in the bare `pytest -q` run where `SERPAPI_KEY` wasn't in the environment.

**Operational note, no secret recorded.** A real SerpApi account now exists and was used for this phase's live verification (free tier, 250 searches/month, well under quota after this phase's calls). The key itself is not written anywhere in this repo or these files — a future phase needing to re-verify the SerpApi tier, or to obtain/verify a Serper key, should ask the project owner directly rather than assume no credentials exist.

---

## Defects added to blueprint §1.6

| # | Defect | Severity | Detail |
|---|---|---|---|
| **D11** | 4 pre-existing test failures, dead since initial commit `dbef62f8` | 🟡 Low | Full detail in the S0-E1 section above. Not regressions — dead scaffolding. Fixes are cheap (delete/rewrite dead tests, fix wrong dict key `sig` vs `hmac_signature`, fix `file_path` returning a directory) and involve **no design decisions**. Deliberately logged, not fixed — was outside S0-E1's scope. |
| **D12** | Window-title/installed-app detection false positive on PWA shortcuts | 🟠 Medium | First surfaced in `31939c8`'s own commit message for `AvailabilityChecker` (installed-check matched a WhatsApp Web PWA shortcut). Independently reproduced and root-caused live during S0-E2's close-out: `GUIBackend.activate_window()`'s substring match also fools `WhatsappDesktopAdapter.open_app()`'s own success signal directly, confirmed via `Get-Process`/`Get-AppxPackage`. Telegram unaffected — confirmed to be the real app on this machine. Affects the resolution gate's "not installed" branch accuracy *and* the adapter's own reported success. |
| **D13** | `IntentRouter` misroutes "search for X" informational phrasings to `action` instead of `llm` | 🟡 Medium | e.g. `"search for the definition of recursion and explain it"`, `"search for python tutorials"` — both currently misclassified. Found during S0-E1's conversational-layer audit, reconfirmed live against the current `classify()` at close-out. Live-path bug (not dead scaffolding, unlike D11) — logged, not fixed, out of S0-E1's declared scope. |

**D1 is resolved** (see S0-E8). Marked closed in blueprint §1.6 rather than deleted — the trail matters. **T3 is flipped to TRUE** in blueprint §1.5, applied as of this reconciliation.

---

## Findings that change strategy — not yet in the blueprint

These emerged from reading the `Dissection` reference corpus and are **evidence-backed, not opinion.** They belong in the blueprint proper; recorded here so they are not lost. **Per standing instruction, these are hard-stop-class judgment calls (Parts 1–3 strategy rewrites) — not queue items, not to be silently folded into Part 1–3 text by any single phase.** They wait for a deliberate review.

### The Commit Gap — the real thesis
*Source: `PHASE_OMEGA_JARVIS_MASTER_ARCHITECTURE_BIBLE.md`*

**"Healthcare software produces recommendations and cannot complete them."** Verified four independent ways: 13.3× AI-vs-automation vocabulary density · 52.4% vs 12.9% shipped completion features · 0.00 vs 1.00 workflow-ownership break rate · 12 vs 1 corroborated patterns.

**The gap is self-sealing:** software stops at recommendation → no outcome data → recommendations cannot improve → trust never rises enough to permit execution. **The market's structure prevents the gap from closing** — which is why incumbents cannot reach it by building faster.

**This is a stronger thesis than "hospital operations is underserved,"** which is what the blueprint currently implies. It is mechanistic and measured rather than observational.

**And it reframes JARVIS from liability to asset:** ~38,700 LOC, only ~24% reachable — but *that 24% is the execution-and-verification engine*, precisely the market's thinnest layer. `resolution_gate.py` (174 lines) matters more than the 149 adapters it refuses to trust.

### The Documentation-Denial Loop — the same phenomenon at ground level
*Source: ELITE role reports (sourced frontline quotes, not generated)*

> Overworked interns/doctors → typos in discharge summaries → TPA rejects ₹50k claim → patient financially ruined → patient sues/attacks hospital

**Synthesis not present anywhere in the source corpus:** the Commit Gap and the Documentation-Denial Loop are *the same phenomenon at different altitudes.* One is the structural explanation; the other is the ground-level manifestation with a rupee figure and a named victim. They live in different folders and nobody connected them.

**Consequence for sequencing:** the physician is the **origin** of the highest-cost loop. Physician-first stops being a deviation from the evidence and becomes the leverage point of it — fixing completion at the physician is upstream of billing pain (8.5/10), admin bottleneck (8.0), bed-blocking, and claim denial simultaneously.

### The Shadow-AI loop — the real argument for local-first
*Source: ELITE Technology Failure Loop*

> Hospitals buy clunky EHRs → IT outsourced/understaffed → clinicians frustrated → **clinicians use unauthorised "Shadow AI" (ChatGPT) → DPDP/HIPAA breaches**

With **DPDP appearing 644 times** across 133 daily market-intelligence reports, this reframes T3 entirely: local-first is not "privacy is a nice differentiator." It is **clinicians are already leaking PHI to consumer chatbots because nothing compliant is fast enough.** Existing, urgent, evidenced demand.

**And D1 was a live instance of this loop inside JARVIS itself** — which is why S0-E8 was thesis-critical rather than a routine bug.

### LAW05 — corrects the blueprint's ABDM strategy
*Source: Phase Ω, 24 Laws*

> **"Standards govern exchange *between* institutions, never operations *inside* them."**

The blueprint currently makes ABDM/FHIR the **primary Stage 1 adapter strategy.** That is wrong. ABDM reaches inter-institutional exchange (claims, records, NHCX) but **cannot reach inside hospital workflow.** ABDM belongs at **Stage 2**, not Stage 1.

Interlocked with LAW02 (*software that cannot complete an action cannot learn from it*): the internal operational layer is **permanently API-poor *and* the only place where completion generates proprietary outcome data.** That is the defensibility, not a problem to solve.

**Blueprint §Stage 1 now carries a pointer to this argument** (added during reconciliation, 2026-07-29) so a future review can find it without re-deriving it — the argument itself is not yet adopted or rejected.

### Corpus quality — three defects in the reference material itself
Recorded so future agents weight the corpus correctly rather than treating all of it as equally authoritative:

1. **`pain_point_index.md` is broken.** 345 of 516 lines are the literal word "Problem" — it extracted headings, not content. The artifact meant to carry the problem space contains zero problems. **The README's fallback path ("if you cannot read all reports, read the reconnaissance folder") points at the broken artifact.** `opportunity_index.md` extracted fine — so *hypotheses survived, evidence did not*.
2. **The founder-blueprint corpus is one idea regenerated.** 117 venture names, 51 distinct stems, **70% share a stem**: `aegis`×19, `claimguard`×17, `clearclaim`×11. The Product Decision Document's *"245 denial documents"* count — which drove Discharge-to-Claim to #1 at 91/100 — is substantially one concept counted repeatedly. **Frequency in this corpus measures the generator's prompt, not the market.**
3. **The strategy is built on the corpus's three *least*-evidenced items.** Across 133 daily reports: claims/TPA/denial **1,949** mentions · DPDP 644 · EMR/HIS 163 · **ABDM 32** · **OPD/queue 25** · **discharge 16.** Claims outweighs discharge 122:1. The conclusions may still be right — ABDM's structural argument holds regardless of chatter, and ELITE reports evidence discharge *mechanistically* — but the corpus does not support them the way the synthesis implies.

**Also:** most healthcare pain is not software-addressable. 307 pain-point lines: low pay **139** · violence **75** · claims 45 · overwork 34 · documentation 33 · legacy IT 30 · queues 19. ~59% economic/safety, **~32% addressable.** JARVIS's value story must therefore be *institutional* (denied-claim recovery, bed-days released, documentation defects prevented) — never "we reduce staff pain."

### Competitor research is pointed at the wrong company
20 dossiers exist. **13 are consumer wearables/longevity** (Function Health, Oura, Whoop, Levels, Ultrahuman, Apple/Google Health, Healthify) — the correct competitive set for Ovexis, not JARVIS. Every strategy memo says *"Ovexis should…"*, never "JARVIS should."

**Zero dossiers on JARVIS's actual competitors:** Qventus, LeanTaaS, Commure, Innovaccer, Abridge, Suki, Notable, Hippocratic AI, Arctic Health, AgileMD.

**Highest-value cheap correction available:** run the same proven 27-deliverable pipeline against that list. The machinery works; it's aimed wrong.

**Best transferable insight found** (UpToDate moat analysis): *"four strong walls, one fatal riverbed: no patient data, no patient relationship, no network effects. Its walls defend yesterday's war — whose synthesis of medicine should a clinician read — while the next war is whose system knows **this patient** over time."* That is the World Model / event-graph thesis, reached independently from competitive analysis. Two unrelated routes, same conclusion.

**Warning worth heeding:** *"Regulatory moat is their best underpriced asset — expect lobbying toward 'validated CDS' standards that starve ad-supported rivals."* For JARVIS this makes MOAT-003 (clinical compliance posture) **offensive, not defensive** — being late means being locked out by a standard someone else wrote.

---

## Open items, precisely stated

| Item | Status | Blocker / next action |
|---|---|---|
| **S0-E3** — knowledge-retrieval fix | ✅ CLOSED (`20ce0a88`) | See the closed-item entry above. Serper tier unverified (no key) — re-verify if/when a `SERPER_KEY` becomes available. |
| **S0-E9** — Tier-1 inference wins | OPEN | `generate_stream()` (exists at `llm_engine.py:161`, **called by nothing**) · model warm-up · task-aware token budgets. **Then re-measure latency before any routing work** (§3.7b). |
| **D11** — 4 dead tests | LOGGED, in blueprint §1.6 | Cheap, no design decisions. Own phase when scheduled. |
| **D12** — window-title/`AvailabilityChecker` PWA false positive | LOGGED, in blueprint §1.6 | Root-caused (substring match in `pyautogui.getWindowsWithTitle`). Own phase when scheduled. |
| **D13** — `IntentRouter` search-phrase misroute | LOGGED, in blueprint §1.6 | Live-path bug. Own phase when scheduled. |
| **RHINAL — wire remaining 13 tools** | SCOPED, NOT STARTED | Distinct phase. Use known risk classes (read-only vs write-capable). |
| **`rhinal_attach_file`** | BLOCKED (hard stop, named explicitly in standing instructions) | Needs a genuinely non-identifying real test file + explicit approval. Do not fabricate a `scanResult`. |
| **Blueprint status rows** | ✅ APPLIED (2026-07-29 reconciliation) | S0-E1/E2/E8 now show ✅ with SHA + evidence pinned in blueprint §Stage 0, cross-referenced to this file. |
| **Blueprint corrections — mechanical, now applied** | ✅ APPLIED (2026-07-29 reconciliation) | T3 → TRUE · D1 → closed · D11/D12/D13 added · layer-map (L6/L7) updated. |
| **Blueprint corrections — strategy, still NOT applied, correctly** | OPEN, hard-stop | Commit Gap as thesis · ABDM demoted to Stage 2 · corpus-quality caveats folded into Part 1–3 prose · competitor-research correction. These are Parts 1–3 rewrites per standing instruction — a pointer to the LAW05/ABDM argument was added to blueprint §Stage 1 so it's findable, but the rewrite itself waits for deliberate review, not a queue phase. |

---

## Standing rules earned this session

1. **Report done only after `git log origin/… --oneline` confirms the commit.** Local test success is not completion.
2. **Never label a failure "pre-existing" without checking `git log --follow`/`git blame` on the file.** A count carried forward is not evidence.
3. **Read the source; never infer a contract from identifier names.** Two occurrences: `GeneratorHelper`/`LLMAdapter`, `vaultWorthy`.
4. **Verify against the live interface, never the documentation** — even same-repo documentation. RHINAL's README said 4 tools; its code registered 14.
5. **Trivial-to-fix and in-scope are different questions.** Log out-of-scope findings as blueprint items; only in-scope licenses acting now.
6. **When new evidence revises a prior conclusion — the reviewer's included — state the correction plainly.** "Regression" → "dead since initial commit" is a different finding, not a rewording.
7. **A blueprint edit outside version control is not an edit.** Both documents live in the repo, tracked. **Proven necessary, not just stated** — see incident #3 above, which happened after this rule was already written down and before it was actually enforced by committing the files.
