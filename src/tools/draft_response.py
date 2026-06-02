"""Tool: draft_response(context) -> str

Used in the classification workflow (B) to assemble a CUSTOMER-facing reply.

Division of labor (WAT): the *prose* (the `body`) is the agent's reasoning; this
tool only formats it into a consistent, auditable structure and attaches the
evidence/citations and SLA note. It never invents policy content.

Expected context keys (all optional except `body`):
    body:            str   - the agent-written message to the customer
    customer_name:   str
    citations:       list[{"source","text"}]  - supporting policy snippets
    sla_response_target: str  - e.g. "30 minutes"
    next_action:     str   - "auto_respond" or "route:<team>"
    escalated_to:    str   - human-readable team, if escalated
"""
from __future__ import annotations

import json
import sys

from tools.common.observability import traced


@traced("draft_response")
def draft_response(context: dict) -> str:
    body = (context.get("body") or "").strip()
    if not body:
        raise ValueError("draft_response requires a non-empty 'body' written by the agent.")

    name = context.get("customer_name") or "there"
    lines = [f"Hi {name},", "", body]

    sla = context.get("sla_response_target")
    if sla:
        lines += ["", f"We aim to follow up within {sla} per our service levels."]

    if context.get("escalated_to"):
        lines += ["", f"Your case has been routed to our {context['escalated_to']} team for review."]

    citations = context.get("citations") or []
    if citations:
        lines += ["", "---", "Supporting policy (internal reference):"]
        for c in citations:
            lines.append(f"- [{c.get('source','?')}] {c.get('text','')}")

    lines += ["", "Best regards,", "Operations Team"]
    return "\n".join(lines)


def _main(argv: list[str]) -> int:
    if not argv:
        print('usage: python -m tools.draft_response \'{"body": "..."}\'', file=sys.stderr)
        return 2
    ctx = json.loads(argv[0])
    print(draft_response(ctx))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
