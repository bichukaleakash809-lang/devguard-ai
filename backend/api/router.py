"""
backend/api/router.py
====================
FastAPI surface for DevGuard AI's observability + resilience layer.

SRE DESIGN NOTES — THE REQUEST LIFECYCLE
----------------------------------------
Every /scan request:
  1. Continues the frontend's trace (traceparent) -> ONE unbroken trace.
  2. Opens the PARENT span "scan_request".
  3. Checks Redis (cache_lookup child span).
  4. On miss, runs the resilient pipeline (breaker + fallback + agent child spans).
  5. Computes cost (cost_calc child span) + emits metrics.
  6. For critical/high severity -> PAUSE at approval gate (no auto-finalize).
  7. On finalize -> append to audit chain + record SLO sample.

ERROR HANDLING CONTRACT:
  - Bad input           -> 400/422 (never trips the breaker, never a 500).
  - Unknown scan_id      -> 404.
  - Pipeline/LLM failure -> 503 with trace_id in the body so support can jump
                            straight to the trace in SigNoz. NEVER an unhandled 500.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from collections import deque
from typing import Any, Optional

from fastapi import APIRouter, Header, HTTPException, Request, WebSocket, WebSocketDisconnect
from opentelemetry import trace
from opentelemetry.trace import format_trace_id
from pydantic import BaseModel, ValidationError

from backend.core import audit, cache, telemetry
from backend.core.ai_agent import AgentExecutionError
from backend.core.mcp_client import get_mcp_client
from backend.core.resilience import (
    CircuitOpenError,
    circuit_status,
    run_pipeline_resilient,
)
from backend.core.schemas import ScanRequest, ScanResult

logger = logging.getLogger("devguard.api")
router = APIRouter()

#: Where a real benchmark run leaves its numbers. Absent by default — the
#: harness has to be run for accuracy figures to exist. Overridable so a
#: deployment can point at a mounted artifact.
BENCHMARK_ARTIFACT_PATH = os.environ.get(
    "DEVGUARD_BENCHMARK_ARTIFACT", "data/benchmark_report.json"
)

# ---------------------------------------------------------------------------
# SLO tracking (Feature #6).
# ---------------------------------------------------------------------------
SLO_TARGET_PCT = 99.5
SLO_LATENCY_BUDGET_S = 3.0
SLO_WINDOW = 100
_slo_window: deque[bool] = deque(maxlen=SLO_WINDOW)  # True = met SLO (under 3s)


def _record_slo_sample(latency_s: float) -> None:
    _slo_window.append(latency_s <= SLO_LATENCY_BUDGET_S)


def _slo_snapshot() -> dict[str, Any]:
    total = len(_slo_window)
    if total == 0:
        return {
            "slo_target": SLO_TARGET_PCT,
            "latency_objective_s": SLO_LATENCY_BUDGET_S,
            "window_size": SLO_WINDOW,
            "samples": 0,
            "current_compliance_pct": 100.0,
            "error_budget_remaining": 100.0,
        }
    met = sum(1 for ok in _slo_window if ok)
    compliance = round(100.0 * met / total, 3)
    allowed_bad = (100.0 - SLO_TARGET_PCT) / 100.0 * total
    actual_bad = total - met
    remaining = 100.0 if allowed_bad == 0 else round(
        max(0.0, 100.0 * (allowed_bad - actual_bad) / allowed_bad), 3
    )
    return {
        "slo_target": SLO_TARGET_PCT,
        "latency_objective_s": SLO_LATENCY_BUDGET_S,
        "window_size": SLO_WINDOW,
        "samples": total,
        "current_compliance_pct": compliance,
        "error_budget_remaining": remaining,
    }


# ---------------------------------------------------------------------------
# Pending-approval state (Feature #7).
# ---------------------------------------------------------------------------
_pending_approvals: dict[str, dict[str, Any]] = {}

# WebSocket subscribers per scan_id, for live waterfall streaming (Feature #10).
_ws_subscribers: dict[str, set[WebSocket]] = {}
_ws_pending_events: dict[str, list[dict]] = {}  # buffer for events published before a subscriber connects
_scan_results: dict[str, dict[str, Any]] = {}  # scan_id -> full frontend-shaped result


async def _publish_span_event(scan_id: str, payload: dict[str, Any]) -> None:
    """Push a span-completion event to all WS subscribers for this scan.
    If no subscriber is connected yet (the POST /scan pipeline usually
    finishes before the frontend opens its WebSocket), buffer the event so
    it can be replayed the instant a subscriber connects."""
    subs = _ws_subscribers.get(scan_id, set())
    if not subs:
        _ws_pending_events.setdefault(scan_id, []).append(payload)
        return
    dead = set()
    for ws in subs:
        try:
            await ws.send_json(payload)
        except Exception:  # noqa: BLE001
            dead.add(ws)
    for ws in dead:
        subs.discard(ws)


def _load_benchmark_artifact() -> Optional[dict[str, Any]]:
    """Read the accuracy figures the harness last measured, or None.

    LAW 6: every published number comes from the machine. This response used to
    carry `{"accuracy": 0.9, "precision": 0.92, "recall": 0.88,
    "false_positive_rate": 0.05, "sample_size": 14}` as hand-typed literals,
    and the result page rendered them as an "Accuracy benchmark proof strip" on
    every scan — while the README correctly stated the harness "has never been
    run to an artifact, so no accuracy figures are published anywhere."

    Now the only source is an artifact written by an actual run
    (`python -m backend.core.benchmark --json > data/benchmark_report.json`).
    No artifact means no figures: the field is `null` and the UI says so. A
    corrupt or partial artifact is also `null` — never a half-populated strip,
    because a missing `recall` rendering as 0% reads as a measured 0% recall.
    """
    required = ("accuracy", "precision", "recall", "false_positive_rate", "sample_size")
    try:
        with open(BENCHMARK_ARTIFACT_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning(
            "Benchmark artifact at %s is unreadable (%s); publishing no accuracy "
            "figures rather than substituting any.", BENCHMARK_ARTIFACT_PATH, exc,
        )
        return None

    if not isinstance(data, dict) or any(data.get(k) is None for k in required):
        logger.warning(
            "Benchmark artifact at %s is missing required metrics %s; publishing "
            "no accuracy figures.", BENCHMARK_ARTIFACT_PATH,
            [k for k in required if not isinstance(data, dict) or data.get(k) is None],
        )
        return None

    out = {k: data[k] for k in required}
    # Provenance, so the UI can date the figures instead of implying they are
    # from this scan. Optional: an older artifact simply has no timestamp.
    if data.get("generated_at") is not None:
        out["generated_at"] = data["generated_at"]
    return out


#: Sentinel `finalized_entry` value meaning "the append was attempted and it
#: raised", as distinct from None ("not attempted yet").
AUDIT_APPEND_FAILED = "append-failed"


def _audit_entry_block(
    scan_id: str, code_hash: str, finalized_entry: Optional[Any],
) -> dict[str, Any]:
    """The audit-chain facts for one scan, reporting only what is true yet."""
    if finalized_entry is AUDIT_APPEND_FAILED:
        return {
            "scan_id": scan_id,
            "code_hash": code_hash,
            "prev_hash": None,
            "entry_hash": None,
            "chain_verified": False,
            "chain_state": "failed",
        }
    if isinstance(finalized_entry, dict):
        return {
            "scan_id": scan_id,
            "code_hash": code_hash,
            "prev_hash": finalized_entry.get("prev_hash"),
            "entry_hash": finalized_entry.get("entry_hash"),
            # The append itself computed and wrote these links, so the record IS
            # chained. This is not a claim about the whole file — that is what
            # GET /audit-log/verify is for, and it walks every entry.
            "chain_verified": True,
            "chain_state": "written",
        }
    return {
        "scan_id": scan_id,
        "code_hash": code_hash,
        "prev_hash": None,
        "entry_hash": None,
        "chain_verified": None,
        "chain_state": "pending",
    }


def _sum_tokens(*results) -> Optional[int]:
    """Total provider-reported tokens across the agents that reported any.

    Returns None when no agent reported usage at all — that is "nothing counted
    them", which is a different fact from "zero tokens were used" and must not
    render as a measured 0 on the "Tokens Used" card.
    """
    counted = [
        t for t in (getattr(r, "tokens_used", None) for r in results if r is not None)
        if t is not None
    ]
    return sum(counted) if counted else None


def _build_frontend_result(
    scan_id: str, req: ScanRequest, pipeline, trace_id: str,
    latency_ms: float, cost: float, status: str = "complete",
    finalized_entry: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Reshape the internal PipelineResult into the exact JSON contract the
    Result Dashboard (frontend/app/result/page.tsx) expects.

    Everything this function emits is rendered to a human as measured fact, so
    every field is either a real measurement or explicitly absent (`null`).
    `finalized_entry` is the audit record `_finalize` actually wrote, when it has
    been written by the time this runs; without it the chain state is reported as
    `pending` rather than asserted as verified.
    """
    scan = getattr(pipeline, "scan", None)
    final_fix = getattr(pipeline, "final_fix", None)
    final_validation = getattr(pipeline, "final_validation", None)
    reflection_history = getattr(pipeline, "reflection_history", []) or []
    routing = getattr(pipeline, "routing_decisions", {}) or {}

    severity_order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
    vulnerabilities = []
    max_sev = "low"
    if scan is not None:
        for v in getattr(scan, "vulnerabilities", []) or []:
            sev = str(getattr(v, "severity", "low")).replace("Severity.", "").lower()
            vulnerabilities.append({
                "cwe": getattr(v, "cwe_id", "UNKNOWN"),
                "title": (getattr(v, "explanation", "") or "")[:80],
                "line": getattr(v, "line_number", 0),
                "severity": sev,
            })
            if severity_order.get(sev, 0) > severity_order.get(max_sev, 0):
                max_sev = sev

    retry_history = []
    for attempt in reflection_history:
        val = getattr(attempt, "validation", None)
        verdict_str = str(getattr(val, "verdict", "")) if val else ""
        retry_history.append({
            "attempt": getattr(attempt, "attempt_number", 0),
            "agent": "fixer",
            "validator_score": getattr(val, "eval_score", 0) if val else 0,
            "passed": "pass" in verdict_str.lower(),
        })

    eval_score = getattr(final_validation, "eval_score", 0) if final_validation else 0

    # SEVERITY, NOT CVSS. This used to publish `cvss_before` from a hard-coded
    # {"critical": 9.5, "high": 7.8, ...} lookup and `cvss_after` as the constant
    # 1.2, both rendered with `.toFixed(1)` under a "CVSS" label — which claims a
    # scored CVSS vector for code nobody scored. The Scanner reports a severity
    # *band*, so that ordinal is what gets published, under its own name.
    #
    # There is deliberately no "after" value: nothing re-scores the patched code.
    # The Validator grades the patch (eval_score, already reported above), which
    # is a different measurement from the residual severity of the result.
    severity_before = max_sev if vulnerabilities else None

    slo_snap = _slo_snapshot()
    budget = slo_snap["error_budget_remaining"]
    slo_state = "green" if budget > 50 else ("amber" if budget > 0 else "red")

    code_hash = telemetry._sha256(getattr(req, "code", ""))

    return {
        "original_code": getattr(pipeline, "original_code", getattr(req, "code", "")),
        "fixed_code": getattr(final_fix, "patched_code", "") if final_fix else "",
        "language": getattr(req, "language", "python"),
        "vulnerabilities": vulnerabilities,
        "eval_score": eval_score,
        "severity_before": severity_before,
        "retry_history": retry_history,
        "model_routing": {
            "tier": routing.get("scanner", "unknown"),
            "reason": f"severity-based routing ({max_sev})",
        },
        "latency_ms": round(latency_ms, 1),
        # Real provider-reported usage, summed over the agents that ran. `null`
        # when nothing counted them (streaming call, SDK without a `usage` block)
        # — this was previously the literal 0 on every response while the UI
        # rendered it as a "Tokens Used" metric.
        "tokens_used": _sum_tokens(scan, final_fix, final_validation),
        "cost_usd": cost,
        "slo_status": {
            "slo_target": SLO_TARGET_PCT,
            "error_budget_remaining_pct": budget,
            "state": slo_state,
        },
        # THE CHAIN BADGE. This block used to be
        # `{"prev_hash": "", "chain_verified": True}` — a hard-coded True that
        # rendered a green "✅ Chain Verified" tamper-evidence badge on the result
        # page. It was also computed BEFORE the entry existed: `_finalize` appends
        # the record after this function returns, so the response asserted a
        # verified hash chain for a record that had not been written.
        #
        # Three states now, and they are distinguishable:
        #   pending  -> not written yet, `chain_verified: null` (the UI says
        #               "pending", not "broken" — reporting False here would cry
        #               tamper on every healthy scan)
        #   written  -> the real prev_hash/entry_hash the append produced
        #   failed   -> the append raised; the entry is NOT in the log
        "audit_entry": _audit_entry_block(scan_id, code_hash, finalized_entry),
        # Accuracy figures come from a real harness run or not at all.
        "benchmark_report": _load_benchmark_artifact(),
        "trace_id": trace_id,
        "spans": [],
        "status": status,
    }


