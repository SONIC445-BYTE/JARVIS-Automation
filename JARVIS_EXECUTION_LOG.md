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

### DEC-002 — Clinical audit trail, architected in, wired into `UIExecutor.execute_intent()` ⭐ *P0/10.00, Stage 0.5 gate*
**Status: ✅ CLOSED.** Commit `b338c4fb` on `phase-2-adapter-wiring`. Risk tier: medium, per standing instruction — same tier as D2 (security/audit-critical, wired into the live pre-adapter path, reversible via `git revert`, no real patient data, no live external writes, no money).

**What was built.** `AgentCore/audit_trail.py` — `AppendOnlyAuditLog`: hash-chained (`prev_hmac` per entry, verifiable end-to-end via `verify_integrity()`), fail-closed key resolution through `secure_key.resolve_key()` — a configuration-class failure (no real key resolvable) is a hard stop at construction, matching D2's discipline exactly. `emit_clinical_action()` builds the standardized who/what/when/why/source/consent record; `why` comes from `Intent.source_text` (new field, `daemon/intent_parser.py`, populated by `CommandRouter.resolve()`) — the physician's actual words, not a placeholder.

**Two distinct failure modes, two distinct treatments — the design point of this phase.** A transient write failure (disk full, permission error) never blocks the underlying action: `append()` catches it, queues the record to a fallback file, and returns an `AuditWriteResult` the caller can surface honestly rather than it being silently swallowed into a log nobody reads. A configuration-class failure (key can't resolve at all) genuinely blocks the action — checked in `UIExecutor.execute_intent()` **before** the action runs, not after. An earlier draft of this method checked it after running the action, which would mean the action already happened by the time the "stop" fired — not a hard stop at all. Caught and fixed before this commit, not after.

**Single chokepoint, not per-adapter emission.** `UIExecutor.execute_intent()` is the one place every `Intent` passes through regardless of which adapter/action it resolves to, so it's also the one place the audit record is emitted — including the `BLOCKED` path (CAPTCHA/login-wall pause), confirmed by a dedicated test: a paused action still gets a real audit record with `outcome_status="blocked"`, not silently skipped because it isn't a "normal" outcome. A transient audit-write failure is folded into `result.metadata['audit_write_warning']`, which `ODAVLoop` (`odav_loop.py`) surfaces into the physician-facing message rather than losing it to a `print()`.

**D14, half-closed as a byproduct, not a separate phase.** `AgentCore/learning_system/audit_log.py`'s `LearningAuditLog` reworked into a thin wrapper over the same shared engine — its append-only + HMAC-chain design was already solid; what needed fixing was the identical D2-class weakness (`os.environ.get('JARVIS_HMAC_KEY', 'jarvis-learning-audit-default-key')`, resolved at *module import time*, before any fail-closed check could run) plus the missing configuration/transient distinction (the old `log_event()`'s file write had no `try/except` at all). Confirmed by reading the file directly, not assumed: `AgentCore/ui_agent/utils/ui_audit.py:14` still has the identical pattern (`os.environ.get("JARVIS_HMAC_KEY", hmac_key)`) — untouched, different subsystem, its own phase when scheduled.

**A real test-isolation bug caught and fixed before this commit.** The `tests/conftest.py` fixture isolating the clinical audit log across tests originally used `JARVIS_INSECURE_DEV_KEY=1` to avoid the real OS keyring. That routes through `secure_key.py`'s `_dev_file_key()`, which writes to a fixed, non-`tmp_path`-aware directory (`data/dev_keys/`) — every test run touching `execute_intent()` was writing real key files into the actual repo, not a sandbox. Caught by finding `clinical_audit.key` and `learning_audit.key` already sitting in the real `data/dev_keys/` after a routine run. Fixed by switching to an explicit, purpose-specific env var (`JARVIS_CLINICAL_AUDIT_KEY`, a real generated key, never touching disk) — the same pattern this file's own `test_audit_trail.py::_WithRealKey()` already used. The two leaked files were confirmed untracked (`git ls-files` — empty) and gitignored (`*.key`) before deletion.

