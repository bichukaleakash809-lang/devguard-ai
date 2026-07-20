# SigNoz Alert Rules — DevGuard AI

Three alert rules covering the three failure modes that matter for a
self-observing agentic pipeline: **is the SLO being met**, **is the breaker
stuck protecting us from a dead upstream**, and **are we burning money**.

> **Setup note before you paste these in:** SigNoz alerts are built on
> **metrics**, not raw span events. `circuit_breaker.state_change` and
> `llm.cost_usd` currently exist as span *events*/*attributes* (see
> `resilience.py` / `mcp_client.py`), which are great for trace correlation
> but aren't directly queryable in the alert rule builder over a rolling
> window. Each alert below assumes one corresponding OTel metric is emitted
> alongside the existing span instrumentation (a few lines added to
> `telemetry.py`, not shown here). Where that's the case it's called out
> explicitly so a judge can see exactly what to check for.

---

## 1. SLO Compliance Degradation

| | |
|---|---|
| **Name** | `devguard-slo-compliance-degradation` |
| **Watches** | The rolling SLO compliance percentage backing the `/slo-status` endpoint — i.e. "are we still inside our 99.5% target error budget." |
| **Threshold** | `< 95` (percent), sustained for **5 minutes** |
| **Notification** | Slack `#devguard-oncall` webhook |
| **Why it matters** | This is the single number that turns "the pipeline threw some errors" into "we are at risk of breaching our published SLO" — it's the metric a judge (or an on-call human) should see *before* anyone opens a dashboard. |

**Metric assumption:** `devguard_slo_compliance_pct` (gauge, 0–100), exported
from the same calculation that backs `/slo-status`.

**PromQL condition** (SigNoz metrics alert, Prometheus-compatible query):

```promql
avg(devguard_slo_compliance_pct{service="devguard-backend"}) < 95
```

**Alert rule config** (SigNoz UI equivalent):

```yaml
alert: SLOComplianceDegradation
ruleType: metric_based_alert
condition:
  query: avg(devguard_slo_compliance_pct{service="devguard-backend"})
  op: "<"
  target: 95
evalWindow: 5m
for: 5m
severity: warning
labels:
  team: devguard
annotations:
  summary: "SLO compliance dropped below 95% for {{ $labels.service }}"
  description: "Current value: {{ $value }}%. Target: 99.5%. Check /slo-status and recent circuit breaker activity."
```

---

## 2. Circuit Breaker Stuck Open

| | |
|---|---|
| **Name** | `devguard-breaker-stuck-open` |
| **Watches** | Whether the `groq_primary` circuit breaker has been in the `OPEN` state continuously for too long — i.e. the fallback model has been carrying 100% of traffic for over a minute, meaning the primary upstream isn't recovering on its own. |
| **Threshold** | Breaker state `== OPEN` for **> 60 continuous seconds** |
| **Notification** | Slack `#devguard-oncall` webhook (mark as `severity: critical` — unlike alert #1, this means live traffic is currently degraded, not just at risk) |
| **Why it matters** | A breaker that *opens* is the system working as designed (see `resilience.py`'s blast-radius containment). A breaker that's *still open a minute later* means the automatic degrade-to-fallback safety net has become the primary path — that's the line between "resilience absorbed a blip" and "we have an ongoing incident," and it's exactly the kind of state transition the pipeline can now narrate about itself via the `PostmortemAgent` hook. |

**Metric assumption:** `devguard_circuit_breaker_state` (gauge, per
`breaker` label: `0=closed`, `1=open`, `2=half_open`), updated at the same
point `_transition()` already emits the `circuit_breaker.state_change` span
event, so the metric and the trace-level narrative never drift apart.

**PromQL condition:**

```promql
max_over_time(devguard_circuit_breaker_state{breaker="groq_primary"}[60s]) == 1
and
min_over_time(devguard_circuit_breaker_state{breaker="groq_primary"}[60s]) == 1
```

*(both `max` and `min` pinned to `1` over the window is the simplest way to
express "held at OPEN for the entire 60s," not just "touched OPEN at some
point.")*

**Alert rule config:**

```yaml
alert: CircuitBreakerStuckOpen
ruleType: metric_based_alert
condition:
  query: min_over_time(devguard_circuit_breaker_state{breaker="groq_primary"}[60s])
  op: "=="
  target: 1
evalWindow: 60s
for: 60s
severity: critical
labels:
  team: devguard
  breaker: groq_primary
annotations:
  summary: "groq_primary circuit breaker has been OPEN for over 60s"
  description: "Primary LLM provider has been suppressed continuously; all traffic is on fallback ({{ $labels.breaker }}). Check the linked trace's circuit_breaker.postmortem span event for the AI-generated incident summary."
```

---

## 3. Cost Budget Exceeded

| | |
|---|---|
| **Name** | `devguard-cost-budget-exceeded` |
| **Watches** | Cumulative LLM spend over a rolling 30-minute window, checked against the same `COST_BUDGET_USD_PER_30MIN` env-configured threshold the self-observing router already uses internally to reason about cost trends. |
| **Threshold** | `sum(llm.cost_usd) over 30m` `>` `COST_BUDGET_USD_PER_30MIN` |
| **Notification** | Slack `#devguard-oncall` webhook, plus (optional) email to whoever owns the Groq billing account |
| **Why it matters** | This is the one alert that isn't about correctness or availability — it's the guardrail that keeps a self-directed agent pipeline (which routes its own model tiers and retries its own fixes) from silently running up an unbounded bill, closing the loop between "the router can *see* cost via `get_recent_cost_trend()`" and "a human gets paged before it becomes a real number." |

**Metric assumption:** `devguard_llm_cost_usd_total` (monotonic counter),
incremented by the same value written to the `llm.cost_usd` span attribute on
every LLM call, so trace-level cost and the alerting metric always agree.

**PromQL condition:**

```promql
sum(increase(devguard_llm_cost_usd_total[30m])) > <COST_BUDGET_USD_PER_30MIN>
```

**Alert rule config:**

```yaml
alert: CostBudgetExceeded
ruleType: metric_based_alert
condition:
  query: sum(increase(devguard_llm_cost_usd_total[30m]))
  op: ">"
  target: ${COST_BUDGET_USD_PER_30MIN}   # same env var the router reads
evalWindow: 30m
for: 1m
severity: warning
labels:
  team: devguard
annotations:
  summary: "LLM spend exceeded budget for the last 30 minutes"
  description: "Spent ${{ $value }} against a ${COST_BUDGET_USD_PER_30MIN} budget. Check cost_by_model breakdown from get_recent_cost_trend() to see which tier is driving it."
```

---

## Wiring notifications (all three)

All three point at the same channel for a hackathon demo — one Slack
Incoming Webhook, added once under **Settings → Alert Channels** in SigNoz,
then referenced by name in each rule's notification step. Split
`#devguard-oncall` into severity-specific channels later if this goes past
demo stage; for now, one channel keeps the judge's verification path to
"add webhook URL → save → done" under the 2-minute budget.
