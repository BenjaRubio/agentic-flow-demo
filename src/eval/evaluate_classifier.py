"""Quantitative evaluation of the classifier on the labeled training set.

Two things are measured:
  1. type accuracy via Leave-One-Out Cross-Validation (LOOCV). With only 10
     labeled examples this is the honest way to get a generalization estimate:
     train on 9, predict the held-out 1, repeat.
  2. decision-table fidelity: given the GOLD type, does rules.yaml reproduce the
     gold `priority` and `human_escalation` labels? (Expected: 100%.)

Run:
    python -m eval.evaluate_classifier
"""
from __future__ import annotations

import json

from tools.common.decision_table import decide
from tools.common.paths import TRAIN_TICKETS
from tools.classify_ticket import TicketTypeKNN, _load_train


def loocv_type_accuracy(texts: list[str], labels: list[str], k: int = 3) -> dict:
    correct = 0
    mistakes = []
    for i in range(len(texts)):
        train_texts = texts[:i] + texts[i + 1 :]
        train_labels = labels[:i] + labels[i + 1 :]
        knn = TicketTypeKNN(train_texts, train_labels)
        pred = knn.predict(texts[i], k=k)["type"]
        if pred == labels[i]:
            correct += 1
        else:
            mistakes.append({"text": texts[i], "gold": labels[i], "pred": pred})
    return {
        "n": len(texts),
        "correct": correct,
        "accuracy": round(correct / len(texts), 4),
        "mistakes": mistakes,
        "backend": TicketTypeKNN(texts, labels).backend,
    }


def decision_table_fidelity() -> dict:
    """Check that rules reproduce priority + escalation given the gold type."""
    rows = [json.loads(l) for l in TRAIN_TICKETS.read_text().splitlines() if l.strip()]
    pri_ok = esc_ok = 0
    errors = []
    for row in rows:
        d = decide(row["text"], row["label_type"])
        gold_esc = row["label_human_escalation"].lower() == "yes"
        if d.priority == row["label_priority"]:
            pri_ok += 1
        else:
            errors.append({"text": row["text"], "field": "priority", "gold": row["label_priority"], "pred": d.priority})
        if d.human_escalation == gold_esc:
            esc_ok += 1
        else:
            errors.append({"text": row["text"], "field": "escalation", "gold": gold_esc, "pred": d.human_escalation})
    n = len(rows)
    return {
        "n": n,
        "priority_accuracy": round(pri_ok / n, 4),
        "escalation_accuracy": round(esc_ok / n, 4),
        "errors": errors,
    }


def main() -> None:
    texts, labels = _load_train()
    type_report = loocv_type_accuracy(texts, labels)
    rules_report = decision_table_fidelity()

    print("=" * 60)
    print("TYPE classifier — LOOCV")
    print(f"  backend : {type_report['backend']}")
    print(f"  accuracy: {type_report['accuracy']}  ({type_report['correct']}/{type_report['n']})")
    if type_report["mistakes"]:
        print("  mistakes:")
        for m in type_report["mistakes"]:
            print(f"    - gold={m['gold']:<22} pred={m['pred']:<22} | {m['text']}")
    print("=" * 60)
    print("Decision table — fidelity to gold labels (given gold type)")
    print(f"  priority accuracy   : {rules_report['priority_accuracy']}")
    print(f"  escalation accuracy : {rules_report['escalation_accuracy']}")
    if rules_report["errors"]:
        print("  errors:")
        for e in rules_report["errors"]:
            print(f"    - {e}")
    print("=" * 60)


if __name__ == "__main__":
    main()
