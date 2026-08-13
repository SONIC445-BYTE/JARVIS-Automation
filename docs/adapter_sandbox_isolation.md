# Adapter-generation sandbox — isolation — design note

**Status:** built and measured, on Windows, non-admin. **Not a container.**
**Closes (partially — see §8):** `JARVIS_BLUEPRINT.md` §1.6 **D18**.
**Code:** `AgentCore/level6/sandbox_isolation.py`, `AgentCore/level6/sandbox_env.py`, `AgentCore/level6/sandbox_runner.py`
**Tests:** `AgentCore/level6/tests/test_sandbox_isolation.py` (24 tests)
**Companion note:** `docs/adapter_sandbox_dependencies.md` (which packages, and why)

---

## 0. What this note claims, and what it refuses to claim

D18 was logged because `sandbox_runner.py` ran `subprocess.run([sys.executable,
"-m", "pytest"], cwd=temp_dir)` — the host interpreter, against the host's
site-packages, isolated by a temporary working directory and nothing else — and
because it set `env["JARVIS_SANDBOX_NETWORK"] = "0"`, a name shaped exactly like
a network control, written in one place in the repo and read in none.

The failure mode being corrected is **a claimed boundary that does not exist.**
The obvious way to fail at fixing it is to build a partial boundary and describe
it as a complete one. So, stated before anything else:

- **This is not a container and not a VM.** Same kernel, same filesystem
  namespace, same network stack, same machine. A kernel-level or Windows
  Filtering Platform vulnerability defeats every layer described below
  simultaneously.
- **The ResolutionGate remains the primary control**, exactly as §4.4b says.
  This is defence-in-depth. It reduces the number of ways a bad day can start.
- **Nothing here should be called "secure" or "sandboxed" unqualified.**
  Khlaaf's *"sandboxes are actually notoriously insecure"* still stands.
- **Every claim below was measured**, by a real child process genuinely
  attempting the escape, with a control run proving the attempt succeeds when
  the boundary is removed. Claims that could not be measured are not made.

---

## 1. Why not a container

The obvious answer to D18 is Docker. It is not available, and the constraint is
not "not installed yet" — it is "cannot be installed here."

Verified on the target machine (Windows 11 Pro 10.0.26200, Python 3.12.10):

| Mechanism | State | Consequence |
|---|---|---|
| Docker / Podman | not on `PATH`, no runtime | no container isolation |
| WSL | `wsl.exe` present, but it is the inbox stub: *"The Windows Subsystem for Linux is not installed"* | no Linux namespace; `wsl --install` needs Administrator |
| Windows Sandbox | `%WINDIR%\System32\WindowsSandbox.exe` absent | unavailable |
| Administrator | `IsUserAnAdmin() == 0` | no firewall rules, no privileged configuration, no feature installation |
| `pywin32` | present and working | restricted tokens, job objects available |

`wsl.exe` being on `PATH` is worth calling out, because a shallower check
(`shutil.which("wsl")`) reports WSL as available when it is not. That is the
same shape of mistake as D18 itself: inferring a capability from a name.

**The design consequence is deliberate.** The manifest's `image:` section —
digest-pinned base, hashed lockfile, `pip install --require-hashes`, no pip at
runtime — remains unbuilt and is still recorded as unbuilt. Shipping an
untested Docker code path "for when it's available" would be another
specification for an unbuilt image, which is precisely what D18 exists to
remove. There is no Docker path in this code.

---

## 2. What was built

Four layers. Each is independently reported, and a layer is never reported as
present unless it was actually constructed.

### 2.1 A genuinely separate interpreter

`sandbox_env.provision()` builds a standalone Python tree — `python.exe`, the
runtime DLLs, `DLLs/`, and the standard library — with an **empty**
site-packages, cached under `projects/.sandbox_env/<digest>/` and keyed by a
hash over the manifest, the host Python version, and the resolved versions of
the vetted packages. The interpreter tree alone is ~35MB; with the vetted closure
installed the cached environment is **~210MB** on this machine (playwright
107MB and numpy 33MB dominate). About 22 seconds to build the first time,
reused thereafter. Stale environments from earlier manifest or package versions
are pruned on reprovision, since the cache key changes on any such edit and
each stranded tree costs another ~210MB.

site-packages is then populated **only** from the manifest's `layer: image`
entries plus their runtime dependency closure, resolved from installed host
metadata and copied file-by-file. On this machine that is 21 distributions.

