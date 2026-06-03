"""Tool: classify_ticket(text) -> ClassificationResult

Hybrid classifier (see README / AGENTS.md):
  - type:        instance-based over embeddings of the labeled training tickets.
                 Default is a Nearest-Centroid prototype classifier; k-NN is kept
                 for comparison (see eval/evaluate_classifier.py). No parameter
                 training, so nothing over-fits.
  - priority /
    escalation /
    next_action: deterministic decision table (config/rules.yaml) derived from
                 the policy docs, applied to (type + fired triggers). No LLM.
                 Fuzzy triggers (service_continuity) are detected semantically.

The result carries a `type_confidence`. When it is low, the workflow asks the
agent to apply its own judgment using the type definitions in the docs.

CLI:
    python -m tools.classify_ticket "Customer reports a temperature alert in reefer cargo."
"""
from __future__ import annotations

import json
import sys

from tools.common.decision_table import decide, load_rules, routing_targets, semantic_triggers
from tools.common.embeddings import Embedder, cosine_top_k
from tools.common.observability import get_logger, traced
from tools.common.paths import TRAIN_TICKETS
from tools.common.prototypes import ConceptMatcher, TypePrototypeClassifier

# Which instance-based classifier drives `type`: "knn" (1-NN) or "prototype"
# (Nearest Centroid). Chosen empirically by LOOCV in eval/evaluate_classifier.py:
# k-NN (0.6) edged out prototypes (0.5) on this tiny set, so k-NN is the default.
TYPE_CLASSIFIER = "knn"

# Confidence flags for k-NN (the prototype classifier sets its own internally).
NEIGHBORS_TO_RETRIEVE = 5
LOW_SIMILARITY = 0.35
MARGIN_MIN = 0.08

_log = get_logger("tool")


def _load_train() -> tuple[list[str], list[str]]:
    texts, labels = [], []
    for line in TRAIN_TICKETS.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        texts.append(row["text"])
        labels.append(row["label_type"])
    return texts, labels


class TicketTypeKNN:
    """k-NN (k=1) type classifier over the training tickets (kept for comparison)."""

    def __init__(self, texts: list[str], labels: list[str]):
        self.texts = texts
        self.labels = labels
        self.embedder = Embedder().fit(texts)
        self.matrix = self.embedder.encode(texts)
        self.backend = self.embedder.backend

    def predict(self, text: str, k: int = NEIGHBORS_TO_RETRIEVE) -> dict:
        qv = self.embedder.encode([text])
        neighbors = cosine_top_k(qv, self.matrix, k=k)
        nn_idx, nn_sim = neighbors[0]
        pred = self.labels[nn_idx]
        runner_up = next((s for i, s in neighbors if self.labels[i] != pred), 0.0)
        margin = nn_sim - runner_up
        return {
            "type": pred,
            "type_confidence": round(nn_sim, 4),
            "top_similarity": round(nn_sim, 4),
            "margin": round(margin, 4),
            "low_confidence": nn_sim < LOW_SIMILARITY or margin < MARGIN_MIN,
            "neighbors": [
                {"text": self.texts[i], "label": self.labels[i], "similarity": round(s, 4)}
                for i, s in neighbors
            ],
        }


# --------------------------------------------------------------------------- #
# Singletons (built once per process).
# --------------------------------------------------------------------------- #
_CLASSIFIER = None
_MATCHERS: dict[str, ConceptMatcher] | None = None


def get_type_classifier():
    global _CLASSIFIER
    if _CLASSIFIER is None:
        texts, labels = _load_train()
        if TYPE_CLASSIFIER == "knn":
            _CLASSIFIER = TicketTypeKNN(texts, labels)
        else:
            _CLASSIFIER = TypePrototypeClassifier(texts, labels)
    return _CLASSIFIER


def get_concept_matchers() -> dict[str, ConceptMatcher]:
    """Build a ConceptMatcher per semantic trigger declared in rules.yaml."""
    global _MATCHERS
    if _MATCHERS is None:
        _MATCHERS = {
            name: ConceptMatcher(cfg["archetypes"], threshold=cfg.get("semantic_threshold", 0.40))
            for name, cfg in semantic_triggers().items()
        }
    return _MATCHERS


def _detect_semantic_triggers(text: str) -> list[str]:
    return [name for name, matcher in get_concept_matchers().items() if matcher.matches(text)]


def _routing_label(next_action: str) -> str | None:
    if next_action.startswith("route:"):
        team = next_action.split(":", 1)[1]
        return routing_targets().get(team, team)
    return None


@traced("classify_ticket")
def classify_ticket(text: str) -> dict:
    """Classify an incoming request into type/priority/escalation/next_action."""
    rules = load_rules()
    type_pred = get_type_classifier().predict(text)
    semantic_fired = _detect_semantic_triggers(text)
    decision = decide(text, type_pred["type"], rules=rules, extra_triggers=tuple(semantic_fired))

    result = {
        "text": text,
        "type": type_pred["type"],
        "type_confidence": type_pred["type_confidence"],
        "top_similarity": type_pred["top_similarity"],
        "margin": type_pred["margin"],
        "low_confidence": type_pred["low_confidence"],
        "neighbors": type_pred["neighbors"],
        "priority": decision.priority,
        "human_escalation": decision.human_escalation,
        "next_action": decision.next_action,
        "routing_target": _routing_label(decision.next_action),
        "fired_triggers": decision.fired_triggers,
        "sla_response_target": rules["sla_response_target"].get(decision.priority),
    }
    _log.info(
        "classified",
        type=result["type"],
        type_confidence=result["type_confidence"],
        low_confidence=result["low_confidence"],
        priority=result["priority"],
        human_escalation=result["human_escalation"],
        next_action=result["next_action"],
        fired_triggers=result["fired_triggers"],
    )
    return result


def _main(argv: list[str]) -> int:
    if not argv:
        print('usage: python -m tools.classify_ticket "<ticket text>"', file=sys.stderr)
        return 2
    print(json.dumps(classify_ticket(argv[0]), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
