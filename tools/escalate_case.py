"""Tool: escalate_case(team, reason) -> EscalationReceipt

Registers a human escalation. In this take-home there is no real ticketing
backend, so we append an auditable record to .tmp/escalations.log and return a
receipt. The valid teams come from the routing targets in rules.yaml.

CLI:
    python -m tools.escalate_case operations_lead "temperature exception in reefer cargo"
"""
from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime, timezone

from tools.common.decision_table import routing_targets
from tools.common.observability import get_logger, traced
from tools.common.paths import ensure_tmp

_LOG_FILE = "escalations.log"
_log = get_logger("tool")


@traced("escalate_case")
def escalate_case(team: str, reason: str) -> dict:
    """Register an escalation and return a receipt."""
    targets = routing_targets()
    known = team in targets or team in targets.values()
    receipt = {
        "escalation_id": str(uuid.uuid4()),
        "team": team,
        "team_label": targets.get(team, team),
        "reason": reason,
        "status": "registered" if known else "registered_unknown_team",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    log_path = ensure_tmp() / _LOG_FILE
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(receipt, ensure_ascii=False) + "\n")

    _log.info(
        "escalation_registered",
        escalation_id=receipt["escalation_id"],
        team=receipt["team_label"],
        status=receipt["status"],
    )
    return receipt


def _main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: python -m tools.escalate_case <team> <reason>", file=sys.stderr)
        return 2
    print(json.dumps(escalate_case(argv[0], argv[1]), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
