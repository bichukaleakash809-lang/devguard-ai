# Blocked work — must be re-run when the external blocker clears

This file exists so that **one externally-blocked verification step cannot be
mistaken for finished work**, and so nobody has to reconstruct what was pending
from commit archaeology. It lists only things that are *implemented but not
verifiable here*, with the exact command to run once the blocker lifts.

Everything not listed here is either done and verified, or genuinely not started.

---

## BLOCKER 1 — `api.groq.com` is denied by the environment's egress policy

**Status:** external. Nothing in this repository can fix it.
**Owner action:** allowlist the hostname `api.groq.com` on the execution
environment's egress policy (hostname, not IP — it resolves to rotating
Cloudflare anycast edges).

**Evidence:** `docs/audit-evidence/t2/signoz-live-llm-blocked.txt`

```
> CONNECT api.groq.com:443 HTTP/1.1
< HTTP/1.1 403 Forbidden
curl: (56) CONNECT tunnel failed, response 403
```

Verified from a clean workspace outside the repository, with a clean `HOME`, and
reproduced with a second HTTP client (Python `urllib`, not just curl). A control
request to `api.github.com` from the same clean context returned **200**, so it
is this host specifically, not the network. DNS resolves fine
(`104.18.38.236`, `172.64.149.20`), so it is not name resolution. The refusal
happens at `CONNECT`, **before TLS and before any HTTP request**, so no
`Authorization` header is ever transmitted — meaning the supplied API key's
validity is **untested, not disproven**.

### T2 §6.3 — LIVE FOUR-AGENT VERIFICATION — **NOT COMPLETE**

**Do not mark §6.3 complete until the command below has been run and passes.**

What *is* already verified and committed (see
`docs/audit-evidence/t2/signoz-6.1-6.3-verified.txt`):

* SigNoz is up on pinned versions (§6.1 DONE).
* A real DevGuard distributed trace is stored in SigNoz and visible in the UI,
  with a screenshot — `scan_request → cache_lookup + resilient_pipeline →
  llm_invoke ×2 (primary + circuit-breaker fallback) → devguard_pipeline →
  scanner_agent`. 9 spans, correctly nested, accurate error status.

What is **missing, and why**:

* `fixer_agent` and `validator_agent` do not appear in that trace. The Scanner's
  LLM call fails because Groq is unreachable, so the pipeline never advances past
  the Scanner and `POST /scan` returns 503.
* **This is missing execution, not missing instrumentation.** The spans are
  emitted by code that is already written and already proven to work for the
  spans that do appear.

**Re-run exactly this once `api.groq.com` is reachable:**

```bash
export GROQ_API_KEY=...                 # runtime only; never commit it
./scripts/verify_signoz.sh
```

Then assert the full chain is present:

```sql
-- against the running stack
SELECT DISTINCT name FROM signoz_traces.distributed_signoz_index_v3
WHERE trace_id = '<the trace_id the script prints>';
-- MUST include: scanner_agent AND fixer_agent AND validator_agent
```

Also re-capture the trace screenshot into
`docs/audit-evidence/t2/signoz/` so the committed image shows the four-agent
chain rather than the Scanner-only one.

### Six dashboard panels have correct names but no samples

`devguard.scan.latency`, `devguard.llm.cost_per_request`,
`devguard.llm.tokens_total`, `devguard.llm.total_tokens`,
`devguard.llm.cost_total` and `devguard.cache.hit_total` are only recorded on a
scan that **completes**. Their metric names were corrected and verified against
the running SigNoz (§6.6 is DONE), but they will read "No data in this time
range" until a live scan runs.

**Nothing to fix.** Re-screenshot the dashboard after the run above.

### The accuracy benchmark artifact has never been produced

```bash
python -m backend.core.benchmark --json data/benchmark_report.json
```

Needs a working key. That artifact is the **only** route by which an accuracy
number reaches the API or the UI — nothing is hard-coded at either end, and the
harness refuses to write it if any scan errored (`--allow-errored` overrides).
Until it exists the result page correctly shows "accuracy not measured".

---

## BLOCKER 2 — no verified SigNoz MCP server (T2 §6.5)

**Status:** partially external. `backend/core/mcp_client.py` targets an assumed
HTTP transport; real MCP is JSON-RPC 2.0, and no round trip has ever been
captured against a real server.

This is **already handled honestly in the code and docs** rather than left as an
overclaim: the cost query falls back to an in-process shadow reported as
`data_source: "local_shadow"`, never as live telemetry, and README states plainly
that "agents query their own telemetry via MCP" is designed-and-stubbed, not
demonstrated. `docs/MCP_DECISION.md` records the decision.

To close it properly, per §6.5: start the SigNoz MCP server, **list its tools**,
commit the tool list, then either wire `_call_tool` to the real schema and commit
a captured request/response round trip — or keep the current honest wording.

The `signoz/signoz-mcp-server:v0.9.0` image **is already pulled and available**
(see the registry evidence), so this is no longer blocked on image access.

---

## How to close this file out

Delete a section only when its command has been run and its output committed as
evidence. Do not delete a section because the work "looks done" — every item here
is code-complete already; what is missing is the *verification*, and that is the
entire point of the file.