**Verification.** 18 new tests — `tests/test_audit_trail.py` (12: real append/verify round-trip, tampering detection via a corrupted written line, a double-failure adversarial case, configuration-class hard-stop with keyring forced to fail, transient-failure queue-and-reconcile), `tests/test_ui_executor_audit_wiring.py` (6: configuration failure blocks before the adapter is ever called, an unexpected non-`KeyConfigurationError` does *not* block, transient failure surfaces the warning without blocking, a successful write adds no warning, the audit record's fields match the Intent, and the BLOCKED-path case). Confirmed deterministic: run 3 times consecutively immediately before commit, 18/18 passed each time (~0.27s each).

**Full suite, and an honest account of a flaky unrelated test rather than a silently re-run-until-green number.** Clean run immediately before staging: **490 passed, 1 skipped** (`SerpApi` live test, no key in this environment — expected), **0 failures.** Two subsequent re-runs (run while confirming the DEC-002 tests specifically weren't the cause of any instability) each surfaced exactly one failure: `tests/test_phase2d_ported_adapters.py::TestExtractQueryGuard::test_twitter_post_with_trailing_platform_name_extracts_real_text`. Root-caused via the full traceback, not assumed transient: `pyautogui.FailSafeException`, triggered by the real mouse cursor's on-screen position at the instant an unmocked `pyautogui.hotkey()` call fires inside `TwitterAdapter.send_message()` — the test mocks `_navigate` but not the backend's `hotkey()` call, so a real fail-safe check runs against wherever the actual cursor happens to be. Confirmed pre-existing and unrelated to this phase: zero diff on that test file or the adapters it touches (`git diff --stat`), last real commit `54a86665` (D12, an already-closed phase). Not fixed — out of DEC-002's declared scope. Logged here rather than silently omitted; own phase when scheduled (mock `hotkey()` in that test, or disable `pyautogui.FAILSAFE` for dry-run adapter tests specifically).

**Blueprint updated in the same phase, evidence-pinned.** §4.1's DEC-002 row and Part 6 item 3 both moved from open/in-progress phrasing to closed, with commit `b338c4fb` and a pointer to this entry — same pattern already used for S0-E1/E2/E8.

---

### Companion-app Phase 1 — scaffolding: Communication Gateway, auth handshake, Session-creation flow
**Status: ✅ BUILT.** `AgentCore/comm_gateway/`, design note `docs/companion_app_scaffold.md`. Risk tier: medium — execution against Phase 0's already-settled safety decisions, not new design judgment. Track A only.

**Structure, matching §4.4c and the v3.9 trust-tier resolution rather than the original text alone:** `channel.py` (Channel ABC, `DesktopChannel`, `SyntheticRemoteChannel` — the Track A double for exercising remote-channel code paths before any real remote channel exists), `deployment_policy.py` (PG-001 "policy is configuration", STRICT_LOCAL enforced default), `auth.py` (second-factor handshake, fail-closed), `capability.py` (Capability Negotiation), `session.py` (channel-opaque `Session`, `SessionManager`), `gateway.py` (`CommunicationGateway.connect()`, the single orchestration point), `approval.py` (Security Broker checkpoint table, interface only). Own audit trail (`audit.py`) reusing `AppendOnlyAuditLog`, same pattern as `mcp_audit.py` and the Mode C gate — a new module, `audit_trail.py` untouched.

**Channel opacity — "Session Manager must never know which channel a session originated from" — enforced structurally, not by convention.** `Session` has no `channel` field: not private, not renamed, absent from the dataclass entirely. Checked one level down too — `CapabilitySet`, which `Session` embeds, carries no channel-identifying field either, since the guarantee would be trivially defeated there instead. Tested by inspecting `dataclasses.fields()` directly rather than trusting no code path happens to read one.

**STRICT_LOCAL is the enforced default, in two independent places.** `load_deployment_policy()` returns it when no policy file exists, and `DeploymentPolicy`'s own dataclass default matches — so code that forgets to load a policy still gets the safe value rather than an accidentally permissive one. A remote channel under STRICT_LOCAL still receives a `CapabilitySet` (empty, T0 only) rather than a distinguishable refusal, so "a remote channel tried to connect" and "a remote channel connected and got nothing" look identical from outside — deliberate, not an oversight.

**No channel reaches T3 in this phase, for every deployment mode, tested exhaustively.** Not because desktop voice is architecturally excluded — `docs/trust_tier_clinical_writes.md` names it as one of the two intended T3 confirmation channels — but because the four-invariant-property confirmation mechanism (payload-rendered presentation, distinguishing-token consent, bounded validity, silence-is-refusal) isn't built for any channel yet. Stated in code as a fact about what exists, not a permanent ceiling — a comment this session has specifically learned to write precisely after finding shape-of-D18 problems more than once.

**"Never renegotiated upward mid-session" enforced by `SessionManager.register()`, not only by `CapabilitySet` being frozen.** A frozen dataclass only stops one instance being mutated; it says nothing about a *new*, more permissive `CapabilitySet` being attached to an *existing* `session_id`. Tested by actually constructing a genuinely stronger capability set from a different channel and confirming the attempt to attach it to an already-registered session is refused, the original weaker session is what remains on file, and the refusal itself is a real audited `renegotiation_refused` event — the test asserted on the audit record's presence, not only the raised exception, after checking and finding the first draft exercised the code path without asserting on it.

**Auth handshake, three adversarial cases kept distinct rather than folded into one:** no second factor presented, a wrong second factor, and a *correct* second factor presented for the wrong claimed principal (phone-number-identity-alone-is-insufficient's sharpest case — someone else's valid PIN must not authenticate you). All three raise `AuthenticationError`, no session is created, and every failure is audited. `DesktopChannel.requires_second_factor()` returns `False` via an overridden method each channel implements, not inferred from a `ChannelKind` enum value at the call site — deliberately, given this project's two prior burns from inferring a contract from a name (`GeneratorHelper`/`LLMAdapter`, `vaultWorthy`).

**Verification, built correctly the first time rather than caught on review.** `AgentCore/comm_gateway/tests/conftest.py` redirects the audit log directory and pins an explicit real key via env vars set *before* any `AppendOnlyAuditLog` construction — written directly against this session's own two prior mistakes (DEC-002's `JARVIS_INSECURE_DEV_KEY` fixture leaking a real key file into the repo; D14's first test draft redirecting `log_dir` after `__init__` had already created the real path), rather than re-deriving the fix. Confirmed by checking `data/comm_gateway/` does not exist in the real repo after a full test run. 31 tests, including `TestRealAuditTrail`, which mocks nothing on the audit side and reads real entries back from disk — same convention D16 established.

**What is deliberately not here, stated rather than left implicit:** no real remote channel (Stage 1c, needs real transport integration); no T3 confirmation execution (nothing in this phase triggers a real T3 action to confirm); no real Mobile Trust Companion; **no integration into `jarvis.py`'s live conversation loop** — wiring the existing single-channel desktop-voice loop to be fed by Gateway-issued Sessions is a real decision about the live path, not implied by scaffolding existing, and is left for its own phase; and no use of `rhinal_mcp_client` or any other real external write — `CapabilitySet.rhinal_writes` is a capability flag only, nothing here calls RHINAL.

---

### D18 — the Level6 sandbox rebuilt as a real isolation boundary
**Status: ✅ CLOSED.** Risk tier: high — security-boundary work directly downstream of the verified OpenAI/Hugging Face sandbox-escape incident.

**What the defect was.** `sandbox_runner.py` ran `subprocess.run([sys.executable, "-m", "pytest"], cwd=temp_dir)` — the host interpreter against the host's own site-packages, isolated by nothing but a temporary working directory — while `env["JARVIS_SANDBOX_NETWORK"] = "0"` sat one line above, written in exactly one place and read in none.

**Environment constraints established first, before any design.** Checked directly rather than assumed, because the answer determines what "real isolation" can even mean here: **Docker not installed. WSL not installed. Windows Sandbox not present. Not running as Administrator.** `pywin32` available. So container isolation is off the table on this machine, and any design premised on it would have been another unbuilt-image specification.

**What was built.** A provisioned standalone interpreter (own `sys.prefix`, populated only from the vetted manifest's `image` layer) running inside three stacked OS-enforced boundaries, all non-admin:
- **AppContainer with no capabilities** — Windows Filtering Platform refuses every socket; the LowBox token denies any file lacking an ACE for the package SID.
- **Restricted token** with the user SID marked deny-only — the user profile's own ACLs stop applying to the child.
- **Job object** — kill-on-job-close, active-process cap, memory and CPU-time limits, UI restrictions.

Plus handle inheritance pinned to exactly three stdio handles and the host environment not inherited. **The launcher refuses to run when a required layer is unavailable rather than degrading silently** — silent degradation being the original defect's whole shape. `JARVIS_SANDBOX_NETWORK` was **deleted rather than repaired**, and an AST-based test now fails if anyone reintroduces it.

**Independent verification — the part that matters, and it did not simply confirm the report.** The implementing agent's own 24 isolation tests pass, but a test written by the same pass that built the boundary can pass vacuously: "reading failed" is equally true when the path is wrong or the child never ran. So the reviewer wrote a separate probe with a **control arm** — the identical script and the identical interpreter, run twice, once contained and once not:

| Probe | Contained | Control (no containment) |
|---|---|---|
| Read canary in `~` | `PermissionError` | **read `PARENT-INDEPENDENT-CANARY-4417`** |
| Enumerate `~` | `PermissionError` | **99 entries** |
| TCP 1.1.1.1:443 | `PermissionError [WinError 10013]` | **connected** |
| DNS `example.com` | `gaierror` | **104.20.23.154** |

**The control arm is what turns this into evidence rather than a passing assertion**, and the first attempt proved the point: pointing the probe at the *host* interpreter produced no output at all — ambiguous, not proof. The host Python is itself unreadable to the AppContainer, which is consistent with the boundary working but does not demonstrate it. Re-running with the provisioned interpreter on both arms produced the table above.

**Dependency isolation separately verified:** `selenium`, `keyring` and `cryptography` are present on the host and genuinely absent from the provisioned interpreter.

**A discrepancy the reviewer raised and then withdrew, recorded because the withdrawal is the honest part.** `mss` and `pyautogui` import inside the sandbox despite the manifest marking them `layer: host_mocked` — "never installed". That looked like a manifest claiming a property the implementation lacked, i.e. D18's own shape at smaller scale. Investigated: their `find_spec` origins are single-file stubs in the sandbox tree, while the real host packages are directories. They are auto-generated doubles, and the stub's own docstring says *"Do not read a green sandbox run as 'tested on Windows'."* The implementation was right and the reviewer's initial reading was wrong.

**One correction to the environment brief, from the implementing pass:** `wsl.exe` *is* on PATH — it is the Windows inbox stub that prints "WSL is not installed". The conclusion held, but `shutil.which("wsl")` would report WSL as available. That is the same infer-capability-from-a-name error D18 is about, caught in the course of fixing D18.

**What is honestly NOT closed, and why D19 exists.** Per §4.4b's own position the ResolutionGate remains the primary control and this is defence-in-depth. It is **not a container** — same kernel, filesystem and network stack. Network denial rests on unaudited BFE/mpssvc. `socket` and `subprocess` remain importable; only the *attempt* now fails. **Loopback is denied too**, which is a real functional cost rather than a win: adapter tests needing a local server cannot run in-sandbox without an admin-granted exemption. And most importantly the vetted closure is **copied from the host with no hashes and no pinning** — logged as **D19** on the implementing agent's own recommendation, and correctly: closing D18 while the manifest still describes hash-pinning as forthcoming would retire a ticket while leaving a document claiming a property the code lacks, which is D18's exact shape one level up.

---

### D18 re-verified · D19 hash-pinning built · scoped loopback exception investigated *(v3.11)*
**Status: D18 re-verified unchanged, still closed. D19 partially closed — drift/tamper half built, provenance half still blocked on infrastructure. Loopback exception investigated, not delivered.** Risk tier: high — sandbox/security-boundary work, same category as D18's original close.

**Step 1 — D18 re-verified from the actual current code, not from memory of v3.9's closure, per instruction.** Read `AgentCore/level6/sandbox_isolation.py` and `sandbox_env.py` directly: `AppContainerProfile` (zero capabilities), `make_restricted_token()` (user SID deny-only, privileges stripped except `SeChangeNotifyPrivilege`), and the job-object limits are all still present and unchanged in shape. Confirmed `JARVIS_SANDBOX_NETWORK` is genuinely absent from the codebase (`grep` across the repo: the only remaining occurrences are historical prose in docs/commit messages explaining its deletion, and `sandbox_runner.py`'s own docstring recounting why); `test_ast_scan_confirms_jarvis_sandbox_network_is_gone`'s AST-based regression test (asserting no code ever sets that key again) is intact and passing. D18 stands as closed.

**Step 2 — D19's own "blocked on infrastructure" framing re-examined before being trusted, per instruction, and found to conflate two different mechanisms.** The manifest (`adapter_sandbox_dependencies.yaml`) and `sandbox_env.py`'s own docstring both described "no hash pinning" as a single blocked item. It is not: the manifest's `image:` section (a linux/amd64 container image, `base_digest`, a `pip-compile --generate-hashes` lockfile, `pip install --require-hashes` against a package index) genuinely needs a container runtime this machine does not have — **that stays PENDING, unchanged.** But hashing the files `sandbox_env._copy_distribution()` actually reads from the host and copies into the sandbox is a local checksum comparison, needing no container at all. Built:

- `sandbox_env.generate_lock()` / `write_lock()` — hashes every file in the resolved closure (all 21 packages including transitives, not just the 9 declared roots) via a new shared iterator, `_iter_distribution_files()`, factored out of `_copy_distribution()` itself so the hashed file set and the copied file set cannot silently diverge. Output committed as `AgentCore/policy/adapter_sandbox_provisioned.lock.json`.
- `sandbox_env.verify_lock()` — compares the CURRENT host state against the committed lock.
- `provision()` now calls `load_lock()` + `verify_lock()` **before building the interpreter or copying anything**, on every call including cache-hit reuse (the cache key is a digest over package *versions*, not file content, so a tampered file that doesn't change a version string would otherwise serve a stale, unverified environment indefinitely). Any mismatch raises `SupplyChainIntegrityError` and nothing is provisioned. The lock's own digest was folded into the cache key (schema bumped 3→4) so regenerating the lock invalidates stale caches too.

**Verified against a REAL host file, independently by the reviewer, not accepted from a self-report — because there was no separate implementing pass to distrust here, the same standard still applied to my own work rather than skipped.** `packaging-25.0.dist-info/INSTALLER` under the actual host site-packages was overwritten with `tampered-by-adversarial-test`, `provision()` was called, and it genuinely raised `SupplyChainIntegrityError` naming `packaging` and the exact file before touching anything else. The file was then restored and the restoration checked byte-for-byte (`target.read_bytes() == original`). Formalized as `AgentCore/level6/tests/test_supply_chain_lock.py` (7 tests: lock exists and matches host with zero mismatches as the control every tamper test depends on, refusal on a missing lock path, refusal on a malformed lock file, refusal when a resolved package is absent from the lock, the real-file tamper test above, and a post-restoration clean-bill-of-health test).

**What D19 still does not close, stated as precisely as the container gap was stated for D18:** the lock pins to a *reviewed host baseline*, not to a package index's published hash. It has no provenance — it cannot tell you the host's packages were ever legitimate, only that they have not silently changed since the lock was committed. `docs/adapter_sandbox_dependencies.md` §8.2 and `docs/adapter_sandbox_isolation.md` §8 item 1 both updated in place to state this split rather than leave the old "entirely unaddressed" framing standing.

**Step 3 — scoped loopback exception, investigated to a specific, evidenced conclusion, not abandoned on first failure and not shipped half-working either.** `LoopbackExceptionPipe` (`sandbox_isolation.py`) ACE-grants the AppContainer SID access to exactly one named pipe — reasoning that a pipe lives in the NT object namespace, not the WFP/socket stack a capability-less AppContainer denies. **Four real bugs found and fixed while building it:**
1. `ACL.AddAccessAllowedAce` raised `OverflowError` on the raw unsigned `GENERIC_READ|GENERIC_WRITE` bits (`0xC0000000` exceeds signed 32-bit range) — fixed using `win32con`'s own pre-signed constants.
2. The created pipe handle lacked permission to modify its own security descriptor — fixed by OR-ing `WRITE_DAC` into `CreateNamedPipe`'s `dwOpenMode`, which the API documents as accepting standard access rights there.
3. `SetSecurityInfo` accepted a mask built from raw `GENERIC_*` bits without error, but access was still denied — per MSDN an ACE's mask must never contain generic bits; fixed using `ntsecuritycon.FILE_GENERIC_READ`/`FILE_GENERIC_WRITE`, the pre-mapped specific rights.
4. Handle-based `SetSecurityInfo` with `SE_FILE_OBJECT` failed outright (`ERROR_INVALID_PARAMETER`); `SE_KERNEL_OBJECT` is the object type that actually works for a live pipe instance handle, empirically confirmed since this contradicts the file-object intuition a pipe otherwise invites.

**After all four fixes: it genuinely works, for AppContainer running alone.** `TestLoopbackExceptionPipe::test_appcontainer_alone_can_reach_a_declared_pipe` — a real contained child, AppContainer only (no restricted token, no job object), opens the declared pipe and completes a real ping/pong. **It does not work against the actual sandbox launcher.** `ContainedLauncher` stacks AppContainer with a restricted token by default — D18's own design, all three layers together. With that restricted token active, the identical, correctly-ACE'd pipe is still refused (`WinError 5`), even after also trying `S-1-15-2-1` (ALL APPLICATION PACKAGES) in addition to the specific AppContainer SID. **Isolated by control, not guessed:** AppContainer alone connects (proven above); AppContainer + restricted token fails, with the job object on or off making no difference — so the restricted token specifically is the blocker, and the job object is ruled out. `socket.AF_UNIX` was checked as a filesystem-namespace alternative to a raw pipe (would reuse the already-proven-working `grant_dir()` ACL path instead of pipe-specific security calls) — `hasattr(socket, "AF_UNIX")` is `False` on this Python/Windows build, ruled out in one call rather than pursued further.

**Root cause not fully isolated beyond "the restricted token, specifically."** Candidate mechanisms considered but not confirmed: `SeChangeNotifyPrivilege`'s traverse-check bypass (kept deliberately in `make_restricted_token()` for NTFS reasons — see D18's own entry) not extending to NPFS the way it does to NTFS; some difference in how `CreateProcessAsUserW` derives a LowBox token from an explicitly-constructed restricted primary token versus the calling process's own token. Not run further to ground — judged as past the point where more non-admin Windows-internals debugging was proportionate to a test-convenience feature, versus reporting the finding and stopping.

**Disposition — this is the moment new evidence should revise a prior conclusion, per the standing hard-stop, and it is reported rather than pushed past.** `LoopbackExceptionPipe` is real, working code for the case it was proven to work for, and a real, reproducible negative result for the case that matters. Both are kept in the repo as adversarial tests (`TestLoopbackExceptionPipe`, both the positive and negative results asserted, not just the positive one) so the finding stays pinned rather than silently re-asserted as fixed or silently forgotten later. **`ContainedLauncher`'s restricted-token default was NOT weakened to make this pass** — that would be a real reduction of D18's closed boundary and needs its own reviewed decision, explicitly out of this phase's scope. Adapters needing a live local endpoint still route to the host, outside the sandbox, exactly as D18's original entry already said.

**Container-upgrade-path note, attached to D18/D19 as instructed, not left to be re-derived later.** New §9 in `docs/adapter_sandbox_isolation.md`: if the deployment environment ever gets a container runtime or Administrator, D18's three-layer stack, D19's host-baseline lock, and `LoopbackExceptionPipe` are all **replaced by real container isolation, not layered underneath it** — a container's own kernel/filesystem/network namespace is a strictly stronger property than any of the three, and running both is unaudited complexity on top of a boundary that would already be stronger. The one piece that survives regardless of runtime: the AST-based static import check, because it is a generation-time developer diagnostic, not a boundary.

**Full suite, independently run, not trusted from a partial pass.** `AgentCore/level6/` (61 tests, isolation + supply-chain + everything else in that package): **61 passed, 0 failed.** Full project suite (`tests/ AgentCore/ platform_adapters/`): **630 passed, 1 skipped, 0 failures** (up from v3.10's 620 passed — net +10 new tests: 7 in `test_supply_chain_lock.py`, 3 in `TestLoopbackExceptionPipe`; the 1 skip is the pre-existing `SerpApi` live test with no key in this environment, unrelated to this phase).

**A debugging note worth keeping, not really a defect but a genuine time cost:** several early attempts at this phase appeared to hang for minutes with zero output when run via `bash ... | tail -N` in the background — traced to `tail` buffering the entire pipeline until the process exits, not an actual hang. Reproduced side-by-side: the identical pytest invocation piped through `cat` (or run in the foreground without a trailing pipe) streamed normally. One genuine hang was found underneath the noise (the `test_the_real_launcher_still_denies_the_declared_pipe` test leaving a server thread blocked in `ConnectNamedPipe` that `CloseHandle` didn't reliably unblock under pytest's process lifecycle) and fixed by removing the unnecessary server thread from that specific test — the denial happens at open time, before any handshake, so no listening server was needed to prove it.

---

### Companion-app Phase 0 — three safety decisions resolved before any app code
**Status: ✅ CLOSED (all three).** Risk tier: medium — each touches a safety-relevant design surface (detection-accuracy claims, authorization tiers, sandbox escape surface). Deliberately sequenced *before* companion-app scaffolding, because the app's own safety model depends on all three.

---

**1. PG-001 Mode C drift-catch detector — built.** `AgentCore/privacy_gateway/`, design note `docs/pg001_mode_c_drift_detector.md`.

Rule/lexicon-based, entirely local (§3.7b — session content may be clinical, so a detector that reaches the network *is* the leak), confidence-scored findings rather than a boolean, policy as configuration. The declared-intent primary gate is untouched; the detector's only outward effects are `drift_review_required` and an audit record, and `tests/test_gate.py` pins that ordering as a test rather than prose.

**The measured numbers are unflattering, and that is the finding.** Full assurance output is embedded in the design note and reproduced by `python -m AgentCore.privacy_gateway.evaluate`:
- **Drift recall 65% at the default threshold — a 35% false-negative rate.**
- **`clinical_colloquial`: 0 of 8 caught.** A structural blind spot, not a tuning problem: *"The chap in the corner bed is still bringing up everything he eats"* is unambiguously clinical, contains no clinical vocabulary, and a lexicon scores it 0.000. Eight of thirteen total misses are this one category.
- Patient-linked identifier recall 76.9% at the default 0.70; raising to 0.90 collapses it to 34.6%.
- Zero false alarms across all three non-clinical categories, including the deliberately confusing one. Precise and insensitive.

**This is the strongest available argument for the architecture PG-001 already chose.** A 35% FN rate would be indefensible as Mode C's primary gate; as a net *behind* a declared-intent gate it is a real improvement over nothing. The blueprint asserted "never let the safety property rest on a classifier" as a principle — this measures the principle.

**Anti-fabrication made mechanical, not promised.** `TestDesignNoteMatchesAFreshRun` fails if any deterministic line the evaluation script prints is missing from the design note. A number cannot be hand-typed into that document without CI noticing — the same discipline §4.4b's CI-enforced verification section argues for, applied to a detector's own accuracy claims.

**Two real defects found and fixed while completing this** (the agent that built it died on a session limit before running anything, so every test here was run for the first time by the reviewer):
- The locality test asserted no network module appears in `sys.modules` at all, and **could never pass** — `urllib.request`, `http.client`, `socket` and `ssl` are already loaded at bare interpreter startup, so it measured the interpreter, not the package. Rewritten to measure the *delta* across the import. A check that cannot pass is not stricter; it is one that gets deleted the first time someone is in a hurry, and it would have masked exactly what it exists to catch. (`requests`/`httpx`/`torch`/`transformers` were absent throughout — the detector genuinely is local.)
- A policy test set `clinical_confidence_threshold=0.999999` expecting no score to reach it. **`clinical_confidence` saturates at exactly 1.0**, so it still fired. Rewritten against a genuinely mid-scoring utterance, plus a companion test pinning the saturation as intended behaviour: a deployment can move the boundary, it cannot configure the detector into ignoring a maximally-confident hit — that is `DriftAction.LOG_ONLY`, an explicit and auditable choice, not a threshold quietly set to 1.0.

---

**2. Trust-tier split for hospital record modification — resolved.** Full working in `docs/trust_tier_clinical_writes.md`; §4.4c principle 5 replaced.

Four tiers ordered by **irreversibility and liability**, not sensitivity — **T3 clinical write** sits above bank transfer deliberately, because money moved in error is recoverable and a discharge is not. Per-action confirmation always, no session pre-authorization, no "approve all". Three rules fix the boundary: the tier follows the **destination** not the verb (marking a queue entry `DONE` is T0 in JARVIS's own surface and T3 the day it writes through to the HIS); the boundary is the **signature** not the keystroke (drafting is T2, only the commit is T3); and **ordering physical work is a write** even when no prose changed.

**"Regardless of channel" resolved as: no channel exempts the action — not that every channel can carry it.** Four invariant properties, and a channel that cannot meet all four **refuses rather than downgrades**, which blocks T3 over Stage 1c remote inbound.

**Approval fatigue addressed with arithmetic rather than assertion:** at 40–100 patients/session a naive T3 fires 150–400 times, adding 10–30 minutes of pure confirmation — which fails NORTH STAR outright. Mitigated by the signature/keystroke split, and made measurable in PG-001's own Detector-Assurance spirit: **if >95% of confirmations are approved in under a second, the gate is not being read and must be reported as not working**, however correctly it fired.

**A real internal contradiction this surfaced:** principle 4 (Channel Independence) said the same engine executes regardless of channel, which principle 5 now partially denies. Fixed with an explicit carve-out on principle 4. Worth noting the design *avoided* a second contradiction: §4.4c requires the Session Manager never learn which channel a session came from, and per-channel T3 refusal naively breaks that — resolved by having Capability Negotiation supply `(max tier, available confirmation modalities)` at connect, so the Gateway knows the channel and the Session Manager still never does.

**Two prerequisites inherited, both additive changes to immutable-tier modules, neither made here:** `mcp_audit.py`'s pairing-by-adjacency breaks the moment a human pause sits between presentation and consent, so **the correlation-id field it already flagged becomes required rather than optional** — an independent second agent reaching the same conclusion as D16's own limitation note; and `audit_trail.py`'s hardcoded `consent: "direct_user_action"` must start carrying the confirmation modality and record id.

---

**3. Adapter-generation sandbox package access — resolved.** `docs/adapter_sandbox_dependencies.md`, manifest `AgentCore/policy/adapter_sandbox_dependencies.yaml`; §4.4b's finding 2 and the Network-egress row replaced.

Pre-staged, not proxied: digest-pinned base, hashed lockfile over the full transitive closure, no index configured, no `pip` at runtime. **Live package fetching is not a default that can be switched off; it is absent.** Outside-the-set packages are a reviewed-once developer escalation through Phase 3d's existing propose → approve → versioned-commit idiom, recorded as a manifest diff.

Three findings worth keeping: **`webdriver_manager` is the OpenAI/HF incident recurring one level down** (it fetches browser drivers over the network at runtime) — hard refusal, and the clearest demonstration that "no egress" and "vetted set" are two separate rules. The set had to **split into two layers** (`image` vs `host_mocked`) because `pywin32`/`pywinauto` cannot install in a Linux container at all, with the honest cost stated: the sandbox verifies adapter *logic*, not Windows behaviour. And **drift was verified as real before any image exists** — `requirements.txt` pins `Pillow==12.1.1` while the developer machine has `11.3.0`.

**Deviation from the instruction, flagged rather than silently absorbed:** "reviewed-once" as literally worded is a permanent hole by construction. Implemented as reviewed-once-then-re-affirmed — every escalated entry carries `review_by:` (a past date fails CI) and `justified_by:` (CI fails when the named adapter no longer imports it), so the set shrinks by default. The soft spot is named too: expiry bumps are exactly what gets rubber-stamped, and the only counter-pressure is that clearing one is a reviewed diff with a written reason.

**Hashes are `null` throughout, deliberately** — nothing has been built, so nothing has a real hash, and plausible-looking ones would be worse than none. `null` is defined as fail-closed: the build refuses.

---

### D18 — the Level6 "sandbox" is not a sandbox *(found, logged, NOT fixed)*
**Status: 🟠 OPEN.** No commit — a finding, surfaced by the sandbox-design work and **independently confirmed against the source before logging**.

`AgentCore/level6/sandbox_runner.py:80–83` runs `subprocess.run([sys.executable, "-m", "pytest"], cwd=sandbox_dir)` — the host interpreter against the host's own site-packages, isolated by nothing but a temp working directory. No container, no separate environment, no egress restriction.

**The sharper half:** line 65 sets `env["JARVIS_SANDBOX_NETWORK"] = "0"`, and a repo-wide grep finds that name **in exactly one place — where it is written.** Nothing reads it. It is decoration shaped like a network control. That is the same failure as D1 (`_fallback_listen` inside a file named `local_stt.py`) and the `vaultWorthy` misread, and it is precisely what this project's standing rule "never infer a contract from an identifier name" exists to catch — this time in our own code, about a security boundary.

**Consequence:** §4.4b's Concrete gating requirements table describes controls the current runner cannot enforce. Those rows are a specification for an image that must be built, not a description of today, and the blueprint now says so. Not fixed here — real isolation is its own phase, and §4.4b's own position is that the ResolutionGate is the primary control with the sandbox as defence-in-depth, so this weakens the second layer rather than the first.

---

### D16 — `rhinal_capture`'s external vault write, now audited
**Status: ✅ CLOSED.** Commit `64055a1b` on `phase-2-adapter-wiring`. Risk tier: medium (DEC-002-adjacent, external write path). Split out of D15 as its only real half after the owner confirmed `code_engine` is intentional build infrastructure, deliberately outside the clinical action path.

**What was built.** `AgentCore/mcp_audit.py` — `audited_mcp_write()`, a reusable pattern for any non-GUI MCP write. It reuses `audit_trail.py`'s mechanism (`get_clinical_audit_log`, `emit_clinical_action`) and its two-tier failure model without modifying `audit_trail.py` at all, and **without** routing through the `Intent`/`AdapterBase`/`ResolutionGate` machinery. That last point is the design decision: that machinery models a GUI platform with an install-detection question ("is WhatsApp Desktop installed, shall I install it?"). RHINAL is an MCP subprocess against a hosted API — either configured or not, and "install it for you" is not a coherent offer. Dressing an MCP call as a GUI intent purely to reach the audit code would make the routing layer lie about what kind of thing it is. Placed in a new module because this is *call-site policy* (what to emit, in what order, what to do when emission fails), not storage or record shape — the same separation that keeps `UIExecutor`'s version in `ui_executor.py`.

**The ordering decision, and the evidence for it.** Two records per write — `attempted` before the call, outcome after — diverging from `UIExecutor`'s single post-hoc record. **Verified against the real client rather than argued from principle:** `rhinal_mcp_client.py` raises the same `RhinalCallError` at line 142 (`"Could not reach Rhinal"`) and line 146 (`"Rhinal reported an error"`). A failure return therefore does **not** prove nothing was written remotely — an accepted-then-timed-out write is indistinguishable from a rejected one. The only claim this process can honestly make is "at time T we attempted to send this"; the outcome record is JARVIS's *view*, which can be wrong. Post-only additionally loses the write entirely in the realistic case where content reaches the vault and the process dies before the audit line — D15's hole in miniature. An `attempted` record with no following outcome record is itself meaningful: it means the process did not survive the call.

**Known limitation, recorded rather than hidden.** The two records are paired by adjacency plus identical who/what/why/source, not a correlation id — `emit_clinical_action()`'s field set is fixed, and hand-rolling a second copy of the DEC-002 record shape through `append()` would be worse. Adjacency holds *today* for a checked reason: this call site is reachable only from `_conversation_loop`, which is strictly one-command-at-a-time and synchronous. If a concurrent or queued dispatch path is ever added, a correlation id becomes necessary and needs an additive field on `emit_clinical_action()`. Flagged so that becomes a decision rather than a rotting assumption.

**A test-quality problem fixed as part of this, not left standing.** `tests/test_rhinal_dispatch.py` previously **mirrored** the dispatch branch's logic inside the test file rather than calling it. A mirror can pass while the shipped branch is broken — the wrong property for anything, and specifically wrong for the audit path of an external write. The branch body was extracted to a module-level `handle_rhinal_capture()`, the mirror deleted, and the test now exercises the real function; its five original assertions consequently also pin that the audit wiring changed no physician-facing response.

**Field values, each chosen rather than defaulted** (justified in-code): `what_adapter="rhinal_mcp"` (deliberately not shaped like a `platform_adapters/` registry key, so a reader cannot mistake it for a GUI adapter driving a window); `what_action="rhinal_capture"` (the real MCP tool name from RHINAL's `index.ts` — externally verifiable, not a JARVIS-side paraphrase); `what_target="rhinal_vault"` (the destination, deliberately **not** the captured text, which would duplicate clinical-adjacent content into a second field of the same record); `why=text`; `source="voice"` passed explicitly because it is checkable here and is the one line that must change if Stage 1c routes a typed channel in; `who` left to `getpass.getuser()` with a comment stating what it can mean (the OS account) and cannot (a verified physician — and note the *vault side* attributes the write to whoever owns the `rhk_` key, which need not be the same principal). The pre-record uses `outcome_ok=None`, not `False` — at that point the outcome is genuinely unknown, and `False` would read as "it failed."

**Honest consequence flagged, not silently accepted:** because `why` is the utterance and the utterance for "remember that X" *contains* X, the audit log now holds a copy of every captured thought. That is a property of the DEC-002 record shape (which already logs dictated message bodies for `send_message`), not something this branch decided — but if that shape ever grows a redaction policy, this call site should be its first customer.

**Verification.** 13 new tests (`tests/test_rhinal_capture_audit_wiring.py`) covering: both records with their exact field values; the `attempted` record written before anything reaches the wire; a configuration-class audit failure blocking the write with the client never called; a non-`KeyConfigurationError` not blocking; transient audit failure not blocking and warning aloud; the could-not-even-queue case flagged more urgently; emission raising outright not breaking the capture; failed vault writes audited with the failure outcome; an unexpected exception type never reported as a save; the empty-`capture_text` clarification prompt emitting nothing (a non-event is not an action); and `TestAgainstTheRealAuditLog`, which mocks nothing on the audit side, runs the real `AppendOnlyAuditLog`, reads both entries back from disk, and asserts all six DEC-002 fields plus `attempted.seq < completed.seq`, `completed.prev_hmac == attempted.hmac`, and `verify_integrity()`. That test doubles as the negative control — no-op wiring would produce zero entries.

**Independent verification, per protocol.** This work was implemented by a separate agent; I reviewed `mcp_audit.py` and the full `jarvis.py` diff directly, and independently confirmed the load-bearing `RhinalCallError` claim against `rhinal_mcp_client.py` rather than accepting the report. The agent's own report explicitly does not get a vote.

---

### D17 — a rescanner test that cannot pass when `_installed_map()` is slow *(found, logged, NOT fixed)*
**Status: 🟡 OPEN.** No commit — a finding.

`tests/test_onboarding.py::TestPeriodicAvailabilityRescanner::test_calls_refresh_repeatedly_on_interval` failed in a full-suite run. Diagnosed rather than retried: `PeriodicAvailabilityRescanner._run()`'s loop body is `refresh()` then `_write_scan_cache()`, and **`_installed_map()` measures ~0.97s even when the checker is a `Mock`** (timed directly). The test sets `interval_s=0.1`, sleeps `0.45`, and asserts `call_count >= 2`; one iteration costs ~1.07s, so exactly one can complete. The test assumes an instant loop body and the implementation does not have one.

**Established as pre-existing, not assumed.** Ran it on a clean `HEAD` worktree: fails 3/3 there, 5/5 on the working branch, identically. Not caused by this run. It is environment-timing-dependent — it passed in earlier full-suite runs the same day, which is exactly why "it passed before" is not evidence of anything here.

**Not fixed — out of this run's declared scope.** Worth noting for whoever picks it up that there are two different fixes and only one is about the test: make the assertion poll for the count against a deadline instead of a fixed sleep, *or* ask why a background tick costs ~1s of work at all. The second is the more interesting question and concerns the rescanner's real cost, not its test.

---

### Boundary Ledger scope — the JARVIS-internal vs. hospital-wide ambiguity, resolved
**Status: ✅ RESOLVED (documentation only, no code).** Blueprint v3.7. Risk tier: none — a wording reconciliation of an already-designed component that has not been built.

**The ambiguity, as found.** The v3.6 review surfaced that the blueprint described what read as two different systems under one name. §Stage 0.5's bullet: *"log every case where a **deterministic rule** was wrong or ambiguous on real clinical input"* — JARVIS-internal, machine-detectable, a symbolic-vs-learned boundary map. The v3.0 reframe two paragraphs below: *"a record of exactly where **hospital software** fails to complete an action"* — hospital-wide, physician-reported, a Commit Gap dataset. Different capture mechanisms, different datasets, and an unresolved question about which one S05-E3 must actually contain.

**Resolution: capture broad, classify downstream.** They were never two systems.
- **At capture time the ledger is a flight recorder** — it records every observed completion failure, undifferentiated, with no fault attribution. The reason this is right rather than merely convenient: attributing fault *is* the analysis the ledger exists to produce, and it cannot be performed reliably in the moment by a physician mid-OPD. Asking "was this JARVIS's fault?" at capture would both slow capture below the three-second budget the dataset's existence depends on and bias the data with a snap judgment.
- **Classification happens at analysis time**, in Adaptive Adapter Generation's trigger logic (§4.4b), which separates *fixable by us* (an unreachable HMIS field, a broken UI path, a rejected format → adapter-generation candidates) from *not fixable by definition* (a colleague not responding, a stockout, a doctor deferring a decision).

**The consequence worth stating, because it is easy to get backwards:** a not-fixable-by-us entry is **not noise to be filtered out.** It is exactly the operational-bottleneck evidence the Stage 2 COO buyer wants and that no competitor has. Both classes stay in the ledger permanently; only one class routes to code generation. Getting this backwards would point a code generator at problems no code can solve *and* discard the data that makes the ledger commercially interesting.

**Applied in three places** so the document no longer contradicts itself: §Stage 0.5's ledger bullet (broadened, with the resolution stated), the v3.0 reframe language (now "where *the work stops* — whether the thing that stopped it was hospital software, JARVIS's own rule, or a human dependency"), and §4.4b's Adaptive Adapter Generation trigger (now explicitly named as where the downstream split lives). The NORTH STAR's one-line description was also widened from "software failing to complete an action" to match.

---

### Model benchmark scanner — advisory tooling for the adapter-generation model slot
**Status: ✅ BUILT.** `AgentCore/model_scanner/`, design note `docs/model_benchmark_scanner.md`. Risk tier: low — a read-only, network-fetching CLI with no write path into any config and no clinical data in scope.

**Data classification stated before implementation, per §3.7b's own rule.** Classified **`general`**, and the design note argues it field by field rather than asserting it: one unauthenticated GET to a hardcoded allow-list of benchmark URLs, no body, no caller-supplied input forwarded anywhere, no code path by which patient data / an `Intent.source_text` / queue or ledger content can reach it. **The classification is a property of the tool's shape, not a promise about its use** — which is the standard §3.7b actually demands. The named drift risk (a convenient network fetcher getting reused for something that *does* carry clinical context) is structurally guarded: the package exposes no general-purpose fetch helper, and `fetch_raw()` raises on any URL outside the allow-list, verified by test.

**Source: real and checkable, not scraped guesswork.** The Aider polyglot coding benchmark's `polyglot_leaderboard.yml` — a versioned YAML file in a public git repo, stable ~24-field schema, per-entry `date` and `commit_hash`. Verified live before building, not assumed. On an unreachable source the tool **fails and exits non-zero**; there is deliberately no cached-or-hardcoded fallback, because a plausible ranking built from substituted data is worse than none — the reader cannot tell the difference. Same fail-closed shape as `secure_key.resolve_key()`.

**Two timestamps, deliberately — and the reason turned out to be live, not hypothetical.** A single "last checked" satisfies the letter of the staleness discipline and misses its point: it reports when *we fetched*, not how old the *data* is. Every rendering shows both, plus an explicit staleness warning past 90 days. **On the first real run the newest measurement in the source was 313 days old** (newest entry `2025-10-03`, fetched 2026-08-12) — exactly the case a single fetch-time timestamp would have concealed behind "checked: just now."

**Cloud vs. open-weights by explicit table, never inference.** The source carries no licensing flag. Inferring from model names was considered and rejected under the standing "read the source, never infer a contract from an identifier name" rule (earned from `GeneratorHelper`/`LLMAdapter` and `vaultWorthy`). An explicit `LICENSING_RULES` map carries a stated basis per family; anything absent renders in a third `unclassified` section rather than being guessed into a bucket.

**A real misclassification caught by running against live data rather than fixtures.** The entry `DeepSeek R1 + claude-3-5-sonnet-20241022` — an architect/editor *pairing* — was landing in OPEN_WEIGHTS purely because `"deepseek"` is a longer token than `"claude"` and won the length-ordered match. Token length is a tie-break heuristic with no business deciding licensing, and a pairing containing a hosted model cannot be run locally, so that label would have actively misled the one decision this tool informs. Combination entries now classify as `unclassified` with a basis explaining that licensing is per-model, not per-row. Kept as a named regression test. **This is the argument for running new tooling against its real source before trusting it** — the fixture-based tests all passed while this was wrong.

**Verification.** 17 tests (`AgentCore/model_scanner/tests/`): ranking order, headline-vs-fallback pass-rate selection, entries with no measurement skipped rather than defaulted to zero (a missing measurement is not a measurement of zero), empty/malformed/non-list source all raising rather than reporting an empty ranking as a result, the allow-list refusal, honest failure on an unreachable source, section splitting, the combination-entry regression, and the staleness property tested as *data* age rather than fetch age. Plus one live-source test that skips cleanly when the network is unavailable, mirroring the SerpApi live-test convention.

**Explicitly out of scope, stated in the design note so it cannot drift:** it does not benchmark anything itself, does not rank by cost/speed/context, has no apply verb, and **must not be cited on the own-vs-adopt question for the coding engine.** That question is undecided; a list of available third-party models is not evidence for adopting one, since it would equally inform a decision to own.

---

### UIAudit log-directory test isolation
**Status: ✅ CLOSED.** Commit `61b06c66` on `phase-2-adapter-wiring`. Risk tier: low — mechanical, no design decision. Flagged during the D14 phase, fixed here as its own phase.

**The defect.** `UIAudit.log_dir` was hardcoded to `Path("data/ui_actions")`, and `__init__` mkdir's it eagerly, so every test constructing a real `UIAgentMain` wrote real files into the actual repo directory on every run. Now honors `JARVIS_UI_ACTIONS_LOG_DIR` — same mechanism and naming shape as DEC-002's `JARVIS_CLINICAL_AUDIT_LOG_DIR` — with an autouse fixture in a new `AgentCore/ui_agent/tests/conftest.py`.

**A flaw in my own previous phase, found and fixed here rather than left standing.** `test_ui_audit_key_resolution.py` (written in the D14 phase, one phase earlier) set `audit.log_dir` *after* construction — too late, since `__init__` had already mkdir'd the real path. **Those tests were themselves creating the directory they existed to avoid.** Rewritten to redirect via the env var, which happens before construction and actually works. Worth recording as its own instance of a recurring shape: the D14 phase also caught the `JARVIS_INSECURE_DEV_KEY` fixture writing real key files into the repo. Two consecutive phases, same class of mistake — a test-isolation mechanism that looks correct and silently isn't.

**Verified by timestamp, not assumption.** Captured `Data/ui_actions/` before and after a full `AgentCore/ui_agent/tests/` run (21 passed): `audit_20260811.jsonl` unchanged at 21046 bytes, no new files created. Added 2 tests covering the isolation mechanism itself (`TestUiAuditLogDirIsolation`) — a fixture that silently stopped working would otherwise return this subsystem to writing into the repo with nothing failing. Also fixed `test_ui_fallback_unknown_app.py`'s hardcoded `"data/ui_actions/"` assertion, which would have degraded silently to its "directory not found" warning branch.

**Full suite: 495 passed, 1 skipped, 1 failed** — the failure is the known pre-existing `pyautogui` fail-safe flake documented in the DEC-002 entry below, unrelated and unmodified.

---

### D15 — DEC-002's audit trail does not cover two live handlers *(found, logged, NOT fixed)*
**Status: 🟠 OPEN.** No commit — this is a finding, not a fix.

**How it was found.** An independent design review of Stage 0.5 (run as a separate agent against the canonical docs and the real code) surfaced it as a side observation. **Confirmed directly against `jarvis.py` before logging** — not taken on the reviewer's word, per the standing rule that a report about code is not evidence about code.

**The finding.** `jarvis.py`'s dispatch chain checks `intent.handler == "code_engine"` (line 883) and `elif intent.handler == "rhinal_capture"` (line 895), calling each subsystem directly. Neither constructs a `daemon.intent_parser.Intent`, so neither reaches `UIExecutor.execute_intent()`, so **neither emits a DEC-002 audit record.** `rhinal_capture` performs a real write to the physician's external Rhinal vault with no audit trail; `code_engine` writes code to disk, likewise.

**The honest reading of DEC-002's own claim.** "The single pre-adapter chokepoint every `Intent` passes through" is *literally true* — every `Intent` does pass through it. It is also misleading, because these two handlers never become `Intent`s. The variable is even named `intent` at those call sites, but it is an `IntentResult` from `IntentRouter.classify()`, a different type. **The architecture is not wrong and DEC-002 is not reopened; the coverage claim was broader than the code supports, and has been narrowed in blueprint §4.1 accordingly.**

**Why it was not fixed on discovery.** It revises a prior closure claim — explicitly a hard stop under the standing instruction. There is also a real design question inside it, not a mechanical swap: should a non-GUI MCP handler be forced through an `Intent`/adapter path built for GUI platforms with install-detection semantics (the `rhinal_capture` branch's own comment explains why it deliberately isn't), or should those branches emit `emit_clinical_action()` directly? Both are defensible; picking one silently while "closing D15" would be exactly the drift this project's rules exist to prevent.

---

### D14 (second half) — `ui_agent/utils/ui_audit.py`'s hardcoded-default HMAC key
**Status: ✅ CLOSED.** Commit `4ca05bfb` on `phase-2-adapter-wiring`. Risk tier: low — mechanical, no design decision, the third application of an already-twice-proven pattern (D2, then DEC-002's `LearningAuditLog` rework).

**The defect.** `UIAudit.__init__` read `os.environ.get("JARVIS_HMAC_KEY", "JARVIS_UI_SECRET")` — the identical hardcoded-default-key weakness D2 fixed, D14 first named it here alongside `learning_system/audit_log.py`. The one real call site, `ui_agent_main.py:36` (`self.audit = UIAudit()`), never passed a key, so every real deployment silently signed with the literal default unless `JARVIS_HMAC_KEY` happened to be set.

**Fix.** Routed through `AgentCore.secure_key.resolve_key()`, same fail-closed contract as D2/DEC-002. Own purpose namespace (`"ui_audit"`/`JARVIS_UI_AUDIT_KEY`) rather than sharing `JARVIS_HMAC_KEY` with `mode_manager/audit.py` — collision would mean one env var silently governing two unrelated audit trails' keys.

**A real behavior change, verified rather than assumed safe.** The one real call site (`UIAgentMain`, exercised by `AgentCore/ui_agent/tests/test_agent_smoke.py`) has no key configured in the test environment, so this fix means it now falls through to the real OS keyring on every run — it never touched the keyring before this fix. Directly verified this still passes (`test_agent_smoke.py::test_ui_agent_smoke` — PASSED), same automatic generate-and-reuse behavior D2's operational note already documented for `memory_store.py`/`mode_manager/audit.py`.

**Verification.** 4 new tests (`AgentCore/ui_agent/tests/test_ui_audit_key_resolution.py`): fail-closed construction when no key source resolves (keyring forced to fail via mock, `KeyConfigurationError` raised, `UIAudit` never constructed); a real construct→sign→write→read-back→independently-recompute-and-compare round trip against a real key; two different real keys producing two different signatures for the identical entry (confirms the key is actually load-bearing in the signature, not decorative); and a direct regression guard confirming the retired `"JARVIS_UI_SECRET"` literal no longer produces a matching signature against a real-key-signed entry. Full suite: **494 passed** (490 + this phase's 4), **1 skipped** (SerpApi live test, expected), **0 failures**.

**A separate, pre-existing finding surfaced while writing these tests — flagged, not fixed here.** `UIAudit.log_dir` is hardcoded to `Path("data/ui_actions")` with no test-isolation path, so every test that constructs a real `UIAgentMain` (`test_agent_smoke.py`) writes real files into the actual repo. Confirmed via file timestamps this predates this phase (files dated 2026-07-29 through 2026-08-11 already present before any work in this phase began) — unrelated to the key-resolution weakness this phase fixed, not made worse by it. Own phase when scheduled — same shape as the `JARVIS_CLINICAL_AUDIT_LOG_DIR` isolation DEC-002's `tests/conftest.py` fixture needed, but a different subsystem, needs its own fixture.

---

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

### S0-E9 — Tier-1 inference wins: streaming, warm-up, task-aware token budgets
**Status: ✅ CLOSED.** Commit `bc83d7ec` on `phase-2-adapter-wiring`.

**Real numbers measured live before building anything (2026-07-30), not assumed from the blueprint's description of the problem.** Cold Ollama call: 10.4s. Warm call (same model, already loaded): 2.8s -- a real ~7.6s tax on whatever request happens to arrive first. A real `chat_stream()`-shaped answer's first chunk arrived at ~2.3s vs. 23.7s for the full response.

**What was found before building.** `generate_stream()` (`llm_engine.py:161`) was real, working code -- but wraps `/api/generate` (single prompt). jarvis.py's actual live conversation loop calls `LLMEngine.chat()` (multi-turn message history via `/api/chat`), a structurally different endpoint. Streaming `generate()` alone, as the blueprint's work-item text literally said, could not have reached the path that needed it -- confirmed by reading `jarvis.py`'s real call site before writing anything, not assumed from the method existing. Built `chat_stream()` as `chat()`'s streaming counterpart instead.

**Warm-up: a design correction made before shipping, not after.** First draft defaulted `LLMEngine.__init__(warm_up=True)`. Caught before committing: dozens of call sites construct `LLMEngine()` across this codebase (tests, `code_engine`, `level6`, one-off CLI utilities) -- defaulting warm-up on would add a real blocking network call to all of them, not just the one live conversational path this is meant to help. Changed the default to `False` and wired `warm_up()` explicitly, once, at `jarvis.py`'s real service-startup site, on a background thread so it doesn't block the rest of startup (already ~16s against the <3s target, D3).

**Token budgets.** `generate()` already accepted `max_tokens` (existing callers vary 50-200 -- confirmed by reading every call site: `rag_engine.py` passes 200, `AgentCore/pipeline/intent_router.py` passes 50, several others use the 256 default). `chat()` had no such parameter at all -- hardcoded to the class default unconditionally. Since `chat()` is the main jarvis.py conversation loop's only real caller, this was the actual task-aware gap, not a general "add token budgets" task. Added the parameter with the same clamping behavior `generate()` already had.

**Wiring into the live path.** `jarvis.py`'s "Standard LLM response" branch now calls a new `_stream_and_speak_chat()` method: streams `chat_stream()`, speaks each completed sentence as it arrives via `self._speak()`, and sets a `spoken_already` flag so the shared end-of-loop `self._speak(response)` (used by every other dispatch branch) doesn't speak the same answer twice. Sentence-level, not token-level -- speaking mid-word fragments as raw tokens arrive would sound worse than the existing flat TTS voice, not better.

**Adversarial finding, fixed in this same phase rather than logged for later.** Live-tested the sentence-splitter against a domain-relevant adversarial input and found a real bug: naive punctuation-based splitting broke `"Dr. Smith will see the patient at 3pm."` into `"Dr."` + `"Smith will see the patient at 3pm."` -- a bad failure mode specifically because "Dr." is about as common a token as a physician-facing voice product will ever speak. Fixed with a bounded abbreviation guard (`dr, mr, mrs, ms, prof, sr, jr, st, vs, etc, e.g, i.e, approx`) checked against the last word before each candidate sentence boundary. Deliberately excluded "no" and "fig" from the set after tracing through a counter-case (`"Call the front desk. No. Call the lab instead."`) -- both are common standalone sentence-starters in ordinary conversation, and including them would trade a rare abbreviation-splitting glitch for a more common false suppression of a real one-word sentence. Live-verified against real (not canned) LLM output containing both "Dr. Smith" and "Mrs. Johnson" -- both spoken correctly as whole sentences.

**Verification (adversarial, not just the happy path).**
- 19 new tests (`tests/test_llm_streaming.py`): warm-up gating in all three states (off by default, on when requested and available, skipped when requested but unavailable), `chat()`'s new token-budget parameter and its ceiling clamp (unchanged from `generate()`'s existing behavior), `chat_stream()`'s chunk yielding and system-message prepending, and the sentence-buffering logic tested directly against `jarvis.py`'s real `PersistentWakeService` class (constructed via `__new__` to skip the heavy `__init__`, not a mirrored copy of the logic) -- including the "Dr.", "St. Mary's" (must NOT wrongly split), and "No." (must still split, the abbreviation guard's own limit) cases.
- **Real end-to-end before/after measurement on the actual jarvis.py code path**, not a synthetic microbenchmark: old blocking `chat()`-then-speak took **34.04s** to first spoken word on a real 3-sentence question; new streaming + sentence-buffered speech took **9.87s** -- **24.17s faster**, live-measured, not estimated from the smaller streaming-only numbers above.
- Full suite: **434 passed, 4 failed** (unchanged D11 baseline, none of those files touched this phase), **1 skipped** (live SerpApi test).

**What this phase did not do, on purpose.** Did not touch D3 (import time, ~16s) or GPU config -- both explicitly separate items in the blueprint's own work-item list, not part of "streaming, warm-up, token budgets." Did not build or evaluate the §3.7b capability/confidence router -- the blueprint's own sequencing table says to re-measure latency after these three items before considering routing, which is exactly what the 9.87s number above is for; whether that number is fast enough to keep deferring router work is the project owner's call, not decided here.

---

### D5, D6, D11, D12, D13 -- the five cheap, no-design-decision defects, batched
**Status: ✅ ALL CLOSED.** Commits `8ce7f044` (D5), `fb332247` (D6), `21c37832` (D11), `54a86665` (D12), `6053c942` (D13). Run consecutively per instruction; reported together here.

**D5 turned out bigger than the blueprint named.** It cited only `Brain/brain.py`. A repo-wide grep before touching anything found the identical hardcoded `C:\Users\chatu\...` pattern live in three more files -- `Features/clap_with_music.py`, `Time_Operations/throw_alert.py`, `ui.py` -- none named in the blueprint. Flagged explicitly rather than either silently fixing only the one named file (leaving the defect demonstrably still live elsewhere) or silently expanding scope without saying so. All four fixed: the `Brain/brain.py` and `throw_alert.py` occurrences were both inside genuinely dead code (a fully commented-out block, and a module-level constant shadowed by a same-named parameter and never imported by any real caller, respectively) -- deleted outright. `clap_with_music.py`'s occurrence is a live call site but the function itself (`clap_to_music()`) is confirmed unreachable from anywhere else in the codebase -- fixed the path to be portable regardless. `ui.py`'s occurrence was a second, distinct bug on top of the hardcoded path: `os.path.join(current_directory, r"C:\...")` silently discards `current_directory` entirely when the second argument is an absolute Windows path, so it never used the "current directory" the surrounding comment claimed -- and pointed at a `main.py` that doesn't exist anywhere in this repo (`ui.py` itself is unreachable, nothing imports it). Fixed to reference `jarvis.py`, this project's real entry point, with a correct relative join.

**D6.** `generate()`/`chat()` in `AgentCore/llm_engine.py` shelled out to `curl` via `subprocess.run` for Ollama's HTTP API, in the same file that already used `requests` correctly for `generate_stream()`/`chat_stream()` (S0-E9). Switched both to `requests.post()`. Left `_check_ollama()`'s `subprocess.run(["ollama", "list"])` alone -- that's a CLI binary check, not an HTTP call, outside D6's stated scope. Live-verified against the real Ollama backend post-fix: `generate()` and `chat()` both still produce correct real responses.

**D11.** All 4 pre-existing failures (already provenance-checked as dead-since-`dbef62f8` during S0-E1) fixed for real, not just re-confirmed dead. `CodeEngine.policy` → `.config` (the real attribute). `test_auto_write`'s `open(result["file_path"])` → opens the actual file written inside that sandbox directory. `test_audit_log_created`'s `"hmac_signature"` → `"sig"` (traced into `AgentCore/mode_manager/audit.py`: `write_log()`/`verify_line()` consistently use `"sig"` on both the write and verify sides -- a working, self-consistent contract; renaming the *code* to match a stale test guess, rather than fixing the test, would have been the wrong-direction fix). All 4 now genuinely pass.

**D12.** Root-caused during S0-E2, fixed here. `GUIBackend.activate_window()`'s `pyautogui.getWindowsWithTitle()` substring-matches, which several browser-based adapters (amazon, google, gmail, youtube, twitter) deliberately rely on -- so the fix couldn't be "make matching exact everywhere" without breaking those. Added an opt-in `exclude_process_names` parameter (default `None`, zero behavior change for anything that doesn't pass it), resolving a matched window's owning process via `win32process.GetWindowThreadProcessId` + `psutil`, failing open (not excluding) if that lookup isn't possible so desktop adapters can't become *more* broken when pywin32/psutil are unavailable. Wired into both `whatsapp_desktop_adapter.py` and `telegram_desktop_adapter.py`, both `open_app()` and `close_app()` -- `close_window()` calls `activate_window()` internally too, and firing Alt+F4 at someone's Chrome window because of a title collision is a worse outcome than a false "installed" claim. Live-verified against real window state on this machine, both directions: WhatsApp's `open_app()` now correctly returns `False` (previously `True` against the Chrome "WhatsApp Web" tab); Telegram's real-app detection is unaffected, still correctly `True`. Fixing this broke 5 pre-existing tests mechanically (`FakeBackend`/mocked `GUIBackend` call-shape assertions expecting the old 1-arg signature) -- each one individually investigated and confirmed caused by this change, not assumed safe, then updated to the new real call shape.

**D13.** `IntentRouter.ACTION_PATTERNS`' `r"^search\s+(?:for\s+)?"` matched unconditionally and was checked before `QUESTION_PATTERNS`, so any "search for X" won as `handler="action"` regardless of what followed -- reproduced live before the fix against both examples the audit named. Narrowed to require an explicit action-continuation verb ("...and open/click/visit/go to..."), the actual signal distinguishing a real UI-action request from an informational one. Live-verified against the two original examples (now `llm`) plus two non-regression checks: a search with a genuine continuation clause still routes to `action`, and a platform-named search ("search amazon for shoes") still reaches the resolution gate untouched by this change.

**Full suite after all 5:** first pass surfaced one new failure (`tests/test_gui_backend.py::test_close_window_fires_hotkey_when_target_activated`) -- investigated immediately rather than assumed transient, confirmed caused by D12's signature change (a stale `assert_called_once_with("Notepad")` no longer matching the new `exclude_process_names=None` kwarg), fixed. Final run: **451 passed, 1 skipped** (the live SerpApi test, no key in this run's environment), **zero failures** -- the D11 baseline is gone because D11 itself is now fixed, not because anything was skipped or excluded. Per standing instruction: this local Windows environment has real audio hardware, so no pyaudio/portaudio gap shows up here -- expected, not a discrepancy, given the sandbox-side limitation is on a different machine's environment.

---

### D2 -- real AES-256-GCM encryption + fail-closed key resolution (memory_store.py, mode_manager/audit.py)
**Status: ✅ CLOSED.** Commit `6e508780` on `phase-2-adapter-wiring`. Risk tier: medium, per instruction -- built and verified, then stopped and reported before pushing, the one deliberate exception to the continuous-run loop this cycle. Pushed and confirmed from the remote object in a separate turn after review.

**Checked before writing any code, not assumed.** Read every real `MemoryStore()` call site (`feedback_engine.py`, `optimizer.py`, `session_memory.py`) -- none passes a custom `encryption_key`; all three silently relied on the hardcoded `"jarvis_default_key"` default. Also checked for existing on-disk data under the old scheme: none exists anywhere in this repo/environment (`data/memory/` doesn't exist, `state/memory/backups/` is empty) -- confirmed the migration path is currently untested-by-necessity in this environment and had to be verified with deliberately-constructed synthetic legacy data instead.

**Escalated the three-way key-management/storage/migration question rather than deciding it inline**, per standing instruction that this class of decision is a hard stop. Got an explicit, detailed spec back rather than picking a design myself:

- **Key source: three explicit, non-fallback-chained options**, never silently degraded from one to another. `JARVIS_INSECURE_DEV_KEY=1` (dev-only, file-based, loud warning every startup) → an explicit `JARVIS_MEMORY_KEY`/`JARVIS_HMAC_KEY` env var (honored, logs loudly that it's non-default) → OS keyring by default (Windows Credential Manager via `keyring`, generated once). A keyring failure is a hard startup error -- confirmed live via a forced `keyring.get_password` failure that this does **not** fall through to the env var or file path.
- **Fail-closed, confirmed both ways:** no key source configured *and* keyring unavailable → `KeyConfigurationError`, no `MemoryStore` gets constructed at all. Live-verified this never silently substitutes the old hardcoded default.
- **Both files fixed together**, sharing one implementation (`AgentCore/secure_key.py`) rather than two separately-maintained copies of the same security-critical logic -- `memory_store.py`'s AES-GCM key and `mode_manager/audit.py`'s HMAC key both resolve through `resolve_key()`.
- **Migration, required and verified, not just built:** legacy XOR data (no format marker -- the only shape pre-D2 files could have) is decrypted with the one key it could ever have used, re-encrypted under AES-GCM, round-trip-verified, backed up to `.xor-backup.json`, and only then does the live file get overwritten. Tested live with deliberately-constructed synthetic legacy data (since none exists in this environment) -- migration succeeded, backup was written, reload didn't re-migrate. **Adversarial case, per instruction:** a deliberately-corrupted legacy record raises `MemoryStoreMigrationError` and leaves the original file completely untouched -- no backup written, no partial state, confirmed by reading the file back byte-for-byte identical to before the attempt.

**A real finding from my own adversarial testing, fixed in-phase rather than shipped with the gap.** First version of `_load()` wrapped the AES-GCM decrypt call in the same broad `except Exception: print(...)` used for genuinely malformed files. Writing the "wrong key raises" test caught that this silently produced an **empty store** instead of an error -- a wrong key became indistinguishable from "nothing was ever saved." That's a worse failure than XOR itself in one respect: at least XOR-with-a-known-key was *readable*; a swallowed decrypt failure hides that real data exists and can't currently be read. Restructured `_load()` so decryption failures on the current format propagate (confirmed: raises the real `cryptography.exceptions.InvalidTag`, not a generic exception), while genuinely malformed/unreadable files keep the pre-existing soft-fail behavior.

**Scope note, flagged rather than silently expanded or silently dropped.** Checking for other `JARVIS_HMAC_KEY` consumers while fixing `mode_manager/audit.py` surfaced the identical hardcoded-default-key pattern in two more files: `AgentCore/learning_system/audit_log.py` (`os.environ.get('JARVIS_HMAC_KEY', 'jarvis-learning-audit-default-key')`) and `AgentCore/ui_agent/utils/ui_audit.py` (same env var, different literal default). Both confirmed live/reachable via their respective package `__init__.py`/main modules. Neither is on the path any real clinical-data write goes through today, so neither gates Stage 0.5 the way `memory_store.py`/`mode_manager/audit.py` did -- but leaving the identical weakness live in two more places while calling D2 "closed" would be the same category of gap as D5's original narrow scope. Logged as **D14**, not fixed here; this phase was already large.

**Verification.** 29 new tests across 3 files: `test_secure_key.py` (9 tests, including 3 run against the real Windows Credential Manager, not mocked -- confirmed live that this machine's keyring backend is `WinVaultKeyring`), `test_memory_store_encryption.py` (9 tests: real round-trip with a real generated key, the wrong-key/silent-empty-store regression above, and the corrupted-legacy-record hard-stop), `test_audit_key_resolution.py` (3 tests). Updated `test_mode_engine.py`/`run_mode_sim.py`'s env-var key setup for the new base64/dev-key contract -- plain strings like `"testkey"` are no longer valid, by design. Full suite: **472 passed, 1 skipped, zero failures.** Confirmed from the pushed remote object (`git show origin/phase-2-adapter-wiring:...`), not local state: `resolve_key()` and `AESGCM` are live in `memory_store.py`; `dev_insecure_key_default` no longer appears anywhere except an explanatory comment in `audit.py`.

**Operational note.** All keyring entries created during live testing (`jarvis`/`memory_store_key`, `jarvis`/`test_purpose_key`) were deleted after each test to avoid leaving artifacts in the real Windows Credential Manager. On first real use, `memory_store.py` and `mode_manager/audit.py` will each generate and store their own real key in the keyring automatically -- no manual setup required for the default path.

---

## Defects added to blueprint §1.6

| # | Defect | Severity | Detail |
|---|---|---|---|
| **D11** | 4 pre-existing test failures, dead since initial commit `dbef62f8` | 🟡 Low | Full detail in the S0-E1 section above. Not regressions — dead scaffolding. Fixes are cheap (delete/rewrite dead tests, fix wrong dict key `sig` vs `hmac_signature`, fix `file_path` returning a directory) and involve **no design decisions**. Deliberately logged, not fixed — was outside S0-E1's scope. |
| **D12** | Window-title/installed-app detection false positive on PWA shortcuts | 🟠 Medium | First surfaced in `31939c8`'s own commit message for `AvailabilityChecker` (installed-check matched a WhatsApp Web PWA shortcut). Independently reproduced and root-caused live during S0-E2's close-out: `GUIBackend.activate_window()`'s substring match also fools `WhatsappDesktopAdapter.open_app()`'s own success signal directly, confirmed via `Get-Process`/`Get-AppxPackage`. Telegram unaffected — confirmed to be the real app on this machine. Affects the resolution gate's "not installed" branch accuracy *and* the adapter's own reported success. |
| **D13** | `IntentRouter` misroutes "search for X" informational phrasings to `action` instead of `llm` | 🟡 Medium | e.g. `"search for the definition of recursion and explain it"`, `"search for python tutorials"` — both currently misclassified. Found during S0-E1's conversational-layer audit, reconfirmed live against the current `classify()` at close-out. Live-path bug (not dead scaffolding, unlike D11) — logged, not fixed, out of S0-E1's declared scope. |
| **D14** | Same hardcoded-default-key weakness D2 fixed, unfixed in two more files | 🟠 High | `AgentCore/learning_system/audit_log.py` and `AgentCore/ui_agent/utils/ui_audit.py` both read `JARVIS_HMAC_KEY` with a hardcoded literal fallback, identical shape to D2's `memory_store.py`/`mode_manager/audit.py` before the fix. Both confirmed live/reachable. Found while auditing D2's real callers; not fixed there — neither file is on a path any real clinical-data write goes through today, so this doesn't gate Stage 0.5 the way D2 did. Fix is mechanical: swap each for `AgentCore.secure_key.resolve_key()`. |

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
| **S0-E9** — Tier-1 inference wins | ✅ CLOSED (`bc83d7ec`) | See the closed-item entry above. 9.87s to first spoken word is the new baseline for the §3.7b re-measure-before-routing decision -- decision itself not made here. |
| **D11** — 4 dead tests | ✅ CLOSED (`21c37832`) | See the batched D5/D6/D11/D12/D13 closed-item entry above. |
| **D12** — window-title/`AvailabilityChecker` PWA false positive | ✅ CLOSED (`54a86665`) | See the batched entry above. |
| **D13** — `IntentRouter` search-phrase misroute | ✅ CLOSED (`6053c942`) | See the batched entry above. |
| **D5** — hardcoded `chatu` paths | ✅ CLOSED (`8ce7f044`) | Turned out to be 4 files, not the 1 the blueprint named — see the batched entry above. |
| **D6** — `curl` subprocess in `LLMEngine` | ✅ CLOSED (`fb332247`) | See the batched entry above. |
| **D2** — XOR encryption / hardcoded default key | ✅ CLOSED (`6e508780`) | Real AES-GCM + fail-closed key resolution, both `memory_store.py` and `mode_manager/audit.py`. Stage 0.5's real-clinical-data gate is clear. See the closed-item entry above. |
| **D14** — same weakness, 2 more files | ✅ CLOSED (`b338c4fb`, `4ca05bfb`) | `learning_system/audit_log.py` fixed as a byproduct of DEC-002; `ui_agent/utils/ui_audit.py` fixed in its own dedicated phase. See the closed-item entries above/below. |
| **D15** — `code_engine`/`rhinal_capture` unaudited | ✅ CLOSED (split) | `code_engine` owner-confirmed intentional (build infrastructure, not a gap); `rhinal_capture` was the real half, split to D16 and fixed. See the closed-items section above. |
| **D16** — `rhinal_capture`'s vault write unaudited | ✅ CLOSED (`64055a1b`) | `AgentCore/mcp_audit.py`'s `audited_mcp_write()`, reusable for the other 13 RHINAL tools. Two records per write; see the closed-item entry for why. |
| **D18** — Level6 sandbox was not a sandbox | ✅ CLOSED | AppContainer + restricted token + job object + provisioned interpreter. Independently re-verified by the reviewer with a control arm, not accepted from the implementing pass. See the closed-item entry above. |
| **D19** — sandbox has no supply-chain integrity | 🟡 PARTIALLY CLOSED (v3.11) | Drift/tamper half closed: `adapter_sandbox_provisioned.lock.json` hash-pins the files actually copied from the host, `provision()` refuses on mismatch, verified against a real tampered host file. Provenance half — container-image `pip install --require-hashes` against a package index — remains 🟠 OPEN, genuinely blocked on infrastructure (no container runtime on this machine). See the v3.11 entry above for the full split. |
| **Companion app Phase 1 — scaffolding** | ✅ BUILT | `AgentCore/comm_gateway/`. See the closed-item entry above. |
| **Scoped loopback exception (`LoopbackExceptionPipe`)** | 🔴 INVESTIGATED, NOT DELIVERED (v3.11) | Works for AppContainer alone (adversarially tested); refused (`WinError 5`) against the real launcher's AppContainer+restricted-token stack, isolated to the restricted token specifically. Root cause not fully isolated. Kept in repo with both results asserted as tests rather than removed or claimed working. Do not weaken the restricted-token default to "fix" this — see the v3.11 entry above. |
| **D17** — rescanner test vs. slow `_installed_map()` | 🟡 OPEN | Pre-existing, proven on a clean `HEAD` worktree. `_installed_map()` costs ~0.97s per tick even with a `Mock`; the test allows 0.45s for ≥2 iterations. Test-only symptom, but the per-tick cost may be a real product question. |
| **Stage 0.5 design proposal** | DRAFTED, AWAITING APPROVAL | Full proposal delivered (data model + state machine, Tkinter UI shape, Boundary Ledger schema, E1/E2/E3 measurement). Not implemented. Carries 13 escalations of its own, including two prerequisites not currently met: physician access in real clinic conditions, and a pre-registered Stage 1 priority list committed *before* the physician session (without which S05-E2 is unfalsifiable and fails by default). |
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
