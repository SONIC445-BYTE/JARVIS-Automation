# AgentCore/platform_adapters/ Audit (Phase 2b step 4)

**Method:** every one of the 160 folders' `adapter.py` was scanned for known defect
signatures (see below), and 25 were individually read in full to establish ground
truth for the classification scheme before trusting the automated scan on the rest.
Full per-folder data: `platform_audit_raw.json` (scratchpad, not committed —
regenerate with the script in "Reproducing this audit" below).

## Headline finding

**None of the 160 folders is a complete, ready-to-port implementation of its full
declared action set.** At most **3 folders (`amazon`, `google`, `chrome`)** have
fully real, working logic for their (small, 1-3 action) scope. Everything else has
at least one of: fabricated logic that does nothing real, hardcoded placeholder
coordinates, an unimplemented "final step" (composes/searches but never completes
the actual verb), or a pure copy-paste scaffold with an aspirational action list.

This is a much starker result than the original diagnosis brief's spot-check of
`whatsapp` (which found *one* real-but-incomplete adapter) suggested — `whatsapp`
turns out to be one of the *better* folders in the library, not a representative
sample of a mixed-quality set.

## Classification

| Class | Count | Meaning |
|---|---|---|
| (a) Real, complete for its declared actions | **3** | `amazon`, `google`, `chrome` |
| (b) Real logic, but incomplete or has a fixable defect | **8 confirmed** (likely ~15-25 more, unverified) | See below |
| (c) Fabricated/non-functional regardless of input | **149** | See below |

### (a) — real, complete, ready to port (3)

| Folder | Actions | Why it's real |
|---|---|---|
| `amazon` | `search_product` | Navigates to `amazon.com/s?k=<query>` — Amazon's real, documented search URL. |
| `google` | `search` | Navigates to `google.com/search?q=<query>` — real, documented. |
| `chrome` | `open_url`, `new_tab`, `close_tab` | Real navigation + standard `Ctrl+T`/`Ctrl+W` hotkeys, not fabricated. |

Note: `amazon` and `google` are single-action search wrappers that add little over
`browser`'s own `send_message` (which already does "go to X" / generic navigation
per Phase 2a). Not worth separately wiring unless a dictated command specifically
needs to be recognized as "search Amazon for X" rather than a generic browse.

### (b) — real logic, but incomplete or defective (8 confirmed by direct read)

| Folder | Real part | Defect |
|---|---|---|
| `whatsapp` | Real keyboard-automation plan (open, find contact, type, send) | Hardcoded placeholder coordinates `{"x": 0, "y": 0}` for the send button, `confidence=0.5` — originally flagged in the diagnosis brief. |
| `notepad` | `type_text` is real | `save_file`'s click coordinates are explicitly marked `# Guess` in the code — admittedly not measured. |
| `gmail` | Compose deep-link (`mail.google.com/mail/?view=cm&fs=1&to=...`) is a real, documented Gmail URL | Never clicks Send — comment: *"Ideally wait for load and click send, but deep link opens compose window."* Opens a pre-filled draft, does not send. |
| `twitter` | Compose intent URL (`twitter.com/intent/tweet?text=...`) is real, documented | Never clicks Post — same "opens pre-filled, doesn't complete" gap. `detect_ui` also checks `"x" in title`, which matches almost any window title. |
| `spotify` | Search URL is real | `play_music`'s "click Play on first result" step is commented out — search works, playback does not. |
| `youtube` | Search URL is real | `play_video`'s click-through is a no-op (`pass`) — same gap as Spotify. |
| `explorer` | `open_folder` logic is real | `detect_ui` unconditionally returns `True` regardless of the actual window ("Plausible fallback for now") — cannot actually detect Explorer is active. |
| `calculator` | `calculate` (type expression + Enter) is real | No `open_app`/`close_app` action declared at all — can't be opened/closed through this adapter, only used once already active. |

