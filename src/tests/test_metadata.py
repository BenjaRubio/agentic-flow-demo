"""Metadata parsing: status / version / effective date extraction."""
from datetime import date

import pytest

from tools.common.ingest import load_chunks
from tools.common.metadata import parse_metadata
from tools.common.paths import DOCS_DIR

EXPECTED_STATUS = {
    "policy_v1_shipping.md": "deprecated",
    "policy_v2_shipping.md": "active",
    "pricing_notes_old.md": "outdated",
    "pricing_notes_current.md": "active",
    "escalation_policy.md": "active",
    "sla_matrix.md": "active",
    "faq_internal.md": "mixed reliability",
}


@pytest.mark.parametrize("filename,status", EXPECTED_STATUS.items())
def test_status_parsed_per_doc(filename, status):
    meta = parse_metadata((DOCS_DIR / filename).read_text())
    assert meta.status == status


def test_dates_and_supersede_flags():
    v2 = parse_metadata((DOCS_DIR / "policy_v2_shipping.md").read_text())
    assert v2.effective_date == date(2025, 7, 1)
    assert v2.is_superseded is False

    v1 = parse_metadata((DOCS_DIR / "policy_v1_shipping.md").read_text())
    assert v1.is_superseded is True


def test_chunks_inherit_metadata():
    chunks = load_chunks()
    assert chunks, "expected to load some chunks"
    # Every chunk from a deprecated/outdated doc must be flagged superseded.
    for c in chunks:
        if c.status in {"deprecated", "outdated"}:
            assert c.is_superseded
    # No metadata header lines leaked into chunk text.
    assert not any(c.text.lower().startswith(("status:", "version:")) for c in chunks)
