"""search_docs retrieval: relevance + vigencia pre-filtering."""
from tools.search_docs import search_docs


def test_excludes_superseded_by_default():
    results = search_docs("pricing dispute commercial team routing", k=6)
    statuses = {r["status"] for r in results}
    assert "deprecated" not in statuses
    assert "outdated" not in statuses


def test_superseded_available_when_requested():
    results = search_docs("pricing dispute commercial team", k=12, include_superseded=True)
    sources = {r["source"] for r in results}
    # The deprecated/outdated commercial-team guidance should now be reachable.
    assert {"policy_v1_shipping.md", "pricing_notes_old.md"} & sources


def test_relevant_active_policy_surfaces():
    results = search_docs("pricing dispute routing", k=5)
    sources = {r["source"] for r in results}
    assert sources & {"policy_v2_shipping.md", "pricing_notes_current.md", "escalation_policy.md"}
    # scores are sorted descending
    scores = [r["score"] for r in results]
    assert scores == sorted(scores, reverse=True)
