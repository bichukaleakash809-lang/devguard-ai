# DEVGUARD — SESSION HANDOFF

**Assume the next session has zero memory of this one. Read this file first.**

Protocol: `docs/03_CORE_CONTRACT.md` §6. First action of every session — read this
file. Last action — update it.

---

## CURRENT TRACK

**T0 — Audit. COMPLETE, approved, pushed.**
**T1 — Build + honesty pass. COMPLETE, approved, pushed.**
**T2 — SigNoz + MCP. PARTIALLY COMPLETE. Blocked on infrastructure for the rest.**
**Post-T2 hardening — IN PROGRESS. Non-blocked improvements, each verified.**

**T2 is NOT fully verified and must not be reported as such.** Four of its seven
sections are done and evidenced; three cannot be executed in this environment.
Do **not** start T3 until the human decides how to handle the blocked three.

`docs/04_TRACK_FINAL.md` remains **not to be executed** until the human says so.

---

## T2 — WHAT IS DONE (4 phases, each committed and pushed)

| Phase | Commit | Content |
|---|---|---|
| 1 | `e0f63ff` | MCP truth decision (§6.5) — branch two, stated honestly |
| 2 | `91fdccb` + `f3bb8e5` | OTLP pipeline verified end to end (§6.3 partial, §6.4) |
| 3 | `5e0df5d` | Fail-safe test suite (§6.7) — **and a real defect it found** |
| 4 | `05fc479` | `otel-collector-config.yaml` (§6.2) |

### §6.5 — the MCP decision: **branch two taken**

The contract offered "prove a real round trip and keep the claim" or "state
precisely what happens." Branch one is impossible here (see blockers), so the
claim is withdrawn. Full reasoning in **`docs/MCP_DECISION.md`**.

- `SIGNOZ_MCP_URL` no longer defaults to `http://localhost:8000` — which was
  **DevGuard's own backend port**. The client was calling DevGuard, getting a
  404, and falling back. Default is now empty.
- New `MCPNotConfiguredError`, raised **before any network I/O**.
- New `capability_report()` reporting `verified_against_real_server: false` and
  `tool_list: null` — rather than hard-coding tool names nobody has confirmed.
- New **`GET /telemetry-status`** so the claim is inspectable at runtime.

### §6.3/§6.4 — real OTLP, verified against decoded protobuf

**`scripts/verify_otel.py`** stands up a real OTLP/gRPC receiver, points a real
backend at it, drives real traffic, and decodes what arrives. Last run:

```
20 spans, 4 log records received over OTLP/gRPC
resource service.name = "devguard-ai"
14 parent/child pairs, every one sharing its parent's trace_id
log<->trace correlation CONFIRMED (trace 362d4f1f801eda77…)
runs with GROQ_API_KEY unset
```

This **verifies AUDIT.md's rejection of finding A10**: log↔trace correlation was
implemented, just never verified. It now is.

`--require-agent-spans` additionally drives `POST /scan` and asserts DevGuard's
own agent spans. **That path is written but has never been run** — it needs a
live Groq key, which this environment does not have.

### §6.7 — fail-safe tests, and the defect they found

**15 tests, all passing** (`tests/test_telemetry_failsafe.py`) — the first tests
in this repository. They run with no Groq key, no MCP URL, and the OTLP endpoint
pointed at the discard port so the failure path is genuinely exercised.

**They found a live production defect.** The suite hung on first run: requests
were fine, but *process shutdown* blocked forever with an unreachable collector.
Two causes, both fixed in `backend/core/telemetry.py`:

1. OTLP exporters had no timeout → now `OTEL_EXPORTER_OTLP_TIMEOUT` (default 5s).
2. **The OTel SDK registers its own `atexit` shutdown hook** which joins the
   exporter thread unbounded. Even a bounded `shutdown_telemetry()` still hung.
   All three providers now use `shutdown_on_exit=False`.

Any deployment whose collector went away would have hung on restart or redeploy.

---

## POST-T2 HARDENING (work that does not depend on the blocked registry)

