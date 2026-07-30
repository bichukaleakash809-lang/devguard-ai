# SigNoz Alert Rules — DevGuard AI

**Status: these rules are NOT pre-created in any SigNoz instance.** Verified, not
assumed — against the live instance this repo stands up:

```
$ curl -H "Authorization: Bearer $JWT" http://localhost:3301/api/v1/rules
{"status":"success","data":[]}
```

What this file gives you is three rules that can be built in the SigNoz UI in a
couple of minutes each, **every one of them written against a metric
`backend/core/telemetry.py` actually emits.** That was not true before: the
previous version of this file specified three metrics
(`devguard_slo_compliance_pct`, `devguard_circuit_breaker_state`,
`devguard_llm_cost_usd_total`) that **do not exist anywhere in the codebase**, and
it said so only in a soft aside ("assumes one corresponding OTel metric is
emitted … a few lines added to `telemetry.py`, not shown here"). Anyone pasting
those rules in would have got three alerts that never fire.

## The metrics that actually exist

Read straight out of `backend/core/telemetry.py`. **Note the dots** — SigNoz
stores OTel metric names verbatim, so `devguard_scan_latency` matches nothing:

| metric | type | unit |
|---|---|---|
| `devguard.scan.latency` | histogram | ms |
| `devguard.llm.cost_per_request` | histogram | USD |
| `devguard.llm.tokens_per_sec` | histogram | tokens/s |
| `devguard.llm.tokens_total` | counter | tokens |
| `devguard.llm.exceptions_total` | counter | 1 |
| `devguard.cache.hit_total` | counter | 1 |
| `devguard.cache.miss_total` | counter | 1 |
| `devguard.circuit_breaker.state_changes_total` | counter | 1 |
| `devguard.threats_blocked` | counter | 1 |
| `devguard.llm.cost_saved` | counter | USD |
| `devguard.llm.total_tokens` | counter | tokens |
| `devguard.llm.cost_total` | counter | USD |

**There is no SLO-compliance metric and no circuit-breaker *state* gauge.** Those
two absences change what can honestly be alerted on, and the rules below are
written around them rather than pretending otherwise.

---

## 1. LLM error burst

| | |
|---|---|
| **Name** | `devguard-llm-error-burst` |
| **Metric** | `devguard.llm.exceptions_total` (counter) |
| **Condition** | `increase` over 5m, **above 5**, at least once |
| **Severity** | warning |

Replaces the old "SLO Compliance Degradation" rule. That rule watched
`devguard_slo_compliance_pct`, which does not exist — nothing in the codebase
exports the calculation behind `/slo-status` as a metric. The error counter is
the closest signal that is genuinely emitted, and it catches the same class of
problem (the pipeline is failing repeatedly) without inventing a metric.

**UI:** Alerts → New Alert → Metric based Alert → metric
`devguard.llm.exceptions_total` → *aggregate within time series* `Increase`,
*across* `Sum` → condition `ABOVE` `5` `AT LEAST ONCE` during `Last 5 minutes`.

---

## 2. Circuit breaker flapping

| | |
|---|---|
| **Name** | `devguard-circuit-breaker-flapping` |
| **Metric** | `devguard.circuit_breaker.state_changes_total` (counter) |
| **Condition** | `increase` over 5m, **above 3**, at least once |
| **Severity** | critical |

Replaces the old "Circuit Breaker Stuck Open" rule, and the change is not
cosmetic. That rule needed `devguard_circuit_breaker_state` as a **gauge**
(`0=closed, 1=open, 2=half_open`) so it could assert "held at OPEN for 60
continuous seconds". **No such gauge is emitted.** What exists is a *counter of
transitions*, and a counter cannot express "is currently open" — only "changed
state N times".

So the honest rule is a different one: a breaker that transitions repeatedly is
failing to settle, which is the same incident from the other side. If you want
the original "stuck open" semantics, `telemetry.py` needs an
`observable_gauge` for breaker state first; until it has one, do not write a rule
that claims to detect it.

---

## 3. LLM cost budget

| | |
|---|---|
| **Name** | `devguard-llm-cost-budget` |
| **Metric** | `devguard.llm.cost_total` (counter, USD) |
| **Condition** | `increase` over 30m, **above your budget**, at least once |
| **Severity** | warning |

The only one of the three that survives largely intact. The old file named
`devguard_llm_cost_usd_total`; the real counter is **`devguard.llm.cost_total`**.
Set the threshold to whatever `COST_BUDGET_USD_PER_30MIN` is set to, so the alert
and the router's own conservation logic agree on the number.

Note the caveat carried over from `local_telemetry.py`: recorded cost is
provider-reported where the SDK supplies usage and a chars/4 estimate otherwise,
so this alert inherits that accuracy.

---

## Notifications

SigNoz needs a channel before any rule can notify: **Settings → Alert Channels**
→ add a Slack Incoming Webhook (or email/PagerDuty/webhook), then reference it
from each rule's notification step. With no channel configured a rule still
evaluates and shows as firing in the UI — it just cannot page anyone.

## Why these are not shipped pre-created

Creating them programmatically was attempted and **failed**, and the failure is
recorded rather than hidden: `POST /api/v1/rules` on SigNoz v0.135.0 rejected
every payload shape tried — builder-style `compositeQuery` (with and without a
`version` field) and `promql_rule` — each with
`{"errorType":"bad_data","error":"alert rule is not valid"}`, and the error does
not say which field is wrong. Driving the UI's query builder headlessly did not
work either: its metric picker is not a plain `<input>`, so the metric could
never be selected and **Save Alert Rule** stayed disabled.

Rather than ship a rule JSON that has never been accepted by a running SigNoz,
this file documents the UI path, which is verified to work and takes about two
minutes per rule. If someone captures a working payload from the browser's
network tab, it belongs in this repo and this section should be replaced with it.
