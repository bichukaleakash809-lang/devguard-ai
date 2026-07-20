"""
backend/core/self_observer.py

The self-observing loop: telemetry IN, runtime decisions OUT.

Every other part of this system treats SigNoz telemetry as something to be
*watched* — dashboards, traces, alerts for a human to read. This module is
the exception: it's the wiring that lets the agents themselves read their
own recent telemetry (via `mcp_client.get_mcp_client()`) and change what
they do next, in the same request path, before the human ever looks at a
dashboard.

Four capabilities, each a distinct telemetry-in/decision-out loop:

  1. TelemetryAwareRouter  — recent cost trend      -> model tier choice
  2. PostmortemAgent       — a breaker's error burst -> plain-English root cause
  3. PatternLearningAgent  — historical CWE failures -> RAG context depth (k)
  4. CostGuardian          — cumulative scan cost    -> global conservation mode

Design constraints that apply to every function here:
  - Never raise. A telemetry-driven optimization must never become a new
    failure mode; every telemetry call is expected to come back with an
    `available: bool` flag, and `available=False` is always treated as
    "no adaptation, fall back to the caller's default."
  - Small, pure-ish, side-effect-explicit. `CostGuardian` is the one
    intentionally stateful piece; everything else is a plain function you
    can call from `ai_agent.py` or `resilience.py` without restructuring
    them.
"""

from __future__ import annotations

import os
import logging
from typing import Optional

from backend.core.mcp_client import get_mcp_client

logger = logging.getLogger(__name__)

# ── Shared tier vocabulary ───────────────────────────────────────────────────
CHEAP_MODEL_TIER = "llama-3.1-8b-instant"
SEVERITY_CRITICAL = "critical"


# ── 1. TelemetryAwareRouter ──────────────────────────────────────────────────

COST_BUDGET_USD_PER_30MIN: float = float(
    os.getenv("COST_BUDGET_USD_PER_30MIN", "5.00")
)


async def adaptive_select_model(
    severity: str, base_model: str
) -> tuple[str, Optional[str]]:
    """Telemetry in: recent 30-minute spend trend from SigNoz.
    Decision out: the model tier to actually use for this scan.

    Safety floor: `critical` severity is NEVER downgraded, regardless of
    cost pressure or conservation mode.
    """
    if severity == SEVERITY_CRITICAL:
        return base_model, None

    if is_conservation_mode():
        return CHEAP_MODEL_TIER, "conservation_mode_active"

    client = get_mcp_client()
    trend = await client.get_recent_cost_trend()

    if not trend.available:
        return base_model, None

    spend_usd = trend.total_cost_usd
    if spend_usd > COST_BUDGET_USD_PER_30MIN:
        reason = (
            f"cost_budget_exceeded: ${spend_usd:.4f}/30min > "
            f"${COST_BUDGET_USD_PER_30MIN:.4f} budget"
        )
        logger.info("adaptive_select_model: %s", reason)
        return CHEAP_MODEL_TIER, reason

    return base_model, None


# ── 2. PostmortemAgent ───────────────────────────────────────────────────────

_POSTMORTEM_FALLBACK = (
    "A circuit breaker opened after repeated failures. Automated root-cause "
    "summary was unavailable this time — check the linked trace for details."
)

_POSTMORTEM_SYSTEM_PROMPT = (
    "You write terse, plain-English incident postmortems for engineers. "
    "Given a breaker name and a summary of recent errors, respond with a "
    "2-3 sentence root-cause explanation. No preamble, no markdown, no "
    "headers — just the summary."
)


async def generate_postmortem(breaker_name: str, recent_error_summary: str) -> str:
    """Telemetry in: the error burst that just tripped a circuit breaker.
    Decision out: a human-readable postmortem.
    """
    try:
        return await _call_llm_for_postmortem(breaker_name, recent_error_summary)
    except Exception:  # noqa: BLE001
        logger.exception(
            "generate_postmortem: LLM call failed for breaker=%s, using fallback",
            breaker_name,
        )
        return _POSTMORTEM_FALLBACK