| Commit | Content |
|---|---|
| `2452500` | Test suite expanded 15 -> 58 |
| `4cf03d2` | `make doctor` preflight + Makefile |
| `bf05d2d` | CI workflow (lint, typecheck, tests, OTLP verification, secret scan) |
| `2ff27c4` | Pydantic protected-namespace warning silenced |
| `4141e05` | Corrected a wrong CI claim (install is 86s, not "12+ minutes") |
| `0ab21d2` | CI confirmed green end to end; badge added |
| `1133985` | Frontend error surfaces (§4.5) — approval gate no longer fails silently |
| `fcfbaaf` | Security: untrusted-content boundary at every agent prompt |
| `cda9d78` | Docs accuracy: removed statements no longer true; DEPLOYMENT.md status banner |
| `9716701` | **RAG: fixed non-deterministic retrieval + found both heavy backends are dead** |
| `0a7341d` | **Pipeline: clean-code short-circuit; removed fake SigNoz log claims** |
| `7678d26` | **Benchmark: a failed scan is no longer reported as a clean scan** |
| `0c7ac2a` | **Performance: audit append was O(N) in log size, on the event loop** |

### Pipeline — two real defects (commit `0a7341d`)

**1. The reflection loop ran on clean code.** `run_pipeline` entered the
Fixer→Validator loop regardless of whether the Scanner reported anything. On
clean input that is up to **6 paid LLM calls**, with the Fixer told to "harden
defensively" code that had no findings — rewriting correct code, then grading
the rewrite. Not hypothetical: `benchmark.py` ships a negative control.
Fixed with a short-circuit; `final_validation` is **None** rather than a
synthesised pass, because no Validator ran and there is no honest `eval_score`
to invent. `PipelineResult.final_fix/final_validation` became `Optional`, which
matches how `router.py` already read them (every access was `getattr(..., None)`).

**2. Self-observation logs asserted a SigNoz MCP round trip.** Six statements
read "Querying SigNoz MCP Server..." / "SigNoz MCP Server reports...". No MCP
server is configured or has ever been contacted — and these records are exported
over OTLP, so they land **in SigNoz** asserting the round trip. Rewritten to name
the real source; a test guards the string from returning.

Evidence: `docs/audit-evidence/t2/pipeline-defects.txt` (includes the pre-fix
failing test output).

### Benchmark — measurement defect (commit `7678d26`)

`except AgentExecutionError: found = set()` recorded a **failed** scan
identically to one that correctly **found nothing**. So a run during an API
outage published itself as poor recall with nothing saying the run was degraded —
and that is the only number in the repo that could ever be published as accuracy
(LAW 6). Measured with 3 of 14 snippets forced to raise: recall 0.7692, and
before the fix that was indistinguishable from genuinely missing three
vulnerabilities. `BenchmarkReport.errored_snippets` (default 0, backward
compatible) plus per-snippet `errored` now make it visible; the negative control
`clean_parameterized` correctly stays `errored=0`.
Evidence: `docs/audit-evidence/t2/benchmark-defect.txt`

### Performance — audit append was O(N) per call (commit `0c7ac2a`)

`_read_last_entry()` iterated the whole audit log to read one field, once per
append — O(N²) over the log's life — and did it synchronously inside
`append_entry`'s lock, so it blocked the **event loop**, stalling unrelated
requests. Measured ms/append by existing log size:

```
entries      BEFORE       AFTER
      0      0.112 ms     0.379 ms
  1 000      0.338 ms     0.314 ms
 10 000      2.738 ms     0.405 ms
 50 000     13.823 ms     0.368 ms
```

123× degradation → flat. Fixed with a seek-from-end tail read plus
`asyncio.to_thread`. Honest tradeoff: the empty case costs ~0.27 ms more (the
thread hop) — a fixed cost replacing an unbounded one. A wrong tail read would
fork the chain silently, so 8 tests cover the edge cases.
Evidence: `docs/audit-evidence/t2/audit-performance.txt`

**Tests now 110.** CI green on runs 6, 8, 9 and 11 (runs 7 and 10 were cancelled by rapid follow-up pushes, not failures).

### RAG — two real defects (commit `9716701`)

