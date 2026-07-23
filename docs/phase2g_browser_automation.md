# Phase 2g: Real Browser Automation (from scratch)

## Why from scratch

Confirmed in the Phase 2c-prime investigation: `AgentCore/ui_agent/inspector/browser_adapter.py`
looks like a real Selenium/Playwright wrapper (real method names --
`open_url`, `get_elements`, `perform_action`, `is_page_loaded`) but
`self.driver` is never assigned anywhere in the class. `get_elements()`
therefore always returns `[]`, `perform_action()` always fails with "no
elements found," and `is_page_loaded()` fakes success via `time.sleep(1);
return True`. None of the actual click/type/verify logic is reusable.
The interface *shape* (open a page, find elements, act on them, verify)
is a reasonable reference, but every implementation underneath it has
to be built new.

## Selenium vs Playwright: chose Playwright

| | Selenium | Playwright |
|---|---|---|
| Waiting | Manual (`WebDriverWait` + explicit conditions) | Built-in auto-wait on every action -- an element must be visible, stable, and receive events before a click/fill proceeds |
| Driver management | Separate webdriver binary (mitigated since Selenium 4.6's Selenium Manager, but still a moving part) | Ships its own browser binaries via `playwright install`, versioned with the library |
| Python API | Synchronous | Both sync and async; used the sync API here (`playwright.sync_api`) to match the rest of this codebase's synchronous adapter style -- no asyncio introduced elsewhere |
| Selector engine | CSS/XPath only | CSS/XPath plus `get_by_text()`, `get_by_role()` -- directly useful for "click Play/Send/Post," which is closer to how a human identifies the element than a hand-written CSS selector |

The auto-wait behavior is the deciding factor for this specific task:
Phase 2g's core requirement is that an adapter actually *completes* the
requested action (clicks Send, not just loads the compose page), and
the most common way that fails in practice is clicking before the
button has finished rendering/becoming interactive. Playwright's
locators handle that by default; Selenium requires writing that
waiting logic by hand for every single interaction, which is exactly
the kind of narrow, easy-to-get-wrong-per-instance code this project
has already paid for multiple times (see the `command_router.py` bug
family). Already installed in this environment (`playwright==1.58.0`,
Chromium binary present) -- no new setup needed here, but this is a
new dependency the project carries going forward; add `playwright` to
`requirements.txt` and run `playwright install chromium` on any new
machine.

## Architecture

### `platform_adapters/browser_automation.py` -- `BrowserSession`

A single, **persistent** Playwright browser context, launched once and
reused across actions and adapters (`get_shared_session()`), not
relaunched per command. Two reasons this matters, not just performance:

1. Session/cookie persistence -- a manually-completed login or CAPTCHA
   solve (see below) has to survive into the *next* action, not just
   the rest of the current one.
2. `headless=False` by default -- the browser window is visible so a
   physician can actually see and interact with a login/CAPTCHA screen
   when asked to.

Thin wrapper methods (`goto`, `click_text`, `click_role`, `fill`,
`wait_for_url_contains`) all return `bool` / raise on genuine failure --
no method fakes success the way `AgentCore/ui_agent`'s equivalents did.

### Honest completion, not "no exception was thrown"

Every browser-equivalent adapter action ends with an explicit
post-condition check specific to that action -- a URL change, a
confirmation element appearing, an input field clearing -- not just
"the click call didn't raise." If the post-condition isn't observed
within a timeout, the action returns `False`. See each adapter's
`send_message()` for the concrete signal it checks.

### CAPTCHA / login-wall handling: detect, pause, resume

`BrowserSession.check_blocked()` scans the current page's URL/title/body
text for common CAPTCHA and login-wall markers and raises `BlockedError`
with an honest, physician-facing explanation. This is a heuristic, not
exhaustive -- new block patterns will need new markers over time.

`BlockedError` propagates through `UIExecutor.execute_intent()` as a
new `ExecutionStatus.BLOCKED` (distinct from `FAILED` -- a block isn't
a failure, it's a pause), through `ODAVLoop.execute()` as
`ODAVResult.blocked=True`, and into `jarvis.py`'s conversation loop as
`PendingResume` state (same shape as Phase 2c's `PendingInstall`):

1. The physician hears/sees the exact block reason and is told to
   complete it manually, then say "continue."
2. `PersistentWakeService._pending_resume` holds the original command
   text between turns.
3. On an affirmative next turn, the *same* command is re-executed
   through `ODAVLoop.execute()` -- since the browser session persisted,
   this re-checks `check_blocked()` on the (now hopefully
   post-login/post-CAPTCHA) page and proceeds with the actual action if
   the block has genuinely cleared. Not a silent failure, not an
   infinite hang, not a fake success -- and not a fresh restart from
   scratch either, since the persistent session means "resume" means
   what it says.

## Platforms built this round

**WhatsApp Web** and **Telegram Web** -- chosen because they map
directly to existing native adapters (`whatsapp_desktop`,
`telegram_desktop`), which is the actual use case the eventual Q2
3-way branch exists for ("WhatsApp Desktop isn't installed -- use
WhatsApp Web instead, or install the app?"), and because both
**require login on a fresh session** (QR code / phone number), which
is a real, live way to prove the block-detection/pause/resume flow
works against genuine websites, not a synthetic test fixture.

Not built this round (backlog, same incremental philosophy as Phase
2e): Gmail web compose, YouTube/Spotify web playback, Twitter/X web
compose. Streaming/webmail/web-chat platforms remain the natural next
targets given their web apps are the most reliable across this
category.

## What was and wasn't verified live

**Verified live** (real browser, real websites): `BrowserSession`
launches a real, visible Chromium window; navigating to
`web.whatsapp.com` and `web.telegram.org` and observing the genuine QR
login screen each site shows on a fresh, unauthenticated session;
`check_blocked()` correctly detecting that real login-wall and raising
`BlockedError` with the right message; the block propagating through
`UIExecutor`/`ODAVLoop` as `BLOCKED`, not a generic failure.

**Not verified live**: an actual message send completing end-to-end
after a real QR-code login. That requires pairing a real phone/account
with the browser session, which isn't something this environment can
do (no phone available to scan a QR code). The send-and-verify logic
past the login wall is covered by unit tests with `BrowserSession`
mocked -- clearly a lower bar than the live-verified block-detection
path, and called out here rather than implied to be equally proven.

## Not wired: Q2 3-way branch

Per the standing rule, `resolution_gate.py`'s Q2 branch stays 2-way.
These two adapters exist and are tested standalone; they are not yet
reachable from the conversation loop's "app not installed" flow.
