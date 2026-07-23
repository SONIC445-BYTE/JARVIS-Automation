# Resolution & Availability Gate (Phase 2c)

## Problem

Before this phase, a command naming a platform with no working adapter
(e.g. "open netflix") or a real-adapter platform whose app isn't
installed (e.g. "open telegram" with Telegram not installed) fell
through to whatever generic classification came next -- typically the
LLM chat handler, producing an unrelated conversational response instead
of an honest "I can't do that" or "want me to install it?" This phase
inserts a two-question gate ahead of execution so every command produces
a distinct, honest outcome.

## Components

### `platform_adapters/platform_catalog.py`

Machine-readable catalog of all 160 `AgentCore/platform_adapters/`
folder names, generated from the Phase 2b audit (`docs/adapter_audit.md`).
Each entry has a display name, text-matching aliases, and an audit
classification (a/b/c, informational only). Separately,
`DAEMON_ADAPTER_FOR` maps the handful of catalog keys that have an
actual *working* adapter today (`chrome`, `notepad`, `whatsapp`,
`telegram`, `gmail` -> the 5 daemon adapters) -- this is the real
"is there an adapter" signal, not the audit classification. Audit class
(a)/(b) describes code quality in a library that hasn't been ported onto
the working contract yet (that's Phase 2d); it does not mean the
platform is controllable today.

### `platform_adapters/availability.py` -- `AvailabilityChecker`

Enumerates installed applications via registry uninstall keys + AppX
packages (same read-only method used ad hoc in Phase 2b step 5), and
answers `is_installed(aliases) -> bool` by substring match. Cached at
construction; call `.refresh()` to re-scan. A module-level cache in
`resolution_gate.py` ensures the real ~1-2s scan runs once per process
(not once per `IntentRouter()` instance -- both `jarvis.py` and
`ODAVLoop` construct their own).

### `AgentCore/resolution_gate.py` -- `ResolutionGate`

```
check(text) -> GateResult
```

1. Try `CommandRouter.resolve()` (Phase 2a). If it resolves:
   - **Q2**: is the platform installed (`AvailabilityChecker`)? Yes ->
     `RESOLVED` (caller executes as before). No -> `NOT_INSTALLED`,
     with the adapter's real declared actions and a winget package id
     if one exists.
2. If `CommandRouter.resolve()` returns nothing, check whether the text
   names a *catalogued* platform that just isn't wired
   (`find_catalog_entry`, excluding anything in `DAEMON_ADAPTER_FOR` --
   a wired platform whose verb didn't match must not be misreported as
   "no adapter"). If so -> **Q1 = no**: `NO_ADAPTER`. Otherwise ->
   `PLATFORM_UNKNOWN`, and the caller falls through to normal
   classification unchanged.

Every `GateResult` carries a distinct `.message` -- there is no silent
"Done." anywhere in this flow, matching the Phase 1 `CodeEngine`
success/failure contract.

### `platform_adapters/winget_installer.py`

Thin, mockable wrapper around `winget install --id <id> --source <src>
-e --silent --accept-package-agreements --accept-source-agreements`.
Package ids were verified against a real `winget search`, not guessed:

| Adapter | Package | Source |
|---|---|---|
| `browser` | `Google.Chrome` | winget |
| `telegram_desktop` | `Telegram.TelegramDesktop` | winget |
| `whatsapp_desktop` | `9NKSQGP7F2NH` | msstore |
| `text_editor` | *(none)* | Notepad ships with Windows |
| `gmail_browser` | *(none)* | Gmail is a website, not an installable app |

The two `None` entries are correct, not gaps -- they produce the honest
"can't find it in the package manager, install manually" branch, which
is the accurate answer for a platform with no separate installable
package.

### `jarvis.py` -- pending-install conversation state

`PersistentWakeService._pending_install: Optional[PendingInstall]`
holds state between "want me to install it?" and the user's next turn.
The conversation loop checks this *before* normal intent classification
on every turn. `_handle_install_confirmation(text)`:

- Not affirmative (including ambiguous replies) -> decline, never
  installs without an unambiguous yes.
- Affirmative + no winget id -> honest "can't find it, install manually".
- Affirmative + winget id -> runs the install, and only on success
  refreshes `AvailabilityChecker` and retries the *original* command
  through `ODAVLoop.execute()` -- the user doesn't have to repeat
  themselves once installation succeeds. Install failure does not retry.

## Testing approach

`winget install` and the availability re-scan are mocked in every
automated test (`tests/test_install_confirmation_flow.py`) -- these
never install real software or spawn real subprocesses, regardless of
machine state. `NO_ADAPTER` and the initial `NOT_INSTALLED` prompt were
additionally verified live (real `IntentRouter`, real `AvailabilityChecker`
against this machine's actual state, real `PersistentWakeService`
method) through a full two-turn exchange ending in decline -- see the
diagnosis conversation for the transcript. The confirm+install+retry
path was not run live in this session (that would install real software
without a separate explicit go-ahead); it is covered by the mocked test
plus the live-verified building blocks (gate message generation, retry
call shape) it's composed from.

## Known limitation

Catalog aliases are auto-derived (folder name + declared display name)
and don't always match real installed-software naming -- e.g. `vscode`'s
aliases (`"vs code"`, `"vscode"`) don't match the real registry entry
"Visual Studio Code" (no contiguous substring match). Not fixed here:
`vscode` isn't one of the 5 wired platforms, so it doesn't affect this
phase's DoD, but alias quality will matter more as Phase 2d/2e wire more
platforms onto this gate.
