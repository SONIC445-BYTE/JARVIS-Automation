"""
Phase 2a: extensible command architecture.

Resolves natural language into a daemon.intent_parser.Intent by matching
adapter-declared platform aliases (AdapterBase.PLATFORM_ALIASES) and
action verbs (AdapterBase.ACTIONS) -- instead of a hardcoded per-platform
if/elif chain (daemon/intent_parser.py's parse_command) or a fixed
central verb enum (AgentCore/intent_planner.py's ActionType, 12 values,
no way to represent per-platform actions like Netflix play/pause).

Adding a new platform action means declaring it on that adapter's
ACTIONS list -- not editing this router or any central regex table. See
docs/command_architecture.md for the full rationale.

Converges on daemon.intent_parser.Intent as the shared data shape since
it already works end-to-end for daemon/dispatcher.py.
"""
from __future__ import annotations

import re
from typing import Dict, Optional, Type

from daemon.intent_parser import Intent
from platform_adapters.adapter_base import ActionSpec, AdapterBase
from platform_adapters.registry import create_default_adapters


class _NullLogger:
    """Adapters require a logger with .info(); this is used only to
    discover adapter classes/declarations, never to perform real actions."""

    def info(self, payload):
        pass

    def log_action(self, **kwargs):
        pass


_MESSAGE_MARKERS = (" saying ", " that says ", " saying: ", " with message ", " for ")
_TARGET_MARKERS = (" to ", " as ")
_MESSAGE_PREFIXES = (
    "send ", "message ", "text ", "write ", "email ", "mail ", "calculate ",
    "type ", "note ", "save ", "play ", "search ", "tweet ", "post ",
)

# Prepositions that introduce a target/trailing clause, not a verb. Verb
# matching is bounded to the text before the earliest of these -- a word
# inside a target name or trailing clause (e.g. "close" in "close-friend",
# "open" in "open-source-group") must never be mistaken for a different
# action's verb. _TARGET_MARKERS is included since target extraction and
# verb-scan bounding must agree on where the target starts.
_TRAILING_CONTEXT_MARKERS = _TARGET_MARKERS + (" from ", " on ", " in ", " about ")


class CommandRouter:
    """
    Resolves text -> Intent by matching declared platform aliases and
    action verbs, instead of a hardcoded per-platform chain or a fixed
    central action enum.
    """

    def __init__(self, adapter_classes: Optional[Dict[str, Type[AdapterBase]]] = None):
        self._adapter_classes = adapter_classes or self._default_adapter_classes()
        self._platform_aliases: Dict[str, str] = {}
        for key, cls in self._adapter_classes.items():
            for alias in cls.PLATFORM_ALIASES:
                self._platform_aliases[alias.lower()] = key

    @staticmethod
    def _default_adapter_classes() -> Dict[str, Type[AdapterBase]]:
        instances = create_default_adapters(logger=_NullLogger(), dry_run=True)
        return {key: type(instance) for key, instance in instances.items()}

    def resolve(self, text: str) -> Optional[Intent]:
        """Return an Intent if text names a known platform + a supported
        action for that platform, else None (caller should fall back to
        other classification).

        STRUCTURAL RULE (read before adding a new marker, verb, or
        matching step): every matching step in this method -- platform
        detection, verb detection, and any future one -- must scan only
        the "structure zone" computed by _structure_zone() below, never
        raw `text`/`lower` directly, and never the split-off message
        payload or the immediate target span. Four bugs were fixed one
        at a time before this rule was written down (message-body verb
        collision, target-name verb collision, trailing-clause verb
        collision, then this one -- payload text containing another
        platform's name misrouting or blocking resolution entirely,
        e.g. "search amazon for spotify gift cards" resolving to
        Spotify). All four were the same root cause: a matching step
        scanning payload/content text instead of command-structure text.
        _structure_zone() is the single enforcement point -- compute it
        once, scope every match to it, and this bug class cannot recur
        by a new step quietly re-implementing its own scan boundary.
        """
        lower = text.lower()

        # Compute message/target zones FIRST, before any matching --
        # this is pure syntactic marker-position processing, independent
        # of which platform or verb (if any) the text names.
        prefix_raw, prefix_lower, message, message_marker_found = _split_message(text, lower)
        platform_zone = _platform_scan_zone(prefix_lower)

        adapter_key = None
        matched_alias = ""
        for alias, key in self._platform_aliases.items():
            if alias in platform_zone and len(alias) > len(matched_alias):
                adapter_key = key
                matched_alias = alias

        if adapter_key is None:
            return None

        # Verb matching is bounded to the text before the earliest
        # trailing-context marker, so a word inside a target name or
        # trailing clause (e.g. "close" in "close-friend", "open" in
        # "open-source-group") is never mistaken for a different
        # action's verb. Multi-word verbs that legitimately contain one
        # of those marker words as part of the verb phrase itself (e.g.
        # browser's "go to", "navigate to") are matched against the
        # untruncated prefix instead, since truncating at " to " would
        # cut the verb phrase in half.
        verb_scan_lower = _bound_verb_scan(prefix_lower)

        adapter_cls = self._adapter_classes[adapter_key]
        matched_action: Optional[ActionSpec] = None
        for spec in adapter_cls.ACTIONS:
            for verb in spec.verbs:
                scan_text = prefix_lower if " " in verb else verb_scan_lower
                if _verb_matches(verb, scan_text):
                    matched_action = spec
                    break
            if matched_action:
                break

        if matched_action is None:
            return None

        # Bugfix (5th instance of the same "router hands adapters an
        # unclean value" family as extract_query() -- see adapter_base.py):
        # the leftover-prefix backfill below (verb + platform name, once
        # no explicit message marker is found) is only ever genuine
        # content for single-value actions (play/search/post, where
        # requires_target is False and the "message" field IS the whole
        # query). For two-field actions like send_message (requires_target
        # True, requires_message True), target and message are
        # independently real, dictated separately -- if no explicit
        # message marker (" saying ", " that says ", etc.) was found,
        # there is no message to backfill from, only router-internal
        # verb+platform text (e.g. "send whatsapp message to mom" with
        # no "saying" clause backfilling to "whatsapp message"). Gating
        # the backfill on requires_target stops it at the source instead
        # of trying to pattern-match the garbage back out afterwards.
        allow_message_backfill = not matched_action.requires_target
        target, message = _extract_target(prefix_raw, prefix_lower, message, allow_message_backfill)

        message_required_but_missing = (
            matched_action.requires_target and matched_action.requires_message and not message
        )

        return Intent(
            adapter=adapter_key,
            action=matched_action.name,
            target=target if (matched_action.requires_target and target) else matched_alias,
            message=message if matched_action.requires_message else "",
            message_required_but_missing=message_required_but_missing,
        )