The stdlib copy deliberately omits `test` (the CPython test suite),
`tkinter`/`idlelib` (need a display), and **`ensurepip`** — putting a package
installer inside a sandbox whose dependency policy is "no installer at runtime"
would reintroduce the fetch path one level down, which is the same reasoning
that makes `webdriver_manager` a hard refusal in the companion note.

`layer: host_mocked` entries are satisfied by generated stub modules that
install a `MagicMock`. They are never the real package. A test passing against
a stub has exercised control flow and contract conformance, **not** behaviour on
a real Windows screen — unchanged from the companion note's §3.1, and still the
honest limit of what a green sandbox run means.

### 2.2 AppContainer — the network and filesystem boundary

A capability-less AppContainer profile (`CreateAppContainerProfile`), applied
via `PROC_THREAD_ATTRIBUTE_SECURITY_CAPABILITIES`. Non-admin.

Because the process holds **no** capabilities — in particular not
`internetClient` and not `privateNetworkClientServer` — the Windows Filtering
Platform denies it every socket. Because it is a LowBox token, the filesystem
grants it only what carries an explicit ACE for its own package SID or for
`ALL APPLICATION PACKAGES`; the user profile carries neither.

**This is why network denial is not Python-level monkeypatching of `socket`.**
Generated code owns its own process and could undo a patched `socket` module in
one line. §5 shows the test that does exactly that and still fails.

### 2.3 Restricted token — a second, independent filesystem denial

The caller's own primary token, with the user's SID marked
`SE_GROUP_USE_FOR_DENY_ONLY` and all privileges deleted except one. The user
profile's ACLs grant the *user SID*; deny-only means those grants stop applying.

Two details cost real debugging time and are recorded because they are
non-obvious and will bite the next person:

1. **The token's default DACL must be replaced.** It grants exactly
   `{user SID, BUILTIN\Administrators, SYSTEM}`; the first is now deny-only and
   the second is already deny-only under UAC. The child could not access
   objects it created for itself and died at `0xC0000142`
   (`STATUS_DLL_INIT_FAILED`) before reaching `main`. This was isolated by
   observing that `cmd.exe` failed identically, ruling out anything
   Python-specific. Also: the handle from `CreateRestrictedToken` lacks
   `TOKEN_ADJUST_DEFAULT`, so it must be re-duplicated before the DACL can be
   set.
2. **`SeChangeNotifyPrivilege` is deliberately kept.** It is "bypass traverse
   checking". Deleting it forces a traverse check on every intermediate
   directory, and the sandbox workspace lives under a user profile whose
   intermediate directories grant only the now-deny-only user SID — so
   stripping it prevents the child from reaching its own workspace. It confers
   no ability to open a file whose own ACL denies it.

### 2.4 Job object — lifetime and resources

Kill-on-job-close, an active-process cap (12), a per-process memory cap (1GB),
per-process and per-job CPU-time caps, and UI restrictions (no host clipboard,
no reaching windows outside the job, no display/system parameter changes).

Kill-on-job-close is the one that matters most: when the last handle to the job
closes — **including because the parent crashed** — Windows terminates every
process in it. The old `subprocess.run(timeout=...)` killed only the direct
child, orphaning any grandchild it had spawned.

Availability is probed at construction, before a process exists, because the
decision "may this run at all" has to be made before generated code is running.
If assignment nonetheless fails after launch, the suspended child is
**terminated rather than resumed** outside the boundary the caller was promised.

### 2.5 Two smaller hardening details

- **Handle inheritance is pinned to exactly three handles**
  (`PROC_THREAD_ATTRIBUTE_HANDLE_LIST`). `bInheritHandles=TRUE` otherwise hands
  the child every inheritable handle the parent holds. An inherited handle
  bypasses ACL checks entirely — the access check already happened when the
  parent opened it — so it is a straight path through the boundary.
- **The host environment is not inherited.** The child gets a minimal
  constructed environment; `HOME`/`USERPROFILE`/`TEMP` are redirected into the
  workspace. The host environment carries API keys and proxy settings, which is
  exactly what an escape would want.

---

## 3. The network control: read and enforced, and the variable is gone

D18's requirement was that the network control be genuinely enforced **or**
removed with the absence stated plainly.

**`JARVIS_SANDBOX_NETWORK` has been deleted.** It is not set anywhere. It is
named in `sandbox_runner.py`'s module docstring only to explain why it is gone.
`test_jarvis_sandbox_network_variable_is_gone` guards the regression by AST —
looking for an *assignment*, not a substring — so that documenting the defect
does not trip the guard against it.

**In its place is an actually-enforced denial**, at the OS layer, measured. See
§5 for the output.

