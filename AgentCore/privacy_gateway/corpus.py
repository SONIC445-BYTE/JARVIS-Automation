"""
Loader for the synthetic Mode C evaluation corpus.

**The corpus is synthetic and was written by the same author as the
detector.** That is stated in the data file, in the design note, and
again here, because it is the single most important caveat attached to
every number this package publishes. Metrics measured against it are an
optimistic bound, not field performance -- see
`docs/pg001_mode_c_drift_detector.md` section 6.

The loader validates rather than trusts. A gold entity whose text does
not appear in its segment, or appears a different number of times than
it is annotated, is a `CorpusError` and stops the run. A silently
mis-annotated corpus produces a wrong published metric, which is worse
than no metric -- so this fails closed, in the `secure_key` idiom.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional

from .findings import IDENTIFIER_TYPES, EntityType

CORPUS_PATH = Path(__file__).resolve().parent / "data" / "mode_c_drift_corpus.jsonl"


class CorpusError(Exception):
    """Corpus is malformed or internally inconsistent. Never recovered from."""


@dataclass(frozen=True)
class GoldEntity:
    entity_type: EntityType
    text: str
    patient_linked: bool
    start: int
    end: int


@dataclass(frozen=True)
class Segment:
    id: str
    category: str
    clinical: bool
    text: str
    entities: tuple[GoldEntity, ...]
    why: str

    def patient_linked_entities(self) -> tuple[GoldEntity, ...]:
        return tuple(e for e in self.entities if e.patient_linked)


def _all_occurrences(haystack: str, needle: str) -> list[int]:
    out: list[int] = []
    i = haystack.find(needle)
    while i != -1:
        out.append(i)
        i = haystack.find(needle, i + 1)
    return out


def load_corpus(path: Optional[Path] = None) -> tuple[Segment, ...]:
    src = path or CORPUS_PATH
    if not src.exists():
        raise CorpusError(f"Corpus file missing: {src}")

    segments: list[Segment] = []
    seen_ids: set[str] = set()

    for lineno, raw in enumerate(_nonblank_lines(src), start=1):
        try:
            record = json.loads(raw)
        except json.JSONDecodeError as e:
            raise CorpusError(f"{src}:{lineno} is not valid JSON: {e}") from e

        if "_schema_version" in record:  # header record
            if record["_schema_version"] != 1:
                raise CorpusError(
                    f"{src}:{lineno} declares schema version "
                    f"{record['_schema_version']}; this loader understands 1 only."
                )
            continue

        for required in ("id", "category", "clinical", "text", "entities", "why"):
            if required not in record:
                raise CorpusError(f"{src}:{lineno} is missing required field '{required}'")

        seg_id = record["id"]
        if seg_id in seen_ids:
            raise CorpusError(f"{src}:{lineno} duplicate segment id {seg_id!r}")
        seen_ids.add(seg_id)

        text = record["text"]
        # Group annotations by their literal text so occurrence counts can be
        # checked, then assign each annotation a distinct occurrence.
        by_text: dict[str, list[dict]] = {}
        for ent in record["entities"]:
            by_text.setdefault(ent["text"], []).append(ent)

        gold: list[GoldEntity] = []
        for ent_text, annotations in by_text.items():
            offsets = _all_occurrences(text, ent_text)
            if not offsets:
                raise CorpusError(
                    f"{src}:{lineno} ({seg_id}): annotated entity {ent_text!r} does not "
                    f"occur in the segment text."
                )
            if len(offsets) != len(annotations):
                raise CorpusError(
                    f"{src}:{lineno} ({seg_id}): {ent_text!r} occurs {len(offsets)} time(s) "
                    f"but is annotated {len(annotations)} time(s). Every occurrence must be "
                    f"annotated, or precision is measured against an incomplete key."
                )
            for offset, ent in zip(offsets, annotations):
                try:
                    etype = EntityType(ent["type"])
                except ValueError as e:
                    raise CorpusError(
                        f"{src}:{lineno} ({seg_id}): unknown entity type {ent['type']!r}"
                    ) from e
                if etype not in IDENTIFIER_TYPES:
                    raise CorpusError(
                        f"{src}:{lineno} ({seg_id}): {etype.value} is not an identifier type; "
                        f"the corpus annotates identifiers, not topic evidence."
                    )
                if "patient_linked" not in ent:
                    raise CorpusError(
                        f"{src}:{lineno} ({seg_id}): entity {ent_text!r} is missing "
                        f"'patient_linked'."
                    )
                gold.append(
                    GoldEntity(etype, ent_text, bool(ent["patient_linked"]),
                               offset, offset + len(ent_text))
                )

        segments.append(
            Segment(
                id=seg_id,
                category=record["category"],
                clinical=bool(record["clinical"]),
                text=text,
                entities=tuple(sorted(gold, key=lambda g: g.start)),
                why=record["why"],
            )
        )

    if not segments:
        raise CorpusError(f"{src} contains no segments.")
    return tuple(segments)


def _nonblank_lines(path: Path) -> Iterator[str]:
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                yield line
