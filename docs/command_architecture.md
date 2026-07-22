# Command Architecture (Phase 2a)

## Problem

Before this phase, natural-language commands were classified against a
**fixed, central verb list**: `AgentCore/intent_planner.py`'s `ActionType`
enum (`OPEN_APP`, `CLOSE_APP`, `CLICK`, `TYPE`, `SCROLL`, `WAIT`,
`NAVIGATE`, `SEARCH`, `SELECT`, `UPLOAD`, `DOWNLOAD`, `SCREENSHOT` — 12
values), plus `ODAVLoop._create_simple_plan`'s fallback regex, which only
recognized `open/close/click/type/play`.

`send_message` and `read_unread` — the two most useful methods on the
`daemon`-contract adapters (`platform_adapters/`), and the entire reason
`whatsapp_desktop`, `telegram_desktop`, and `gmail_browser` exist — were
not representable anywhere in that vocabulary. Nothing upstream of
`UIExecutor` could ever *produce* those verbs, regardless of how well
`UIExecutor` itself was wired to the adapter registry.

This isn't a one-off gap. The project's goal is genuinely wiring up all
~160 platforms under `AgentCore/platform_adapters/` with their real
supported actions (e.g. Netflix play/pause, not just launching Netflix).
A fixed central enum cannot represent "every action every platform
supports" at that scale without becoming unmanageable — every new
platform-specific action would require editing central router code.

## Design

Adapters now **declare** what they support; the router **resolves**
natural language against those declarations. Nothing about a new action
lives in central code.

### 1. Adapters declare their capabilities (`platform_adapters/adapter_base.py`)

```python
@dataclass
class ActionSpec:
    name: str                      # method name to invoke, e.g. "send_message"
    verbs: List[str]                # trigger words, e.g. ["send", "message", "text"]
    requires_target: bool = False
    requires_message: bool = False

class AdapterBase(ABC):
    PLATFORM_ALIASES: List[str] = []   # e.g. ["whatsapp"]
    ACTIONS: List[ActionSpec] = []     # declared per-subclass
```

Each of the 5 real adapters (`browser`, `text_editor`, `whatsapp_desktop`,
`telegram_desktop`, `gmail_browser`) declares its `PLATFORM_ALIASES` and
`ACTIONS`. Adding a new action to an existing adapter, or a wholly new
platform, means adding declarations here — never touching a router file.

**Convention for actions beyond the base four:** `ActionSpec.name` must
match a real method name on the adapter (e.g. a future
`NetflixAdapter.play()` for `ActionSpec("play", verbs=["play", "resume"])`).
`UIExecutor._invoke_adapter_action` calls the four base methods
explicitly, and falls back to `getattr(adapter, action_name)()` for
anything else — see `AgentCore/ui_executor.py`.

### 2. Shared data shape: `daemon.intent_parser.Intent`

Rather than inventing a third data shape, this phase converges on the
`Intent` dataclass already proven end-to-end by `daemon/dispatcher.py`:

```python
@dataclass
class Intent:
    adapter: str
    action: str
    target: str = ""
    message: str = ""
    destructive: bool = False
    meta: Dict[str, str] = field(default_factory=dict)
```

### 3. Resolution: `AgentCore/command_router.py`

`CommandRouter` builds an alias table and per-adapter action table from
the adapter registry (`platform_adapters.registry.create_default_adapters`)
at construction time, then resolves text in three steps, **in this
order**:

1. **Platform match** — longest matching `PLATFORM_ALIASES` substring in
   the text (case-insensitive) selects the adapter.
2. **Message split** — `_split_message()` finds a message-boundary marker
   (`" saying "`, `" that says "`, etc.) and splits the text into a
   prefix and the dictated message payload, *before* any verb matching
   happens.
3. **Action match** — first `ActionSpec` on that adapter whose verb list
   has a word-boundary match **against the prefix only** (never the
   message payload) selects the action.

