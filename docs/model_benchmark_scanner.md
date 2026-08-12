# LLM Benchmark Scanner — design note

**Status:** built. `AgentCore/model_scanner/`.
**Purpose:** rank coding-capable LLMs by measured benchmark performance, in two sections (cloud API / open-weights), to inform the **developer-configured model slot** that Adaptive Adapter Generation (§4.4b) already specifies.

---

## 1. Data classification — stated explicitly, before any code was written

Per §3.7b's own rule, the data-class gate is a deterministic lookup that must be *stated*, not left implicit.

> **This tool is classified `general`, not `clinical`.**

Justification, field by field against what actually moves:

| What this tool sends | What it receives | Contains clinical data? |
|---|---|---|
| An unauthenticated HTTPS GET to a public benchmark leaderboard file. No body, no query parameters derived from any local state. | A public list of model names and benchmark scores. | **No** — in either direction. |

There is no code path by which patient data, a physician's utterance, an `Intent.source_text`, a queue entry, or any Boundary Ledger content can reach this tool. It does not accept caller-supplied input that is forwarded anywhere. **The `general` classification is therefore a property of the tool's shape, not a promise about how it is used** — which is the standard §3.7b demands, and the same reasoning that makes Adaptive Adapter Generation's cloud model slot permissible (it runs offline, at development time, with no clinical data in scope).

**The failure mode this classification must not drift into:** a convenient, already-built network fetcher gets reused for something adjacent that *does* carry clinical context. Guard: this package performs exactly one outbound request, to a hardcoded allow-list of benchmark URLs, and exposes no general-purpose fetch helper. Anything needing a different URL is a code change and a review, not a config value.

## 2. It recommends. It never selects.

Adaptive Adapter Generation's slot is **developer-configured** — the developer pastes an API key or points at a local Ollama endpoint. This tool exists to make that choice better informed. It has:

- no write access to any config,
- no knowledge of which model is currently configured,
- no "apply" verb of any kind.

Output is a ranked table for a human to read. That boundary is deliberate: auto-selecting a code-generation model on benchmark score would be a system silently changing what writes code for a hospital deployment, on the strength of a third-party number.

## 3. Source — real and checkable, not scraped guesswork

**Primary: the Aider polyglot coding benchmark.**
`https://raw.githubusercontent.com/Aider-AI/aider/main/aider/website/_data/polyglot_leaderboard.yml`

Chosen because it is a **versioned YAML file in a public git repository**, not an HTML page to be scraped or a JS-rendered dashboard. It has a stable schema (~24 fields per entry), a real methodology, and per-entry `date` and `commit_hash` fields, so entries carry their own provenance. Verified live before building: the file parses, and the schema is as documented.

Deliberately *not* used: any leaderboard that requires scraping rendered HTML, any aggregate "LLM rankings" site with undisclosed methodology, and anything requiring an API key. If the primary source is unreachable the tool **reports that and exits non-zero** — it does not fall back to a cached guess or a hardcoded list. Same fail-closed discipline as `secure_key.resolve_key()`: there is no return value meaning "no real data, here's something plausible."

## 4. Staleness is shown twice, deliberately

The blueprint's custody rule is about not trusting an artifact whose freshness you cannot see. A single "last checked" timestamp would satisfy the letter of that and miss the point: it tells you when *we fetched*, not how old the *data* is. A leaderboard we fetched 30 seconds ago whose newest entry is ten months old is stale, and a single timestamp actively conceals that.

So every rendering shows both:

- **Fetched:** when this process retrieved the file.
- **Newest benchmark entry:** the maximum `date` across parsed entries, with an explicit age in days.

When the newest entry is older than 90 days the tool prints a visible staleness warning. **This was not hypothetical when built** — the source's newest entries were already several months old, which is exactly the case a single timestamp would have hidden.

## 5. Cloud vs. open-weights — an explicit table, never inference

The source does not carry an open/closed flag. Two options: infer from the model name, or maintain an explicit map.

**Inference was rejected.** This project has been burned twice by inferring a contract from an identifier name (`GeneratorHelper`/`LLMAdapter`'s `hasattr` checks; RHINAL's `vaultWorthy`), and the standing rule from those is *read the source, never infer from names*. Model naming is exactly as unreliable — vendor prefixes get renamed, open-weight releases carry vendor names, and a substring match on "gpt" or "llama" would be a guess wearing a fact's clothing.

So: an explicit `LICENSING` map in `classification.py`, one entry per known model family, each with a short provenance note. Anything not in the map renders in a third **`unclassified`** section rather than being guessed into one of the two. An unclassified model is a visible prompt to add an entry, not a silent miscategorisation.

## 6. What this tool does not do, and must not grow into

- It does not benchmark anything itself. It reports someone else's published measurements, and names whose they are.
- It does not rank by cost, speed, or context length. Coding capability only — that is the slot's actual constraint.
- It does not decide, recommend a default, or express a preference beyond the source's own ordering.
- **It does not bear on the own-vs-adopt question for the coding engine, and must not be cited as if it does.** That question is explicitly undecided. A tool that lists available third-party models is not evidence for adopting one; it would equally inform a decision to own. Anyone reaching for this output in that argument should note it was built to inform the *model slot*, a decision already made in §4.4b, not the architecture question above it.

## 7. Usage

```bash
python -m AgentCore.model_scanner
```

`--json` emits machine-readable output. `--min-entries N` fails if the source yields fewer than N parsed entries, for use as a sanity gate.
