"""Tool: get_active_policy(topic) -> PolicyMetadata

Returns the highest-priority ACTIVE policy statements for a topic, plus a record
of which documents were superseded. This is the deterministic core of conflict
resolution: Deprecated/Outdated docs are dropped, and remaining candidates are
ranked by (status_rank, effective_date, similarity). The agent uses the exposed
metadata to make the final call when genuine Active-vs-Active ties remain.

CLI:
    python -m tools.get_active_policy "pricing disputes routing"
"""
from __future__ import annotations

import sys
from datetime import date

from tools.common.observability import get_logger, traced
from tools.search_docs import get_index

_log = get_logger("tool")


def _sort_key(chunk) -> tuple:
    eff = chunk.effective_date or date.min
    rank = {"active": 3, "mixed reliability": 1}.get(chunk.status, 1)
    return (rank, eff, chunk.score)


@traced("get_active_policy")
def get_active_policy(topic: str, k: int = 6) -> dict:
    """Resolve the active policy for a topic.

    Returns:
        {
          "topic": str,
          "found": bool,
          "active_statements": [chunk dicts, best first],
          "superseded": [chunk dicts that were excluded],
          "winner": chunk dict | None,   # single best active statement
        }
    """
    _log.info("resolving_policy", topic=topic)
    index = get_index()
    # Pull a wide candidate set including superseded, so we can report them.
    all_candidates = index.search(topic, k=k, include_superseded=True)

    active = [c for c in all_candidates if not c.is_superseded]
    superseded = [c for c in all_candidates if c.is_superseded]

    active.sort(key=_sort_key, reverse=True)

    winner = active[0] if active else None
    _log.info(
        "policy_resolved",
        found=bool(active),
        winner=f"{winner.source} ({winner.status}, {winner.effective_date})" if winner else None,
        n_superseded=len(superseded),
        superseded=[c.source for c in superseded],
    )
    return {
        "topic": topic,
        "found": bool(active),
        "active_statements": [c.to_dict() for c in active],
        "superseded": [c.to_dict() for c in superseded],
        "winner": winner.to_dict() if winner else None,
    }


def _main(argv: list[str]) -> int:
    if not argv:
        print('usage: python -m tools.get_active_policy "<topic>"', file=sys.stderr)
        return 2
    result = get_active_policy(argv[0])
    if not result["found"]:
        print("No active policy found for topic.")
        return 0
    w = result["winner"]
    print(f"WINNER ({w['status']}, {w['effective_date']}) {w['source']}: {w['text']}")
    if result["superseded"]:
        print("\nSuperseded (excluded):")
        for c in result["superseded"]:
            print(f"  ({c['status']}) {c['source']}: {c['text']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
