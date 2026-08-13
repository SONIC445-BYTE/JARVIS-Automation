# Adapter-generation sandbox — package access — design note

> **UPDATE (D18 isolation phase).** This note was written when there was no
> sandbox at all. Part of it is now built, and the parts that are not have
> changed status rather than content. Read this box before the rest of the
> document, because several sentences below are now historical.
>
> **Now genuinely enforced** (see `docs/adapter_sandbox_isolation.md`, measured
> by `AgentCore/level6/tests/test_sandbox_isolation.py`):
> - The sandbox runs a **separate interpreter** with its own site-packages,
>   provisioned from this note's vetted set. Host packages outside the set are
>   genuinely not importable — verified against PyYAML, which is installed on
>   the host and listed under `refused:`.
> - The `layer: image` / `layer: host_mocked` split from §3.1 is real:
>   host_mocked entries are generated stubs, never the real package.
> - The §6 static import check exists, fails closed before execution, and emits
>   the diagnostic block reproduced in that section.
> - **Network egress is genuinely denied**, by a capability-less AppContainer
>   (OS/WFP enforcement). §8.5's "egress is blocked at the network layer or not
>   at all" is now the former.
> - Filesystem access outside the sandbox tree is denied, so §4.4b's Secrets
>   row ("no keyring access, no `.env`, no credential paths") is enforced by
>   what the sandbox exposes rather than by instruction.
>
> **Still not built, and now the largest remaining gap:** everything under
> `image:` — the digest-pinned base, the hashed lockfile, `--require-hashes`.
> There is no container runtime on this machine and none can be installed
> without Administrator. Packages are therefore **copied from the host
> installation**, so §8.2 (supply-chain compromise at pin time) is not merely
> unmitigated — there is no pinning at all, and the sandbox's supply chain is
> exactly the host's.
>
> **Two claims below are now wrong and are corrected here rather than edited
> away:**
> - §3.2 says `requests` "can only reach loopback" inside the sandbox. It can
>   reach **nothing**; AppContainer denies loopback too, and exempting it needs
>   Administrator. That is a functional cost, discussed in the isolation note §7.
> - §0 and §8.6's "there is no container today ... none of the above is
>   running" remain literally true about the container, but the manifest is no
>   longer only "a review aid" — it is now the input to real provisioning.

> **UPDATE (D19 hash-pinning phase).** Re-read carefully, because this
> corrects a claim made in good faith above and in the D18 box: the boxed
> text says supply-chain integrity needs the container image and stops there.
> That conflated two different things. The **image's** hash-pinning
> (`image.base_digest`, `image.lockfile`, `pip install --require-hashes`
> against a package index) genuinely does need a container runtime and
> remains **not built** — nothing below changes that. But **the files
> `sandbox_env.py` actually copies from the host** can be hash-pinned without
> a container: hash them once, when a human reviews the set, commit the
> hashes, and refuse to provision if the host's copy no longer matches. That
> needs nothing but a checksum comparison, and it is now built and enforced:
>
> - `AgentCore/policy/adapter_sandbox_provisioned.lock.json` — the reviewed
>   baseline: `{package: {version, files: {relative_path: sha256}}}` for
>   every file `_copy_distribution` copies, for the full resolved closure.
> - `sandbox_env.provision()` hashes the CURRENT host state and compares
>   against this lock, before anything is built or copied, on every call
>   including cache reuse — not just cold provisioning — and raises
>   `SupplyChainIntegrityError` on any mismatch. `AgentCore/level6/tests/
>   test_supply_chain_lock.py` mutates a REAL file under the host's own
>   site-packages (not a copy) and confirms provisioning genuinely refuses,
>   then restores it.
> - **What this is not**, stated as plainly as the container gap was stated
>   above: it pins to a *reviewed host baseline*, not to a package index's
>   published hash. It has no provenance and cannot tell you the packages
>   were ever legitimate — only that they have not silently changed since a
>   human last reviewed and committed the lock. §8.2 below is corrected in
>   place rather than left to read as still fully open.

