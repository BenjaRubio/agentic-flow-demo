"""Prototype classifier (Nearest Centroid) and semantic ConceptMatcher."""
import numpy as np

from tools.classify_ticket import _load_train
from tools.common.prototypes import ConceptMatcher, TypePrototypeClassifier


def test_centroids_are_normalized_and_one_per_class():
    texts, labels = _load_train()
    clf = TypePrototypeClassifier(texts, labels)
    assert clf.centroids.shape[0] == len(set(labels))
    norms = np.linalg.norm(clf.centroids, axis=1)
    assert np.allclose(norms, 1.0, atol=1e-4)


def test_prototype_predicts_clear_cases():
    texts, labels = _load_train()
    clf = TypePrototypeClassifier(texts, labels)
    assert clf.predict("Where is my shipment? Need an ETA update.")["type"] == "tracking_request"
    assert clf.predict("Reefer container temperature deviation reported.")["type"] == "temperature_exception"


ARCHETYPES = [
    "the issue affects the customer's service continuity",
    "the customer may miss a deadline or delivery window",
    "the problem causes a financial penalty or a lost sale for the customer",
]


def test_concept_matcher_matches_paraphrase():
    matcher = ConceptMatcher(ARCHETYPES, threshold=0.40)
    # A paraphrase that shares no exact keyword with the archetypes.
    assert matcher.matches("If it is late we will lose our retail shelf window tomorrow.")


def test_concept_matcher_ignores_neutral_text():
    matcher = ConceptMatcher(ARCHETYPES, threshold=0.40)
    assert not matcher.matches("Please send me a copy of the packing list.")