**1. Retrieval was non-reproducible and irrelevant.** The fallback embedder used
`v[hash(tok) % DIM] += 1.0`, commented as "deterministic ... retrieval order
stable". Python randomises `hash()` for `str` per process, so three processes
gave three different CWE sets for the same SQL snippet, CWE-89 top-ranked in
none. Those results are injected into the Scanner prompt as "RELEVANT SECURITY
KNOWLEDGE (retrieved)" — so it was feeding near-random CWE definitions to the
model as authoritative. Replaced with a corpus-fitted token-overlap vector: no
hashing, determinism is structural. Correct CWE now ranks first for command
injection, weak hash and weak PRNG; CWE-89 top-3 for SQL.

**2. Neither pinned RAG backend can be imported.** On a clean install from
`requirements.txt` as committed:

```
sentence-transformers==2.2.2 -> ImportError: cannot import name 'cached_download'
                                from 'huggingface_hub' (0.36.2 removed it)
chromadb==0.4.24            -> AttributeError: np.float_ was removed in NumPy 2.0
                                (numpy 2.4.6 installed)
```

So the fallback is **always** what runs, and the 5.4 GiB of torch/CUDA buys
nothing. A pin incompatibility, not egress. Evidence:
`docs/audit-evidence/t2/rag-dependency-finding.txt`. **Not actioned** — repinning
or removing dependencies needs approval per §6. This is now the strongest
argument for open issue 4.

`make doctor` reports the *actually active* retrieval backend so this cannot
hide again.

**§4.5 error-surface audit — done.** All 7 frontend `catch` blocks audited. Two
were swallowing failures, both in `app/result/page.tsx`: the approval gate
rolled back silently (a user clicking "Approve fix" on a critical finding saw
no indication their decision had failed), and fetch errors discarded the reason
so every failure rendered the same generic message. Both now surface. The two
WebSocket `JSON.parse` catches are deliberately left ignoring malformed frames —
connection loss is surfaced separately by `onerror`.

**Security: prompt-injection boundary — added.** This was SECURITY.md's stated
"most significant open issue". Every agent system prompt now carries
`UNTRUSTED_CONTENT_RULE`, and `fence_untrusted()` wraps untrusted content in
sentinel markers rather than a ``` block (untrusted code can contain ``` and
break out of a markdown fence). The Fixer's own free-text output is fenced when
it reaches the Validator, since it inherits the taint. 12 tests.
**Mitigated, not solved** — SECURITY.md says so explicitly; the residual
false-negative risk is real and stated.

**Test inventory — 110 passing**, all with no API key, no collector, no network:
- `test_schema_contracts.py` (20) — the typed-boundary claim actually enforced:
  bounded `eval_score`/`confidence_score`, enum rejection, minimum reasoning
  length, no raw dicts across boundaries, empty code rejected before any LLM call
- `test_audit_chain.py` (19) — tamper-evidence *demonstrated*, not asserted,
  plus the tail-read edge cases (empty/whitespace/corrupt/multi-chunk).
  In-place edit, code_hash swap, deletion, reordering and forged append are all
  caught. The key one: an attacker who recomputes the edited record's own hash
  defeats the per-record check but not the link check.
- `test_circuit_breaker.py` (12) — the real state machine, CLOSED → OPEN →
  HALF_OPEN → CLOSED, including that an OPEN breaker does not invoke the
  callable at all, and that a ValueError from our own code does not consume the
  outage budget
- `test_telemetry_failsafe.py` (15) — T2 §6.7, plus the shutdown-hang defect
- `test_prompt_injection_boundary.py` (12) — the untrusted-content boundary
- `test_rag_store.py` (13) — retrieval determinism + relevance, incl. a
  source-level guard that builtin `hash()` never returns
- `test_pipeline_loop.py` (11) — the reflection loop: convergence, retry with
  feedback threaded, exhaustion, both gate conditions independently, the `>=`
  boundary, and the clean-code short-circuit
- `test_benchmark_harness.py` (8) — errored vs clean scans, partial outage
  visibility, FP counting, metric bounds, negative control preserved

**`make doctor`** (contract §4.3) reports what it observed, distinguishes
OPTIONAL from MISSING, and exits 0 only when every required check passes.
Verified in both directions — healthy venv exits 0; an interpreter without the
dependencies names all 8 missing packages and exits 1.

**CI** (`.github/workflows/ci.yml`) — three jobs, no API key, no collector.
Observed on GitHub, run 3 (`2f5abe8`):

