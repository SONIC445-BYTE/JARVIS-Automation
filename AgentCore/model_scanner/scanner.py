"""
Fetch and rank coding-benchmark results for the Adaptive Adapter
Generation model slot (§4.4b).

**Data class: `general`, not `clinical`** -- see docs/model_benchmark_scanner.md
§1. One unauthenticated GET to a hardcoded public benchmark URL; no
caller-supplied input is forwarded anywhere; no clinical data can reach
this path by construction. Deliberately exposes no general-purpose fetch
helper: a reusable network utility here is exactly how a general-classed
component drifts into carrying clinical context later.

**This recommends. It never selects.** No config write path, no
knowledge of the currently-configured model, no apply verb.
"""
from __future__ import annotations

import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Iterable

from .classification import Licensing, classify

#: Hardcoded allow-list of one. A versioned YAML file in a public git
#: repo -- not a scraped HTML page, not a JS dashboard, not an aggregator
#: with undisclosed methodology. Changing this is a code change and a
#: review, never a config value.
AIDER_POLYGLOT_URL = (
    "https://raw.githubusercontent.com/Aider-AI/aider/main/"
    "aider/website/_data/polyglot_leaderboard.yml"
)

SOURCE_NAME = "Aider polyglot coding benchmark"
STALENESS_WARN_DAYS = 90
FETCH_TIMEOUT_S = 20


class BenchmarkSourceError(RuntimeError):
    """
    The source could not be fetched or parsed.

    Raised rather than returning partial or substituted data. There is
    deliberately no "return a cached/hardcoded list" path -- a plausible
    ranking built from stale or invented data is worse than no ranking,
    because the reader cannot tell the difference. Same fail-closed
    discipline as secure_key.resolve_key().
    """


@dataclass(frozen=True)
class ModelResult:
    model: str
    pass_rate: float           # percent, the benchmark's headline correctness figure
    entry_date: date | None
    edit_format: str | None
    licensing: Licensing
    licensing_basis: str
    total_cost: float | None   # reported by the source; NOT used for ranking

    @property
    def age_days(self) -> int | None:
        if self.entry_date is None:
            return None
        return (datetime.now(timezone.utc).date() - self.entry_date).days


@dataclass(frozen=True)
class ScanResult:
    results: tuple[ModelResult, ...]
    fetched_at: datetime
    source_name: str
    source_url: str

    @property
    def newest_entry_date(self) -> date | None:
        dates = [r.entry_date for r in self.results if r.entry_date is not None]
        return max(dates) if dates else None

    @property
    def data_age_days(self) -> int | None:
        newest = self.newest_entry_date
        if newest is None:
            return None
        return (datetime.now(timezone.utc).date() - newest).days

    @property
    def is_stale(self) -> bool:
        """
        Staleness is a property of the DATA, not of when we fetched it.
        A file retrieved seconds ago whose newest entry is a year old is
        stale; reporting only "last checked: just now" would conceal
        exactly that. See docs/model_benchmark_scanner.md §4.
        """
        age = self.data_age_days
        return age is not None and age > STALENESS_WARN_DAYS

    def by_licensing(self, licensing: Licensing) -> tuple[ModelResult, ...]:
        return tuple(r for r in self.results if r.licensing is licensing)


def fetch_raw(url: str = AIDER_POLYGLOT_URL, timeout: float = FETCH_TIMEOUT_S) -> str:
    if url != AIDER_POLYGLOT_URL:
        # The allow-list is the containment boundary for the `general`
        # classification. Widening it must be a reviewed code change.
        raise BenchmarkSourceError(
            f"Refusing to fetch {url!r}: not in this module's allow-list. "
            f"Add it deliberately in scanner.py if it is genuinely a benchmark source."
        )
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310 (hardcoded https allow-list)
            if resp.status != 200:
                raise BenchmarkSourceError(f"{SOURCE_NAME} returned HTTP {resp.status}")
            return resp.read().decode("utf-8")
    except urllib.error.URLError as e:
        raise BenchmarkSourceError(
            f"Could not reach {SOURCE_NAME} ({e}). No cached or substituted ranking is "
            f"available by design -- re-run when the source is reachable."
        ) from e


def _parse_date(value) -> date | None:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return datetime.strptime(value.strip(), "%Y-%m-%d").date()
        except ValueError:
            return None
    return None


def parse(raw_yaml: str) -> tuple[ModelResult, ...]:
    """
    Parse the leaderboard into ranked results.

    Entries missing the headline pass-rate field are skipped rather than
    defaulted to zero -- a missing measurement is not a measurement of
    zero, and defaulting would silently rank a model last on the basis
    of absent data.
    """
    try:
        import yaml
    except ImportError as e:  # pragma: no cover - dependency is in requirements
        raise BenchmarkSourceError("PyYAML is required to parse the benchmark source") from e

    try:
        entries = yaml.safe_load(raw_yaml)
    except yaml.YAMLError as e:
        raise BenchmarkSourceError(f"{SOURCE_NAME} did not parse as YAML: {e}") from e

    if not isinstance(entries, list):
        raise BenchmarkSourceError(
            f"{SOURCE_NAME} parsed to {type(entries).__name__}, expected a list of entries -- "
            f"the upstream schema may have changed."
        )

    results: list[ModelResult] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        model = entry.get("model")
        # pass_rate_2 is the benchmark's headline figure (correct after the
        # second attempt); pass_rate_1 is the single-shot figure. Prefer the
        # headline, fall back only to the other real measurement, never to 0.
        rate = entry.get("pass_rate_2", entry.get("pass_rate_1"))
        if not model or not isinstance(rate, (int, float)):
            continue
        licensing, basis = classify(str(model))
        results.append(
            ModelResult(
                model=str(model),
                pass_rate=float(rate),
                entry_date=_parse_date(entry.get("date")),
                edit_format=entry.get("edit_format"),
                licensing=licensing,
                licensing_basis=basis,
                total_cost=(
                    float(entry["total_cost"])
                    if isinstance(entry.get("total_cost"), (int, float))
                    else None
                ),
            )
        )

    if not results:
        raise BenchmarkSourceError(
            f"{SOURCE_NAME} yielded zero usable entries -- the upstream schema has likely "
            f"changed. Refusing to report an empty ranking as if it were a result."
        )

    # Ranked by measured coding performance only. Deliberately not by cost,
    # speed, or context length -- capability is the slot's real constraint.
    results.sort(key=lambda r: r.pass_rate, reverse=True)
    return tuple(results)


def scan(url: str = AIDER_POLYGLOT_URL) -> ScanResult:
    raw = fetch_raw(url)
    return ScanResult(
        results=parse(raw),
        fetched_at=datetime.now(timezone.utc),
        source_name=SOURCE_NAME,
        source_url=url,
    )
