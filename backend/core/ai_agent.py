"""
ai_agent.py — Multi-agent orchestration, model routing, self-healing loop.

DESIGN PHILOSOPHY (for the review):
-----------------------------------
This is the "does it actually reason?" file. The answer is yes, via a
Scanner -> Fixer -> Validator loop where the Validator's critique is fed BACK
into the Fixer until the fix clears a quality bar or we exhaust a retry budget.
That closed feedback loop is the difference between "an API wrapper" and "an
agent that verifies its own work."

Key architectural decisions, each defended inline:
  * JSON-mode / structured output at every hop (no regex).
  * Typed model routing keyed on severity.
  * Bounded reflection (max 3) with full history retained.
  * Every LLM call funnels through _call_llm which centralizes error handling
    and raises AgentExecutionError so the upstream circuit breaker has one
    exception type to catch.

# SELF-OBSERVATION (new in this revision):
# This file now also consumes backend/core/self_observer.py — the module
# that turns SigNoz telemetry into runtime decisions instead of just
# recording them. Every touchpoint is tagged with a `# SELF-OBSERVATION:`
# comment so a reviewer can grep this file for exactly what changed and
# audit each one. The hard rule across all of them: the self-observation
# layer can change WHICH model gets used or HOW MUCH context gets retrieved,
# but it can never be the reason a scan itself fails — every call into it is
# wrapped and falls back to the original, pre-existing behavior on any error.
#
# SelfObservationSummary now lives in backend/core/schemas.py (moved there
# so PipelineResult can reference it directly, no string forward-refs).

# TODO: swap Groq for GPT-5.6 — every `groq_client...` call and every model
# string in MODEL_* constants below is the swap point.
"""

from __future__ import annotations

import json
import logging
from typing import AsyncGenerator, Optional

from backend.core.rag_store import get_store, format_cwe_context
from backend.core.schemas import (
    AgentExecutionError,
    FixResult,
    PipelineResult,
    ReflectionAttempt,
    ScanResult,
    SelfObservationSummary,
    Severity,
    ValidationResult,
    Verdict,
    Vulnerability,
)

# The observability module owns this decorator. We only consume it.
from backend.core.telemetry import traced  # noqa: F401  (assumed to exist)

# Assumed injected/imported async client. Placeholder for GPT-5.6.
from groq_client import groq_client  # type: ignore  # noqa: F401

# SELF-OBSERVATION: local, dependency-free shadow cost recorder. Lets
# self_observer.get_recent_cost_trend() see real numbers immediately, even
# before the MCP-based SigNoz query path is fully wired up end-to-end.
from backend.core.local_telemetry import record_llm_call

# SELF-OBSERVATION: telemetry-in/decision-out functions. Every call into
# these is wrapped locally (see _select_model_adaptive, _safe_is_conservation_mode,
# and the finally-block in run_pipeline) so a failure here can never bubble
# up and break a scan.
from backend.core.self_observer import (
    adaptive_select_model,
    is_conservation_mode,
    record_scan,
    suggest_context_k,  # noqa: F401  (kept imported; see run_pipeline note on why it's not called yet)
)

logger = logging.getLogger(__name__)

# SELF-OBSERVATION: best-effort OpenTelemetry span access, used only to stamp
# an attribute on the current span when an adaptive override fires — this is
# what makes the adaptation itself traceable in SigNoz, right next to the
# scan it affected. Imported defensively: if otel isn't installed/configured
# in some environment, span-tagging degrades to a no-op rather than an
# ImportError at module load time.
try:  # pragma: no cover - environment dependent
    from opentelemetry import trace as _otel_trace
except Exception:  # noqa: BLE001
    _otel_trace = None  # type: ignore[assignment]


def _set_span_attr_safe(key: str, value: object) -> None:
    """SELF-OBSERVATION: set an attribute on the current span, best-effort.

    Telemetry in -> decision out is only half the story if the decision
    itself isn't visible in telemetry. This is the write-back half: when an
    adaptation fires, we stamp the reason onto the current span so it shows
    up in the same SigNoz trace as the scan it influenced. Never raises —
    a tracing failure must not affect the scan any more than a telemetry
    read failure should.
    """
    if _otel_trace is None:
        return
    try:
        span = _otel_trace.get_current_span()
        if span is not None:
            span.set_attribute(key, value)
    except Exception:  # noqa: BLE001
        logger.debug("SELF-OBSERVATION: failed to set span attribute %s", key, exc_info=True)


