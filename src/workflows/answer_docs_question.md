# Workflow A — Answer Internal Documentation Question

## Objective
Answer an **internal** question about company policy/operations, grounded in the
internal documents, with citations. If the documents do not explicitly support an
answer, **abstain** — never invent policy.

> Scope: this is for internal staff asking about policy. It does NOT classify
> customer requests and does NOT escalate. Escalation lives in Workflow B.

## Required inputs
- `question`: the user's question (free text, English).

## Tools
- `tools/search_docs.py` → `search_docs(query, k=5)`
  Returns relevant chunks. Deprecated/Outdated chunks are pre-filtered out.
  Each chunk carries `status` and `effective_date`.
- `tools/get_active_policy.py` → `get_active_policy(topic)`
  Returns the resolved active policy for a topic plus the `superseded` documents
  it excluded. Use this when the question is about a specific policy/rule.

## Steps
1. **Understand the question.** If it is vague or ambiguous (users often ask
   badly), reformulate it into a clear search query — or ask one clarifying
   question before searching. Use your judgment.
2. **Retrieve.** Call `search_docs(question)`. For a policy/rule question, also
   call `get_active_policy(topic)` to get the authoritative active statement and
   the list of superseded documents.
3. **Resolve conflicts (agent judgment).** The tools already drop
   Deprecated/Outdated content. If two or more **Active** statements still
   conflict, pick the one with the most recent `effective_date`; if dates tie,
   prefer the higher version. State briefly why you chose it.
4. **Answer with evidence.** Write the answer and include the **literal policy
   text** (in English) plus its source filename as a citation. Quote, don't
   paraphrase, the governing statement.
5. **Abstain when unsupported.** If no Active document explicitly answers the
   question, say so plainly: state that there is no supporting policy and do not
   guess. Suggest the user confirm with the relevant team if appropriate.

## Expected output
A short answer that contains:
- the direct answer,
- a quoted citation `[source.md] "<policy text>"`,
- if relevant, a one-line note that older/superseded guidance was disregarded
  (e.g. "policy_v1 / pricing_notes_old say otherwise but are deprecated/outdated").
- OR an explicit abstention if there is no support.

## Edge cases
- **Conflicting active docs:** resolve by recency/version and say which won.
- **Only superseded docs match:** treat as unsupported → abstain (the active
  policy is silent on this).
- **Low-relevance results (low scores):** if nothing is clearly on-topic,
  abstain rather than stretch a weak match into an answer.

## Worked example
Q: "Can pricing disputes for active shipments be handled by the commercial team?"
- `get_active_policy("pricing dispute routing")` →
  winner: `pricing_notes_current.md` "Any pricing discrepancy involving active
  shipments must be reviewed by pricing operations."; superseded:
  `policy_v1_shipping.md`, `pricing_notes_old.md`.
- Answer: **No.** Active policy requires pricing operations, not commercial.
  Cite `policy_v2_shipping.md` ("...routed first to pricing operations, not
  commercial.") and `pricing_notes_current.md`. Note the commercial-team
  guidance is from deprecated/outdated docs.
