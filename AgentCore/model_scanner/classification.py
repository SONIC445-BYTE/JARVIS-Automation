"""
Cloud-API vs. open-weights classification for benchmarked models.

**An explicit table, deliberately not inference.** The source leaderboard
carries no open/closed flag, so this has to come from somewhere. Matching
on substrings of the model name ("gpt" -> cloud, "llama" -> open) was
considered and rejected: this project has been burned twice by inferring
a contract from an identifier name (GeneratorHelper/LLMAdapter's hasattr
checks against methods that never existed; RHINAL's `vaultWorthy`, which
reads like a save/skip gate and isn't). The standing rule from those is
"read the source, never infer from names," and model naming is at least
as unreliable -- open-weight releases carry vendor names, vendors rename
prefixes, and a fine-tune of an open model may be served only as a
hosted API.

So: an explicit map, each entry carrying why it's classified that way.
Anything absent renders as UNCLASSIFIED rather than being guessed into a
bucket -- a visible prompt to add an entry, not a silent miscategorisation.
"""
from dataclasses import dataclass
from enum import Enum


class Licensing(Enum):
    CLOUD = "cloud"          # reachable only as a hosted API; weights not published
    OPEN_WEIGHTS = "open"    # weights downloadable and runnable locally
    UNCLASSIFIED = "unclassified"


@dataclass(frozen=True)
class FamilyRule:
    #: Lowercased substring matched against the leaderboard's model string.
    #: A *family* prefix, not a guess at a full name -- leaderboards spell
    #: individual versions inconsistently ("Claude 3.5 Sonnet",
    #: "claude-3-5-sonnet-20241022"), but the family token is stable.
    token: str
    licensing: Licensing
    #: Why this classification. Kept in the data so a future reader can
    #: check the reasoning rather than trusting the label.
    basis: str


#: Ordered longest-token-first at match time, so a more specific rule wins
#: over a more general one that happens to be a substring of it.
LICENSING_RULES: tuple[FamilyRule, ...] = (
    FamilyRule("claude", Licensing.CLOUD, "Anthropic; hosted API only, weights unpublished"),
    FamilyRule("gpt-", Licensing.CLOUD, "OpenAI; hosted API only"),
    FamilyRule("o1", Licensing.CLOUD, "OpenAI reasoning line; hosted API only"),
    FamilyRule("o3", Licensing.CLOUD, "OpenAI reasoning line; hosted API only"),
    FamilyRule("o4", Licensing.CLOUD, "OpenAI reasoning line; hosted API only"),
    FamilyRule("qwq", Licensing.OPEN_WEIGHTS, "Alibaba QwQ reasoning line; weights on HuggingFace"),
    FamilyRule("gemini", Licensing.CLOUD, "Google; hosted API only"),
    FamilyRule("grok", Licensing.CLOUD, "xAI; hosted API"),
    FamilyRule("deepseek", Licensing.OPEN_WEIGHTS, "DeepSeek publishes weights (MIT / bespoke open licence)"),
    FamilyRule("qwen", Licensing.OPEN_WEIGHTS, "Alibaba Qwen; weights on HuggingFace, Apache-2.0 for most sizes"),
    FamilyRule("llama", Licensing.OPEN_WEIGHTS, "Meta; weights downloadable under the Llama community licence"),
    FamilyRule("mistral", Licensing.OPEN_WEIGHTS, "Mistral; open-weight releases (note: some models are API-only)"),
    FamilyRule("codestral", Licensing.OPEN_WEIGHTS, "Mistral code model; weights published"),
    FamilyRule("gemma", Licensing.OPEN_WEIGHTS, "Google open-weights line"),
    FamilyRule("glm", Licensing.OPEN_WEIGHTS, "Zhipu GLM; weights published"),
    FamilyRule("kimi", Licensing.OPEN_WEIGHTS, "Moonshot Kimi; weights published"),
)


def classify(model_name: str) -> tuple[Licensing, str]:
    """
    Returns (licensing, basis) for a leaderboard model string.

    Unknown models return UNCLASSIFIED with an actionable basis rather
    than a default bucket. "Probably cloud" is not a fact, and a wrong
    bucket here would silently misinform the model-slot decision this
    whole tool exists to support.
    """
    haystack = model_name.lower()

    # Combination entries ("DeepSeek R1 + claude-3-5-sonnet", i.e. an
    # architect/editor pairing) are genuinely neither bucket. Caught by
    # running against the real leaderboard: such an entry was landing in
    # OPEN_WEIGHTS purely because "deepseek" is a longer token than
    # "claude" and won the length-ordered match. Token length is a
    # tie-break heuristic, not a correctness criterion, and it has no
    # business deciding this. A pairing that includes any hosted model
    # cannot be run locally, so calling it open-weights would actively
    # mislead the one decision this tool exists to inform.
    if " + " in haystack:
        return (
            Licensing.UNCLASSIFIED,
            "multi-model configuration (architect/editor pairing) -- licensing is per-model, "
            "not per-row; classify the individual models instead",
        )

    for rule in sorted(LICENSING_RULES, key=lambda r: len(r.token), reverse=True):
        if rule.token in haystack:
            return rule.licensing, rule.basis
    return (
        Licensing.UNCLASSIFIED,
        "no entry in LICENSING_RULES -- add one in classification.py rather than guessing",
    )