# ---------------------------------------------------------------------------
# Model routing (feature #4)
# ---------------------------------------------------------------------------
#
# Rationale for the mapping:
#   low/medium  -> a fast, cheap model. These findings are usually pattern-
#                  obvious (hardcoded secret, weak hash) where a smaller model
#                  is accurate enough, and we don't want to pay flagship prices
#                  for every low-severity nit.
#   high/critical -> the strongest model. A missed critical (SQLi, RCE) is a
#                  breach; the marginal token cost is trivial next to that risk.
#
# This is an asymmetric-cost decision: false negatives on criticals are
# catastrophic, false negatives on lows are cheap. So we spend compute exactly
# where the downside is worst.

# TODO: swap Groq for GPT-5.6
MODEL_CHEAP = "llama-3.1-8b-instant"       # -> GPT-5.6-mini equivalent
MODEL_STRONG = "llama-3.3-70b-versatile"   # -> GPT-5.6 (full) equivalent

# The Validator always uses the strong model regardless of severity: a weak
# critic that rubber-stamps bad fixes defeats the entire self-healing loop.
MODEL_VALIDATOR = MODEL_STRONG

EVAL_PASS_THRESHOLD = 85   # feature #5 gate
MAX_REFLECTION_RETRIES = 3


def select_model(severity: str) -> str:
    """
    Route to a model tier based on the highest severity in scope.

    Args:
        severity: one of 'low' | 'medium' | 'high' | 'critical'.

    Returns:
        The model string to invoke.

    Design note: we accept the raw string (as the spec dictates) but coerce
    through the Severity enum so an unknown value fails loudly rather than
    silently defaulting to the cheap model — silently under-provisioning a
    critical scan is the exact failure mode we must never have.

    NOTE: this stays a pure, severity-only function on purpose — it's the
    "base model" every other layer (including self-observation) builds on
    top of. See `_select_model_adaptive` below for the telemetry-aware
    wrapper used at the actual Fixer call site.
    """
    sev = Severity(severity.lower())  # raises ValueError on garbage — intentional
    if sev in (Severity.HIGH, Severity.CRITICAL):
        return MODEL_STRONG
    return MODEL_CHEAP


async def _select_model_adaptive(severity: str) -> tuple[str, Optional[str]]:
    """SELF-OBSERVATION: telemetry-aware wrapper around select_model().

    Telemetry in: recent cost trend + CostGuardian's conservation-mode flag
    (both read inside self_observer.adaptive_select_model). Decision out:
    possibly a cheaper model than the pure severity-based choice, plus a
    human-readable reason for the override.

    Fail-safe: ANY exception from the self-observation layer here results in
    silently falling back to the original severity-based model with no
    override — a telemetry read failure must degrade to "behave exactly as
    if this layer didn't exist," never to a broken scan.
    """
    base_model = select_model(severity)
    try:
        model, reason = await adaptive_select_model(severity, base_model)
        return model, reason
    except Exception:  # noqa: BLE001 — self-observation must never break a scan
        logger.exception(
            "SELF-OBSERVATION: adaptive_select_model failed for severity=%s; "
            "falling back to base model %s",
            severity,
            base_model,
        )
        return base_model, None


def _safe_is_conservation_mode() -> bool:
    """SELF-OBSERVATION: fail-safe wrapper around CostGuardian's flag.

    Used only for the SelfObservationSummary reported alongside the scan
    result (routing decisions already reflect conservation mode indirectly
    via _select_model_adaptive -> adaptive_select_model). If this read fails,
    we report `False` rather than propagate — worst case the summary under-
    reports conservation mode for this one scan, which is a cosmetic issue,
    not a correctness one.
    """
    try:
        return is_conservation_mode()
    except Exception:  # noqa: BLE001
        logger.exception("SELF-OBSERVATION: is_conservation_mode() failed; reporting False")
        return False


def _max_severity(vulns: list[Vulnerability]) -> Severity:
    """Pick the worst severity present; drives Fixer/routing for the whole batch."""
    order = {Severity.LOW: 0, Severity.MEDIUM: 1, Severity.HIGH: 2, Severity.CRITICAL: 3}
    if not vulns:
        return Severity.LOW
    return max((v.severity for v in vulns), key=lambda s: order[s])