# ===========================================================================
# POST /scan  — the main entry point
# ===========================================================================
@router.post("/scan")
async def scan(request: Request, x_traceparent: Optional[str] = Header(default=None)):
    # ---- Input parsing (400/422, never a 500) ----
    try:
        body = await request.json()
        scan_req = ScanRequest(**body)
    except (ValidationError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=f"Invalid scan request: {exc}")

    # ---- Continue the frontend's trace (Feature #2) ----
    ctx = telemetry.extract_context(dict(request.headers))
    tracer = telemetry.get_tracer()
    scan_id = str(uuid.uuid4())

    with tracer.start_as_current_span("scan_request", context=ctx) as parent:
        trace_id = format_trace_id(parent.get_span_context().trace_id)
        parent.set_attribute("scan.id", scan_id)
        parent.set_attribute("scan.severity", getattr(scan_req, "severity", "unknown"))

        started = time.perf_counter()
        try:
            # ---- Cache lookup ----
            with telemetry.start_span("cache_lookup"):
                cached = await cache.get_cached(scan_req)
            if cached is not None:
                await _publish_span_event(
                    scan_id, {"stage": "cache", "status": "hit", "duration_ms": 0}
                )
                latency = time.perf_counter() - started
                _record_slo_sample(latency)
                _emit_request_metrics(cached, latency, cache_hit=True)
                return await _finalize_or_gate(scan_id, scan_req, cached, trace_id, latency, cached_hit=True)

            # ---- Run the resilient pipeline (breaker + fallback) ----
            result = await run_pipeline_resilient(scan_req)

            # ---- Cost calc (child span) ----
            with telemetry.start_span("cost_calc") as cost_span:
                cost = _compute_and_record_cost(result, cost_span)

            await cache.set_cached(scan_req, result)
            await _publish_span_event(
                scan_id,
                {
                    "stage": "pipeline",
                    "status": "ok",
                    "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                    "cost_usd": cost,
                },
            )

            latency = time.perf_counter() - started
            _record_slo_sample(latency)
            _emit_request_metrics(result, latency, cache_hit=False)

            return await _finalize_or_gate(scan_id, scan_req, result, trace_id, latency, cached_hit=False, cost=cost)

        except CircuitOpenError as exc:
            latency = time.perf_counter() - started
            _record_slo_sample(latency)
            parent.set_attribute("error.type", "CircuitOpenError")
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "LLM provider temporarily unavailable (circuit open).",
                    "trace_id": trace_id,
                    "retry_after_s": circuit_status()["reset_timeout_s"],
                },
            )
        except AgentExecutionError as exc:
            latency = time.perf_counter() - started
            _record_slo_sample(latency)
            raise HTTPException(
                status_code=503,
                detail={"error": f"Scan pipeline failed: {exc}", "trace_id": trace_id},
            )
        except HTTPException:
            raise
        except Exception as exc:  # noqa: BLE001 — the catch-all that prevents raw 500s
            latency = time.perf_counter() - started
            _record_slo_sample(latency)
            parent.record_exception(exc)
            parent.set_status(trace.Status(trace.StatusCode.ERROR, str(exc)))
            logger.exception("Unhandled scan error (trace_id=%s)", trace_id)
            raise HTTPException(
                status_code=500,
                detail={"error": "Internal error", "trace_id": trace_id},
            )