def _verb_matches(verb: str, lower_text: str) -> bool:
    return re.search(rf"\b{re.escape(verb)}\b", lower_text) is not None


def _bound_verb_scan(prefix_lower: str) -> str:
    """Return the leading portion of prefix_lower up to the earliest
    trailing-context marker, so target names / trailing clauses are
    excluded from single-word verb matching."""
    earliest = len(prefix_lower)
    for marker in _TRAILING_CONTEXT_MARKERS:
        idx = prefix_lower.find(marker)
        if idx != -1:
            earliest = min(earliest, idx)
    return prefix_lower[:earliest]


def _split_message(raw: str, lower: str):
    """Split off a dictated message payload using explicit boundary
    markers (" saying ", " that says ", etc.). Returns
    (prefix_raw, prefix_lower, message, marker_found) -- message is ""
    and marker_found is False if no marker is present at all (verb
    matching and target extraction then run against the whole text, as
    for commands with no separate payload like "open browser" or "go to
    google.com").

    Also handles a "dangling" marker -- the marker word present with
    nothing dictated after it (e.g. "...to mom saying" with the command
    cut off before any content), which the exact substring match above
    misses since it requires trailing content. Found via adversarial
    testing: without this, the marker word itself ("saying") silently
    leaks into whatever field consumes the rest of the prefix (usually
    the target, via _extract_target's " to "/" as " split) instead of
    being recognized as an attempted-but-empty message. marker_found is
    still True here (a message was clearly attempted), just with an
    empty result -- callers must NOT treat this the same as "no marker
    was ever present" (see CommandRouter.resolve()'s
    message_required_but_missing)."""
    for marker in _MESSAGE_MARKERS:
        if marker in lower:
            split_at = lower.find(marker)
            prefix_raw = raw[:split_at]
            prefix_lower = lower[:split_at]
            message = raw[split_at + len(marker):].strip()
            return prefix_raw, prefix_lower, message, True

    rstripped = lower.rstrip()
    for marker in _MESSAGE_MARKERS:
        dangling = " " + marker.strip()
        if rstripped.endswith(dangling):
            split_at = rstripped.rfind(dangling)
            prefix_raw = raw[:split_at]
            prefix_lower = lower[:split_at]
            return prefix_raw, prefix_lower, "", True

    return raw, lower, "", False


