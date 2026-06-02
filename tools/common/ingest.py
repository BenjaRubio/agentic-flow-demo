"""Load and chunk the internal documents in dataset/docs/.

Each document is tiny (a handful of statements), so we chunk at the statement
level: every non-empty, non-metadata content line becomes one chunk. That gives
precise, quotable citations while keeping each chunk's metadata attached.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from .metadata import DocMetadata, parse_metadata
from .paths import DOCS_DIR

# Header / metadata lines we skip when extracting content statements.
_METADATA_PREFIXES = ("version:", "effective date:", "date:", "status:")


@dataclass
class DocumentChunk:
    chunk_id: str
    source: str            # filename, e.g. "policy_v2_shipping.md"
    text: str              # the statement
    title: str = ""
    status: str = ""       # normalized, e.g. "active"
    version: str = ""
    effective_date: date | None = None
    score: float = 0.0     # filled in by retrieval

    @property
    def is_superseded(self) -> bool:
        return self.status in {"deprecated", "outdated"}

    def to_dict(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "source": self.source,
            "title": self.title,
            "text": self.text,
            "status": self.status,
            "version": self.version,
            "effective_date": self.effective_date.isoformat() if self.effective_date else None,
            "score": round(self.score, 4),
        }


def _content_lines(text: str) -> list[str]:
    out: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):            # markdown heading (title)
            continue
        if line.lower().startswith(_METADATA_PREFIXES):
            continue
        # Strip list markers / Q: A: prefixes are kept as-is (they carry meaning).
        line = line.lstrip("-* ").strip()
        if line:
            out.append(line)
    return out


def load_chunks(docs_dir=DOCS_DIR) -> list[DocumentChunk]:
    """Read every .md file in docs_dir into a flat list of DocumentChunk."""
    chunks: list[DocumentChunk] = []
    for path in sorted(docs_dir.glob("*.md")):
        raw = path.read_text(encoding="utf-8")
        meta: DocMetadata = parse_metadata(raw)
        for i, line in enumerate(_content_lines(raw)):
            chunks.append(
                DocumentChunk(
                    chunk_id=f"{path.name}#{i}",
                    source=path.name,
                    text=line,
                    title=meta.title,
                    status=meta.status,
                    version=meta.version,
                    effective_date=meta.effective_date,
                )
            )
    return chunks
