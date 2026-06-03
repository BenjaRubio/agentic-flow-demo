"""Prototype-based classification and concept matching using local embeddings.

Two independent pieces (see README / plan):

1. `TypePrototypeClassifier` — Nearest Centroid (Rocchio) over the labeled
   training tickets. For each type, it averages the embeddings of that type's
   examples into one centroid (an "archetype" vector), then classifies a new
   ticket by the closest centroid. It uses the labels but only computes means, so
   there is nothing to over-fit. Drop-in replacement for the k-NN classifier.

2. `ConceptMatcher` — matches free text against hand-written archetype phrases
   that describe a *concept* (e.g. "service continuity"). Used to replace brittle,
   over-fit keyword triggers with a semantic signal that generalizes to
   paraphrases while staying grounded in the policy language.
"""
from __future__ import annotations

from collections import defaultdict

import numpy as np

from .embeddings import Embedder


class TypePrototypeClassifier:
    """Nearest-centroid type classifier over the training tickets."""

    def __init__(self, texts: list[str], labels: list[str]):
        self.texts = texts
        self.labels = labels
        self.embedder = Embedder().fit(texts)
        self.backend = self.embedder.backend

        vectors = self.embedder.encode(texts)
        by_label: dict[str, list[np.ndarray]] = defaultdict(list)
        for vec, label in zip(vectors, labels):
            by_label[label].append(vec)

        self.classes: list[str] = sorted(by_label)
        # Centroid per class, re-normalized so cosine == dot product.
        centroids = []
        for label in self.classes:
            mean = np.mean(np.vstack(by_label[label]), axis=0)
            norm = np.linalg.norm(mean) or 1.0
            centroids.append(mean / norm)
        self.centroids = np.vstack(centroids).astype(np.float32)

    def predict(self, text: str, k: int | None = None) -> dict:
        """Classify by nearest centroid. `k` is ignored (kept for interface parity)."""
        qv = self.embedder.encode([text]).reshape(-1)
        sims = self.centroids @ qv
        order = np.argsort(-sims)
        best, second = int(order[0]), int(order[1]) if len(order) > 1 else int(order[0])
        top_sim = float(sims[best])
        margin = top_sim - float(sims[second])

        return {
            "type": self.classes[best],
            "type_confidence": round(top_sim, 4),
            "top_similarity": round(top_sim, 4),
            "margin": round(margin, 4),
            "low_confidence": top_sim < 0.35 or margin < 0.05,
            "neighbors": [
                {"label": self.classes[int(i)], "similarity": round(float(sims[i]), 4)}
                for i in order[:3]
            ],
        }


class ConceptMatcher:
    """Semantic detector for a single concept, given archetype phrases.

    `matches(text)` is True when the max cosine similarity between the text and
    any archetype exceeds `threshold`.
    """

    def __init__(self, archetypes: list[str], threshold: float = 0.40):
        if not archetypes:
            raise ValueError("ConceptMatcher requires at least one archetype phrase.")
        self.archetypes = archetypes
        self.threshold = threshold
        # Fit on the archetypes themselves so the (TF-IDF fallback) vocabulary is
        # defined; the semantic backend ignores fit content.
        self.embedder = Embedder().fit(archetypes)
        self.matrix = self.embedder.encode(archetypes)
        self.backend = self.embedder.backend

    def similarity(self, text: str) -> float:
        qv = self.embedder.encode([text]).reshape(-1)
        return float(np.max(self.matrix @ qv))

    def matches(self, text: str, threshold: float | None = None) -> bool:
        return self.similarity(text) >= (self.threshold if threshold is None else threshold)
