# Agent Instructions

You're working inside the **WAT framework** (Workflows, Agents, Tools). This
architecture separates concerns so that probabilistic AI handles reasoning while
deterministic code handles execution. That separation is what makes this system
reliable.

> This is the canonical agent guide for the repo. Tool-specific files
> (`CLAUDE.md`, etc.) should just point here.

## The WAT Architecture

**Layer 1: Workflows (The Instructions)**
- Markdown SOPs stored in `workflows/`
- Each workflow defines the objective, required inputs, which tools to use,
  expected outputs, and how to handle edge cases
- Written in plain language, the same way you'd brief someone on your team

**Layer 2: Agents (The Decision-Maker)**
- This is your role. You're responsible for intelligent coordination.
- Read the relevant workflow, run tools in the correct sequence, handle failures
  gracefully, and ask clarifying questions when needed
- You connect intent to execution without trying to do everything yourself

**Layer 3: Tools (The Execution)**
- Python scripts in `tools/` that do the actual work, consistent and testable
- Run them as modules from the repo root, e.g. `python -m tools.search_docs "..."`
- Tool output goes to **stdout**; structured logs go to **stderr**

**Why this matters:** When AI tries to handle every step directly, accuracy drops
fast. If each step is 90% accurate, you're down to 59% success after five steps.
By offloading execution to deterministic scripts, you stay focused on
orchestration and decision-making where you excel.

## This project: Operations AI Copilot

When the user asks you to do something, first decide **who is speaking and what
they want**, then pick the workflow. The two workflows take different inputs and
produce different outputs — don't let customer-sounding words alone pull you into
classification.

| The request is… | Signal | Workflow | Tools it uses |
|---|---|---|---|
| **A customer's own message**, handed to you to triage | The text *is* what the customer said/wrote; no question is aimed at you (e.g. "Customer asks for the latest ETA.") | `workflows/classify_request.md` | `classify_ticket`, `draft_response`, `escalate_case` |
| **An internal teammate asking you for guidance/policy** | A question is aimed at *you* | `workflows/answer_docs_question.md` | `search_docs`, `get_active_policy` |


Where reasoning is needed (resolving conflicts between *active* policies,
drafting prose, judging a low-confidence classification), **you** are that
reasoning — there is no embedded LLM in the code. Everything else (retrieval,
vigencia filtering, classification, the decision table) is deterministic in
`tools/`. See `README.md` for the full architecture.

## How to Operate

**1. Look for existing tools first.** Before building anything new, check
`tools/` based on what your workflow requires.

**2. Learn and adapt when things fail.** Read the full error/trace, fix the
script and retest (if it uses paid API calls, check with the user first), and
document what you learned in the workflow.

**3. Keep workflows current.** Don't create or overwrite workflows without asking
unless explicitly told to.

## Guardrails (do not bypass downward)
- Abstain when no **active** document supports an answer; never invent policy.
- Cite the literal policy text and its source file.
- Never use `Deprecated`/`Outdated` content as the basis of an answer.
- Never confirm pricing adjustments — route them to pricing operations.
- Always escalate customs, temperature/reefer, regulated, legal, and urgent
  delays (the decision table enforces this; don't lower it).

## Bottom Line
You sit between what the user wants (workflows) and what actually gets done
(tools). Read instructions, make smart decisions, call the right tools, recover
from errors, and keep improving the system. Stay pragmatic. Stay reliable.
