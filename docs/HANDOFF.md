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

**Tests: 58 passing**, all with no API key, no collector, no network.
- `test_schema_contracts.py` (20) — the typed-boundary claim actually enforced:
  bounded `eval_score`/`confidence_score`, enum rejection, minimum reasoning
  length, no raw dicts across boundaries, empty code rejected before any LLM call
- `test_audit_chain.py` (11) — tamper-evidence *demonstrated*, not asserted.
  In-place edit, code_hash swap, deletion, reordering and forged append are all
  caught. The key one: an attacker who recomputes the edited record's own hash
  defeats the per-record check but not the link check.
- `test_circuit_breaker.py` (12) — the real state machine, CLOSED → OPEN →
  HALF_OPEN → CLOSED, including that an OPEN breaker does not invoke the
  callable at all, and that a ValueError from our own code does not consume the
  outage budget
- `test_telemetry_failsafe.py` (15) — from T2 phase 3

**`make doctor`** (contract §4.3) reports what it observed, distinguishes
OPTIONAL from MISSING, and exits 0 only when every required check passes.
Verified in both directions — healthy venv exits 0; an interpreter without the
dependencies names all 8 missing packages and exits 1.

**CI** (`.github/workflows/ci.yml`) — three jobs, no API key, no collector.
Secret scan is **confirmed green on GitHub**. Backend and frontend job results
are recorded below once observed; nothing is claimed before then.

**Note for whoever picks this up: CI install time is a real problem.** The
backend job's `pip install -r requirements.txt` exceeded 12 minutes on a
GitHub runner, because of the 5.4 GB chromadb/sentence-transformers/torch tree.
This is concrete evidence for open issue 4 (cutting them) — it is no longer
just a clean-clone annoyance, it is a CI cost on every push.

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

**Smallest fix:** allowlist `registry-1.docker.io`, `auth.docker.io`, and
`production.cloudfront.docker.com`. Resources are adequate (21 GB disk, 15 GB
RAM vs SigNoz's ~4–6 GB). Then `docker compose --profile obs up` works
immediately, since the collector config now exists.

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