**Pattern across all 8:** the *first* step of a multi-step action (navigate to
search/compose page) is consistently real; the *last* step (click Send/Post/Play)
is consistently missing, guessed, or the detection logic around it is broken. This
looks like a "half-implemented then abandoned" pattern repeated across the library,
not independent one-off issues.

An estimated further 15-25 folders likely share this same "real navigate, fake or
missing completion" shape based on the automated scan, but were not individually
read — see "What's not yet verified" below.

### (c) — fabricated or scaffold-only, non-functional regardless of input (149)

Two sub-patterns, both confirmed by direct read on multiple examples:

**Copy-paste scaffold (16 folders)** — `adobe_acrobat`, `android_studio`,
`arduino_ide`, `git_cli`, `github_desktop`, `lm_studio`, `ms_excel`,
`ms_powerpoint`, `ms_word`, `nodejs_runtime`, `ollama`, `onedrive`, `pycharm`,
`python_runtime`, `vscode`, `winrar`. Each declares an elaborate, plausible-sounding
`supported_actions` list (30-55 entries) but `build_plan` ignores `action_name`
entirely and always emits the same one generic `launch_app` step. The action list
is aspirational — none of it is actually implemented differently per action.

**Fabricated URL scheme (133 folders)** — the large majority of the library,
including `netflix` and `telegram` (the diagnosis brief's own motivating examples)
and `outlook`. Pattern: `build_plan` builds a URL like
`https://netflix.com/?action={action_name}&q={query}` and navigates to it. **This
is not a real API** — Netflix, Telegram, and the rest have no such query-string
action protocol; this just loads the site's homepage with meaningless query
parameters attached. Confirmed by direct read on `netflix`, `telegram`, `outlook`;
the other 130 share the identical `f"...?action={action_name}..."` structure per
automated scan. None of these are closer to working than "opens the website."

Full list of the 133 fabricated-URL folders and the 16 scaffold folders is in
`platform_audit_raw.json`.

## What's not yet verified

The 8 (b)-classified folders and the `netflix`/`telegram`/`outlook` (c) samples
were read in full. The remaining ~130 (c)-classified-by-heuristic folders were
**not** individually read — their `?action=` fabricated-URL signature was confirmed
structurally identical to the 3 that were read, which is strong but not exhaustive
evidence. If a specific platform from that list turns out to matter (e.g. for the
OPD software list once provided), it should get an individual read before being
trusted as (c) rather than assumed.

## Implication for Phase 2b wiring

Given this, "port (a)-classified adapters" (the original Phase 2b step 4
instruction) yields almost nothing to port — 3 folders, 5 total actions, 2 of
which (`amazon`, `google`) are redundant with `browser`'s existing capability.
The daemon adapters remain the only substantial working automation surface. Real
expansion of the 160-platform library requires writing new, real implementations
(measuring actual coordinates, verifying actual URL schemes, completing the
missing "click send/post/play" steps) — not porting existing code, since there is
very little existing code that's actually correct.

## Reproducing this audit

```python
import os, re
base = 'AgentCore/platform_adapters'
folders = sorted(e for e in os.listdir(base) if os.path.isdir(os.path.join(base, e)) and e != '__pycache__')
for d in folders:
    content = open(os.path.join(base, d, 'adapter.py'), encoding='utf-8').read()
    flags = []
    if 'launch_app' in content and 'not in self.supported_actions' in content:
        flags.append('template')
    if re.search(r'["\']x["\']\s*:\s*0\s*,\s*["\']y["\']\s*:\s*0', content):
        flags.append('zero_coords')
    if re.search(r'#\s*[Gg]uess', content):
        flags.append('guess_comment')
    if re.search(r'\?action=', content):
        flags.append('fabricated_url')
    if re.search(r'#\s*steps\.append|ideally|Fallback: User manually', content, re.I):
        flags.append('incomplete_action')
    print(d, flags)
```
