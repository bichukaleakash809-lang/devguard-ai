# Existing system audit — D0 (05_DATAHUB_MASTER §21.5)

**Date:** 2026-07-31 · **Status:** D0 in progress, stopped at the mandated gate.

What follows is measured, not remembered. Every figure came from a command run
today against this repository.

---

## What works, verified

| Area | State | Evidence |
|---|---|---|
| Test suite | **306 passing**, no key / collector / network | `python -m pytest` → `306 passed in 35.73s` |
| CI | 4 jobs green on every push | `.github/workflows/ci.yml`, run 42 |
| Scanner → Fixer → Validator orchestration | Converges, retries, exhausts, short-circuits — all covered with agents mocked | `tests/test_pipeline_loop.py` |
| OTel export | Real OTLP/gRPC, decoded protobuf asserted | `scripts/verify_otel.py` |
| SigNoz | Stack up on pinned versions; **a real DevGuard trace stored and visible in the UI** | `docs/audit-evidence/t2/signoz-6.1-6.3-verified.txt` |
| SigNoz assets | Dashboard imported and rendering; 3 alert rules applied and verified | `docs/audit-evidence/t2/signoz-6.6-dashboard-alerts.txt` |
| Audit trail | Hash-chained, tamper-evident, verified endpoint | `tests/test_audit_chain.py` (37 tests) |
| Circuit breaker | CLOSED/OPEN/HALF_OPEN, fallback routing | `tests/test_circuit_breaker.py` |
| Fail-safe | Pipeline converges unchanged with the collector unreachable | `tests/test_pipeline_failsafe.py` (new) |
| Licence | Apache-2.0 present | `LICENSE` |
| Docker | B1/B2/A1 fixed, each proven | `docs/audit-evidence/t2/docker-build-fixes.txt` |

## What is incomplete

| Item | Why |
|---|---|
| T2 §6.3 four-agent trace | `fixer_agent` / `validator_agent` absent — Scanner's LLM call cannot complete. **External blocker**, see below |
| Six dashboard panels | Correct metric names, no samples — same root cause |
| Benchmark artifact | Never produced; needs a completed scan |
| T2 §6.5 (MCP truth) | `mcp_client.py` transport is assumed, never verified against a real MCP server |
| T3/T4/T5 | Not started |

## What is simulated, and labelled as such

* **Nexus god-mode endpoints** return synthetic data when called with an empty
  body, which is what the UI sends. Every response carries a `data_source` of
  `live` / `local_shadow` / `synthetic` / `partial`, and the UI renders it.
* **Self-observation** reads an in-process telemetry shadow, not SigNoz. Reported
  as `local_shadow`, never as live telemetry.
* **Pattern-Learning Agent does not fire.** Documented in README and pinned by
  `tests/test_self_observation_loops.py` so the claim cannot drift.

None of these is an undisclosed simulation. That matters for LAW 3.

---

## The external blocker (unchanged, and not a code defect)

`api.groq.com` is denied by the execution environment's egress policy —
`403 Forbidden` at CONNECT, before TLS, before any request. Verified from a clean
workspace outside the repo and with a second HTTP client; a control call to
`api.github.com` from the same context returns 200. **Owner action: allowlist
`api.groq.com`.** Full detail and the re-run commands: `docs/TODO-BLOCKED.md`.

---

## Environment verdict (§21.2 — this decides §18's first row)

| Resource | Measured | DataHub Core needs | Verdict |
|---|---|---|---|
| RAM | **15 GiB** total, 15 GiB available | ~8 GiB for the quickstart (ES heap dominates) | **Feasible, but not alongside SigNoz** |
| Disk | **16 GiB free** (of 252 GiB, 22 GiB used) | ~5 GiB on-disk for core images + Postgres substrate | **Tight. Workable only if the SigNoz images (3.9 GiB) are pruned first** |
| CPU | 4 cores | — | Adequate |
| Docker | 29.3.1, overlayfs | — | Working, via the `mirror.gcr.io` registry mirror |

**Image availability — measured, not assumed** (compressed, amd64):

