# Available Tools

## search_docs(query: str) -> list[DocumentChunk]
Searches relevant chunks from internal documents.

## get_active_policy(topic: str) -> PolicyMetadata
Returns the highest-priority active policy if available.

## classify_ticket(text: str) -> ClassificationResult
Returns ticket type, priority suggestion, and escalation recommendation.

## draft_response(context: dict) -> str
Drafts a user-facing response.

## escalate_case(team: str, reason: str) -> EscalationReceipt
Registers escalation to a human team.