async def _finalize_or_gate(
    scan_id: str, req: ScanRequest, result: ScanResult, trace_id: str,
    latency_s: float = 0.0, cached_hit: bool = False, cost: float = 0.0,
) -> dict[str, Any]:
    """
    Human-in-the-loop gate (Feature #7): critical/high severity fixes PAUSE for
    approval instead of auto-finalizing. Everything else finalizes immediately.

    The audit append for the low/medium path is AWAITED here, not fired as a
    background task. It used to be `asyncio.create_task(_finalize(...))`, which
    had three problems: the docstring claimed the write was synchronous when it
    was not; an append that raised was swallowed with no log and no signal, so
    the audit record was silently lost while the response had already told the
    client the chain was verified; and asyncio keeps only a weak reference to a
    bare task, so it could be garbage-collected before it ran. The append is a
    sub-millisecond off-thread file write (see audit.append_entry), so awaiting
    it costs the request nothing measurable and makes the reported chain state
    true.
    """
    severity = str(getattr(req, "severity", "")).lower()
    verdict = str(getattr(result, "verdict", "unknown"))
    score = _extract_score(result)
    gated = severity in ("critical", "high")

    # Critical/high pause at the gate, so no entry is written yet -> the chain
    # state is reported as "pending" until /approve or /reject writes one.
    finalized_entry: Optional[Any] = None
    if not gated:
        try:
            finalized_entry = await _finalize(scan_id, req, result)
        except Exception:  # noqa: BLE001 — the audit write must not 500 the scan
            logger.exception(
                "Audit append FAILED for scan_id=%s; the scan result stands but "
                "this scan is NOT in the audit chain.", scan_id,
            )
            telemetry.add_span_event("audit.append_failed", {"scan.id": scan_id})
            finalized_entry = AUDIT_APPEND_FAILED

    frontend_result = _build_frontend_result(
        scan_id, req, result, trace_id, latency_s * 1000, cost,
        status="pending_approval" if gated else "complete",
        finalized_entry=finalized_entry,
    )
    _scan_results[scan_id] = frontend_result

    if gated:
        _pending_approvals[scan_id] = {
            "request": req,
            "result": result,
            "trace_id": trace_id,
            "created_at": time.time(),
        }
        telemetry.add_span_event(
            "approval.gate_opened", {"scan.id": scan_id, "severity": severity}
        )
        asyncio.create_task(
            _publish_span_event(
                scan_id,
                {
                    "type": "span",
                    "agent": "validator",
                    "status": "completed",
                    "message": f"Pending human approval (severity={severity}).",
                },
            )
        )
        return {
            "scan_id": scan_id,
            "status": "pending_approval",
            "severity": severity,
            "verdict": verdict,
            "trace_id": trace_id,
            "message": "High-severity fix requires human approval before finalization.",
        }

    # Low/medium: the audit entry was already written above, awaited.
    # Tell any (current or future, thanks to the buffer) WebSocket subscriber
    # that this scan is done — this is the event the frontend actually waits on.
    asyncio.create_task(
        _publish_span_event(
            scan_id, {"type": "done", "scan_id": scan_id, "score": score}
        )
    )
    return {
        "scan_id": scan_id,
        "status": "cache_hit" if cached_hit else "completed",
        "severity": severity,
        "verdict": verdict,
        "trace_id": trace_id,
        "result": _dump(result),
    }