```
linkedin/datahub-gms:head                 0.36 GB
linkedin/datahub-frontend-react:head      0.78 GB
linkedin/datahub-upgrade:head             0.25 GB
linkedin/datahub-elasticsearch-setup:head 0.01 GB
confluentinc/cp-kafka:7.4.0               0.44 GB
```

**Verdict: DataHub Core can run here, but not concurrently with the SigNoz
stack.** Disk is the binding constraint, not RAM. This is a real scheduling
consequence: the two demos cannot be live in the same session without pruning
between them, and that must be stated in the README rather than discovered on
camera.

## Tooling reachability (§5) — all green

```
PyPI mcp-server-datahub        0.6.0        (>= 0.5.0 required for mutation tools ✓)
PyPI datahub-agent-context     1.6.0.16
PyPI acryl-datahub             1.6.0.16
PyPI datahub-analytics-agent   0.4.0
uvx installed                  yes
npx installed                  yes
datahub-skills repo            HTTP 200
```

Notably, **the DataHub surface is NOT blocked by the egress policy** the way Groq
is. The DataHub half of this project is executable in this environment; the Groq
half is not.

---

## What is genuinely reusable for the hero loop

Judged against 05 §6's agent roster, and against LAW 1 (criterion or cut).

**Reuse — high value, already proven:**

| Existing | Maps to | Note |
|---|---|---|
| `backend/core/resilience.py` circuit breaker | Referee / general robustness | Battle-tested, 12 tests |
| `backend/core/audit.py` hash-chained trail | Proof pack / auditability (§11.6) | Exactly the "every action recorded" requirement |
| Prompt-injection boundary (`UNTRUSTED_CONTENT_RULE`, `fence_untrusted()`) | **Sentinel** (§6) | §11.2 requires precisely this; it exists and is tested |
| Typed Pydantic agent boundaries | **Evidence / AgentHandoff** contracts (§7) | "No raw dicts across module boundaries" is already the house style |
| OTel + SigNoz instrumentation | `timings.json` / cost accounting (§9C) | Real cost and token accounting already lands per call |
| Human-in-the-loop approval gate | **Magistrate** (§6) | Approve/reject with identity already exists |
| `scripts/verify_*.sh` discipline | `make verify` (§20) | The pattern is established |

**Cut or leave behind under LAW 1:**

| Existing | Why |
|---|---|
| Nexus god-mode simulators | Synthetic panels raise no DataHub criterion. §2 anti-goals name "a generic catalog or lineage browser" |
| The benchmark harness | Measures Scanner accuracy on OWASP snippets — orthogonal to every DataHub criterion |
| `chromadb` / `sentence-transformers` | 5.4 GiB of unimportable optional accelerators. Disk is the binding constraint (above). Cutting them is now a **capacity** decision, not just hygiene |
| The Scanner's own RAG store | The hero loop retrieves from **DataHub Context Documents**, not a local CWE store |

---

## What I would argue should change in the contract (§21.7)

Stated because §21 asks for it explicitly.

1. **The calendar has already slipped and the contract should acknowledge it.**
   05 §14 puts D0 on Jul 28 and MWP LOCK on Aug 3. **Today is Jul 31 — D3 by that
   calendar — and D0 is only now being executed.** D1 (prove the write path) and
   D2–D3 (substrate + real ingestion) have not happened. Three calendar days
   remain to MWP lock. I am not going to pretend that is recoverable at the
   contract's stated depth without a scope decision from you.

2. **The Groq blocker is not in the risk register, and it should be.** §18 lists
   "Live API/LLM failure while recording" — mitigated by an insurance cut. That
   is not this. Here the LLM is unreachable *at build time*, which blocks
   development, not just recording. If it is never unblocked, every LLM-backed
   agent in §6 (Archivist, Cartographer, Pathfinder, Diagnostician, Surgeon) can
   be *written* and *unit-tested with mocks* but never *demonstrated*.

3. **§17's PATH A vs PATH B is now the highest-leverage open decision**, and it
   is genuinely finely balanced — see the report accompanying this file. It
   cannot be decided unilaterally and the contract is right to gate on it.
