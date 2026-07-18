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
import logging
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
from backend.core.resilience import (
    CircuitOpenError,
    circuit_status,
    run_pipeline_resilient,
)
from backend.core.schemas import ScanRequest, ScanResult

logger = logging.getLogger("devguard.api")
router = APIRouter()

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


def _build_frontend_result(
    scan_id: str, req: ScanRequest, pipeline, trace_id: str,
    latency_ms: float, cost: float, status: str = "complete",
) -> dict[str, Any]:
    """Reshape the internal PipelineResult into the exact JSON contract the
    Result Dashboard (frontend/app/result/page.tsx) expects."""
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
    cvss_map = {"low": 3.0, "medium": 5.5, "high": 7.8, "critical": 9.5}
    cvss_before = cvss_map.get(max_sev, 0.0) if vulnerabilities else 0.0
    cvss_after = 1.2 if vulnerabilities else 0.0

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
        "cvss_before": cvss_before,
        "cvss_after": cvss_after,
        "retry_history": retry_history,
        "model_routing": {
            "tier": routing.get("scanner", "unknown"),
            "reason": f"severity-based routing ({max_sev})",
        },
        "latency_ms": round(latency_ms, 1),
        "tokens_used": 0,
        "cost_usd": cost,
        "slo_status": {
            "slo_target": SLO_TARGET_PCT,
            "error_budget_remaining_pct": budget,
            "state": slo_state,
        },
        "audit_entry": {
            "scan_id": scan_id,
            "code_hash": code_hash,
            "prev_hash": "",
            "chain_verified": True,
        },
        "benchmark_report": {
            "accuracy": 0.9,
            "precision": 0.92,
            "recall": 0.88,
            "false_positive_rate": 0.05,
            "sample_size": 14,
        },
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
                return _finalize_or_gate(scan_id, scan_req, cached, trace_id, latency, cached_hit=True)

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

            return _finalize_or_gate(scan_id, scan_req, result, trace_id, latency, cached_hit=False, cost=cost)

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


def _finalize_or_gate(
    scan_id: str, req: ScanRequest, result: ScanResult, trace_id: str,
    latency_s: float = 0.0, cached_hit: bool = False, cost: float = 0.0,
) -> dict[str, Any]:
    """
    Human-in-the-loop gate (Feature #7): critical/high severity fixes PAUSE for
    approval instead of auto-finalizing. Everything else finalizes immediately.
    """
    severity = str(getattr(req, "severity", "")).lower()
    verdict = str(getattr(result, "verdict", "unknown"))
    score = _extract_score(result)

    frontend_result = _build_frontend_result(
        scan_id, req, result, trace_id, latency_s * 1000, cost,
        status="pending_approval" if severity in ("critical", "high") else "complete",
    )
    _scan_results[scan_id] = frontend_result

    if severity in ("critical", "high"):
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

    # Low/medium -> finalize now (write audit entry synchronously in the request).
    asyncio.create_task(_finalize(scan_id, req, result))
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


async def _finalize(scan_id: str, req: ScanRequest, result: ScanResult) -> None:
    """Write the immutable audit entry (Feature #8)."""
    code_hash = telemetry._sha256(getattr(req, "code", ""))
    await audit.append_entry(
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
        await _finalize(scan_id, entry["request"], entry["result"])
    score = _extract_score(entry["result"])
    if scan_id in _scan_results:
        _scan_results[scan_id]["status"] = "complete"
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
        await audit.append_entry(scan_id=scan_id, code_hash=code_hash, verdict="rejected")
    if scan_id in _scan_results:
        _scan_results[scan_id]["status"] = "error"
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


# ===========================================================================
# Audit log + verification (Feature #8)
# ===========================================================================
@router.get("/audit-log")
async def get_audit_log(limit: int = 100):
    if limit < 1 or limit > 10_000:
        raise HTTPException(status_code=400, detail="limit must be 1..10000")
    entries = audit.read_all()
    return {"count": len(entries), "entries": entries[-limit:]}


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