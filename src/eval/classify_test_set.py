"""Classify the unlabeled test tickets for manual human review.

The test set has no labels, so this produces a readable report a human can scan
to judge whether the classifier behaves sensibly.

Run:
    python -m eval.classify_test_set
"""
from __future__ import annotations

import json

from tools.classify_ticket import classify_ticket
from tools.common.paths import TEST_TICKETS


def main() -> None:
    rows = [json.loads(l) for l in TEST_TICKETS.read_text().splitlines() if l.strip()]
    for i, row in enumerate(rows, 1):
        r = classify_ticket(row["text"])
        flag = "  <-- LOW CONFIDENCE (agent should review)" if r["low_confidence"] else ""
        print(f"\n[{i}] {row['text']}")
        print(f"     type            : {r['type']} (conf={r['type_confidence']}, top_sim={r['top_similarity']}){flag}")
        print(f"     priority        : {r['priority']}   escalation: {r['human_escalation']}")
        print(f"     next_action     : {r['next_action']}  -> {r['routing_target'] or 'auto respond'}")
        print(f"     fired_triggers  : {r['fired_triggers']}")
        print(f"     sla_target      : {r['sla_response_target']}")


if __name__ == "__main__":
    main()
