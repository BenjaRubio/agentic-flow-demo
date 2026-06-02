"""Tool: search_docs(query) -> list[DocumentChunk]

RAG retrieval over the internal docs using local embeddings + cosine similarity.

Vigencia handling: by default, chunks from Deprecated/Outdated documents are
pre-filtered out, so the agent never bases an answer on superseded policy. The
metadata (status, effective_date) travels with every chunk so the agent can
resolve any remaining Active-vs-Active conflict by recency.

CLI:
    python -m tools.search_docs "pricing dispute commercial team"
"""
from __future__ import annotations

import sys

from tools.common.embeddings import Embedder, cosine_top_k
from tools.common.ingest import DocumentChunk, load_chunks
from tools.common.observability import traced

# --------------------------------------------------------------------------- #
# In-process index (built once per process; cheap for this tiny corpus).
# --------------------------------------------------------------------------- #
class DocIndex:
    def __init__(self, chunks: list[DocumentChunk]):
        self.chunks = chunks
        texts = [c.text for c in chunks]
        self.embedder = Embedder().fit(texts)
        self.matrix = self.embedder.encode(texts)
        self.backend = self.embedder.backend

    def search(self, query: str, k: int = 5, include_superseded: bool = False) -> list[DocumentChunk]:
        qv = self.embedder.encode([query])
        results: list[DocumentChunk] = []
        for idx, sim in cosine_top_k(qv, self.matrix, k=len(self.chunks)):
            chunk = self.chunks[idx]
            if not include_superseded and chunk.is_superseded:
                continue
            ranked = DocumentChunk(**{**chunk.__dict__})
            ranked.score = sim
            results.append(ranked)
            if len(results) >= k:
                break
        return results


_INDEX: DocIndex | None = None


def get_index() -> DocIndex:
    global _INDEX
    if _INDEX is None:
        _INDEX = DocIndex(load_chunks())
    return _INDEX


@traced("search_docs")
def search_docs(query: str, k: int = 5, include_superseded: bool = False) -> list[dict]:
    """Return up to k relevant document chunks (as dicts), best first."""
    chunks = get_index().search(query, k=k, include_superseded=include_superseded)
    return [c.to_dict() for c in chunks]


def _main(argv: list[str]) -> int:
    if not argv:
        print('usage: python -m tools.search_docs "<query>" [k]', file=sys.stderr)
        return 2
    query = argv[0]
    k = int(argv[1]) if len(argv) > 1 else 5
    for c in search_docs(query, k=k):
        print(f"[{c['score']:.3f}] ({c['status']}, {c['effective_date']}) {c['source']}: {c['text']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
