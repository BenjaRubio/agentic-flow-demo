"""Parse vigencia/version metadata from a policy document.

Docs in dataset/docs/ carry their metadata as plain header lines, e.g.:

    # Shipping Policy v2
    Version: 2.0
    Effective date: 2025-07-01
    Status: Active

This module extracts that metadata so the retrieval layer can pre-filter
deprecated/outdated content and the agent can resolve conflicts by recency.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

# Status values, ranked. Higher rank = more authoritative / current.
STATUS_RANK = {
    "active": 3,
    "mixed reliability": 1,
    "deprecated": 0,
    "outdated": 0,
}
# Statuses whose content must NOT be used as the basis for an answer.
SUPERSEDED_STATUSES = {"deprecated", "outdated"}

_TITLE_RE = re.compile(r"^#\s+(.*)$", re.MULTILINE)
_VERSION_RE = re.compile(r"^Version:\s*(.+)$", re.MULTILINE | re.IGNORECASE)
_STATUS_RE = re.compile(r"^Status:\s*(.+)$", re.MULTILINE | re.IGNORECASE)
# Matches "Effective date:" or "Date:"
_DATE_RE = re.compile(r"^(?:Effective date|Date):\s*(\d{4}-\d{2}-\d{2})", re.MULTILINE | re.IGNORECASE)


@dataclass
class DocMetadata:
    title: str = ""
    version: str = ""
    status: str = ""           # normalized lowercase, e.g. "active"
    effective_date: date | None = None

    @property
    def is_superseded(self) -> bool:
        return self.status in SUPERSEDED_STATUSES

    @property
    def status_rank(self) -> int:
        return STATUS_RANK.get(self.status, 1)


def parse_metadata(text: str) -> DocMetadata:
    """Extract metadata from a document's raw markdown text."""
    title_m = _TITLE_RE.search(text)
    version_m = _VERSION_RE.search(text)
    status_m = _STATUS_RE.search(text)
    date_m = _DATE_RE.search(text)

    effective: date | None = None
    if date_m:
        try:
            effective = date.fromisoformat(date_m.group(1))
        except ValueError:
            effective = None

    return DocMetadata(
        title=title_m.group(1).strip() if title_m else "",
        version=version_m.group(1).strip() if version_m else "",
        status=status_m.group(1).strip().lower() if status_m else "",
        effective_date=effective,
    )