async def _finalize(scan_id: str, req: ScanRequest, result: ScanResult) -> dict[str, Any]:
    """Write the immutable audit entry (Feature #8) and return the record written.

    Returning it lets the caller report the real prev_hash/entry_hash instead of
    asserting a chain link it never saw. Raises on failure — callers decide what
    to do, but nobody may report a verified chain for a write that did not happen.
    """
    code_hash = telemetry._sha256(getattr(req, "code", ""))
    return await audit.append_entry(
        scan_id=scan_id, code_hash=code_hash, verdict=str(getattr(result, "verdict", "unknown"))
    )


# ===========================================================================
# GET /scan/{scan_id}  — fetch the stored result for the Result Dashboard
# ===========================================================================
@router.get("/scan/{scan_id}")
async def get_scan(scan_id: str):
    result = _scan_results.get(scan_id)
    if result is None:
        if scan_id in _pending_approvals:
            raise HTTPException(status_code=202, detail="Scan still processing.")
        raise HTTPException(status_code=404, detail="Scan not found.")
    return result


# ===========================================================================
# Approval / rejection (Feature #7)
# ===========================================================================
@router.post("/scan/{scan_id}/approve")
async def approve(scan_id: str):
    entry = _pending_approvals.get(scan_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="No pending approval for scan_id.")
    with telemetry.start_span("approval_decision") as span:
        span.set_attribute("scan.id", scan_id)
        span.set_attribute("approval.decision", "approved")
        telemetry.add_span_event("approval.approved", {"scan.id": scan_id})
        written = await _finalize(scan_id, entry["request"], entry["result"])
    score = _extract_score(entry["result"])
    if scan_id in _scan_results:
        stored = _scan_results[scan_id]
        stored["status"] = "complete"
        # The gated result was stored with chain_state "pending" because no entry
        # existed yet. It does now, so replace the placeholder with the real
        # links rather than leaving the dashboard showing a stale pending badge.
        stored["audit_entry"] = _audit_entry_block(
            scan_id, stored["audit_entry"]["code_hash"], written
        )
    await _publish_span_event(
        scan_id, {"type": "done", "scan_id": scan_id, "score": score}
    )
    _pending_approvals.pop(scan_id, None)
    return {"scan_id": scan_id, "status": "approved", "verdict": str(getattr(entry["result"], "verdict", "unknown"))}


