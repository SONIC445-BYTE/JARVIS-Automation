# Phase 2d: Porting the 11 Real/Near-Real Adapters

Ports the 11 audit-confirmed class-(a)/(b) `AgentCore/platform_adapters/`
folders (`docs/adapter_audit.md`) onto the daemon contract
(`platform_adapters/registry.py`), fixing each folder's specific defect
as part of porting rather than carrying it over.

## Finding: 2 of the 11 needed no work at all

`whatsapp` and `gmail` are already fully correct in their daemon
versions (`whatsapp_desktop_adapter.py`, `gmail_browser_adapter.py`) —
live since Phase 2a. The audit's defects (hardcoded `{x:0,y:0}`
coordinates for whatsapp's send button; gmail never completing the send
step) exist **only** in the separate, orphaned
`AgentCore/platform_adapters/whatsapp` and `/gmail` folders, which use a
different, inferior strategy (coordinate-guessing / incomplete
Plan-building) than the daemon versions (keyboard shortcuts: Enter to
send WhatsApp, Ctrl+Enter to send Gmail). Nothing was changed for these
two; porting them means recognizing they're already done.

## Finding: most "coordinate defects" don't actually need UIScanner

Per the Phase 2c-prime investigation, `AgentCore.ui_perception.UIScanner`
is real and usable — but tracing through the remaining 9 platforms, only
**2** (Spotify, YouTube) genuinely need it. Everything else has a real,
reliable keyboard shortcut that sidesteps coordinate-finding entirely —
which is a *more* robust fix than routing through UIScanner, not a
compromise:

| Platform | Fix | Mechanism |
|---|---|---|
| `chrome` (new_tab/close_tab) | Added to `browser_adapter.py` | Ctrl+T / Ctrl+W |
| `amazon`, `google` | New adapters | Real documented search URLs |
| `calculator` | New adapter | Type expression + Enter (+ word-operator normalization, see below) |
| `explorer` | New adapter | `os.startfile` — no `detect_ui` concept in the daemon contract, so that specific audit defect doesn't carry over |
| `notepad` save | Added to `text_editor_adapter.py` | Ctrl+S (replacing the original's `# Guess`-commented coordinates) |
| `twitter` post | New adapter | Ctrl+Enter (Twitter's real post shortcut, same convention as Gmail) |
| `spotify` play | New adapter | **UIScanner** — no fixed shortcut for "play this specific search result" |
| `youtube` play | New adapter | **UIScanner** — same reasoning, uses position (topmost-then-leftmost clickable) since a video thumbnail has no fixed text label unlike Spotify's "Play" button |

`platform_adapters/element_finder.py` wraps `UIScanner` for these two
cases, imported lazily (inside the function, not at module load) to
avoid worsening the Phase-3-flagged `AgentCore/__init__.py` eager-import
coupling for the other 9 adapters that don't need it. Both `play`
implementations return `False` (honest failure) when the element can't
be found — never a fake/simulated success, unlike the original audit
folders' commented-out or no-op click-through.

## Bugs found and fixed along the way

1. **Custom-action calling convention gap**: `UIExecutor._invoke_adapter_action`'s
   fallback for actions beyond the base 4 called `method()` with no
   arguments. `calculate` needs the expression. Fixed: custom actions are
   now called uniformly as `method(target, message)`; adapters that
   don't need one or the other just declare it as an unused/defaulted
   parameter (see `new_tab`/`close_tab`).
2. **Message-prefix stripping only applied in one of two code paths**:
   `command_router.py`'s `_extract_target` stripped a leading verb
   (`"send "`, `"type "`, etc.) off the message only when a `" to "`
   marker was present, not in the no-marker fallback branch. Fixed by
   factoring both into a shared `_strip_verb_prefix()` — otherwise
   `"calculate 5 plus 3"` would send Calculator the literal string
   `"calculate 5 plus 3"`, not `"5 plus 3"`.
3. **`save_file` target/message declaration mismatch**: initially declared
   `requires_message=True`, but the natural phrasing ("save notepad **to**
   report.txt") puts the filename in `target` via the established `" to "`
   marker, not `message`. Declaring `requires_target=True` fixed the
   marker-present case, but exposed a second issue: when no filename is
   given at all, `target` falls back to the platform alias itself
   ("notepad") — which would have been "saved" as a literal filename.
   Fixed by filtering that fallback value out in `save_file()` itself.
4. **Live-testing caught a real correctness gap in the ported logic,
   not just my new plumbing**: "calculate 12 times 8" typed the literal
   English words into Calculator, which doesn't understand them (needs
   `12*8`). This was present in the *original* audit folder too (it just
   typed the raw expression), not something I introduced — but since
   `calculate` is a genuinely new capability (not already covered by any
   daemon adapter), it needed fixing to actually work. Added
   `_normalize_expression()`: `times`/`multiplied by` → `*`,
   `plus`/`added to` → `+`, `minus` → `-`, `divided by`/`over` → `/`.
5. **`new` platform aliases for natural phrasing**: `calculate 5 plus 3`
   and `post a tweet saying X` don't name "calculator"/"twitter"
   explicitly. Added `"calculate"` and `"tweet"` as additional
   `PLATFORM_ALIASES` (not from the audit — found via testing).

## Verified

- All 11 platforms' key actions resolve correctly via `CommandRouter`
  (`tests/test_phase2d_ported_adapters.py`), including verb-collision
  regression checks against the now-larger 12-adapter set (`close tab`
  vs `close_app`, etc.) and that `whatsapp`/`gmail` are unaffected.
- Dry-run execution verified for every action via
  `UIExecutor.execute_intent()`.
- `play`'s honest-failure and honest-success paths both verified with
  `element_finder` mocked (no dependency on a real screen scan in
  automated tests).
- Live, real, end-to-end verification through the actual conversation
  loop (`ODAVLoop.execute()`) for the one fully safe, reversible,
  genuinely-new capability: open Calculator → calculate "12 times 8"
  (correctly typed as `12*8` after the normalization fix) → close
  Calculator. Twitter/Spotify/YouTube's live real-world actions (posting
  publicly, playing media) were not run live in this session — covered
  by dry-run + mocked tests instead, consistent with not taking
  irreversible/public-facing actions without a separate explicit
  go-ahead.

Full suite: 98 passed, same 3 pre-existing unrelated failures as the
Phase 1 baseline (`test_auto_write`, `test_routing`, `test_tier2_flow` —
unrelated to this work).