**Status:** partially built. The vetted set is enforced by a real, separate,
network-denied execution environment; the digest-pinned **image** this note
specifies does not exist and cannot be built on the current machine.
Provisioned-file **hashes are pinned and verified against a reviewed
baseline** (D19) — see the update box above for exactly what that does and
does not cover.
**Resolves:** the explicitly-unresolved design question in `JARVIS_BLUEPRINT.md` §4.4b — *"air-gapped testing (harder, requires pre-staged dependencies) versus proxied package access (convenient, demonstrably exploitable)."*
**Owner decision being made concrete:** pre-stage a fixed, vetted dependency set inside the sandbox image. Anything outside it is an explicit, reviewed-once escalation. Never open-ended live package fetching by default.
**Manifest:** `AgentCore/policy/adapter_sandbox_dependencies.yaml`.

---

## 0. What this note does not claim

The blueprint quotes Heidy Khlaaf: *"sandboxes are actually notoriously insecure."* That is still true after this change, and this note is not a rebuttal to it.

Pre-staging removes **one** escape route — the package-registry proxy that was the actual vulnerability in the 21 July 2026 incident. It removes a *route*, not a *class*. It does not make the sandbox secure, it does not make the sandbox the boundary, and it does not change the goal-hyperfocus dynamic the blueprint identifies as the underlying mechanism (§9). The primary control is unchanged and is not in this document: **action-level interception at the ResolutionGate.** Generated code executes *through* the gate. Everything below is defence-in-depth, and should be read as reducing the number of ways a bad day can start rather than preventing one.

One more thing this note cannot claim, stated up front because it changes how everything else should be read: **there is no container today.** What the project currently calls a sandbox — `AgentCore/level6/sandbox_runner.py` — is a `subprocess` running `sys.executable -m pytest` in a temp directory, under the host interpreter, against the host's own site-packages, with an advisory `JARVIS_SANDBOX_NETWORK=0` environment variable that nothing reads and nothing enforces. Until an image exists, the manifest is a review aid and the input to a static check (§6), not an isolation boundary. Saying otherwise would be describing a mitigation as a guarantee.

---

## 1. Why the decision is right, briefly, and where it costs

The incident's lesson was not "proxies are badly implemented." It was that a sandbox with a permitted egress path is a sandbox with an egress path, and the models found the one that existed rather than the one anyone was watching. A proxy is a piece of software reachable from inside the sandbox by design; a zero-day in it is a zero-day in the sandbox wall.

Pre-staging trades that for two real costs, worth naming rather than glossing:

1. **Every genuinely-new dependency becomes a human interruption.** If the set is too narrow, escalations become routine, and routine approvals become rubber-stamps — which is the exact approval-fatigue failure mode the immutable tier was introduced (v3.0) to guard against. A set calibrated too tightly does not produce safety; it produces a habit of clicking yes.
2. **The image itself becomes a thing that rots.** A pinned, hashed image with no refresh discipline is a frozen snapshot of whatever CVEs existed on pin day. "Air-gapped" is not a security property on its own; it is a property that has to be maintained.

The design below is calibrated against (1) — the set is deliberately a little wider than the strict minimum — and §4 is entirely about (2).

---

## 2. What generated adapters actually do

The set is grounded in reading `platform_adapters/`, not in guessing. What a real adapter is made of:

| What the adapter does | What it touches | Verified in |
|---|---|---|
| Subclass the contract, declare `ACTIONS` | stdlib only (`abc`, `dataclasses`, `typing`) | `adapter_base.py` |
| Activate/close a window, type, hotkey | `GUIBackend` → `pyautogui`; `win32process` + `psutil` for process identity (D12) | `gui_backend.py` |
| Find an element that has no fixed shortcut | `element_finder` → `AgentCore.ui_perception.UIScanner` → accessibility API, then OCR, then vision (§3.2) | `spotify_adapter.py`, `element_finder.py` |
| Drive a web target | `browser_automation.py` → `playwright.sync_api` | `browser_automation.py` |
| Build a URL, shell out, sleep, log | `urllib.parse`, `subprocess`, `time`, `json` — all stdlib | every adapter |
| Be verified | `pytest`, with `element_finder` mocked so no test depends on a real screen | `tests/test_phase2d_ported_adapters.py` |

Two observations that shaped the set more than anything else:

**Adapters are mostly stdlib plus one GUI backend.** The aggregate import census across `platform_adapters/*.py` is dominated by `time`, `typing`, `__future__`, and project-relative imports. Third-party surface is small. A generous vetted set would therefore not be justified by need — it would be justified by nothing.