@router.post("/scan/{scan_id}/reject")
async def reject(scan_id: str, reason: Optional[str] = None):
    entry = _pending_approvals.get(scan_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="No pending approval for scan_id.")
    with telemetry.start_span("approval_decision") as span:
        span.set_attribute("scan.id", scan_id)
        span.set_attribute("approval.decision", "rejected")
        span.set_attribute("approval.reason", reason or "unspecified")
        telemetry.add_span_event("approval.rejected", {"scan.id": scan_id, "reason": reason or ""})
        code_hash = telemetry._sha256(getattr(entry["request"], "code", ""))
        written = await audit.append_entry(
            scan_id=scan_id, code_hash=code_hash, verdict="rejected"
        )
    if scan_id in _scan_results:
        stored = _scan_results[scan_id]
        stored["status"] = "error"
        # A rejection is also an audited decision — the entry exists, so report it.
        stored["audit_entry"] = _audit_entry_block(scan_id, code_hash, written)
    await _publish_span_event(
        scan_id, {"type": "error", "message": f"Fix rejected: {reason or 'no reason given'}"}
    )
    _pending_approvals.pop(scan_id, None)
    return {"scan_id": scan_id, "status": "rejected", "reason": reason}


# ===========================================================================
# SLO status (Feature #6)
# ===========================================================================
@router.get("/slo-status")
async def slo_status():
    snap = _slo_snapshot()
    snap["circuit_breaker"] = circuit_status()
    return snap


