"""Observability: token estimation, cost pricing, and the @traced decorator."""
import pytest

from tools.common import observability as obs
from tools.common.observability import estimate_cost, estimate_tokens, traced


def test_estimate_tokens_nonzero_for_text():
    assert estimate_tokens("hello world this is a sentence") > 0
    assert estimate_tokens("") == 0
    assert estimate_tokens(None) == 0


def test_estimate_cost_uses_pricing_rates():
    # 1M input tokens should cost exactly the configured input rate.
    p = obs._PRICING.load()
    assert estimate_cost(1_000_000, 0) == pytest.approx(p.input_per_1m)
    assert estimate_cost(0, 1_000_000) == pytest.approx(p.output_per_1m)


def test_traced_preserves_return_and_metadata(caplog):
    @traced("dummy_tool")
    def add(a, b):
        return {"sum": a + b}

    result = add(2, 3)
    assert result == {"sum": 5}
    # decorator preserves function identity
    assert add.__name__ == "add"


def test_traced_propagates_exceptions():
    @traced("boom")
    def boom():
        raise ValueError("kaboom")

    try:
        boom()
        assert False, "expected ValueError"
    except ValueError as e:
        assert "kaboom" in str(e)
