"""get_active_policy conflict resolution: active wins over commercial/deprecated."""
from tools.common.decision_table import confidence_threshold
from tools.get_active_policy import get_active_policy


def test_pricing_resolves_to_active_not_commercial():
    result = get_active_policy("pricing dispute routing team commercial pricing operations", k=12)
    assert result["found"] is True
    winner = result["winner"]
    assert winner["status"] == "active"
    # The winning (active) policy must not be the commercial-team guidance.
    assert "commercial" not in winner["text"].lower()


def test_superseded_documents_are_reported_and_excluded_from_winner():
    result = get_active_policy("pricing dispute commercial team below USD 300", k=12)
    superseded_sources = {c["source"] for c in result["superseded"]}
    # Deprecated/outdated commercial guidance should be reported as superseded...
    assert superseded_sources & {"policy_v1_shipping.md", "pricing_notes_old.md"}
    # ...and never selected as the winner.
    assert result["winner"]["source"] not in {"policy_v1_shipping.md", "pricing_notes_old.md"}


def test_confidence_threshold_is_policy_v2_value():
    # policy_v2_shipping.md (Active) raised the auto-answer threshold to 0.80.
    assert confidence_threshold() == 0.80
