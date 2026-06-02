"""Classifier: decision-table fidelity on train labels + LOOCV type accuracy."""
import json

import pytest

from tools.classify_ticket import classify_ticket
from tools.common.decision_table import decide
from tools.common.paths import TRAIN_TICKETS
from eval.evaluate_classifier import loocv_type_accuracy
from tools.classify_ticket import _load_train

TRAIN_ROWS = [json.loads(l) for l in TRAIN_TICKETS.read_text().splitlines() if l.strip()]


@pytest.mark.parametrize("row", TRAIN_ROWS, ids=[r["label_type"] for r in TRAIN_ROWS])
def test_decision_table_reproduces_gold_labels(row):
    """Given the gold type, rules must reproduce gold priority + escalation."""
    d = decide(row["text"], row["label_type"])
    assert d.priority == row["label_priority"]
    assert d.human_escalation == (row["label_human_escalation"].lower() == "yes")


def test_loocv_type_accuracy_beats_baseline():
    texts, labels = _load_train()
    report = loocv_type_accuracy(texts, labels)
    # Majority-class baseline on this set is ~0.2. The semantic backend should
    # clear 0.5; the TF-IDF fallback is weaker but must still beat the baseline.
    floor = 0.5 if report["backend"].startswith("sentence-transformers") else 0.25
    assert report["accuracy"] >= floor, report


def test_classify_ticket_result_shape():
    r = classify_ticket("Customer asks for latest ETA and vessel status.")
    for key in ("type", "priority", "human_escalation", "next_action", "type_confidence"):
        assert key in r
    assert r["type"] == "tracking_request"
    assert r["next_action"] == "auto_respond"
