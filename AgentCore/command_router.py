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
        other classification)."""
        lower = text.lower()

        adapter_key = None
        matched_alias = ""
        for alias, key in self._platform_aliases.items():
            if alias in lower and len(alias) > len(matched_alias):
                adapter_key = key
                matched_alias = alias

        if adapter_key is None:
            return None

        # Split off any dictated message payload BEFORE verb matching, so
        # a word inside the message body (e.g. "close" in "saying check
        # the close date") is never mistaken for another action's verb.
        # Bug found via adversarial testing on 4e55699b: verb matching
        # used to scan the full raw text, so message content could
        # misfire as a different action depending on AdapterBase.ACTIONS
        # declaration order -- not deterministic on input meaning.
        prefix_raw, prefix_lower, message = _split_message(text, lower)

        # Second collision path (found via further adversarial testing on
        # 71ded210): even with the message split off, a target name or
        # trailing clause with no explicit "saying" marker was still
        # scanned in full for verbs -- e.g. "close" in "close-friend", or
        # "open" in "open-source-group" after " from ". Bound single-word
        # verb matching to the text before the earliest trailing-context
        # marker. Multi-word verbs that legitimately contain one of those
        # marker words as part of the verb phrase itself (e.g. browser's
        # "go to", "navigate to") are matched against the untruncated
        # prefix instead, since truncating at " to " would cut the verb
        # phrase in half.
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

        target, message = _extract_target(prefix_raw, prefix_lower, message)

        return Intent(
            adapter=adapter_key,
            action=matched_action.name,
            target=target if (matched_action.requires_target and target) else matched_alias,
            message=message if matched_action.requires_message else "",
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
    (prefix_raw, prefix_lower, message) -- message is "" if no marker is
    present (verb matching and target extraction then run against the
    whole text, as for commands with no separate payload like "open
    browser" or "go to google.com")."""
    for marker in _MESSAGE_MARKERS:
        if marker in lower:
            split_at = lower.find(marker)
            prefix_raw = raw[:split_at]
            prefix_lower = lower[:split_at]
            message = raw[split_at + len(marker):].strip()
            return prefix_raw, prefix_lower, message
    return raw, lower, ""


def _extract_target(prefix_raw: str, prefix_lower: str, message: str):
    """Extract the target from the (already message-marker-truncated)
    prefix using whichever of _TARGET_MARKERS (" to ", " as ") appears
    last. If no message was split off by _split_message, the text before
    that marker becomes the message instead (covers "send X to Y" with
    no "saying" marker, and "go to X" navigation-style commands with no
    separate payload). With no target marker at all, the whole prefix
    (verb-stripped, trailing-clause-trimmed) becomes the message --
    covers "play X on Y" / "note X" style commands."""
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

        if not message:
            message = _strip_verb_prefix(prefix_raw[:split_at].strip())
    elif not message:
        # No target marker at all -- e.g. "play despacito on spotify".
        # Trim trailing clauses the same way target extraction does
        # ("on spotify" here), then strip the verb, so the platform name
        # or other trailing context doesn't end up embedded in the
        # message content.
        message = _strip_verb_prefix(_trim_trailing_clause(prefix_raw, prefix_lower))

    return target, message


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
