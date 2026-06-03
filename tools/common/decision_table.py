"""Deterministic decision table for ticket priority / escalation / next action.

Reads config/rules.yaml (authored from the source docs) and applies:
  1. a base mapping from ticket type, then
  2. triggers that can RAISE priority and/or FORCE escalation.

Triggers are detected two ways (see rules.yaml):
  - keyword triggers are matched here, against the ticket text.
  - semantic triggers are detected upstream (ConceptMatcher) and passed in via
    `extra_triggers`; they are NOT keyword-matched here.

Triggers never lower an existing decision. No LLM is involved.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import yaml

from .paths import RULES_FILE


@dataclass
class Decision:
    priority: str
    human_escalation: bool
    next_action: str            # "auto_respond" or "route:<team>"
    fired_triggers: list[str]

    def to_dict(self) -> dict:
        return {
            "priority": self.priority,
            "human_escalation": self.human_escalation,
            "next_action": self.next_action,
            "fired_triggers": self.fired_triggers,
        }


@lru_cache(maxsize=1)
def load_rules() -> dict:
    return yaml.safe_load(RULES_FILE.read_text(encoding="utf-8"))


def confidence_threshold() -> float:
    return float(load_rules().get("confidence_threshold", 0.8))


def routing_targets() -> dict:
    return load_rules().get("routing_targets", {})


def semantic_triggers(rules: dict | None = None) -> dict:
    """Return {name: trigger_cfg} for triggers detected semantically (archetypes)."""
    rules = rules or load_rules()
    return {
        name: cfg
        for name, cfg in rules.get("triggers", {}).items()
        if cfg.get("detection") == "semantic"
    }


def _max_priority(a: str, b: str, order: list[str]) -> str:
    return a if order.index(a) >= order.index(b) else b


def decide(
    text: str,
    ticket_type: str,
    rules: dict | None = None,
    extra_triggers: tuple[str, ...] = (),
) -> Decision:
    """Apply the decision table to a ticket given its predicted type.

    `extra_triggers` are trigger names already detected upstream (e.g. semantic
    matches) that should be applied in addition to the keyword triggers.
    """
    rules = rules or load_rules()
    order: list[str] = rules["priority_order"]

    base = rules["types"].get(ticket_type) or rules["default"]
    priority = base["priority"]
    escalation = bool(base["human_escalation"])
    next_action = base["next_action"]

    lowered = text.lower()
    fired: list[str] = []
    route_override: str | None = None
    extra = set(extra_triggers)

    for name, trig in rules.get("triggers", {}).items():
        is_semantic = trig.get("detection") == "semantic"
        if is_semantic:
            matched = name in extra
        else:
            matched = any(kw.lower() in lowered for kw in trig.get("keywords", []))
        if matched:
            fired.append(name)
            if "min_priority" in trig:
                priority = _max_priority(priority, trig["min_priority"], order)
            if trig.get("force_escalation"):
                escalation = True
                if trig.get("route"):
                    route_override = trig["route"]

    # If a trigger forced escalation but the base action was auto_respond,
    # convert it into a route to the appropriate team.
    if escalation and next_action == "auto_respond":
        target = route_override or _route_for_type(ticket_type, rules)
        next_action = f"route:{target}"
    elif route_override and next_action.startswith("route:"):
        # Keep the most specific routing from a fired trigger.
        next_action = f"route:{route_override}"

    return Decision(priority, escalation, next_action, fired)


def _route_for_type(ticket_type: str, rules: dict) -> str:
    base = rules["types"].get(ticket_type)
    if base and isinstance(base.get("next_action"), str) and base["next_action"].startswith("route:"):
        return base["next_action"].split(":", 1)[1]
    return "operations_lead"