| Job / step | Result |
|---|---|
| Secret scan (history + tracked-env check) | **success** |
| Frontend — lint, typecheck, build | **success** |
| Backend — install dependencies | **success, 86 s** (19:20:01 → 19:21:27) |
| Backend — import without an API key | **success** |
| Backend — preflight (`make doctor`) | **success** |
| Backend — tests (58), OTLP verification | **success** |

**Run 3 overall conclusion: `success`.** All three jobs green — the first
complete CI run. Run URL:
https://github.com/akashbichukale111/devguard-ai/actions/runs/30483894329

**CORRECTION.** An earlier version of this file claimed the backend job's pip
install "exceeded 12 minutes" and cited that as evidence for cutting
chromadb/sentence-transformers. **That was wrong.** Runs 1 and 2 were cancelled
by `concurrency: cancel-in-progress` when subsequent commits were pushed
moments later — run 2's backend job died about 75 seconds in — and the GitHub
API returned stale `in_progress` status when polled, which was misread as a
still-running install. The real figure is **86 seconds**, because
`actions/setup-python` with `cache: pip` restores the wheel cache.

The dependency tree is still 5.4 GB and still worth cutting (open issue 4), but
on the grounds of clean-clone install size — **not** CI time, which is fine.

**Operational note:** `cancel-in-progress` is correct, but it means pushing
again while a run is in flight kills it. When a CI result is actually needed,
push once and wait.

---

## T2 — WHAT IS STILL OPEN (blocked, with evidence)

| § | Item | Status |
|---|---|---|
| 6.1 | Stand up SigNoz at a pinned version | **BLOCKED** |
| 6.3 | One trace visible in the SigNoz UI + screenshot | **BLOCKED** |
| 6.6 | `signoz/dashboard.json` imported and verified; `alerts.md` reflecting real alerts | **BLOCKED** |

**The blocker is one thing only: container registry egress policy.**

Docker itself is fine — the daemon was not running and **I started it**; it
works (`Server Version: 29.3.1`). But every registry is refused by the egress
gateway with `403 to CONNECT`:

```
production.cloudfront.docker.com      (docker.io)
pkg-containers.githubusercontent.com  (ghcr.io)
quay.io
d2glxqk2uabbnd.cloudfront.net         (public.ecr.aws)
registry.k8s.io
ingest.us.signoz.cloud, signoz.io     (SigNoz Cloud — also blocked)
```

Raw proxy-recorded evidence: **`docs/audit-evidence/t2/registry-egress-block.txt`**

**DIAGNOSED PRECISELY** — see `docs/audit-evidence/t2/registry-egress-diagnosis.txt`.

The failing component is the **Claude execution environment's egress policy**,
enforced by the gateway its local HTTPS proxy relays to. It is a **default-deny
allowlist**, and the shape of the gap is specific:

| host | result |
|---|---|
| `registry-1.docker.io/v2/` | HTTP 401 — **allowed** (normal unauth response) |
| `index.docker.io/v2/` | HTTP 401 — **allowed** |
| `auth.docker.io` | HTTP 404 — **allowed** |
| `ghcr.io` | HTTP 301 — **allowed** |
| `production.cloudfront.docker.com` | **BLOCKED** (Docker Hub blob CDN) |
| `pkg-containers.githubusercontent.com` | **BLOCKED** (GHCR blob host) |

Registry **API** hosts are allowlisted; the **blob/CDN** hosts they redirect
layer downloads to are not. So `docker pull` authenticates, resolves the
manifest, then fails fetching layers. `example.com` is also blocked, which
proves default-deny rather than Docker being singled out.

Failure layer is exactly CONNECT authorization: DNS resolves, the local proxy
accepts the connection, and the **upstream gateway answers 403 to CONNECT**
(`kind=connect_rejected`). Nothing downstream is ever reached.

**Ruled out with evidence:** Docker Hub access (their API answers normally),
GitHub permissions (`api.github.com` 200, pushes work, Actions API works),
SigNoz permissions (no SigNoz software is ever contacted — the tunnel is refused
before any request, so no credential is involved), and a local firewall (the
refusal is from the upstream gateway, not locally).

