"""
CLI: `python -m AgentCore.model_scanner`

Prints two ranked sections (cloud API / open-weights), plus an
unclassified section when the source contains models this tool has no
explicit licensing entry for. Both timestamps -- when we fetched, and
how old the data itself is -- are always shown.
"""
from __future__ import annotations

import argparse
import json
import sys

from .classification import Licensing
from .scanner import STALENESS_WARN_DAYS, BenchmarkSourceError, ScanResult, scan

_SECTIONS = (
    (Licensing.CLOUD, "CLOUD API MODELS"),
    (Licensing.OPEN_WEIGHTS, "OPEN-WEIGHTS MODELS"),
    (Licensing.UNCLASSIFIED, "UNCLASSIFIED"),
)


def _render_header(result: ScanResult) -> list[str]:
    newest = result.newest_entry_date
    age = result.data_age_days
    lines = [
        "",
        f"  Coding-benchmark rankings -- {result.source_name}",
        f"  {result.source_url}",
        "",
        f"  Fetched:              {result.fetched_at.strftime('%Y-%m-%d %H:%M UTC')}",
    ]
    if newest is not None:
        lines.append(f"  Newest benchmark entry: {newest.isoformat()}  ({age} days old)")
    else:
        lines.append("  Newest benchmark entry: unknown -- no parseable dates in source")
    if result.is_stale:
        lines += [
            "",
            f"  *** STALE: the newest measurement in this source is {age} days old",
            f"      (threshold {STALENESS_WARN_DAYS}d). Recency of the fetch is not",
            "      recency of the data. Treat this ranking as historical.",
        ]
    lines += [
        "",
        "  Ranked by measured coding pass rate. This tool recommends; it does",
        "  not select. The adapter-generation model slot stays developer-configured.",
        "",
    ]
    return lines


def _render_section(result: ScanResult, licensing: Licensing, title: str, limit: int) -> list[str]:
    rows = result.by_licensing(licensing)
    if not rows:
        return []
    lines = [f"  {title}  ({len(rows)})", f"  {'-' * 66}"]
    for i, r in enumerate(rows[:limit], 1):
        when = r.entry_date.isoformat() if r.entry_date else "unknown date"
        lines.append(f"   {i:>2}. {r.pass_rate:>5.1f}%  {r.model[:44]:<44} {when}")
    if len(rows) > limit:
        lines.append(f"       ... {len(rows) - limit} more (use --limit to show)")
    if licensing is Licensing.UNCLASSIFIED:
        lines += [
            "",
            "       These have no entry in classification.py's LICENSING_RULES.",
            "       Shown separately rather than guessed into a bucket -- add an",
            "       explicit rule instead of inferring from the model name.",
        ]
    lines.append("")
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m AgentCore.model_scanner",
        description=(
            "Rank coding-capable LLMs by published benchmark performance, to inform "
            "the developer-configured adapter-generation model slot. Recommends only."
        ),
    )
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--limit", type=int, default=10, help="rows per section (default 10)")
    parser.add_argument(
        "--min-entries",
        type=int,
        default=0,
        help="exit non-zero if fewer than N entries parsed (sanity gate for automation)",
    )
    args = parser.parse_args(argv)

    try:
        result = scan()
    except BenchmarkSourceError as e:
        # Honest failure: no cached list, no fabricated ranking.
        print(f"error: {e}", file=sys.stderr)
        return 2

    if len(result.results) < args.min_entries:
        print(
            f"error: parsed {len(result.results)} entries, --min-entries required "
            f"{args.min_entries}",
            file=sys.stderr,
        )
        return 3

    if args.json:
        print(json.dumps(
            {
                "source": {"name": result.source_name, "url": result.source_url},
                "fetched_at": result.fetched_at.isoformat(),
                "newest_entry_date": (
                    result.newest_entry_date.isoformat() if result.newest_entry_date else None
                ),
                "data_age_days": result.data_age_days,
                "is_stale": result.is_stale,
                "staleness_threshold_days": STALENESS_WARN_DAYS,
                "advisory_only": True,
                "results": [
                    {
                        "rank": i,
                        "model": r.model,
                        "pass_rate": r.pass_rate,
                        "licensing": r.licensing.value,
                        "licensing_basis": r.licensing_basis,
                        "entry_date": r.entry_date.isoformat() if r.entry_date else None,
                        "edit_format": r.edit_format,
                    }
                    for i, r in enumerate(result.results, 1)
                ],
            },
            indent=2,
        ))
        return 0

    out = _render_header(result)
    for licensing, title in _SECTIONS:
        out += _render_section(result, licensing, title, args.limit)
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