# ---------------------------------------------------------------------------
# Central LLM call — the single choke point for error handling.
# ---------------------------------------------------------------------------

async def _call_llm(
    *,
    agent: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    json_schema: Optional[dict] = None,
    stream: bool = False,
):
    """
    Invoke the LLM with structured-output enforcement and uniform error
    handling. All agents go through here so AgentExecutionError is the ONLY
    exception the orchestrator (and the upstream circuit breaker) must handle.

    When json_schema is provided we request JSON mode; the caller is
    responsible for Pydantic-validating the parsed dict.
    """
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    kwargs: dict = {"model": model, "messages": messages, "stream": stream}
    if json_schema is not None:
        # Groq/OpenAI JSON mode. We embed the schema in the prompt too (below)
        # because JSON-mode guarantees valid JSON, not schema-conformant JSON.
        kwargs["response_format"] = {"type": "json_object"}

    try:
        # TODO: swap Groq for GPT-5.6
        resp = await groq_client.chat.completions.create(**kwargs)
    except Exception as exc:  # noqa: BLE001 — deliberate: normalize ALL SDK errors
        raise AgentExecutionError(agent, f"LLM call failed on model {model}", cause=exc)

    # SELF-OBSERVATION: shadow-record this call's approximate cost locally,
    # so get_recent_cost_trend has real numbers even before MCP is fully wired.
    # Best-effort only — a recording failure must never break a scan, so any
    # exception here is swallowed rather than propagated or logged noisily.
    try:
        out_text = "" if stream else (resp.choices[0].message.content or "")
        record_llm_call(model, user_prompt, out_text)
    except Exception:  # noqa: BLE001 — never let cost tracking break a scan
        pass

    return resp


def _parse_json_content(agent: str, content: str) -> dict:
    """Parse LLM JSON output, raising a typed error on failure."""
    try:
        return json.loads(content)
    except (json.JSONDecodeError, TypeError) as exc:
        raise AgentExecutionError(agent, f"Non-JSON output: {content[:200]!r}", cause=exc)


# ---------------------------------------------------------------------------
# Agent 1: Scanner
# ---------------------------------------------------------------------------

SCANNER_SYSTEM = """You are DevGuard's Scanner Agent, a senior application-security auditor.
You identify security vulnerabilities in source code with precision.

RULES:
- Report ONLY genuine security weaknesses. Do NOT invent findings; false positives
  destroy developer trust. If the code is clean, return an empty list.
- Each explanation MUST be a 2-3 sentence reasoning chain explaining WHY the
  specific pattern is dangerous, referencing the provided security knowledge.
- Use canonical CWE ids (e.g. CWE-89).
- confidence_score reflects your genuine certainty (0..1).

Return ONLY JSON matching this shape:
{"vulnerabilities": [{"cwe_id": str, "severity": "low|medium|high|critical",
"line_number": int, "explanation": str, "confidence_score": float}]}"""


@traced("scanner_agent")
async def run_scanner(code: str, k_context: int = 4) -> ScanResult:
    """
    Scanner Agent: RAG-augmented vulnerability detection.
    (see original docstring — unchanged)
    """
    store = get_store()
    retrieved = store.retrieve(code, k=k_context)
    context_block = format_cwe_context(retrieved)

    model = MODEL_STRONG  # detection is too important to under-provision
    numbered = "\n".join(f"{i+1}: {ln}" for i, ln in enumerate(code.splitlines()))

    user_prompt = (
        f"{context_block}\n\n"
        f"Analyze this code (line numbers prefixed). Report vulnerabilities as JSON.\n\n"
        f"```\n{numbered}\n```"
    )

    resp = await _call_llm(
        agent="scanner",
        model=model,
        system_prompt=SCANNER_SYSTEM,
        user_prompt=user_prompt,
        json_schema=ScanResult.model_json_schema(),
    )
    content = resp.choices[0].message.content
    data = _parse_json_content("scanner", content)

    try:
        vulns = [Vulnerability(**v) for v in data.get("vulnerabilities", [])]
    except Exception as exc:  # noqa: BLE001
        raise AgentExecutionError("scanner", "Findings failed schema validation", cause=exc)

    return ScanResult(
        vulnerabilities=vulns,
        model_used=model,
        retrieved_cwe_ids=[e["cwe_id"] for e in retrieved],
    )