async def _call_llm_for_postmortem(breaker_name: str, recent_error_summary: str) -> str:
    from backend.core.ai_agent import _call_llm  # local import: optional coupling

    user_prompt = (
        f"Breaker: {breaker_name}\n"
        f"Recent error summary: {recent_error_summary}\n\n"
        "What's the likely root cause, in 2-3 sentences?"
    )
    response_text = await _call_llm(
        system=_POSTMORTEM_SYSTEM_PROMPT,
        user=user_prompt,
        max_tokens=200,
    )
    return response_text.strip() or _POSTMORTEM_FALLBACK


# ── 3. PatternLearningAgent ──────────────────────────────────────────────────

CWE_FAILURE_RATE_THRESHOLD: float = float(
    os.getenv("CWE_FAILURE_RATE_THRESHOLD", "0.30")
)
ELEVATED_CONTEXT_K: int = int(os.getenv("ELEVATED_CONTEXT_K", "8"))


async def suggest_context_k(candidate_cwe_ids: list[str], base_k: int = 4) -> int:
    """Telemetry in: historical validator-failure rate per CWE.
    Decision out: how much RAG context (`k`) to retrieve for this scan.
    """
    if not candidate_cwe_ids:
        return base_k

    client = get_mcp_client()
    max_failure_rate = 0.0
    for cwe_id in candidate_cwe_ids:
        pattern = await client.get_cwe_failure_pattern(cwe_id)
        if pattern.available:
            max_failure_rate = max(max_failure_rate, pattern.fail_rate)

    if max_failure_rate > CWE_FAILURE_RATE_THRESHOLD:
        logger.info(
            "suggest_context_k: elevated k=%d for %s (max_failure_rate=%.2f)",
            ELEVATED_CONTEXT_K,
            candidate_cwe_ids,
            max_failure_rate,
        )
        return ELEVATED_CONTEXT_K

    return base_k


# ── 4. CostGuardian ───────────────────────────────────────────────────────────

COST_GUARDIAN_CHECK_EVERY_N_SCANS: int = int(
    os.getenv("COST_GUARDIAN_CHECK_EVERY_N_SCANS", "10")
)
COST_GUARDIAN_CUMULATIVE_THRESHOLD_USD: float = float(
    os.getenv("COST_GUARDIAN_CUMULATIVE_THRESHOLD_USD", "25.00")
)


class CostGuardian:
    """Telemetry in: cumulative session cost, sampled every N scans.
    Decision out: a global `conservation_mode` flag.
    """

    def __init__(
        self,
        check_every_n_scans: int = COST_GUARDIAN_CHECK_EVERY_N_SCANS,
        cumulative_threshold_usd: float = COST_GUARDIAN_CUMULATIVE_THRESHOLD_USD,
    ) -> None:
        self._check_every_n_scans = check_every_n_scans
        self._cumulative_threshold_usd = cumulative_threshold_usd
        self._scan_count: int = 0
        self._conservation_mode: bool = False

    async def record_scan(self) -> None:
        """Call once per completed scan. Every `check_every_n_scans` calls,
        this samples cumulative cost and updates conservation mode.
        """
        self._scan_count += 1
        if self._scan_count % self._check_every_n_scans != 0:
            return

        client = get_mcp_client()
        trend = await client.get_recent_cost_trend()

        if not trend.available:
            return

        cumulative_usd = trend.total_cost_usd
        was_conserving = self._conservation_mode
        self._conservation_mode = cumulative_usd > self._cumulative_threshold_usd

        if self._conservation_mode and not was_conserving:
            logger.warning(
                "CostGuardian: entering conservation_mode at scan #%d "
                "(cumulative=$%.4f > threshold=$%.4f)",
                self._scan_count,
                cumulative_usd,
                self._cumulative_threshold_usd,
            )
        elif was_conserving and not self._conservation_mode:
            logger.info(
                "CostGuardian: exiting conservation_mode at scan #%d "
                "(cumulative=$%.4f <= threshold=$%.4f)",
                self._scan_count,
                cumulative_usd,
                self._cumulative_threshold_usd,
            )

    def is_conservation_mode(self) -> bool:
        return self._conservation_mode


_cost_guardian = CostGuardian()


def is_conservation_mode() -> bool:
    return _cost_guardian.is_conservation_mode()


async def record_scan() -> None:
    await _cost_guardian.record_scan()