**The existing test convention already mocks the platform layer.** The Phase 2d test file says so in its own docstring: `element_finder` is mocked "so these tests never depend on (or are slowed by) a real screen scan." This matters enormously for the image design (§3.1) — the sandbox never needed a real display in the first place.

---

## 3. The vetted set

Full entries, with per-package justification, live in `AgentCore/policy/adapter_sandbox_dependencies.yaml`. This section explains the *shape*.

### 3.1 Two layers, because the host is Windows and the image is not

This is the part that does not fall out of the obvious design, so it is worth being explicit about.

Four of the packages adapters genuinely depend on — `pywinauto`, `pywin32`, `comtypes`, and effectively `pyautogui` — are Windows-only or display-only. A Linux container cannot install `pywin32` at all. That leaves three options: a Windows container (Hyper-V-isolated on a client OS, i.e. a VM, which is a heavy ask against §3.1's ordinary-laptop constraint), a dedicated Windows VM, or something smarter.

The something-smarter is already in the codebase. `GUIBackend` imports `pyautogui` through `_optional_import`, which returns `None` on failure rather than raising — so **the adapter import graph holds together on Linux without any of these packages present.** And the test suite already supplies mock doubles for the platform layer. So:

- **`layer: image`** — installed for real, pinned and hashed: `pytest`, `requests`, `beautifulsoup4`, `lxml`, `Pillow`, `numpy`, `opencv-python-headless`, `playwright`, `psutil`. Nine packages. All install and import cleanly on `linux/amd64` with no display and no network.
- **`layer: host_mocked`** — declared in the manifest, never installed, satisfied by `unittest.mock` doubles from the harness: `pyautogui`, `pywinauto`, `pywin32`, `comtypes`, `pytesseract`, `mss`. Six packages.

The honest consequence, stated rather than buried: **the sandbox verifies adapter *logic*, not adapter *behaviour on Windows*.** A generated adapter that passes in-sandbox has had its control flow, error handling, and contract conformance exercised against doubles. Whether `pywinauto` actually finds that HMIS button is verified on the host, by the developer, outside the sandbox. That is a real limitation of this design and it should not be reported as "tested."

### 3.2 The two judgement calls

**`requests` is in, and that is arguable.** No current adapter uses it. It is an egress-shaped library sitting inside a no-egress sandbox. The reasoning for including it anyway: "the HMIS has a REST endpoint nobody wired up" is the single most likely non-GUI instance of the unreachable-system case this feature exists for, and excluding it does not remove the capability — `urllib.request` and `socket` are stdlib and always present. Excluding it would produce uglier generated code and longer reviews, in exchange for no reduction in what the code can attempt. **Criterion for overturning:** if after the first dozen real generations no adapter has needed HTTP, drop it — the cost of the escalation path is lower than the cost of a convenience nobody uses.

**`opencv-python-headless` is in, and it is the heaviest thing here by a wide margin.** Kept because the vision tier is an adopted part of §3.2's resolver, not a speculative one. Revisit if generated adapters turn out never to reach tier 3.

### 3.3 What was refused, and one refusal that is not a judgement call

The manifest's `refused:` block is machine-readable so the generator can be told these are known-refused — an escalation naming one is auto-rejected rather than routed to a human, which keeps the human's queue meaningful.

**`webdriver_manager` is a hard refusal.** It downloads browser drivers over the network at runtime. That is the live-fetch pattern this entire decision bans, resurfacing one level down — not at the proxy, but inside a dependency. It is the clearest illustration of why "no network egress" and "vetted dependency set" are two rules and not one: a vetted set containing a fetcher is not a vetted set. `selenium` goes with it.

`keyring` and `cryptography` are refused for consistency rather than for risk: the gating table already says the sandbox exposes no keyring access, and shipping the library while claiming the access is blocked is precisely the kind of gap that reads as an oversight two years later. `libcst` is refused because code-rewriting inside the thing that writes code is a step toward the self-dev mode §4.4c explicitly declined.

`PyYAML` is refused on **need**, not risk — nothing in `platform_adapters/` imports yaml. It is listed so the omission reads as a decision rather than a gap.

---

## 4. Building and pinning the image

### 4.1 Mechanism

- **Base pinned by digest, never by tag.** `python:3.12-slim@sha256:…`. A tag is a moving target; an image that drifts is an allow-list with extra steps. The manifest's `base_digest` is `null` today, and `null` means the build refuses to run.
- **Lockfile carries the full transitive closure with hashes**, generated by `pip-compile --generate-hashes`, installed with `pip install --require-hashes`. The transitive part is not optional: `pyautogui` alone drags in `PyGetWindow`, `PyScreeze`, `MouseInfo`, and `pyperclip`, none of which anyone reviews individually. `--require-hashes` refuses the whole install if *any* package in the closure lacks a hash — which is the fail-closed property we want, and it is a real pip behaviour rather than something to be built.
- **No index configured in the image, and no pip on the runtime path.** Belt and braces: even with network egress somehow available, there is nowhere to fetch from.
- **`tesseract-ocr` is a system package, not a pip package.** `pytesseract` is a thin wrapper and does nothing without the binary. The manifest names it under `image.system_packages` so a manifest listing only pip names cannot silently ship a broken OCR tier.

### 4.2 Two files, two jobs

The manifest is the **human-reviewed policy**: what may be present, and why, one paragraph per entry, reviewable as a diff. The lockfile is the **machine-enforced closure**: exact artifacts and hashes including transitives. CI asserts they agree — every direct requirement in the lock appears in the manifest, and every non-null manifest hash matches the lock. Neither file alone is sufficient: a manifest without a lock does not pin transitives, and a lock without a manifest is 60 lines of hashes nobody can review.

### 4.3 Who rebuilds, when, and what re-verifies

**Who:** the developer. Same approver as adapter generation itself (§4.4b — a clinician cannot meaningfully review this, and asking them to would be approval theatre).

**When — three triggers, all producing a reviewed diff:**
1. An approved escalation merges a new entry.
2. A published advisory names any package in the closure.
3. Scheduled quarterly refresh.

**Deliberately not a trigger: upstream base-image updates.** Auto-rebuilding when `python:3.12-slim` moves would reintroduce unreviewed change through the back door — the same shape of hole this whole exercise closed at the proxy.

**What re-verifies:** a CI check, reusing §4.4b's CI-enforced-verification entry rather than inventing a parallel mechanism. It fails the build when the image digest recorded in the manifest does not match the image the sandbox actually runs; when the lock and manifest disagree; or when any `review_by` date has passed. Two properties matter here:

- **It checks the running image, not the Dockerfile.** The blueprint's own rule — verify against the live interface, never the documentation — applies to your own build artifacts, which is exactly where people stop applying it.
- **Drift fails the build. It does not warn.** A warning about a drifted allow-list is an allow-list.

---

## 5. The escalation path

Reusing Phase 3d's existing idiom — *propose → explicit approval → versioned commit* — rather than inventing a parallel approval mechanism.

**Who reviews:** the developer. Not the physician, for the same reason adapter approval routes to the developer.

**What they see.** A generated escalation request containing, at minimum:

1. The Boundary Ledger entry IDs that triggered this generation. An escalation with no ledger provenance is not an escalation, it is a wish.
2. Package name, requested version, and the resolved transitive closure it drags in — the count and the names. Reviewers approve one name and inherit twelve.
3. The exact import sites in the draft adapter, with line numbers.
4. **What the generator tried without it.** Mandatory. An escalation with no attempted alternative is auto-rejected without reaching a human.
5. Whether anything in the closure fetches at install time or on first use. `webdriver_manager` is the worked example of why this question is asked separately.

**What makes it approvable.** All four, not any:
- It is needed by a *specific* draft adapter for a *specific* logged failure — not "adapters might want this."
- The closure it adds is bounded and reviewable.
- Nothing in the closure fetches at install or first use.
- There is no stdlib or existing-set way to do it that the generator actually tried and reported.

**Where the approval is recorded.** As a diff to `AgentCore/policy/adapter_sandbox_dependencies.yaml`, merged through the normal review workflow. **The git commit is the record.** This is worth stating explicitly because the project has an `ApprovalWorkflow` class (`AgentCore/human_loop/approval_workflow.py`) that looks like the right home and is not: it keeps approvals in an in-memory dict that does not survive the process. It is fine for in-session gating and useless as a durable record. Git already is the durable record, and Phase 3d already says "versioned commit."

**What stops an approved-once package becoming a permanent hole.** Two fields, both CI-enforced:
- `review_by:` — a date. Past date fails CI.
- `justified_by:` — the adapter that needed it. CI fails when that adapter no longer exists or no longer imports the package.

The effect is that the set **shrinks by default**. A package stays only while something still uses it and someone still re-affirms it.

**The honest weakness in that mechanism:** expiry reviews are exactly the thing that gets rubber-stamped, and a CI failure demanding a date bump is a nuisance that people learn to clear reflexively. The only real counter-pressure is that clearing it requires editing a file, writing a reason, and getting the diff reviewed — friction, not a click. That is weaker than I would like and it is the mechanism's soft spot rather than a solved problem.

---

## 6. Generation time: what happens when an import is missing

**Static check first, before anything executes.** An AST scan of the generated file's imports against the manifest, run at generation time. Two reasons this ordering matters: the developer gets a precise diagnostic instead of an `ImportError` buried in pytest output, and **this check works today, with no container.** It is the one part of this design that is buildable against the existing subprocess runner, and it is where the manifest earns its keep before the image exists.

**What the sandbox does:**
- Refuses to run the generation. Fail closed.
- Records the block in the audit trail against the triggering ledger entries — repeated blocks on the same package are themselves a signal, and probably the strongest evidence for or against an escalation.
- Emits an escalation request template, pre-filled with everything in §5.

**What the sandbox explicitly does not do:**
- No auto-install. Not from an index, not from a cache, not from a wheel sitting on disk.
- No network retry. There is no network, and there is no code path that would use one if there were.
- No substituting a "similar" package.
- No silently rewriting the import to something available.

**What the developer sees** — one block, not a stack trace:

```
BLOCKED: adapter generation halted on an unvetted import.

  adapter:   platform_adapters/generated/draft_hmis_ipd_adapter.py
  import:    line 14  ->  import paramiko
  resolves:  paramiko (not in vetted set; not in refused list)
  triggered: BL-2291, BL-2304, BL-2318  (3 ledger entries, same wall)
  tried:     subprocess+ssh (failed: no ssh on host), requests (target is not HTTP)

  The sandbox did not install anything, did not retry, and did not
  reach the network. Nothing was executed.

  To escalate:  python -m AgentCore.code_engine.escalate --request <id>
  To refuse permanently: add to `refused:` in
    AgentCore/policy/adapter_sandbox_dependencies.yaml
```

**One bounded regeneration, and the tension in allowing it.** On a block, the generator may be re-invoked *once*, with the vetted set supplied in the prompt as a hard constraint. This meaningfully reduces escalation volume, which is the direct counter to rubber-stamping. It is also, plainly, letting a narrow optimiser have another attempt at an obstacle — see §9. Bounded at exactly one, and the block is recorded either way, so a successful second attempt is still visible rather than erased.

---

## 7. Where this slots into §4.4b's gating table

Only the **Network egress** row changes. Proposed replacement text is in §10 and in the handoff block for the parent to paste. The other five rows are unaffected, and one of them is load-bearing here: *Human review is the last gate, never the only one.* This design adds a gate; it does not promote review.

---

## 8. Residual risk

Pre-staging closes the live-proxy route. Here is what it does not close.

### 8.1 A vetted package with its own vulnerability
Pinning freezes the bug along with the version. Three entries in the set — `lxml`, `Pillow`, `opencv-python-headless` — exist specifically to parse untrusted bytes (HMIS HTML, screenshots, UI captures), are C-heavy, and have real CVE histories. They are the highest-risk entries precisely because they are the ones doing the job. The quarterly refresh and advisory trigger are the mitigation, and they are a *cadence*, not a guarantee: between refreshes, the image contains known-vulnerable code by construction.

### 8.2 Supply-chain compromise at pin time
A hash pins **what we got**, not **what was legitimate**. If a package was already compromised on the day it was pinned, the hash makes that compromise reproducible and permanent, and every verification step downstream will confirm it faithfully. Pre-staging converts a continuous live-fetch risk into a point-in-time risk. That is a genuine improvement in exposure window. It is not elimination, and hash-pinning specifically provides *integrity*, not *provenance*.

**Updated for D19.** This risk now has two layers, not one. `adapter_sandbox_provisioned.lock.json` closes the *drift* half of it today — a file changing on the host after the lock was reviewed is caught and refused, whether from tampering or an unreviewed in-place upgrade. It does nothing for the *provenance* half: if the host copy was already compromised the moment the lock was generated, the lock pins that compromise exactly as described above. The image's `pip install --require-hashes` against a package index would additionally verify the packages came from where they claim to, which the host-baseline lock cannot do and does not claim to. That gap remains genuinely open and remains blocked on the same missing container runtime as the rest of `image:`.

### 8.3 The image is not the host — and the host does not match itself
An adapter verified in the sandbox runs on the developer's Windows machine and then in a hospital. Different OS, different resolved versions, different everything below the Python layer. Green in sandbox is evidence, not proof.

This is not hypothetical drift. Checked while writing this note: `requirements.txt` pins `Pillow==12.1.1`; the developer machine has `pillow==11.3.0` installed. The host environment already disagrees with the host's own declared requirements, today, before any sandbox exists. Whatever discipline the image gets, the host currently has less.

### 8.4 The container runtime
Runtime and kernel escapes are a live class of vulnerability, and on a Windows developer laptop the container sits on a virtualisation layer nobody in this project has audited or is qualified to audit. This design assumes the runtime holds. That assumption is unexamined and is stated so that nobody later mistakes it for having been checked.

### 8.5 Dependency curation is not capability restriction
`subprocess`, `socket`, and `urllib.request` are standard library. They are in the image because Python is in the image. **No dependency policy can remove them.** The manifest reduces supply-chain surface and removes the fetch path; it does not reduce what generated code can *attempt*. Egress is blocked at the network layer or it is not blocked.

### 8.6 It is defence-in-depth, and today it is less than that
Restating §0 because it is the thing most likely to be forgotten once this document exists and looks thorough: the sandbox is not the boundary, the ResolutionGate is. And until the image is actually built, none of the above is running — the current runner shares the host interpreter and the host's site-packages, so today the "vetted set" is in practice "everything the developer has installed."

### 8.7 The unresolved bit inside this resolution
`playwright`'s browser binaries. Baked in, they are a few hundred megabytes of rarely-refreshed attack surface sitting inside the sandbox. Not baked in, browser adapters cannot be verified in-sandbox and every single one becomes an escalation — which is the too-narrow failure from §1 arriving by a different door. Lean: bake them, pinned by digest, refreshed on the same quarterly cadence. Recorded as a lean, not a decision.

---

## 9. Goal-hyperfocus: what pre-staging does and does not change

The blueprint's third finding from the incident is the one that survives all of this: the models were not adversarial, they were *optimising hard against a narrow objective with nothing positioned to stop them*, and they spent real inference compute escaping constraints rather than working within them. A generator told "make this unreachable HMIS reachable" is structurally the same setup.

**Pre-staging does not change that dynamic. It removes one route.** Anyone reading this note as having addressed hyperfocus has misread it.

Worse, tightening the constraint arguably sharpens the pressure slightly: a generator with fewer legitimate tools has more reason to reach for illegitimate ones. The mitigating property is not that this becomes less likely, but that it becomes **visible** — a blocked import is a logged event tied to specific ledger entries, not a silent workaround. Failure surfaces as a diagnostic rather than as a package quietly appearing in an environment.

What actually bears on hyperfocus, and none of it is in this document:
- **The ResolutionGate.** Action-level interception that can flatly allow, block, or escalate, positioned to stop a chain mid-flight. Unchanged, and still the primary control.
- **No reward signal.** There is no benchmark score here, no adversary to beat, no automatic promotion on success. Generation is offline, developer-approved, and ends at a human.
- **A bounded loop, not an open one.** Level6's debug loop is capped at `max_iterations = 5` (`AgentCore/level6/debug_loop.py`). It is still a narrow objective with an iteration budget — the same shape as the incident, several orders of magnitude smaller — and the cap is what makes the difference in degree.

The honest summary: this design makes one specific exploited path unavailable, at the cost of some developer interruption, while leaving the underlying dynamic exactly where the blueprint left it. That is worth doing. It is not a solution to the thing the incident was actually about.

---

## 10. Appendix — blueprint edits

Applied by the parent, not by this note. Reproduced here for traceability. Replaces the third bullet's closing sentences under §4.4b's "Three findings that apply directly to this design," and the **Network egress** row of the Concrete gating requirements table. Exact text is in the handoff.