**The dependency worth naming:** AppContainer egress denial is enforced by the
Windows Filtering Platform, driven by BFE and mpssvc. If those services are
stopped, the denial is not applied. `firewall_state()` reports them (both
`RUNNING` here), but the service state is advisory — the authoritative check is
`verify_containment()`, which runs a real child that genuinely attempts egress.

---

## 4. Vetted dependency set — enforced, not configured

Three mechanisms, in order of strength:

1. **Genuine absence.** A package outside the set was never copied in. This is
   the actual boundary.
2. **Static AST import check, fails closed before execution.** Refuses the run
   and emits the companion note's §6 diagnostic block. Nothing has executed at
   the point the block is recorded.
3. **No auto-install, no network retry, no substitution.** There is no pip in
   the sandbox and no network to reach an index.

**The static check is evadable and is documented as such in its own docstring.**
`importlib.import_module("ya" + "ml")` is invisible to an AST scan. It is a
developer-facing diagnostic and a policy tripwire, **not** the boundary. There
is a test that performs exactly that evasion, confirms it gets past the scanner,
and confirms it still fails — because the package genuinely is not there.

**A live example of fail-closed behaviour, not a hypothetical:**
`opencv-python-headless` is vetted in the manifest and is **not installed on
this host** — the host has `opencv-python`, the GUI build, which provides the
same `cv2` import name. The provisioner records it as unavailable and refuses
`import cv2` with a diagnostic saying so, rather than silently satisfying it
from the GUI build. "No substituting a similar package" is enforced.

---

## 5. Measured results

Identical probe script, same provisioned interpreter, run twice: once fully
contained, once with AppContainer and the restricted token disabled. The control
column is what makes the left column mean anything.

| Attempt | Contained | Control (boundary removed) |
|---|---|---|
| Read `~\_d18_evidence_canary.txt` | `PermissionError [Errno 13]` | `CANARY-CONTENTS-8891` |
| List `C:\Users\mukho` | `PermissionError [WinError 5]` | 99 entries |
| Read `~\.gitconfig` | `PermissionError [Errno 13]` | 302 bytes |
| Read `AgentCore/resolution_gate.py` | `PermissionError [Errno 13]` | 7099 bytes |
| Write into repo root | `PermissionError [Errno 13]` | succeeded |
| Outbound TCP `1.1.1.1:443` | `PermissionError [WinError 10013]` | connected |
| DNS `example.com` | `gaierror [Errno 11001]` | `104.20.23.154` |
| Loopback `127.0.0.1:<port>` | `TimeoutError` | connected |
| `import yaml` (installed on host) | absent | absent¹ |
| `sys.prefix` | `projects\.sandbox_env\<digest>` | same¹ |
| `JARVIS_SANDBOX_NETWORK` in env | `False` | `False` |

¹ The control still uses the provisioned interpreter, so the vetted-set boundary
holds in both columns. That is correct and worth noting: **the dependency
boundary is the interpreter, and is independent of the OS layers.**

`WinError 10013` is `WSAEACCES` — the OS refusing the socket outright, which is
distinguishable from the `TimeoutError` a merely-unreachable network produces.

Job object, measured separately:

- Fork bomb: spawned 7 of 60 attempts, then `OSError [WinError 1816] Not enough
  quota is available to process this command`.
- Survivorship: a grandchild told to sleep 8s and then write a file produced no
  file after the run ended and 14s elapsed.
- Timeout: a 600s sleep with a 6s budget returned `timed_out=True` with the
  whole tree terminated.

`verify_containment()` verdict, all measured rather than asserted:

```json
{ "measured": true, "host_file_read_blocked": true, "home_listing_blocked": true,
  "tcp_egress_blocked": true, "dns_blocked": true,
  "host_only_package_absent": true, "separate_prefix": true }
```

**Test suite:** 24/24 pass in `test_sandbox_isolation.py`; the pre-existing
`AgentCore/level6/tests/` suite is 51/51.

---

## 6. Fail-closed posture

`SandboxRunner` **refuses to execute** when any required layer (AppContainer,
restricted token, job object) is unavailable, rather than degrading silently.
`allow_degraded=True` overrides, and the degradation is stamped into the result
(`containment.degraded`, `containment.required_but_missing`).

This is the deliberate opposite of the old behaviour. A sandbox that quietly
becomes "no sandbox" is D18 with more code.

---

## 7. Costs and limitations this creates

