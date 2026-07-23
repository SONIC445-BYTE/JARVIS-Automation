# Phase 3a-3d: Hermes-inspired capabilities -- design doc

Groundwork only, review-gated. Nothing here is wired into the live
conversation loop yet. Per the brief that opened this phase: most of
Nous Research's Hermes Agent doesn't transfer -- it's built to be
reachable remotely through chat platforms, which conflicts with
JARVIS's standing on-device-only requirement. Four capabilities were
judged genuinely valuable and additive to the existing pipeline: the
resolution gate, `CommandRouter`, and the confirm-before-consequential-
action pattern stay exactly as they are. Nothing below replaces or
weakens any of them.

## 3a -- Persistent cross-session memory

### An existing, unused component changes this design

Before building anything, checked whether a local storage layer already
existed (same discipline as onboarding's state-directory check last
round). It does: `AgentCore/memory_store.py`'s `MemoryStore` -- a
local-only, JSON-backed key/value store with `category`/`tags`,
`get`/`set`/`get_pref`/`set_pref`/`search`/`backup`/`export_plaintext`/
`purge`/`get_stats`. It is **not currently reachable from the live
path**: only `AgentCore/feedback_engine.py` and `AgentCore/optimizer.py`
import it, and grepping the whole codebase, nothing imports
`feedback_engine` or `optimizer` either -- the same "real component,
dead subsystem" situation Phase 2c-prime found with
`ui_agent/inspector/browser_adapter.py`.

