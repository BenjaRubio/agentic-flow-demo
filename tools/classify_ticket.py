"""Tool: classify_ticket(text) -> ClassificationResult

Hybrid classifier:
  - type:        k-NN over embeddings of the labeled training tickets. Instance-
                 based learning degrades gracefully with very little data (10
                 examples) and requires no training/fitting of parameters.
  - priority /
    escalation /
    next_action: deterministic decision table (config/rules.yaml) derived from
                 the policy docs. No LLM.

The result also carries a `type_confidence`. When it is low, the workflow asks
the agent to apply its own judgment using the type definitions in the docs.

CLI:
    python -m tools.classify_ticket "Customer reports a temperature alert in reefer cargo."
"""
from __future__ import annotations

import json
import sys
from tools.common.decision_table import decide, load_rules, routing_targets
from tools.common.embeddings import Embedder, cosine_top_k
from tools.common.observability import traced
from tools.common.paths import TRAIN_TICKETS

# Prediction is nearest-neighbor (k=1): with ~1.6 labeled examples per class,
# larger k averages in neighbouring classes and hurts accuracy (verified by
# LOOCV). We still retrieve a few neighbours to compute a confidence margin.
NEIGHBORS_TO_RETRIEVE = 5
# Confidence flags for instance-based prediction:
LOW_SIMILARITY = 0.35   # absolute cosine of the nearest neighbour
MARGIN_MIN = 0.08       # gap to the nearest neighbour of a *different* class


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
    """k-NN type classifier over the training tickets."""

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
        # Margin: gap to the closest neighbour of a *different* class. A large
        # margin means the nearest example is decisively the winner.
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


_KNN: TicketTypeKNN | None = None


def get_knn() -> TicketTypeKNN:
    global _KNN
    if _KNN is None:
        _KNN = TicketTypeKNN(*_load_train())
    return _KNN


def _routing_label(next_action: str) -> str | None:
    if next_action.startswith("route:"):
        team = next_action.split(":", 1)[1]
        return routing_targets().get(team, team)
    return None


@traced("classify_ticket")
def classify_ticket(text: str, k: int = NEIGHBORS_TO_RETRIEVE) -> dict:
    """Classify an incoming request into type/priority/escalation/next_action."""
    rules = load_rules()
    type_pred = get_knn().predict(text, k=k)
    decision = decide(text, type_pred["type"], rules=rules)

    return {
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


def _main(argv: list[str]) -> int:
    if not argv:
        print('usage: python -m tools.classify_ticket "<ticket text>"', file=sys.stderr)
        return 2
    result = classify_ticket(argv[0])
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
