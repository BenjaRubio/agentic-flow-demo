"""Decision table: triggers force escalation / raise priority correctly."""
import pytest

from tools.common.decision_table import decide


def test_temperature_trigger_forces_high_escalation():
    # Even if the base type were a low-risk one, a temperature trigger escalates.
    d = decide("Customer reports a temperature alert in refrigerated cargo.", "tracking_request")
    assert d.priority == "high"
    assert d.human_escalation is True
    assert d.next_action == "route:operations_lead"
    assert "temperature" in d.fired_triggers


def test_legal_trigger_routes_to_compliance():
    d = decide("Can you interpret a liability clause in the contract?", "tracking_request")
    assert d.priority == "high"
    assert d.human_escalation is True
    assert d.next_action == "route:compliance"


def test_customs_trigger_escalates():
    d = decide("Customer reports customs retention.", "tracking_request")
    assert d.priority == "high"
    assert d.human_escalation is True


def test_service_continuity_is_semantic_not_keyword():
    # service_continuity is now detected semantically (upstream), so a bare
    # keyword no longer fires it inside decide().
    d = decide("Customer may lose a supermarket slot tomorrow.", "tracking_request")
    assert "service_continuity" not in d.fired_triggers


def test_service_continuity_via_extra_triggers_bumps_priority():
    # When the semantic matcher fires it upstream, it is passed via extra_triggers
    # => at least Medium, but it does not by itself force human escalation.
    d = decide(
        "Customer may lose a sales window.",
        "tracking_request",
        extra_triggers=("service_continuity",),
    )
    assert d.priority == "medium"
    assert d.human_escalation is False
    assert d.next_action == "auto_respond"
    assert "service_continuity" in d.fired_triggers


def test_no_trigger_keeps_base_mapping():
    d = decide("Customer requests packing list copy.", "document_request")
    assert d.priority == "low"
    assert d.human_escalation is False
    assert d.next_action == "auto_respond"
