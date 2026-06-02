# Workflow B — Classify an Incoming Customer Request

## Objective
Classify an incoming customer request and decide what to do with it: type,
priority, whether it needs human escalation, and the next action (auto-respond or
route to a team). Then either draft a customer reply or register an escalation.

## Required inputs
- `text`: the customer request (free text, English).

## Tools
- `tools/classify_ticket.py` → `classify_ticket(text)`
  Returns `{type, type_confidence, low_confidence, neighbors, priority,
  human_escalation, next_action, routing_target, fired_triggers,
  sla_response_target}`.
  - `type` is predicted by k-NN over the labeled training tickets.
  - `priority` / `human_escalation` / `next_action` come from the deterministic
    decision table (rules.yaml), derived from sla_matrix.md + escalation_policy.md.
  - `next_action` is `auto_respond` (low-risk, answerable) or `route:<team>`.
- `tools/draft_response.py` → `draft_response(context)`
  Formats a **customer-facing** reply. You write the `body`; the tool structures it.
- `tools/escalate_case.py` → `escalate_case(team, reason)`
  Registers a human escalation and returns a receipt.

## Steps
1. **Classify.** Call `classify_ticket(text)`.
2. **Check confidence (agent judgment).** If `low_confidence` is true, do not
   blindly trust the predicted `type`. Re-read the request and the `neighbors`,
   and apply your judgment using the type definitions in the docs (the six types:
   tracking_request, document_request, pricing_dispute, shipment_exception,
   temperature_exception, legal_sensitive). Correct the type if needed, then
   re-derive the action consistent with the decision table.
3. **Act on `next_action`:**
   - `auto_respond` → call `draft_response` with a `body` you write, citing the
     relevant active policy when useful (you may use Workflow A to fetch it).
   - `route:<team>` → call `escalate_case(team, reason)` with a concise reason.
     You may also draft a short holding message to the customer acknowledging the
     handoff and the SLA target.

## Expected output
- The classification result, and
- either a drafted customer reply (auto_respond) or an escalation receipt (route).

## Guardrails
- **Never confirm a pricing adjustment** to the customer; pricing changes need
  pricing-operations approval (pricing_notes_current.md). Acknowledge and route.
- **Always escalate** customs retention, temperature/reefer exceptions,
  regulated cargo, and legal/contractual interpretation (escalation_policy.md).
  The decision table already enforces this; do not override it downward.
- Keep drafts factual and grounded; do not promise outcomes the policy doesn't
  support.

## Worked examples
- "Customer reports a temperature alert in refrigerated cargo." →
  type `temperature_exception`, priority `high`, escalate `yes`,
  `route:operations_lead`. Register escalation; send a 30-min-SLA holding note.
- "Customer asks for latest ETA and vessel status." →
  type `tracking_request`, priority `low`, escalate `no`, `auto_respond`.
  Draft a tracking reply.
- "Customer asks why the invoice is USD 220 above quote on an active shipment." →
  type `pricing_dispute`, priority `medium`, escalate `yes`,
  `route:pricing_operations`. Do NOT confirm the amount; route to pricing ops.