Step 2 must happen before step 3. An earlier version matched verbs
against the full raw text, so a word inside the dictated message body
(e.g. "close" in "send a message to john saying check the close date")
could match a different action's verb list than the one actually
intended — which action won was an accident of `ACTIONS` declaration
order, not of what the command meant. Fixed and covered by
`tests/test_command_router.py`'s `test_message_body_does_not_collide_with_*`
cases (two independent collision pairs: `send_message` vs `close_app`,
and `send_message` vs `open_app`).

If platform or action matching fails, `resolve()` returns `None` and the
caller falls back to the pre-2a classification path (`ACTION_PATTERNS`,
`CODE_PATTERNS`, etc.) — this is why no regression testing was needed for
anything that doesn't name a known platform.

Target/message extraction handles `"... to TARGET saying MESSAGE"`
phrasing, including the `"saying"` / `"that says"` marker that
`daemon/intent_parser.py`'s simpler `_parse_send` does not split on —
needed for Phase 2b's "send a WhatsApp message to X saying Y" DoD
example to produce a correct `target`/`message`, not the whole trailing
clause dumped into one field.

### 4. Classification: `AgentCore/intent_router.py`

`IntentRouter.classify()` tries `CommandRouter.resolve()` after the
confirm/abort/followup checks and before `CODE_PATTERNS` (a resolved
platform+action match is more specific than a generic action pattern).
On a match, it returns `handler="action"` with the resolved `Intent`
attached at `extracted_entities["resolved_intent"]`.

### 5. Execution: `AgentCore/ui_executor.py`

`UIExecutor.execute_intent(intent)` is the new adapter-aware execution
path:

1. Look up the adapter for `intent.adapter` in the registry (lazily
   built via `platform_adapters.registry.create_default_adapters`, using
   `daemon.logging_utils.ActionLogger` for consistent logging with the
   daemon path).
2. If the adapter declares support for `intent.action`
   (`AdapterBase.supports()`), invoke it and map the result to an
   `ExecutionResult`.
3. If no adapter is registered for `intent.adapter`, fall back to the
   pre-2a raw `subprocess`/`os.startfile` path — but **only** for
   `open_app`/`close_app`, since those are the only two actions that had
   a legacy fallback before this phase. `send_message`/`read_unread` have
   no fallback; they simply weren't reachable before Phase 2a.

`ODAVLoop.execute()` checks for a resolved `Intent` on the classified
result and, if present, dispatches straight to `execute_intent()` —
skipping the OBSERVE/DECIDE plan-building pipeline entirely, since the
`Intent` already fully specifies what to do.

## Why not a new data shape, and why not `AgentCore/platform_adapters/`'s `Plan`-based contract

Two contracts already existed (see the original diagnosis brief):
`daemon/platform_adapters/`'s `open_app/close_app/send_message/read_unread`
methods (5 real, working implementations), and
`AgentCore/platform_adapters/`'s `Plan`-based `build_plan/detect_ui/verify_action_result`
contract (160 folders, but confirmed to contain non-trivial stub-quality
issues — e.g. hardcoded placeholder coordinates). Phase 2b's canonical-contract
decision (recommended: the `daemon`/`platform_adapters` contract, since
it is the only one proven end-to-end) determines which adapters this
architecture wires against; Phase 2a's `ActionSpec`/`PLATFORM_ALIASES`
mechanism is contract-agnostic and works the same way regardless of which
contract's adapters ultimately implement the declared actions.

## What Phase 2a does *not* do

- No 160-folder audit or porting (Phase 2b).
- No `--daemon` flag fix (Phase 2b).
- No NLU beyond word-boundary verb matching — deliberately simple and
  testable per-command, not a generalized language model. Ambiguous or
  multi-platform commands in one sentence are out of scope; each command
  is expected to name one platform.
- `read_unread`'s `limit` parameter is not yet threaded from natural
  language (always uses the adapter's default) — nothing in the DoD
  required it, so it wasn't added speculatively.