@router.get("/telemetry-status")
async def telemetry_status():
    """Honest, machine-readable statement of what observability is actually on.

    Exists so the SigNoz/MCP claim is inspectable at runtime rather than taken
    on trust from a README. Every field here is read from live configuration or
    a real object — none of it is asserted.
    """
    client = get_mcp_client()
    return {
        "otlp": {
            "endpoint": telemetry.OTLP_ENDPOINT,
            "sdk_disabled": os.environ.get("OTEL_SDK_DISABLED", "").lower() == "true",
            "service_name": telemetry.SERVICE_NAME,
            # Whether spans are being *emitted*. Whether anything is listening
            # at the other end is a separate question this cannot answer.
            "exporter_configured": bool(telemetry.OTLP_ENDPOINT),
        },
        "signoz_mcp": client.capability_report(),
        "self_observation_source": (
            "signoz_mcp" if client.is_configured() else "local_shadow"
        ),
    }


# ===========================================================================
# Audit log + verification (Feature #8)
# ===========================================================================
@router.get("/audit-log")
async def get_audit_log(limit: int = 100):
    if limit < 1 or limit > 10_000:
        raise HTTPException(status_code=400, detail="limit must be 1..10000")
    # read_tail parses only the page it returns, and both calls go to a thread
    # so a large audit log cannot stall the event loop. This endpoint used to
    # json.loads() the entire log to produce one page — 311 ms at 50k entries.
    count, entries = await asyncio.gather(
        asyncio.to_thread(audit.count_entries),
        asyncio.to_thread(audit.read_tail, limit),
    )
    return {"count": count, "entries": entries}