**Loopback is denied too.** This is a functional cost, not a win. A generated
adapter test that stands up a local HTTP server to exercise an adapter cannot
work in-sandbox. The companion note's §3.2 assumed `requests` "can only reach
loopback" inside the sandbox; in fact it can reach nothing. Exempting loopback
for an AppContainer requires `CheckNetIsolation LoopbackExempt`, which requires
Administrator. Adapters needing a live local endpoint must be verified on the
host, outside the sandbox, under developer supervision — the same route already
used for the Windows-only layer.

**A non-admin scoped exception was attempted (D19 follow-up) and investigated
to a specific, evidenced dead end, not abandoned on the first failure.**
`LoopbackExceptionPipe` (sandbox_isolation.py) ACE-grants the AppContainer SID
access to exactly one named pipe, reasoning that a pipe lives in the NT object
namespace rather than the WFP/socket stack the AppContainer's zero-capability
profile denies. Four real bugs were found and fixed while building it (a
pywin32 ACE-mask overflow from unsigned generic rights, a missing `WRITE_DAC`
open-mode bit needed before a handle can `SetSecurityInfo` on itself, raw
`GENERIC_*` bits being invalid in a stored ACE where MSDN requires the
object's *specific* rights, and the wrong `SE_OBJECT_TYPE` for a handle-based
security call) — and after all four fixes, the mechanism genuinely works: an
AppContainer running ALONE can open a declared pipe and nothing else.

