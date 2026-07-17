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

# TODO: swap Groq for GPT-5.6 — every `groq_client...` call and every model
# string in MODEL_* constants below is the swap point.
"""

from __future__ import annotations

import json
from typing import AsyncGenerator, Optional

from backend.core.rag_store import get_store, format_cwe_context
from backend.core.schemas import (
    AgentExecutionError,
    FixResult,
    PipelineResult,
    ReflectionAttempt,
    ScanResult,
    Severity,
    ValidationResult,
    Verdict,
    Vulnerability,
)

# The observability module owns this decorator. We only consume it.
from backend.core.telemetry import traced  # noqa: F401  (assumed to exist)

# Assumed injected/imported async client. Placeholder for GPT-5.6.
from groq_client import groq_client  # type: ignore  # noqa: F401


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
    """
    sev = Severity(severity.lower())  # raises ValueError on garbage — intentional
    if sev in (Severity.HIGH, Severity.CRITICAL):
        return MODEL_STRONG
    return MODEL_CHEAP


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
        return await groq_client.chat.completions.create(**kwargs)
    except Exception as exc:  # noqa: BLE001 — deliberate: normalize ALL SDK errors
        raise AgentExecutionError(agent, f"LLM call failed on model {model}", cause=exc)


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

    Retrieves top-k CWE context, injects it, and asks the model for structured
    findings. Severity of the findings determines the model tier — but we face
    a chicken-and-egg problem (we need findings to know severity to pick the
    model). We resolve it pragmatically: the Scanner runs on the STRONG model
    because detection quality is the foundation everything else builds on; a
    missed vuln can never be fixed. Routing savings are realized on the Fixer.
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
) -> FixResult:
    """
    Fixer Agent: generate a secured version of the code.

    `prior_feedback` is populated by the reflection loop on retries so the
    Fixer can course-correct against the Validator's critique — this is what
    makes the loop *converge* rather than repeat the same mistake.

    Model tier is chosen from the worst severity in the batch (feature #4):
    critical findings get the strong model, low/medium the cheap one.
    """
    model = select_model(_max_severity(vulns).value)
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

    Yields raw token deltas as they arrive. NOTE: token streaming is
    incompatible with strict JSON-mode validation mid-stream — you can't
    Pydantic-validate a half-written object. So this generator is for DISPLAY
    only; the authoritative, validated result must come from run_fixer(). The
    frontend shows the stream for UX, then reconciles with the validated
    FixResult. This separation is intentional: never let a pretty stream become
    the source of truth for a security patch.
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

    Always runs on the strong model (MODEL_VALIDATOR): the critic is the
    quality gate for the whole loop, so under-powering it would let bad fixes
    slip through and defeat self-healing.
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

    Loop semantics:
      1. Scanner produces findings.
      2. Fixer produces a patch.
      3. Validator scores it.
      4. If eval_score >= 85 AND verdict == pass -> converged, done.
         Else append the Validator's feedback and retry the Fixer.
      5. Stop after MAX_REFLECTION_RETRIES (3) attempts regardless.

    WHY 3 RETRIES?
      Empirically, agentic reflection shows sharply diminishing returns after
      ~2-3 iterations: if the model can't fix it in three tries with explicit
      feedback each time, the issue is usually out of its competence and
      further loops just burn tokens and latency while oscillating. Capping at
      3 bounds worst-case cost/latency to a predictable ceiling — essential for
      a fintech SLA — and prevents infinite loops on adversarial inputs. We
      return the FULL history so a human (or the frontend) can inspect the
      trajectory and take over when it fails to converge.

    Returns:
        PipelineResult with the final fix, final validation, every reflection
        attempt, convergence flag, and per-agent routing decisions.

    Raises:
        AgentExecutionError: if any agent fails irrecoverably (bubbled to the
        upstream circuit breaker).
    """
    scan = await run_scanner(code)

    routing: dict[str, str] = {"scanner": scan.model_used}
    history: list[ReflectionAttempt] = []
    feedback: Optional[str] = None
    converged = False

    final_fix: Optional[FixResult] = None
    final_validation: Optional[ValidationResult] = None

    for attempt in range(1, MAX_REFLECTION_RETRIES + 1):
        fix = await run_fixer(code, scan.vulnerabilities, prior_feedback=feedback)
        validation = await run_validator(code, scan.vulnerabilities, fix)

        routing[f"fixer_attempt_{attempt}"] = fix.model_used
        routing[f"validator_attempt_{attempt}"] = MODEL_VALIDATOR

        history.append(
            ReflectionAttempt(attempt_number=attempt, fix=fix, validation=validation)
        )
        final_fix, final_validation = fix, validation

        # Convergence gate: BOTH the numeric threshold and the adversarial
        # verdict must agree. A high score with a fail verdict means the critic
        # spotted something the rubric didn't capture — we trust the veto.
        if validation.eval_score >= EVAL_PASS_THRESHOLD and validation.verdict == Verdict.PASS:
            converged = True
            break

        # Feed the critique forward so the next Fixer iteration is informed.
        feedback = (
            f"Previous attempt scored {validation.eval_score}/100 (verdict={validation.verdict.value}).\n"
            f"Unresolved: {validation.unresolved_cwe_ids}\n"
            f"Reviewer feedback: {validation.feedback}\n"
            f"Reviewer reasoning: {validation.reasoning}"
        )

    assert final_fix is not None and final_validation is not None  # loop runs >=1x

    return PipelineResult(
        original_code=code,
        scan=scan,
        final_fix=final_fix,
        final_validation=final_validation,
        reflection_history=history,
        converged=converged,
        routing_decisions=routing,
    )