def _extract_target(prefix_raw: str, prefix_lower: str, message: str, allow_message_backfill: bool = True):
    """Extract the target from the (already message-marker-truncated)
    prefix using whichever of _TARGET_MARKERS (" to ", " as ") appears
    last. If no message was split off by _split_message, the text before
    that marker becomes the message instead (covers "send X to Y" with
    no "saying" marker, and "go to X" navigation-style commands with no
    separate payload). With no target marker at all, the whole prefix
    (verb-stripped, trailing-clause-trimmed) becomes the message --
    covers "play X on Y" / "note X" style commands.

    allow_message_backfill gates both of those backfill paths: the
    caller (CommandRouter.resolve()) sets it to False for actions that
    require an independently real target (send_message-shaped) -- for
    those, leftover verb+platform prefix text is never genuine dictated
    content (there's no "saying"-style marker convention for it to have
    come from), so backfilling it would just be router structure noise
    passed off as a message. When False and no explicit message was
    captured, message stays "" -- the caller reports this honestly via
    Intent.message_required_but_missing rather than silently using it."""
    target = ""
    split_at, marker = _find_last_target_marker(prefix_lower)
    if split_at != -1:
        target_raw = prefix_raw[split_at + len(marker):]
        target_lower = prefix_lower[split_at + len(marker):]

        # Trim any further trailing clause off the target itself, e.g.
        # "close-friend on whatsapp" -> "close-friend".
        cut = len(target_raw)
        for trailing_marker in _TRAILING_CONTEXT_MARKERS:
            if trailing_marker in _TARGET_MARKERS:
                continue
            idx = target_lower.find(trailing_marker)
            if idx != -1:
                cut = min(cut, idx)
        target = target_raw[:cut].strip()

        if not message and allow_message_backfill:
            message = _strip_verb_prefix(prefix_raw[:split_at].strip())
    elif not message and allow_message_backfill:
        # No target marker at all -- e.g. "play despacito on spotify".
        # Trim trailing clauses the same way target extraction does
        # ("on spotify" here), then strip the verb, so the platform name
        # or other trailing context doesn't end up embedded in the
        # message content.
        message = _strip_verb_prefix(_trim_trailing_clause(prefix_raw, prefix_lower))

    return target, message


def _platform_scan_zone(prefix_lower: str) -> str:
    """Return prefix_lower (already message-marker-truncated by
    _split_message) with the immediate target span excised -- the
    content between a target marker and the next trailing-context
    marker, exactly what _extract_target() would extract as `target`.

    This is the platform-detection half of the structural rule
    documented on CommandRouter.resolve(): a platform mention inside
    the actual target/query content (e.g. "spotify" in "search amazon
    for spotify gift cards", or "telegram" in "send a whatsapp message
    to my telegram friend") must never be visible to platform-alias
    matching.

    The trailing clause AFTER the target is deliberately preserved
    (e.g. "on whatsapp" in "to close-friend on whatsapp" stays visible)
    -- that's the conventional position for a genuine platform mention
    in "do X to Y on PLATFORM" phrasing, and excluding it would break
    that already-working case.
    """
    split_at, marker = _find_last_target_marker(prefix_lower)
    if split_at == -1:
        return prefix_lower

    target_start = split_at + len(marker)
    target_lower = prefix_lower[target_start:]

    cut = len(target_lower)
    for trailing_marker in _TRAILING_CONTEXT_MARKERS:
        if trailing_marker in _TARGET_MARKERS:
            continue
        idx = target_lower.find(trailing_marker)
        if idx != -1:
            cut = min(cut, idx)

    return prefix_lower[:target_start] + " " + prefix_lower[target_start + cut:]


def _find_last_target_marker(prefix_lower: str):
    """Return (position, marker) of whichever _TARGET_MARKERS entry
    occurs closest to the end of prefix_lower, or (-1, "") if none is
    present."""
    best_pos = -1
    best_marker = ""
    for marker in _TARGET_MARKERS:
        pos = prefix_lower.rfind(marker)
        if pos > best_pos:
            best_pos = pos
            best_marker = marker
    return best_pos, best_marker


def _trim_trailing_clause(text_raw: str, text_lower: str) -> str:
    """Trim text at the earliest trailing-context marker (to/as/from/
    on/in/about), so a trailing platform mention or other clause doesn't
    end up embedded in extracted message content."""
    earliest = len(text_lower)
    for marker in _TRAILING_CONTEXT_MARKERS:
        idx = text_lower.find(marker)
        if idx != -1:
            earliest = min(earliest, idx)
    return text_raw[:earliest].strip()


def _strip_verb_prefix(text: str) -> str:
    """Strip a leading trigger verb (e.g. "calculate ", "type ") off a
    message so the adapter receives just the content -- "calculate 5
    plus 3" becomes "5 plus 3", not the whole phrase including the verb
    that routed it here."""
    for prefix in _MESSAGE_PREFIXES:
        if text.lower().startswith(prefix):
            return text[len(prefix):].strip()
    return text
