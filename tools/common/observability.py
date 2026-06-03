"""Observability: structured logging + per-tool tracing of latency and cost.

Every tool is wrapped with @traced, which logs one structured event per call:
    {tool, duration_ms, in_tokens, out_tokens, est_cost_usd}

Cost note: this system embeds no LLM API calls, but the agent that orchestrates
the tools runs on a paid plan. We meter the tokens of data flowing through each
tool (a measurable lower bound on the request's footprint) and price them with
config/pricing.yaml. The agent's own reasoning tokens are estimated separately
in the README. See pricing.yaml for the full rationale.
"""
from __future__ import annotations

import functools
import json
import logging
import os
import sys
import time
from typing import Any, Callable, TypeVar

import structlog
import yaml

from .paths import PRICING_FILE

F = TypeVar("F", bound=Callable[..., Any])

# --------------------------------------------------------------------------- #
# Logging setup
# --------------------------------------------------------------------------- #
_CONFIGURED = False


def configure_logging(level: int = logging.INFO) -> None:
    """Idempotently configure structlog.

    Logs go to **stderr** (Unix convention: stdout = program data, stderr =
    diagnostics) so tool output on stdout stays clean/parseable. Format is JSON
    by default, or a human-readable console renderer when
    COPILOT_LOG_FORMAT=console.
    """
    global _CONFIGURED
    if _CONFIGURED:
        return
    if os.getenv("COPILOT_LOG_FORMAT", "json").lower() == "console":
        renderer = structlog.dev.ConsoleRenderer()
    else:
        renderer = structlog.processors.JSONRenderer()
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )
    _CONFIGURED = True


def get_logger(name: str = "copilot") -> structlog.BoundLogger:
    configure_logging()
    return structlog.get_logger(name)


# --------------------------------------------------------------------------- #
# Token + cost estimation
# --------------------------------------------------------------------------- #
try:  # optional, more accurate
    import tiktoken

    _ENC = tiktoken.get_encoding("cl100k_base")

    def _count_tokens(text: str) -> int:
        return len(_ENC.encode(text))
except Exception:  # pragma: no cover - exercised only when tiktoken absent
    _ENC = None

    def _count_tokens(text: str) -> int:
        # ~4 characters per token is a standard rough heuristic.
        return max(1, (len(text) + 3) // 4) if text else 0


def _stringify(obj: Any) -> str:
    """Best-effort, stable serialization of arbitrary tool I/O for token counts."""
    if obj is None:
        return ""
    if isinstance(obj, str):
        return obj
    try:
        return json.dumps(obj, default=str, sort_keys=True, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(obj)


def estimate_tokens(*objs: Any) -> int:
    return sum(_count_tokens(_stringify(o)) for o in objs)


class _Pricing:
    """Lazily-loaded token rates from config/pricing.yaml."""

    def __init__(self) -> None:
        self._loaded = False
        self.input_per_1m = 0.0
        self.output_per_1m = 0.0
        self.model = "unknown"

    def load(self) -> "_Pricing":
        if self._loaded:
            return self
        try:
            data = yaml.safe_load(PRICING_FILE.read_text()) or {}
        except FileNotFoundError:
            data = {}
        self.input_per_1m = float(data.get("input_per_1m_usd", 0.0))
        self.output_per_1m = float(data.get("output_per_1m_usd", 0.0))
        self.model = str(data.get("model", "unknown"))
        self._loaded = True
        return self


_PRICING = _Pricing()


def estimate_cost(in_tokens: int, out_tokens: int) -> float:
    p = _PRICING.load()
    return (in_tokens * p.input_per_1m + out_tokens * p.output_per_1m) / 1_000_000.0


# --------------------------------------------------------------------------- #
# Tracing decorator
# --------------------------------------------------------------------------- #
def traced(name: str | None = None) -> Callable[[F], F]:
    """Decorator that times a tool call and logs latency + token/cost estimates."""

    def decorator(func: F) -> F:
        tool_name = name or func.__name__

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            log = get_logger("tool")
            start = time.perf_counter()
            status = "ok"
            result = None
            try:
                result = func(*args, **kwargs)
                return result
            except Exception:
                status = "error"
                raise
            finally:
                duration_ms = round((time.perf_counter() - start) * 1000, 2)
                in_tokens = estimate_tokens(args, kwargs)
                out_tokens = estimate_tokens(result) if status == "ok" else 0
                log.info(
                    "tool_call",
                    tool=tool_name,
                    status=status,
                    duration_ms=duration_ms,
                    in_tokens=in_tokens,
                    out_tokens=out_tokens,
                    est_cost_usd=round(estimate_cost(in_tokens, out_tokens), 6),
                )

        return wrapper  # type: ignore[return-value]

    return decorator
