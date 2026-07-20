"""
backend/core/local_telemetry.py

SELF-OBSERVATION FALLBACK: an in-memory, same-process shadow of LLM spend,
used when the SigNoz MCP server's exact wire protocol isn't wired up yet
(see mcp_client.py's TODO). This gives the self-observing router *real*
numbers to react to today, without waiting on the full MCP JSON-RPC
integration. Cost is approximated as (chars_in + chars_out) / 4 tokens,
priced per model tier — a standard rough heuristic, clearly marked as an
approximation. Swap in real `usage.total_tokens` from the Groq response
later for exact figures.
"""
from __future__ import annotations

import threading
import time
from collections import deque
from typing import Deque, NamedTuple

PRICE_PER_1K_TOKENS_USD = {
    "llama-3.3-70b-versatile": 0.0006,
    "llama-3.1-8b-instant": 0.00008,
}
DEFAULT_PRICE_PER_1K = 0.0003


class _Sample(NamedTuple):
    ts: float
    model: str
    cost_usd: float


_lock = threading.Lock()
_samples: Deque[_Sample] = deque(maxlen=5000)


def estimate_cost_usd(model: str, text_in: str, text_out: str) -> float:
    approx_tokens = (len(text_in) + len(text_out)) / 4
    price = PRICE_PER_1K_TOKENS_USD.get(model, DEFAULT_PRICE_PER_1K)
    return (approx_tokens / 1000) * price


def record_llm_call(model: str, text_in: str, text_out: str) -> float:
    cost = estimate_cost_usd(model, text_in, text_out)
    with _lock:
        _samples.append(_Sample(ts=time.time(), model=model, cost_usd=cost))
    return cost


def get_recent_cost_trend_local(window_minutes: int = 30) -> dict:
    cutoff = time.time() - window_minutes * 60
    with _lock:
        recent = [s for s in _samples if s.ts >= cutoff]
    total = sum(s.cost_usd for s in recent)
    count = len(recent)
    by_model: dict[str, float] = {}
    for s in recent:
        by_model[s.model] = by_model.get(s.model, 0.0) + s.cost_usd
    return {
        "total_cost_usd": total,
        "avg_cost_per_request_usd": (total / count) if count else 0.0,
        "request_count": count,
        "cost_by_model": by_model,
    }