Given that, and given this project's established preference for
extending an existing mechanism over inventing a new one (see the 5th
router-bug fix), **3a's storage layer reuses `MemoryStore` rather than
building a parallel SQLite store from scratch.** A new SQLite store was
the original instinct (structured queries for "recurring command
patterns" felt like a natural fit), but the actual query needs here are
modest -- read a value, write a value, increment a counter, list the
top N by count -- and `MemoryStore`'s existing dict-of-records model
already covers that without a fifth local-storage convention in this
codebase (there are already four: `WakeService/models/`,
`state/onboarding_complete.json`, `feature_flags/*.yaml`, and
`MemoryStore`'s own JSON file). Reuse also means the storage boundary
enforcement (below) only has to reason about one code path, not two.

### Two things fixed while reusing it, not glossed over

1. **Storage location.** `MemoryStore`'s default path is
   `data/memory/memory_store.json`. `data/` exists on disk but has
   **zero files tracked in git and is not covered by `.gitignore`** --
   confirmed with `git ls-files data/` (empty) and `git check-ignore`
   (not ignored). Writing physician preference/pattern data there is a
   real risk: a careless `git add -A` would commit it. `SessionMemory`
   (below) redirects `MemoryStore`'s `store_dir` to `state/` instead --
   the same gitignored runtime-state directory onboarding's marker file
   already uses, so there's one place, already protected, for all local
   runtime state.
2. **The "encryption" isn't real.** `MemoryStore._encrypt`/`_decrypt` is
   XOR with a hardcoded default key (`"jarvis_default_key"`, visible in
   source) plus base64 -- trivially reversible by anyone with the
   source, which is everyone. It's obfuscation, not confidentiality,
   despite the class docstring saying "Encrypted." Not fixed in this
   pass (real key management -- OS keyring, a per-install generated
   key -- is a deliberate decision this doc is flagging for review, not
   quietly deciding). Documented here so nobody mistakes this for a
   real protection once preferences/patterns start accumulating.

### `AgentCore/session_memory.py` (new, thin wrapper -- not modifying `MemoryStore` itself)

```python
class SessionMemory:
    def __init__(self, store: Optional[MemoryStore] = None):
        self._store = store or MemoryStore(store_dir=Path("state") / "memory")

    # Preferences
    def get_preference(self, key: str, default=None): ...
    def set_preference(self, key: str, value) -> None: ...

    # Recurring command patterns
    def record_command_pattern(self, pattern_key: str) -> None:
        """pattern_key: a normalized (adapter, action) shape, e.g.
        "whatsapp_desktop.send_message" -- never the raw command text
        (which may contain names/content), and never used to skip
        confirmation, only to inform tone/shortcuts later."""

    def top_command_patterns(self, limit: int = 5) -> List[Tuple[str, int]]: ...

    # Prior session context
    def start_session(self) -> str: ...  # returns a session id
    def end_session(self, session_id: str, summary: str) -> None: ...
    def recent_sessions(self, limit: int = 5) -> List[dict]: ...
```

Read/write only, per the instruction -- nothing in
`jarvis.py`'s conversation loop calls this yet.

### The enforced boundary

"Memory must never be read by the resolution gate to skip or weaken any
confirmation step" is enforced structurally, not just documented:

- `AgentCore/resolution_gate.py` and `AgentCore/command_router.py` do
  not import `AgentCore.session_memory` anywhere, and never will as long
  as this boundary holds.
- A new regression test
  (`tests/test_session_memory_boundary.py`, added alongside the storage
  layer) runs `resolution_gate`/`command_router` imports in a clean
  subprocess and asserts `AgentCore.session_memory` never ends up in
  `sys.modules` -- the same technique
  `tests/test_agentcore_ui_coupling.py` already uses for the mss/
  pyautogui coupling fix. This catches not just a direct import but any
  future transitive one.
- What memory is allowed to influence, stated explicitly so "informs
  tone/defaults" doesn't quietly expand: response phrasing, TTS
  preferences, which shortcut to offer first. Never: whether a
  confirmation prompt fires, which branch a `GateOutcome` takes, or
  `AvailabilityChecker`/`ResolutionGate` behavior in any way.

## 3b -- Sub-agent spawning for parallel, independent tasks

### A prerequisite this design surfaces rather than assumes away

"Parallel execution of multiple already-resolved, independent commands
in one turn" presumes multiple `Intent`s already exist from one turn of
text. They don't yet: `CommandRouter.resolve(text) -> Optional[Intent]`
resolves at most one `Intent` per call, and there is no multi-intent
splitter anywhere in this codebase today. Splitting "open Chrome and
send Mom a WhatsApp message" into two separate resolvable commands is
its own piece of work, not yet built, and out of this pass's scope --
flagging it here rather than silently assuming it exists, since without
it 3b has nothing to parallelize yet.

### Design (assumes a `List[str]` of already-separated commands)

- **Concurrency primitive:** `concurrent.futures.ThreadPoolExecutor`.
  This codebase's concurrency is threading-based throughout
  (`WakeDetector`, `onboarding.PeriodicAvailabilityRescanner`,
  `UIExecutor`) -- asyncio appears nowhere, so a thread pool matches the
  existing paradigm instead of introducing a second one.
- **Hook point:** a new `ODAVLoop.execute_many(commands: List[str]) ->
  List[ODAVResult]`, sitting *above* the existing `execute()`, calling
  it once per command via the pool. `execute()` itself, and everything
  it calls (`ResolutionGate` -> `CommandRouter` -> adapter registry), is
  untouched -- every sub-agent still goes through the identical
  single-command pipeline, just potentially concurrently with another.
  This is the "not a redesign of resolution/routing" requirement made
  concrete: there is no second pipeline, only a parallel caller of the
  existing one.
- **Failure isolation:** `UIExecutor.execute_intent()` already never
  lets an adapter exception escape uncaught (wraps in try/except,
  returns `ExecutionResult(status=FAILED, ...)`) -- that guarantee is
  reused, not rebuilt. `execute_many()` collects one `ODAVResult` per
  input command, in order, and returns all of them; one command's
  failure/exception is never allowed to abort or mask another's result.
  Reporting each distinctly (not merged into one blob) is the caller's
  job (jarvis.py, when this gets wired live) -- `execute_many()`'s
  contract is just "N in, N results out, always."
- **Concrete complication for the live-wiring phase (not solved now):**
  if one sub-agent's command hits a CAPTCHA/login-wall (`BLOCKED`),
  today's `PersistentWakeService` has exactly one `_pending_resume`
  slot -- Phase 2g's adversarial pass already found and fixed the bug
  where a *second* sequential block silently overwrote the first. With
  *concurrent* sub-agents, that same slot can't represent "resume the
  right one of N blocked sub-agents" at all. Whenever 3b's live wiring
  happens, `_pending_resume` needs to become a dict keyed by
  sub-agent/intent, not a single value. Noted now so it isn't
  rediscovered the hard way later; not built now.

## 3c -- Natural-language scheduling

### Data model

```python
@dataclass
class ScheduledCommand:
    id: str
    original_text: str        # "every weekday at 9am, open the OPD queue"
    command_text: str         # "open the opd queue" -- what actually
                               # gets handed to ODAVLoop.execute() at fire time
    kind: str                 # "once" | "recurring"
    fire_at: Optional[str]    # ISO8601, "once" only
    weekdays: Optional[List[int]]  # 0=Mon..6=Sun, "recurring" only
    time_of_day: Optional[str]     # "HH:MM", "recurring" only
    created_at: str
    enabled: bool = True
```

### Parsing

A purpose-built, marker-based parser in the same style as
`AgentCore/command_router.py`'s existing extraction (explicit boundary
words, not a general NLP dependency this project has no other use for):
`"remind me to <command> at <time>"`, `"every <weekday(s)> at <time>,
<command>"`, `"every day at <time>, <command>"`. Time/weekday parsing is
the only genuinely new grammar; everything after the comma/"to" is
handed unchanged to the exact same command-resolution path a spoken
command would use -- scheduling never gets its own interpretation of
what a command means, only of *when* to run it.

### Storage

Reuses 3a's `SessionMemory` (`category="schedule"`) rather than a sixth
storage convention -- `ScheduledCommand.id` as the key, the dataclass
(as a dict) as the value.

### Execution -- and the one non-obvious design decision

A background daemon thread (same shape as
`onboarding.PeriodicAvailabilityRescanner`: `threading.Event.wait()` in
a loop, checked once a minute) that finds due items and calls
`ODAVLoop.execute(item.command_text)` -- the *exact* live command path,
same `ResolutionGate`, same confirmation rules where applicable. Not a
second execution path that bypasses anything.

The non-obvious part: what happens when a scheduled trigger resolves to
`GateOutcome.NOT_INSTALLED` (would normally prompt "want me to install
it?")? Nobody's there to answer. Three options considered:
- Auto-install: rejected outright -- violates the standing
  confirm-before-consequential-action rule, no exception for
  "unattended."
- Silently skip: rejected -- indistinguishable from the scheduler being
  broken; exactly the kind of silent failure this project has
  repeatedly rejected elsewhere (Phase 2g's CAPTCHA handling, the
  router's extraction-failure guards).
- **Log as "needs confirmation, not run" and surface it the next time
  the physician interacts** (a queued notice, read out or shown at the
  next wake) -- chosen. Preserves the confirmation rule, doesn't
  pretend the trigger succeeded, doesn't require solving unattended
  authorization.

### List/cancel

`list_scheduled() -> List[ScheduledCommand]`,
`cancel_scheduled(id: str) -> bool`, both trivial once storage exists.
Spoken surface ("what's scheduled" / "cancel the labs reminder") is
identified as a hook point, not wired -- same pattern as 3a/3b.

## 3d -- Skill-writing, proposal-only, human-approval-gated

This is the one the brief said needs the most care, and it's the one
built least in this pass -- proposal format and approval workflow only,
deliberately no pattern-detection/auto-drafting logic yet.

### Proposal format

```python
@dataclass
class SkillProposal:
    name: str
    description: str
    trigger_pattern: str          # the repeated pattern that was noticed
    adapters_needed: List[str]    # existing adapter keys/actions ONLY --
                                   # see hard boundary below
    example_inputs_outputs: List[Tuple[str, str]]
    draft_code: str               # proposed implementation, as inspectable
                                   # source text -- never executed as part
                                   # of proposing it
    risk_notes: str
    status: str                   # "proposed" | "approved" | "rejected"
```

**Hard boundary:** `adapters_needed` may only reference adapters/actions
that already exist in `platform_adapters/registry.py`'s registry. A
proposal that would need new raw system access (a new adapter, a new
capability) is out of scope for auto-proposal -- it gets flagged as
"needs a new adapter first," which is its own, separately-reviewed piece
of work, not something a skill proposal can wave into existence.

### Approval workflow -- reuses this project's existing review discipline, doesn't invent a new one

Proposals are written to a new `skill_proposals/` directory as a paired
markdown description + `.py` draft. Unlike `state/`, this is **git-
tracked, not gitignored** -- proposals are meant to go through the same
branch + review process as every other piece of this project's work,
not live as invisible runtime state. Concretely:

1. JARVIS notices a pattern, writes `skill_proposals/<name>.md` +
   `skill_proposals/<name>_draft.py`. Nothing runs. Nothing is imported
   or wired anywhere.
2. Ayan reviews the proposal (same as reviewing any other change in this
   engagement).
3. Approving the *proposal* is not the same as approving *final code* --
   an approved proposal becomes a normal implementation task (built,
   tested, and merged through the identical draft-review-merge workflow
   this entire project has used since Phase 0), not something that
   starts running the moment Ayan says yes. This is the explicit,
   non-negotiable requirement from the brief, restated here as the
   design's actual mechanism, not just a promise: there is no code path
   in this design where approval and execution are the same event.

### Not built in this pass

Pattern-detection (what counts as "a repeated pattern" worth proposing)
and the auto-drafting logic that would fill in `draft_code`. Per
instruction, getting the review-gate mechanism right came first.

## What's actually live after this pass

Only 3a's storage layer + read/write API
(`AgentCore/session_memory.py`), reusing `AgentCore/memory_store.py`,
redirected to `state/`, with a structural test enforcing the
resolution-gate boundary. Not wired into the conversation loop's
response generation. 3b/3c/3d are design-only -- no new runtime code,
no live wiring, per the instruction to report back before building
further.