@router.get("/audit-log/verify")
async def verify_audit_log():
    report = audit.verify_chain()
    if not report["valid"]:
        raise HTTPException(status_code=409, detail=report)
    return report


# ===========================================================================
# WebSocket live waterfall (Feature #10)
# ===========================================================================
@router.websocket("/ws/scan/{scan_id}")
async def ws_scan(websocket: WebSocket, scan_id: str):
    await websocket.accept()
    _ws_subscribers.setdefault(scan_id, set()).add(websocket)
    try:
        await websocket.send_json({"scan_id": scan_id, "status": "subscribed"})
        pending = _ws_pending_events.pop(scan_id, [])
        for payload in pending:
            await websocket.send_json(payload)
        while True:
            await asyncio.sleep(30)
            await websocket.send_json({"type": "keepalive", "ts": time.time()})
    except WebSocketDisconnect:
        pass
    finally:
        subs = _ws_subscribers.get(scan_id, set())
        subs.discard(websocket)
        if not subs:
            _ws_subscribers.pop(scan_id, None)


# ---------------------------------------------------------------------------
# Metric helpers
# ---------------------------------------------------------------------------
def _compute_and_record_cost(result: ScanResult, span) -> float:
    model_id = str(getattr(result, "model_id", "__default__"))
    pt = int(getattr(result, "prompt_tokens", 0) or 0)
    ct = int(getattr(result, "completion_tokens", 0) or 0)
    cost = telemetry.compute_cost_usd(model_id, pt, ct)
    span.set_attribute("llm.model_id", model_id)
    span.set_attribute("llm.prompt_tokens", pt)
    span.set_attribute("llm.completion_tokens", ct)
    span.set_attribute("llm.cost_usd", cost)
    if telemetry.COST_PER_REQUEST_USD is not None:
        telemetry.COST_PER_REQUEST_USD.record(cost, {"model": model_id})
    if telemetry.TOKENS_TOTAL is not None:
        telemetry.TOKENS_TOTAL.add(pt + ct, {"model": model_id})
    return cost


def _emit_request_metrics(result: ScanResult, latency_s: float, cache_hit: bool) -> None:
    if telemetry.REQUEST_LATENCY_MS is not None:
        telemetry.REQUEST_LATENCY_MS.record(latency_s * 1000, {"cache_hit": str(cache_hit)})
    total_tokens = int(getattr(result, "prompt_tokens", 0) or 0) + int(
        getattr(result, "completion_tokens", 0) or 0
    )
    if total_tokens and latency_s > 0 and telemetry.TOKENS_PER_SEC is not None:
        telemetry.TOKENS_PER_SEC.record(total_tokens / latency_s)


def _extract_score(result: ScanResult) -> float:
    """Best-effort extraction of a 0-100 validator score from whatever shape
    `result` actually has."""
    for attr in ("eval_score", "score", "validator_score"):
        val = getattr(result, attr, None)
        if val is not None:
            return float(val)
    final_validation = getattr(result, "final_validation", None)
    if final_validation is not None:
        val = getattr(final_validation, "eval_score", None)
        if val is not None:
            return float(val)
    return 0.0


def _dump(result: ScanResult) -> dict[str, Any]:
    try:
        return result.model_dump()
    except AttributeError:
        return result.dict()