**Smallest fix — ONE host:** allowlist `production.cloudfront.docker.com`
(Docker Hub; its API hosts are already allowed) **or**
`pkg-containers.githubusercontent.com` (GHCR; `ghcr.io` already allowed). Either
alone unblocks image pulls. Docker itself is fine — daemon started successfully
this session (29.3.1), and resources are adequate (21 GB disk, 15 GB RAM vs
SigNoz's ~4–6 GB). `otel-collector-config.yaml` already exists, so
`docker compose --profile obs up` becomes runnable immediately.

Side note: `huggingface.co` is also blocked, which explains why the semantic RAG
embedder could never fetch `all-MiniLM-L6-v2` — though that path is independently
broken by a dependency pin conflict.

---

## VERIFICATION — full gate, re-run at end of T2

```
import backend.main with GROQ_API_KEY unset  -> PASS
pytest                                       -> 15 passed
scripts/verify_otel.py                       -> PASSED (OTLP + context + log correlation)
npm run build                                -> Compiled successfully, 7/7 pages
npm run lint                                 -> No ESLint warnings or errors
docker compose --profile obs config          -> valid
```

Evidence on disk: `docs/audit-evidence/t2/` —
`registry-egress-block.txt`, `telemetry-status-unconfigured.json`,
`mcp-unconfigured-behaviour.txt`, `otel-verification.json`,
`pytest-failsafe.txt`, `otel-collector-config-validation.txt`.

---

## EXACT NEXT COMMAND

```bash
git checkout claude/track-t0-audit-evgu8j

# Re-verify the whole T2 surface at any time:
python -m pytest
python scripts/verify_otel.py

# The moment the registry egress policy allows Docker Hub, T2's remaining
# three sections become executable — the collector config already exists:
docker compose --profile obs up -d
docker compose logs otel-collector      # debug exporter shows arriving spans
```

---

## OPEN ISSUES — NEED A HUMAN DECISION

Blocking first:

1. **Registry egress policy (blocks the rest of T2, and T6/DataHub later).**
   Allowlist Docker Hub, or accept that §6.1/§6.3/§6.6 stay open and decide
   whether T2 counts as closed without them. **This is the decision to make.**
2. **No Groq API key.** No live LLM scan has ever run, in any session. The
   Scanner's end-to-end path and `verify_otel.py --require-agent-spans` are
   both unexercised because of it.
3. **Licence.** `03_CORE_CONTRACT.md` §2 makes Apache-2.0 a hard requirement;
   README previously said MIT; no `LICENSE` file exists. Owner's call.
4. **Cut `chromadb` + `sentence-transformers`?** 5.4 GiB including CUDA, for
   optional accelerators with a working fallback. Needs approval per §6. **Cut
   them only after the explicit instrumentation pins added in T1 phase 1** —
   `chromadb` was transitively supplying `opentelemetry-instrumentation-fastapi`.
5. **Delete the orphaned `signoz-system` gitlink?** No `.gitmodules`, breaks
   `git clone --recurse-submodules`. Recommend: delete.
6. **Agent roster count.** Contracts disagree: 12 (`03_CORE_CONTRACT.md` §5),
   11 (`02_ADDENDUM.md` Part D), and a third set in `01_PLATFORM_MASTER.md` §6.
   Must be settled before any UI renders it. Recommend 12.
7. **Flagship name.** Recommend **DevGuard Lineage Guard**.
8. **`DISCLOSURE.md`** still needs the hackathon-start SHA and the target
   hackathon (README says *Agents of SigNoz*, contracts say *Build with
   DataHub*). Note `9651db3` cited in `01_PLATFORM_MASTER.md` does not exist in
   this repo's history.

---

## STANDING RULES (do not relearn these the hard way)

- Never `git push --force`, never rewrite published history, never delete files
  without approval. A `git rebase --exec` was run in error during T1 and had to
  be aborted — **`--exec` is not a dry run.**
- Commit and push at every phase boundary; verify on GitHub before continuing.
- Never mark your own work green because the code looks correct. Green comes
  from pasted output. If §3's five conditions cannot all be met, the track is
  **reported as blocked**, never "complete with a caveat."
- Do not claim a capability in a commit message before implementing it. This
  happened once in T2 phase 2 (`--require-agent-spans`) and was corrected in
  `f3bb8e5`.
- Work on branch `claude/track-t0-audit-evgu8j`.

---

*Last updated: 2026-07-29, post-T2 hardening. HEAD: `2ff27c4`.*
