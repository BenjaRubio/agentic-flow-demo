"""Local embedding backends + cosine similarity.

Primary backend: sentence-transformers (all-MiniLM-L6-v2) — real semantic
matching, runs locally, $0 per query. If it (or torch) is unavailable, we fall
back to a TF-IDF vectorizer so the system still runs everywhere (CI, tests).

Both backends expose the same interface and return L2-normalized vectors, so
cosine similarity is just a dot product.
"""
from __future__ import annotations

from typing import Sequence

import numpy as np

_ST_MODEL_NAME = "all-MiniLM-L6-v2"

# Cache the (expensive) model load process-wide so repeated Embedder() instances
# (e.g. LOOCV folds, multiple tools) reuse one model. Big latency win.
_ST_MODEL_CACHE: dict = {}


def _load_st_model(name: str):
    if name not in _ST_MODEL_CACHE:
        from sentence_transformers import SentenceTransformer

        _ST_MODEL_CACHE[name] = SentenceTransformer(name)
    return _ST_MODEL_CACHE[name]


def _normalize(mat: np.ndarray) -> np.ndarray:
    mat = np.asarray(mat, dtype=np.float32)
    if mat.ndim == 1:
        mat = mat.reshape(1, -1)
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return mat / norms


class Embedder:
    """Fit on a corpus once, then encode corpus/queries into normalized vectors.

    Usage:
        emb = Embedder().fit(corpus_texts)
        corpus_vecs = emb.encode(corpus_texts)
        query_vec = emb.encode([query])
    """

    def __init__(self, prefer_semantic: bool = True) -> None:
        self.backend: str = "uninitialized"
        self._model = None          # sentence-transformers model
        self._vectorizer = None     # TF-IDF vectorizer
        self._prefer_semantic = prefer_semantic

    # -- lifecycle -------------------------------------------------------- #
    def fit(self, corpus: Sequence[str]) -> "Embedder":
        if self._prefer_semantic and self._try_load_sentence_transformer():
            self.backend = f"sentence-transformers:{_ST_MODEL_NAME}"
            return self
        # Fallback: TF-IDF fitted on the corpus.
        from sklearn.feature_extraction.text import TfidfVectorizer

        self._vectorizer = TfidfVectorizer(
            lowercase=True, ngram_range=(1, 2), min_df=1, sublinear_tf=True
        )
        self._vectorizer.fit(list(corpus))
        self.backend = "tfidf"
        return self

    def _try_load_sentence_transformer(self) -> bool:
        try:
            self._model = _load_st_model(_ST_MODEL_NAME)
            return True
        except Exception:
            return False

    # -- encoding --------------------------------------------------------- #
    def encode(self, texts: Sequence[str]) -> np.ndarray:
        if self.backend == "uninitialized":
            raise RuntimeError("Embedder.fit() must be called before encode().")
        if self._model is not None:
            vecs = self._model.encode(list(texts), normalize_embeddings=False)
            return _normalize(np.asarray(vecs, dtype=np.float32))
        # TF-IDF
        mat = self._vectorizer.transform(list(texts)).toarray()
        return _normalize(mat)


def cosine_top_k(query_vec: np.ndarray, matrix: np.ndarray, k: int) -> list[tuple[int, float]]:
    """Return [(index, similarity)] for the top-k rows of `matrix`.

    Assumes both inputs are L2-normalized, so cosine == dot product.
    """
    q = query_vec.reshape(-1)
    sims = matrix @ q
    k = min(k, sims.shape[0])
    top = np.argsort(-sims)[:k]
    return [(int(i), float(sims[i])) for i in top]