**It does not work against this file's real launcher.** `ContainedLauncher`
stacks AppContainer with a restricted token by default (this whole design,
D18's own point). With that restricted token active alongside AppContainer,
the same, correctly-ACE'd pipe is still refused (WinError 5), even after also
trying the `S-1-15-2-1` (ALL APPLICATION PACKAGES) SID in addition to the
specific AppContainer SID. Isolated by control, not guessed: AppContainer
alone connects; AppContainer + restricted token fails identically whether the
job object is on or off, so the job object is not a factor. The restricted
token specifically is the blocker, and the exact mechanism was not run to
ground beyond that (candidates not confirmed: `SeChangeNotifyPrivilege`'s
traverse-check bypass not extending to NPFS the way it does to NTFS; some
difference in how `CreateProcessAsUserW` derives a LowBox token from an
explicit restricted primary token versus the calling process's own token).
`socket.AF_UNIX` was checked as a filesystem-namespace alternative — not
available on this Python/Windows build, ruled out quickly.

**Disposition:** not delivered, not silently dropped either. The code and its
adversarial tests stay in the repo (`TestLoopbackExceptionPipe` in
`test_sandbox_isolation.py`, both the AppContainer-alone success and the
real-launcher failure, both asserted, so neither claim can silently drift back
to being assumed rather than measured). Adapters needing a live local endpoint
still route to the host, outside the sandbox, exactly as the paragraph above
already says. Do not weaken `ContainedLauncher`'s restricted-token default to
make this pass — that reduces D18's closed boundary and needs its own
reviewed decision, not a side effect of a test-convenience feature.

**pytest must be able to stat the sandbox's parent directory.** Measured: no
combination of `--rootdir`, `--confcutdir` or `--noconftest` stops pytest 9 from
stat-ing the parent during collection, and a denied parent surfaces as a
`PermissionError` during collection rather than a test result. The parent
therefore carries a **non-inheritable, stat-only** ACE
(`FILE_READ_ATTRIBUTES | FILE_TRAVERSE | SYNCHRONIZE`, deliberately **without**
`FILE_LIST_DIRECTORY`). Verified with that ACE in place: `os.listdir(parent)`
still fails `WinError 5`, and reading a sibling run's file still fails
`Errno 13`.

**Cross-run readability inside the sandbox root.** All runs share one
AppContainer SID, and each workspace grants it. A run that could *name* another
run's directory could read it. It cannot enumerate them (no
`FILE_LIST_DIRECTORY`) and directory names carry a `uuid4` component, so this is
not practically reachable — but it is a real residual, and the fix if it ever
matters is a per-run AppContainer profile.

**Provisioning writes ACEs.** The workspace and the provisioned interpreter get
explicit ACEs for the AppContainer SID and `BUILTIN\Users`. These are confined
to the sandbox's own tree; no ACL outside `projects/` is modified. `grant_dir()`
is idempotent, because a per-run duplicate ACE would grow the DACL without bound
until ACL writes started failing — the boundary degrading with use.

**First-run latency.** ~22s to provision, then cached.

---

## 8. What is still NOT closed

Stated as a list because these are the things a reader should not have to infer.

1. **No provenance, and no digest-pinned base image.** `image.base_digest` and
   `image.lockfile` in the manifest remain null; `pip install --require-hashes`
   against a package index still needs a container runtime this machine does
   not have. This is the companion note's §8.2 provenance half, and it is
   still genuinely open. **Updated by D19, not left as originally written
   here:** the files actually copied from the host ARE now hash-pinned
   against a reviewed baseline (`adapter_sandbox_provisioned.lock.json`) and
   provisioning refuses on any mismatch, verified by mutating a real host
   file (`test_supply_chain_lock.py`). That closes the drift/tamper half of
   this gap and does not touch the provenance half -- see the companion
   note's §8.2 for the corrected split between the two.
2. **No kernel-level isolation.** Same kernel, same filesystem namespace, same
   network stack. This is not a container and cannot become one on this machine.
3. **The WFP/BFE dependency is unaudited.** Network denial rests on services
   this project has not audited and is not qualified to audit — the same
   unexamined-assumption class the companion note's §8.4 named about container
   runtimes, relocated rather than removed.
4. **Capability restriction is still not achieved.** `socket`, `subprocess` and
   `urllib.request` are standard library and present. What changed is that the
   *attempt* now fails at the OS layer; the *capability to attempt* is
   untouched.
5. **Goal-hyperfocus is untouched.** The companion note's §9 stands verbatim.
   This removes routes; it does not change the dynamic the incident was about.
6. **The sandbox verifies logic, not Windows behaviour.** Unchanged.
7. **Only measured on one machine, one OS build, non-admin.** These are
   empirical results from this laptop, not a portability claim. On a machine
   without AppContainer support the runner refuses to run rather than degrading
   — which is the intended behaviour, but it does mean the boundary's
   availability is environment-dependent.

**Recommended disposition:** D18's specific defect — a sandbox that isolated
nothing, and a variable shaped like a control that enforced nothing — is closed,
with adversarial evidence. The broader §4.4b gating table is **partially**
satisfied: the Network egress, Secrets, and Immutable tier rows are now
genuinely enforced for the first time; the rows that depend on a built image
(hash pinning, digest-pinned base) remain specification. Marking D18 fully
closed is defensible only if the residual in item 1 is re-logged as its own
item, because it is a real gap that this phase did not close and the manifest
still describes as if it will be.

---

## 9. Container upgrade path — a note attached to D18 and D19, not a plan

Everything in this note and its D19 follow-up exists because Docker, WSL,
Windows Sandbox, and Administrator are all unavailable on the target machine
today. That is an environment fact, not a design preference, and it can
change under this project without anyone touching this document.

**If the deployment environment ever gets a container runtime** (Docker, WSL2,
or equivalent) **or Administrator rights**, this whole design should be
revisited with real container isolation as a **strictly stronger replacement**,
not layered on top of what exists here. Concretely, that means:

- The AppContainer / restricted-token / job-object stack in this file
  (§2.2–§2.4) is replaced, not kept as an inner shell inside a container. A
  container adds a separate kernel-visible namespace, filesystem namespace,
  and network stack — properties §1 and §8.2 both state this design does not
  and cannot have. Running both is not defence-in-depth; it is unaudited
  complexity on top of a boundary that would already be stronger.
- The D19 host-baseline lock (`adapter_sandbox_provisioned.lock.json`) is
  replaced by the manifest's original `image:` design — a digest-pinned base
  and `pip install --require-hashes` against a package index — because that
  provides the provenance property the D19 lock explicitly does not (§8.2,
  updated). The D19 lock was always the non-container substitute for that
  mechanism, not an alternative implementation of it.
- `LoopbackExceptionPipe` (§7, D19 follow-up — investigated, not currently
  delivered against the real launcher) is replaced by whatever the
  container's own network namespace makes possible for a declared local
  target — very likely something closer to the originally-envisioned scoped
  loopback rather than a named-pipe workaround, since a container's network
  stack is not the same WFP/AppContainer capability model this pipe exception
  was built to work around.
- The AST-based static import check (§4, companion note §6) is the one piece
  that stays regardless of runtime, because it is a generation-time developer
  diagnostic, not a boundary — it earns its keep whether or not a container
  exists underneath it.

**Why this is written down now rather than left implicit:** the project has a
standing rule against unbuilt-image specifications describing a boundary that
does not exist (that was D18's original defect one level up). Recording the
upgrade path explicitly is the alternative to two silent failure modes:
building the container work as an unreviewed surprise later, or never
revisiting the non-admin design once it stops being the only option and
quietly becoming permanent by default.