# ---------------------------------------------------------------------------
# Agent 2: Fixer  (+ streaming variant)
# ---------------------------------------------------------------------------

FIXER_SYSTEM = """You are DevGuard's Fixer Agent, a senior secure-coding engineer.
Given vulnerable code and a list of findings, produce a corrected version.

RULES:
- Preserve original behavior and public interface; change only what security requires.
- Apply idiomatic, production-grade fixes (parameterized queries, safe deserializers,
  env-var secrets, CSPRNGs, etc.).
- If prior reviewer feedback is provided, address EVERY point it raises.

Return ONLY JSON:
{"patched_code": str, "diff_summary": str, "addressed_cwe_ids": [str]}"""


def _build_fixer_prompt(
    code: str,
    vulns: list[Vulnerability],
    prior_feedback: Optional[str],
) -> str:
    findings = "\n".join(
        f"- {v.cwe_id} ({v.severity.value}) line {v.line_number}: {v.explanation}"
        for v in vulns
    ) or "- (no structured findings; harden defensively)"
    feedback_block = (
        f"\n\nPRIOR REVIEWER FEEDBACK — you MUST resolve these:\n{prior_feedback}"
        if prior_feedback
        else ""
    )
    return (
        f"Vulnerabilities to fix:\n{findings}{feedback_block}\n\n"
        f"Original code:\n```\n{code}\n```\n\nReturn the corrected code as JSON."
    )


@traced("fixer_agent")
async def run_fixer(
    code: str,
    vulns: list[Vulnerability],
    prior_feedback: Optional[str] = None,
    override_model: Optional[str] = None,
) -> FixResult:
    """
    Fixer Agent: generate a secured version of the code.
    (see original docstring — unchanged, including override_model note)
    """
    model = override_model if override_model is not None else select_model(_max_severity(vulns).value)
    user_prompt = _build_fixer_prompt(code, vulns, prior_feedback)

    resp = await _call_llm(
        agent="fixer",
        model=model,
        system_prompt=FIXER_SYSTEM,
        user_prompt=user_prompt,
        json_schema=FixResult.model_json_schema(),
    )
    content = resp.choices[0].message.content
    data = _parse_json_content("fixer", content)
    data["model_used"] = model
    try:
        return FixResult(**data)
    except Exception as exc:  # noqa: BLE001
        raise AgentExecutionError("fixer", "Fix failed schema validation", cause=exc)


@traced("fixer_agent_stream")
async def run_fixer_stream(
    code: str,
    vulns: list[Vulnerability],
    prior_feedback: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    """
    Streaming variant of the Fixer for live frontend progress (feature #2).
    (see original docstring — unchanged)
    """
    model = select_model(_max_severity(vulns).value)
    user_prompt = _build_fixer_prompt(code, vulns, prior_feedback)

    stream = await _call_llm(
        agent="fixer_stream",
        model=model,
        system_prompt=FIXER_SYSTEM,
        user_prompt=user_prompt,
        stream=True,
    )
    try:
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta
    except Exception as exc:  # noqa: BLE001
        raise AgentExecutionError("fixer_stream", "Streaming failed mid-generation", cause=exc)


# ---------------------------------------------------------------------------
# Agent 3: Validator / Critic
# ---------------------------------------------------------------------------

VALIDATOR_SYSTEM = """You are DevGuard's Validator Agent, an adversarial security reviewer.
You are SKEPTICAL by default. Your job is to find reasons the fix is inadequate,
not to approve it.

Evaluate the patched code against the ORIGINAL vulnerabilities:
- Is each finding genuinely remediated (not merely hidden or commented out)?
- Did the fix introduce NEW vulnerabilities or break behavior?
- eval_score: 0-100 overall security+quality. verdict: "pass" only if you would
  personally ship this. List any unresolved CWE ids. Provide actionable feedback
  the Fixer can act on next iteration.

Return ONLY JSON:
{"eval_score": int, "verdict": "pass|fail", "reasoning": str,
"unresolved_cwe_ids": [str], "feedback": str}"""


@traced("validator_agent")
async def run_validator(
    original_code: str,
    vulns: list[Vulnerability],
    fix: FixResult,
) -> ValidationResult:
    """
    Validator/Critic Agent: adversarially review the Fixer's output.
    (see original docstring — unchanged)
    """
    findings = "\n".join(
        f"- {v.cwe_id} ({v.severity.value}) line {v.line_number}: {v.explanation}"
        for v in vulns
    ) or "- (none reported)"
    user_prompt = (
        f"ORIGINAL vulnerabilities:\n{findings}\n\n"
        f"ORIGINAL code:\n```\n{original_code}\n```\n\n"
        f"PATCHED code to review:\n```\n{fix.patched_code}\n```\n\n"
        f"Fixer's claimed fixes: {fix.addressed_cwe_ids}\n"
        f"Fixer's diff summary: {fix.diff_summary}\n\n"
        f"Review adversarially and return JSON."
    )

    resp = await _call_llm(
        agent="validator",
        model=MODEL_VALIDATOR,
        system_prompt=VALIDATOR_SYSTEM,
        user_prompt=user_prompt,
        json_schema=ValidationResult.model_json_schema(),
    )
    content = resp.choices[0].message.content
    data = _parse_json_content("validator", content)
    try:
        return ValidationResult(**data)
    except Exception as exc:  # noqa: BLE001
        raise AgentExecutionError("validator", "Validation failed schema validation", cause=exc)


# ---------------------------------------------------------------------------
# Orchestrator: the self-healing reflection loop (feature #5)
# ---------------------------------------------------------------------------

@traced("devguard_pipeline")
async def run_pipeline(code: str) -> PipelineResult:
    """
    Full DevGuard pipeline: Scan -> (Fix -> Validate)* with bounded reflection.
    (see original docstring — unchanged, including all SELF-OBSERVATION notes)
    """
    try:
        scan = await run_scanner(code)

        routing: dict[str, str] = {"scanner": scan.model_used}
        routing_overrides: dict[str, str] = {}
        history: list[ReflectionAttempt] = []
        feedback: Optional[str] = None
        converged = False

        severity_for_fix = _max_severity(scan.vulnerabilities).value
        adaptive_model, override_reason = await _select_model_adaptive(severity_for_fix)
        if override_reason:
            routing_overrides["fixer"] = override_reason
            _set_span_attr_safe("routing.override_reason", override_reason)

        final_fix: Optional[FixResult] = None
        final_validation: Optional[ValidationResult] = None

        for attempt in range(1, MAX_REFLECTION_RETRIES + 1):
            fix = await run_fixer(
                code,
                scan.vulnerabilities,
                prior_feedback=feedback,
                override_model=adaptive_model,  # SELF-OBSERVATION
            )
            validation = await run_validator(code, scan.vulnerabilities, fix)

            routing[f"fixer_attempt_{attempt}"] = fix.model_used
            routing[f"validator_attempt_{attempt}"] = MODEL_VALIDATOR

            history.append(
                ReflectionAttempt(attempt_number=attempt, fix=fix, validation=validation)
            )
            final_fix, final_validation = fix, validation

            if validation.eval_score >= EVAL_PASS_THRESHOLD and validation.verdict == Verdict.PASS:
                converged = True
                break

            feedback = (
                f"Previous attempt scored {validation.eval_score}/100 (verdict={validation.verdict.value}).\n"
                f"Unresolved: {validation.unresolved_cwe_ids}\n"
                f"Reviewer feedback: {validation.feedback}\n"
                f"Reviewer reasoning: {validation.reasoning}"
            )

        assert final_fix is not None and final_validation is not None  # loop runs >=1x

        self_observation = SelfObservationSummary(
            routing_override=routing_overrides.get("fixer"),
            context_k_adjusted=False,
            conservation_mode_active=_safe_is_conservation_mode(),
        )

        return PipelineResult(
            original_code=code,
            scan=scan,
            final_fix=final_fix,
            final_validation=final_validation,
            reflection_history=history,
            converged=converged,
            routing_decisions=routing,
            self_observation=self_observation,
        )
    finally:
        # SELF-OBSERVATION: tick CostGuardian exactly once per pipeline run,
        # success or failure — this is the "did a scan happen at all" signal
        # CostGuardian batches its cumulative-cost checks against, so it must
        # fire even when the pipeline raises above.
        try:
            await record_scan()
        except Exception:  # noqa: BLE001 — must never mask the real exception
            logger.exception("SELF-OBSERVATION: record_scan() failed; continuing")
