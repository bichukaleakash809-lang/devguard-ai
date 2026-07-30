# DEVGUARD — TRACK T0 AUDIT

**Date:** 2026-07-29
**Branch:** `claude/track-t0-audit-evgu8j`
**HEAD at audit:** `3f590b1`
**Auditor:** Claude Code, executing Track T0 of `docs/03_CORE_CONTRACT.md` §7.
**Scope:** read-only. No implementation file was modified. Only `docs/AUDIT.md`,
`docs/HANDOFF.md` and `DISCLOSURE.md` (draft) were created.

> The master prompt's §2 findings were taken from a snapshot at commit `9651db3`.
> That commit is **not** in this repository's history (see §7). Every §2 item was
> therefore re-verified against the live tree; the verdict table is §3.

---

## 1 — ENVIRONMENT CAPACITY

| Resource | Measured | Command |
|---|---|---|
| Disk (root fs) | 252 G total, **27 G available** | `df -h /` |
| RAM | **15 GiB total**, 14 GiB free, **no swap** | `free -h` |
| CPU | 4 cores | `nproc` |
| Python | 3.11.15 | `python3 --version` |
| Node | v22.22.2, npm 10.9.7 | `node --version` |
| Docker CLI | Engine 29.3.1 (client) | `docker version` |
| Docker daemon | **NOT RUNNING** | `dial unix /var/run/docker.sock: connect: no such file or directory` |
| Docker Compose | v5.1.1 | `docker compose version` |

### Verdict on the §3.3 / §18 capacity question

**No. This machine cannot run SigNoz + DataHub Core + Postgres simultaneously,
and today it cannot run any of them.**

1. **There is no Docker daemon in this environment.** The CLI and Compose plugin
   are installed, but `/var/run/docker.sock` does not exist. `docker compose
   config` (static validation) works; `docker compose up` cannot run at all.
   Every container-dependent gate — SigNoz, DataHub Core, Postgres, the `obs`
   profile, `make demo` — is unexecutable here.
2. **Even with a daemon, 15 GiB RAM with no swap is below the floor.** DataHub
   Core (GMS + Elasticsearch + Kafka + MySQL/Postgres + frontend) wants ~8–10
   GiB on its own; SigNoz (ClickHouse + Zookeeper + collector + query-service +
   UI) wants ~4–6 GiB; the substrate Postgres + dbt + the ML model wants ~1–2
   GiB. That totals at or above physical RAM before DevGuard itself starts.
3. **27 GiB free disk is the tighter constraint.** DataHub's image set alone is
   ~10–12 GiB pulled; SigNoz ~3–4 GiB; and this repo's own Python dependency
   tree is **> 1.1 GiB and still installing** at the time of writing (§2.2) —
   because `sentence-transformers` pulls torch.

**Consequence for the architecture, stated now as §3.3 requires:** the plan of
record cannot assume a single local machine hosting the full stack. The realistic
options, in order of preference:

- **(a)** Run DataHub Core and SigNoz on a separate host (cloud VM ≥ 32 GiB RAM,
  ≥ 100 GiB disk) and point DevGuard at them over the network. Costs money, but
  it is the only option that satisfies the D0/D1 gates as written.
- **(b)** Never co-run them: bring up SigNoz, capture its evidence, tear it down,
  then bring up DataHub. Satisfies the *evidence* requirements without ever
  needing both live at once. Cheapest path that keeps the contract honest.
- **(c)** Use DataHub Cloud trial + SigNoz Cloud. Fastest, but §5's "self-hosted
  DataHub Core" and the incident-privilege configuration need re-verification
  against Cloud, and the contract explicitly warns that Cloud-only features must
  not appear in the hero path.

This is a decision for the human, and it blocks T2 and T6. It does not block
T1a/T1b.

---

## 2 — WHAT WAS RUN, AND WHAT IT PRINTED

### 2.1 `docker compose config` — **PASSES** (misleadingly)

```
time="2026-07-29T10:38:31Z" level=warning msg="/home/user/devguard-ai/docker-compose.yml:
the attribute `version` is obsolete, it will be ignored, please remove it to avoid potential confusion"
name: devguard-ai
services:
  backend:
    build:
      context: /home/user/devguard-ai/backend
      dockerfile: Dockerfile
...
```

Exit 0 (with `GROQ_API_KEY` supplied; without it, compose aborts on
`GROQ_API_KEY: ${GROQ_API_KEY:?set GROQ_API_KEY in .env}`).

**This green is not meaningful.** `config` validates YAML only — it never checks
that the referenced build contexts contain the files their Dockerfiles copy. Both
images fail at build time (§3, B1/B2). Do not cite `docker compose config` as
evidence that Docker works.

### 2.2 `pip install -r requirements.txt` — **SUCCEEDS, at a cost of 5.4 GiB**

Run in a clean venv (`python3 -m venv`). Exit 0. The resolved tree:

```
Successfully installed ... chromadb-0.4.24 sentence-transformers-2.2.2 torch-2.13.0
torchvision-0.28.0 transformers-4.57.6 triton-3.7.1 nvidia-cublas-13.1.1.3
nvidia-cudnn-cu13-9.20.0.48 nvidia-cusolver-12.0.4.66 nvidia-nccl-cu13-2.29.7
cuda-toolkit-13.0.3.0 ... (139 packages)
```

```
$ du -sh venv
5.4G	venv
```

**A judge running the documented quickstart downloads 5.4 GiB, including the full
CUDA toolkit, to see a demo that never touches a GPU.** A11 confirmed, and the
magnitude is worse than "multi-GB" suggests. It also took ~9 minutes on 4 cores.

### 2.3 Backend import — **FAILS on a clean install**

Executed against the venv from §2.2:

```
$ python -c "import backend.main"
Traceback (most recent call last):
  File "<string>", line 1, in <module>
  File "/home/user/devguard-ai/backend/main.py", line 4, in <module>
    from opentelemetry.instrumentation.logging import LoggingInstrumentor
ModuleNotFoundError: No module named 'opentelemetry.instrumentation.logging'
```

`opentelemetry-instrumentation-logging` is in neither `requirements.txt` nor the
resolved tree. **New finding, not in §2 (B5).**

There is a trap inside this trap. `opentelemetry-instrumentation-fastapi` — also
imported by `main.py:3`, also absent from `requirements.txt` — *does* get
installed, but only by accident:

```
$ pip show opentelemetry-instrumentation-fastapi
Version: 0.41b0
Required-by: chromadb
```

**It is a transitive dependency of `chromadb`.** So the A11 dependency diet and
the B5 missing-dependency bug are coupled: **removing `chromadb` (which §6
recommends) silently breaks `FastAPIInstrumentor` too** unless both instrumentation
packages are added explicitly first. Sequence matters here.

After installing the missing package, the *next* failure is B4 — the import-time
secret requirement:

```
$ python -c "import backend.main"      # no GROQ_API_KEY
  File "/home/user/devguard-ai/backend/api/router.py", line 39, in <module>
    from backend.core.ai_agent import AgentExecutionError
  File "/home/user/devguard-ai/backend/core/ai_agent.py", line 94, in <module>
    from groq_client import groq_client
  File "/home/user/devguard-ai/groq_client.py", line 18, in <module>
    raise RuntimeError(
RuntimeError: GROQ_API_KEY environment variable is not set. ...
```

**The backend package is unimportable without a live Groq key.** No test can
import it, no CI can typecheck it, `make doctor` could not report on it.

With both fixed (`GROQ_API_KEY=dummy`), import succeeds:

```
IMPORT OK
```
(plus `UserWarning: Field "model_used" has conflict with protected namespace "model_"`
— minor, `schemas.py` should set `protected_namespaces = ()`.)

### 2.3b Backend boot and live endpoint exercise — **RUNS**

With the two blockers worked around, the server boots cleanly:

```
INFO:     Started server process [18691]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8099
```

Endpoints that do not need a live LLM were then exercised for real. Raw responses
are committed under `docs/audit-evidence/`.

**`GET /slo-status`** — works:
```json
{"slo_target":99.5,"latency_objective_s":3.0,"window_size":100,"samples":0,
 "current_compliance_pct":100.0,"error_budget_remaining":100.0,
 "circuit_breaker":{"name":"groq_primary","state":"closed","fail_count":0,
 "fail_max":5,"reset_timeout_s":30.0}}
```

**`GET /audit-log/verify`** — genuinely re-verifies the hash chain:
```json
{"valid":true,"entries_checked":35,"broken_at":null,"reason":"chain intact"}
```

**`POST /god-mode/simulate/cost-spike`** — **this is the LAW 4 breach, caught at
runtime.** No SigNoz, no MCP server, and no collector were running:
```json
{"run_id":"finops_725a5b55be","module":"finops_agent","data_source":"live",
 "spend_usd_per_30min":0.0,"budget_usd_per_30min":5.0,"over_budget":false,
 "reasoning":"30-min spend $0.0000 is within the $5.00 budget; no sampling change needed."}
```
The MCP call failed, fell back to the empty in-process shadow, and the response is
labelled **`"data_source":"live"`**. See §3.B.3.

**`POST /god-mode/simulate/error`** with `{}` — the exact body the Nexus UI sends:
```json
{"run_id":"heal_7b0737de4e","module":"omni_heal","data_source":"synthetic", ...}
```
Confirms D3 at runtime: the UI's own request shape can only ever produce the
synthetic branch.

**`POST /god-mode/simulate/god-mode`** — the Executive summary labels the whole
run `live` while its own body reports its sections as `[synthetic]`:
```json
{"module":"executive_sre_commander","data_source":"live",
 "slack_message":"... • Omni-Heal: 1/3 reflection attempts, verdict=pass, eval_score=92 [synthetic]\n
                  • FinOps: $0.0000/30min (within budget) [live]\n
                  • Pre-Cog Ops: ... [synthetic]\n ..."}
```
The cause is `god_mode_orchestrator.py:552`:
```python
"data_source": "live" if not errors and sections else ("synthetic" if not sections else "partial"),
```
The label tracks **whether anything errored**, not whether the data was real — so
it reads `live` whenever the synthetic fallbacks all succeed, and the `"partial"`
branch is unreachable whenever `sections` is non-empty and `errors` is empty.

**No live scan and no live pipeline run was executed** — that needs a real Groq
key, which is not available here. Everything above ran against the synthetic and
telemetry paths only, and nothing in this audit claims otherwise.

### 2.4 `npm install` — **PASSES** (exit 0)

### 2.5 `npx tsc --noEmit` — **FAILS, 5 errors**

```
app/nexus/page.tsx(266,15): error TS2322: Type 'Record<string, unknown> | null' is not assignable to type 'Partial<OmniHealData> | undefined'.
  Type 'null' is not assignable to type 'Partial<OmniHealData> | undefined'.
app/nexus/page.tsx(275,15): error TS2322: ... 'Partial<FinOpsData> | undefined'.
app/nexus/page.tsx(284,15): error TS2322: ... 'Partial<PreCogData> | undefined'.
app/nexus/page.tsx(293,15): error TS2322: ... 'Partial<LLMJudgeData> | undefined'.
app/nexus/page.tsx(302,15): error TS2322: ... 'Partial<ExecutiveCommanderData> | undefined'.
```

### 2.6 `npm run build` — **FAILS**

```
  ▲ Next.js 14.2.35
  - Environments: .env.local

   Creating an optimized production build ...
 ✓ Compiled successfully
   Linting and checking validity of types ...
Failed to compile.

./app/nexus/page.tsx:266:15
Type error: Type 'Record<string, unknown> | null' is not assignable to type 'Partial<OmniHealData> | undefined'.
  Type 'null' is not assignable to type 'Partial<OmniHealData> | undefined'.
Next.js build worker exited with code: 1 and signal: null
```

Two things to read off this output:

- **The frontend does not build.** §10's "zero TypeScript errors" gate is red, and
  it is red on `main`, not just here.
- **`- Environments: .env.local`** is Next.js confirming it loaded the committed
  `frontend/.env.local`. A clean clone therefore bakes the dead GitHub Codespaces
  host into the build. This is direct evidence for A5/A6.

### 2.7 `npm run lint` — **CANNOT RUN NON-INTERACTIVELY**

```
> next lint
? How would you like to configure ESLint? https://nextjs.org/docs/basic-features/eslint
❯  Strict (recommended)
   Base
   Cancel
```

There is no ESLint configuration in the repo. `npm run lint` drops into an
interactive prompt and will **hang any CI job that calls it**. **New finding, not
in §2.**

### 2.8 Tests — **NONE EXIST**

`find` across the repo (excluding `node_modules`) returns no `test_*.py`,
`*_test.py`, `*.test.ts(x)`, `*.spec.ts(x)`, no `pytest.ini`, no `conftest.py`,
no `jest.config`. Only `scripts/load_test.py`, which is a load generator, not a
test. There is no `.github/` directory (no CI) and no `Makefile` (so `make
doctor` / `make demo` / `make eval`, referenced throughout the contract, do not
exist yet). Confirms A9.

### 2.9 Secret scan of full git history — **CLEAN**

`git grep -E "gsk_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}"` across
`git rev-list --all` returned nothing. The committed `frontend/.env.local`
contains hostnames, not credentials. **No key rotation appears necessary** — but
see A5 for the workspace-identifier leak.

---

## 3 — VERIFICATION OF §2 FINDINGS

### A. Broken / missing files

| # | Finding | Verdict | Evidence |
|---|---|---|---|
| A1 | `frontend/Dockerfile` missing | **CONFIRMED** | Not in file listing; `docker-compose.yml:41-43` builds it |
| A2 | `otel-collector-config.yaml` missing | **CONFIRMED** | Not in file listing; mounted at `docker-compose.yml:65` |
| A3 | `.env.example` missing | **CONFIRMED** | Not in file listing; `README.md` quickstart line 1 is `cp .env.example .env` |
| A4 | No `LICENSE`; README says MIT | **CONFIRMED** | No `LICENSE` file; `README.md` last line: `## License` / `MIT` |
| A5 | `frontend/.env.local` committed with dead Codespaces URLs | **CONFIRMED** | `git ls-files` matches it; contains `https://super-system-jjw7j557w6xrf559g-8001.app.github.dev` ×3 + `-8080` ×1 |
| A6 | Port mismatch 8000/8001 | **CONFIRMED** | README `--port 8001`; compose `8000:8000`; `.env.local` `:8001`; code defaults `http://localhost:8000` |
| A7 | `SECURITY.md` 0 bytes | **CONFIRMED** | `wc -c SECURITY.md` → `0` |
| A8 | `requirements.txt` has UTF-8 BOM | **CONFIRMED — and wider than reported** | BOM (`357 273 277`) on `requirements.txt`, **`groq_client.py`**, and **`.gitignore`** |
| A9 | No test suite | **CONFIRMED** | §2.8 |
| A10 | Dangling comment where log↔trace correlation was meant to be; feature never implemented | **REJECTED — the finding is wrong** | The feature **is** implemented. `backend/main.py:16` calls `LoggingInstrumentor().instrument(set_logging_format=True)`, and `backend/core/telemetry.py:203-213` builds a full OTel logs pipeline (`LoggerProvider` + `BatchLogRecordProcessor` + `OTLPLogExporter` + `LoggingHandler`). The comment at `main.py:13-15` describes working code. **It has never been verified against a live collector**, which is a different (real) problem — but the README claim is backed by code, not by nothing. |
| A11 | `chromadb` + `sentence-transformers` pull multi-GB | **CONFIRMED — 5.4 GiB measured** | §2.2. Both are imported **lazily inside `try/except`** (`rag_store.py:213, 276`) as optional accelerators — the store has a working pure-Python fallback. **They are pinned as hard requirements but are not hard requirements.** Caveat before cutting them: `chromadb` is what transitively supplies `opentelemetry-instrumentation-fastapi`, which `main.py` imports (§2.3). Add both instrumentation packages explicitly **before** removing chromadb. |

### A′. Clean-clone breakers §2 did not find (all new)

| # | Finding | Consequence | Severity |
|---|---|---|---|
| **B1** | **`backend/Dockerfile` copies files that are not in its build context.** Compose sets `context: ./backend`, but the Dockerfile does `COPY requirements.txt .` — and `requirements.txt` lives at the repo **root**. `backend/requirements.txt` does not exist. | `docker compose build backend` fails on the first `COPY`. The backend image has **never** been built successfully. §2 only flagged the *frontend* Dockerfile. | **Critical** |
| **B2** | **`backend/Dockerfile`'s CMD targets the wrong module path.** `CMD uvicorn main:app` with context `./backend` puts `main.py` at `/app/main.py` — but `main.py` imports `from backend.core import telemetry` and `from backend.api.router import router`, and no `backend/` package exists inside the image. `groq_client.py` (root) is also outside the context. | Even if B1 were fixed, the container would `ModuleNotFoundError` on boot. | **Critical** |
| **B3** | **`signoz-system` is an orphaned git submodule.** `git ls-tree -r HEAD` shows `160000 commit de1e21a05052e9527b04a3e3c7afae2fb02597e1 signoz-system` — a gitlink — but **there is no `.gitmodules` file**. | Measured, not inferred (correcting an earlier overstatement in this row that said a recursive clone "errors" — it does not): `git clone --recurse-submodules` exits **0** and leaves `signoz-system/` **empty**, so an ordinary clone succeeds silently. It is the explicit submodule commands that fail: `git submodule update --init` → exit 128, *"fatal: No url found for submodule path 'signoz-system' in .gitmodules"*, and `git submodule status` → exit 128, *"fatal: no submodule mapping found in .gitmodules for path 'signoz-system'"*. So a judge's clean clone is **not** blocked; the cost is an empty directory that looks like missing content, plus two git commands that hard-fail if anyone runs them. | **Low** (downgraded from Critical: a clean clone works) |
| **B4** | **Backend is unimportable without `GROQ_API_KEY`** (`groq_client.py:18` raises at import time). | No import, no test, no typecheck, no CI, no `make doctor`, no boot — without a live paid API key. | **Critical** |
| **B5** | **Two OTel instrumentation packages imported by `main.py` are absent from `requirements.txt`** (`opentelemetry-instrumentation-logging`, `opentelemetry-instrumentation-fastapi`). Only the latter is present, and only as a transitive dep of `chromadb`. | `pip install -r requirements.txt` then `uvicorn backend.main:app` → `ModuleNotFoundError` (reproduced, §2.3). The documented quickstart cannot work. | **Critical** |
| **B6** | **No ESLint config**; `npm run lint` is interactive. | CI hangs. §10's lint gate cannot be met. | **High** |
| **B7** | `docker-compose.yml` declares obsolete `version: "3.9"`. | Warning on every invocation; noise in a judge's terminal. | **Low** |
| **B8** | README's clone URL is `github.com/bichukaleakash809-lang/devguard-ai`; the live repo is `akashbichukale111/devguard-ai`. | The first command in the quickstart 404s. | **High** |
| **B9** | `frontend/tsconfig.json` sets `"target": "es5"` while shipping Next 14 / React 18. | Unnecessarily degraded output; not a blocker, but it is not what the README's "Next.js 14" implies. | **Low** |

### B. The SigNoz / MCP gap

**CONFIRMED, and materially worse than §2.B states.** Three distinct problems:

1. **The transport is invented.** `mcp_client.py:171-174` POSTs to
   `/mcp/tools/call` with `{"tool": ..., "arguments": ...}`. That is not MCP.
   Real MCP is JSON-RPC 2.0. The file's own TODO (lines 10–24) says so.
2. **The default URL points at DevGuard's own backend.**
   `SIGNOZ_MCP_URL = os.environ.get("SIGNOZ_MCP_URL", "http://localhost:8000")`
   (`mcp_client.py:54`) — and `localhost:8000` is the **backend's** port in
   `docker-compose.yml`. Out of the box the "SigNoz MCP client" calls DevGuard
   and gets a 404. It has never spoken to SigNoz.
3. **The fallback lies about its own provenance — this is the LAW 4 breach, and
   it was reproduced at runtime (§2.3b).**
   `get_recent_cost_trend()` catches the failure and returns
   `CostTrend(available=True, ...)` populated from the in-process shadow
   (`mcp_client.py:212-221`). Downstream, `god_mode_orchestrator.py:229-233` does
   `if trend.available: data_source = "live"`. **So the local estimate is
   labelled `live`** — confirmed by
   `docs/audit-evidence/godmode-cost-spike.json`, captured with nothing
   observable running. The one field the whole honesty model depends on is set
   wrong at the source. Note `get_error_rate_detailed` and
   `get_cwe_failure_pattern` do this correctly (`available=False`) — it is
   specifically the cost path that is broken.
4. **A second, independent mislabel in the Executive summary**
   (`god_mode_orchestrator.py:552`): `data_source` is derived from the absence of
   *errors*, not the presence of *real data*, so a run whose every section is
   synthetic is still stamped `live`. Evidence:
   `docs/audit-evidence/godmode-executive.json`.

The README's claim — *"the self-observation layer queries SigNoz's MCP server
directly from agent code"* — is not supported by anything in this repository.

### C. Fabricated UI values

| # | Verdict | Evidence |
|---|---|---|
| C1 | **CONFIRMED** | `frontend/app/page.tsx:485` — `SigNoz Hackathon 2026 · Grand Finalist` |
| C2 | **CONFIRMED — worse than described** | `page.tsx:199` `useState(24059)`; `page.tsx:208` `if (Math.random() < 0.35) setThreats((p) => p + ...)` on a 1s interval. It is not a static invented number, it is a **counter that fakes live activity**. |
| C3 | **CONFIRMED** | `FinOpsPanel.tsx:39` `moneySavedUsd: 1250` |
| C4 | **CONFIRMED** | `ExecutiveCommanderPanel.tsx:48-49` `Cost avoided $1,250`, `Health score 97%`; also `:31` `healthScore: 97` |
| C5 | **CONFIRMED** | `OmniHealPanel.tsx:60-61` `prUrl: "#"`, `prLabel: "View GitHub PR #142"` |
| C6 | **CONFIRMED** | `OmniHealPanel.tsx:50` and `ExecutiveCommanderPanel.tsx:40` `eval_score 92/100`; `page.tsx:197,206-210` synthesises `Global Latency` by random walk between 7 and 28 ms |

**Additional LAW 3 / LAW 6 violations §2.C missed:**

| # | Location | Value | Problem |
|---|---|---|---|
| C7 | `frontend/app/page.tsx:231` | `OTel Mesh Connected` + animated green pulse | Asserts a live connection that is never checked. It is hard-coded chrome. |
| C8 | `frontend/app/page.tsx:492` (`<ShieldCheck /> Live`) | `Live` pill | Same — a status badge with no status behind it. |
| C9 | `DEMO_SCRIPT.md:45` | `benchmark accuracy strip (92% / 88% / 95% / 5% FPR)` | Hand-typed benchmark figures. `backend/core/benchmark.py` is a genuine harness with a negative control, but **it has never been run to an artifact** — no `timings.json`, no benchmark report exists anywhere on disk, and no endpoint exposes it. LAW 6 violation. |
| C10 | `README.md` (problem statement) and `DEMO_SCRIPT.md:15` | `$85/hour of engineer time` | Unsourced external figure presented as fact. |
| C11 | `README.md` SigNoz Usage §, "Alerts" | `signoz/alerts.md`: SLO degradation, breaker stuck open, cost budget exceeded | Presented as shipped alerts. `signoz/alerts.md` **itself honestly states** the backing metrics do not exist yet ("Metric assumption: `devguard_slo_compliance_pct` … a few lines added to `telemetry.py`, **not shown here**"). The file is honest; the README's summary of it is not. |
| C12 | `README.md` Architecture table | `Python 3.12` | Both Dockerfile stages are `python:3.11-slim`. |

### D. The Nexus "live" gap — **CONFIRMED, and the diagnosis in §2.D is out of date and understates the problem**

§2.D says *"The API response is never passed into them."* **That is no longer
true** — `frontend/app/nexus/page.tsx:263-307` passes `data={results.X.data}` into
all five panels. The wiring exists. The problem has moved, and it is worse:

**D1 — The panels merge real data *over* fabricated defaults.**
Every panel does the identical thing:

```tsx
export default function FinOpsPanel({ data }: { data?: Partial<FinOpsData> }) {
  const d = useMemo(() => ({ ...DEFAULT_DATA, ...data }), [data]);
```
(`FinOpsPanel.tsx:229-230`, and identically at `OmniHealPanel.tsx:239-240`,
`PreCogPanel.tsx:280-281`, `LLMJudgePanel.tsx:258-259`,
`ExecutiveCommanderPanel.tsx:334-335`.)

This is exactly the pattern §5.1 forbids: *"never fall back to the pretty default
and never interpolate."* Any field absent from the response silently renders the
invented value instead of `N/A`.

**D2 — And essentially every field is absent, because the key namespaces do not
intersect.** The backend returns snake_case keys; the panels type camelCase keys:

| Backend returns (`god_mode_orchestrator.py`) | Panel expects |
|---|---|
| `original_code`, `patched_code`, `diff_summary`, `eval_score`, `data_source`, `reflection_attempts` | `originalCode`, `fixedCode`, `traceSpans`, `thinkingLines`, `prUrl`, `prLabel`, `cweId` |
| `spend_usd_per_30min`, `budget_usd_per_30min`, `data_source` | `costSeries`, `spikeUsd`, `normalUsd`, `budgetUsd`, `moneySavedUsd`, `costReductionPct` |

**There is no overlapping key.** The spread therefore overwrites nothing the UI
renders. **After a real backend call, every number visible in every Nexus panel is
still the fabricated constant** — `$1,250 saved`, `97% health`, `PR #142`,
`92/100`, `420/180/310 ms`. The run genuinely happened; the screen does not show
it. This is the single most damaging finding in the repository, because it looks
live and is not.

**D3 — Nexus never invokes the real pipeline anyway. Confirmed at runtime.**
`nexus/page.tsx:202` sends `body: JSON.stringify({})`. `execute_omni_heal(code=None)`
skips the `if code:` branch entirely (`god_mode_orchestrator.py:150`) and returns
the `data_source: "synthetic"` payload; `execute_llm_judge` behaves the same way.
POSTing that exact body returned `"data_source":"synthetic"`
(`docs/audit-evidence/godmode-error.json`). So of the five "agents", **two are
hard-wired to the synthetic branch and can never run live from this UI**, and the
other two (`finops`, `precog`) resolve through the MCP client that mislabels its
fallback as `live` (§3.B.3) — also reproduced. **Not one of the five panels can
currently display a genuinely live number.**

**D4 — The panels accept only `data`.** `page.tsx` passes `result`, `status`,
`error`, `elapsedMs` and `onRunSingle` to every panel; every panel's signature is
`({ data })`. All five extra props are silently discarded — which is also the
proximate cause of the five TS errors in §2.5. Consequently there is **no error
state, no elapsed timer, and no `LIVE`/`SIMULATED` badge anywhere in Nexus**,
despite the backend already returning `data_source` on every response.

---

## 4 — WHAT WORKS

Genuinely good, and covered by LAW 1 — preserve it:

- **The agent pipeline core.** `ai_agent.py` (744 LOC) implements a real
  Scanner → Fixer → Validator reflection loop with bounded retries
  (`MAX_REFLECTION_RETRIES`), an `EVAL_PASS_THRESHOLD` gate, and full reflection
  history retained. Not a single prompt call wearing a job title.
- **Typed contracts throughout.** `schemas.py` (317 LOC) is strict Pydantic at
  every agent boundary — `eval_score` bounded `ge=0, le=100`, `verdict` as an
  enum, deliberately separated from the score with a documented rationale. No
  regex parsing of model output anywhere.
- **The telemetry layer is real and well built.** `telemetry.py` (683 LOC) sets
  up traces, metrics **and** logs with correct OTLP exporters, a proper
  `Resource`, W3C context propagation (`inject`/`extract`), and a genuine
  log↔trace bridge. This is the strongest file in the repo. It has simply never
  been pointed at a running collector.
- **Resilience.** `resilience.py` (454 LOC) — circuit breaker with state
  transitions and a postmortem hook on open.
- **The hash-chained audit trail is real.** `audit.py` + `data/audit_log.jsonl`
  — 35 entries with genuine `prev_hash` → `entry_hash` chaining, and a
  `/audit-log/verify` endpoint that actually re-verifies the chain.
- **The benchmark harness is honest engineering.** `benchmark.py` includes an
  explicit **negative control** (`clean_parameterized`, `expected_cwes: set()`)
  with a comment explaining why FP rate is meaningless without one. This is
  exactly the instinct §9B wants — it has just never been run.
- **The backend's `data_source` discipline is mostly right.**
  `god_mode_orchestrator.py` labels every response `live` / `synthetic` /
  `partial` and degrades rather than 500-ing. The design is correct; one path
  (cost) sets the label wrongly, and the frontend ignores the field entirely.
- **`local_telemetry.py` is honest about being an estimate** — the cost heuristic
  (`chars/4`) is documented as an approximation in the module docstring.
- **RAG store degrades properly.** `rag_store.py` treats chromadb and
  sentence-transformers as optional accelerators behind `try/except` with a
  working pure-Python fallback.
- **`signoz/alerts.md` is more honest than the README about it.** It explicitly
  flags that the metrics it alerts on are not yet emitted.
- **The Nexus concurrency claim is true.** `Promise.all` at
  `nexus/page.tsx:237` really does fire all five module calls in one tick, with
  real per-module `performance.now()` elapsed tracking.
- **Frontend compiles.** `✓ Compiled successfully` — the build only fails at the
  typecheck step, on five errors with one shared root cause.

---

## 5 — WHAT IS SIMULATED BUT HONEST

Keep these; they need a **label**, not deletion:

- `god_mode_orchestrator.py`'s synthetic branches — they return
  `data_source: "synthetic"` and say so. Honest at the API boundary; the
  dishonesty is added by the frontend.
- `local_telemetry.py`'s cost shadow — an estimate, documented as one.
- `rag_store.py`'s fallback path.
- `signoz/alerts.md`'s stated metric assumptions.

## 5b — WHAT IS FABRICATED

C1–C12 above, plus D1/D2 (the merge-over-defaults pattern, which fabricates by
construction rather than by a literal). Nothing in this list is defensible under
LAW 3; all of it is T1a scope.

---

## 6 — WHAT SHOULD BE CUT (LAW 2 — criterion or cut)

| Item | Recommendation | Reason |
|---|---|---|
| `chromadb`, `sentence-transformers` in `requirements.txt` | **Cut** | Optional accelerators behind `try/except`; > 1 GiB of torch for a path a judge will never exercise. Raises no criterion; actively harms Technical Execution by making install brutal. |
| `casting.yaml` / `casting.yaml.lock` / `pours/` (SigNoz Foundry) | **Cut or demote** | The README makes `foundryctl cast` a *required* quickstart step for a binary that a judge will not have. §6.1 already permits choosing "the lightest path that works" and prefers plain docker-compose. Foundry raises no criterion and adds a hard dependency to the first five minutes. |
| `signoz-system` gitlink | **Cut** | An orphaned submodule pointer that references nothing. It does not break a clean clone (measured: exit 0, empty directory — see B3), so this is tidiness rather than a blocker. Deletion needs approval per contract §6; tracked as HANDOFF open issue 5. |
| `scripts/load_test.py` | **Keep, deprioritise** | Harmless; not evidence of anything judged. |
| The `Threats Blocked` / `Global Latency` ticker | **Cut entirely** | LAW 3. §7.4 already specifies the honest replacement (real status bar). |
| The god-mode *simulator* framing | **Keep the endpoints, re-aim them** | The orchestrator is the right shape. What must go is the frontend's synthetic-by-default wiring (D3). |

---

## 7 — CONTRACT ITEMS I WOULD ARGUE SHOULD CHANGE

Offered as recommendations under §21.7 / §14.6. **No action taken.**

1. **§2's provenance is broken and it caused a real error.** The master prompt
   says it audited commit `9651db3`; that SHA is not in this repo's history
   (`git log` runs `93ddb5c … 3f590b1`). §2.D — the item the document calls
   *"the single highest-leverage fix"* — is **factually out of date**: the data
   *is* passed to the panels. Following §2 literally would have produced the
   wrong fix. Recommend §2 be replaced wholesale by §3 of this file, and that
   §2.D's remedy be re-specified as *"remove the `{...DEFAULT_DATA, ...data}`
   merge and add a mapping layer"* rather than *"pass the data in."*

2. **The environment invalidates the D0/D1 calendar as written.** §14 assumes
   DataHub Core is up on D0 and a full write-back smoke test lands on D1. There
   is **no Docker daemon here at all**. Until the human resolves §1's (a)/(b)/(c),
   T2 and T6 cannot start, and no amount of care in T1 changes that. This should
   be the first decision made after this report.

3. **Sequence T1b before T1a.** The contract runs the honesty pass (T1a) first.
   But the frontend does not currently build, and B4/B5 mean the backend cannot
   even be imported to check whether a change broke it. §3's "definition of
   verified" (build passes; behaviour executed; no regression) is
   **unsatisfiable for T1a** in the current state. Recommend a minimal T1b-first
   slice — fix B4, B5, the TS errors, and add `.env.example` — so that T1a's
   changes can actually be verified rather than asserted. This is not
   re-litigating a decision; it is that the stated gate cannot be met in the
   given order.

4. **The roster count is inconsistent inside the contract itself.**
   `03_CORE_CONTRACT.md` §5 numbers **12** agents (1–12, with `auditor`/Commander
   as #12). `02_ADDENDUM.md` Part D numbers **11** and renders `auditor` as `—`,
   then instructs *"The status bar reports `11 registered`."* §6 of the master
   prompt lists a different set again (including `Surgeon`, which appears nowhere
   in the other two rosters, while `Strategist` and `Patchsmith` appear nowhere
   in §6). Since the contract's own rule is *"one count, stated identically"*,
   **this must be resolved by the human before any UI renders a number.** My
   recommendation: 12 including Commander, and say "12 registered".

5. **LAW 4 needs a third category, or `data_source` needs a third value.** The
   contract insists every number is either live or `SIMULATED`. The cost path is
   genuinely neither: it is a *real measurement of this session* computed by a
   *documented heuristic* rather than retrieved from SigNoz. Forcing it into
   "live" is what produced the §3.B.3 bug. Recommend `data_source` become
   `live | local_shadow | synthetic`, with `local_shadow` badged distinctly
   (e.g. amber `LOCAL`). This makes the honest thing easy to render and removes
   the incentive that caused the mislabel.

6. **Minor: the flagship name.** §1 asks for a decision. My recommendation is
   **DevGuard Lineage Guard** — it names the DataHub-facing job in two words to a
   judge who reads nothing else, and it does not collide with "Enterprise", which
   currently reads as a pricing tier rather than a product. Flagged for the human;
   **not locked**, since §1 makes this a human decision.

---

## 8 — TOP FIVE RISKS

| # | Risk | Why it is top-five | Mitigation |
|---|---|---|---|
| 1 | **No Docker daemon, and the machine is under-specced for the target stack.** | It blocks T2, T6, every write-back gate, and `make demo` — i.e. Criterion #1 in its entirety. Nothing else on this list matters if this is not solved. | Decide §1 (a)/(b)/(c) **now**. Option (b) — never co-run — is free and satisfies the evidence gates. |
| 2 | **The product looks live and is not (D1/D2/D3).** | A judge who runs Nexus sees `$1,250 saved` and `PR #142` after a real call. If that is noticed, it costs more than the whole module is worth, and it is exactly the "does the code do what the submission claims" rubric line. | T1a + a real mapping layer. Delete `DEFAULT_DATA` merging; render `N/A`. |
| 3 | **Clean clone does not work — at five independent points** (B1, B2, B3, B4, B5, plus A1/A2/A3 and B8). | "Reproducible from a clean clone" is Technical Execution's whole definition, and it is the first thing a judge does. Today: the clone warns, the install is >1 GiB, the backend will not import, the frontend will not build, and neither image will build. | T1b, and then actually test it in a fresh container. |
| 4 | **The headline differentiator has never executed** (§3.B). | The README's central claim — agents query SigNoz via MCP — is unsupported by the code, which points at DevGuard's own port over an invented transport. Discovery by a judge is a credibility event, not a bug report. | §6.5's fork: prove one real round trip, **or** rewrite the claim. The rewritten claim is still genuinely interesting. |
| 5 | **Zero tests, no CI, and a codebase that cannot be imported to test.** | 5,039 LOC of backend with no test can regress silently, and B4 means even writing the first test requires a paid API key. Compounds every track after this one. | Fix B4 (lazy client init) *first*, then pipeline contract tests, then CI. |

---

## 9 — REQUIRED FIXES (ordered; T1a/T1b scope, not executed)

**Blockers — nothing can be verified until these land:**

1. **B4** — make the Groq client lazy. Move construction behind a function so
   importing the backend does not require a secret.
2. **B5** — add `opentelemetry-instrumentation-fastapi` and
   `opentelemetry-instrumentation-logging` to `requirements.txt` (pinned).
3. **Frontend typecheck** — fix the five TS2322 errors. The correct fix is not a
   cast; it is D1/D4 (panels take the real props, no default merging).
4. **B3** — remove the `signoz-system` gitlink. *(Deprioritised: a clean clone
   works, so this is cosmetic. Needs approval — contract §6 forbids deleting
   files unasked.)*
5. **B1/B2** — rebuild `backend/Dockerfile` against the repo root as context, or
   move `requirements.txt` + `groq_client.py` into `backend/`. Fix the CMD to
   `backend.main:app`.
6. **A1** — create `frontend/Dockerfile`.
7. **A3** — create `.env.example` (root) and `frontend/.env.example`.
8. **A5** — `git rm --cached frontend/.env.local`, add to `.gitignore`.
9. **A8** — strip the BOM from `requirements.txt`, `groq_client.py`, `.gitignore`.
10. **A4** — add the Apache-2.0 `LICENSE`, and correct the README.
11. **B6** — add an ESLint config so `npm run lint` is non-interactive.
12. **A2** — create `otel-collector-config.yaml`.
13. **A6/B8** — unify on one port; fix the README clone URL.

**Honesty pass (T1a):**

14. Delete C1, C2, C6's latency ticker, C7, C8 from `page.tsx`.
15. Delete C3, C4, C5 and every `DEFAULT_DATA` numeric from the five panels.
16. Remove `{...DEFAULT_DATA, ...data}` in all five panels; render `N/A`.
17. Surface `data_source` as a `LIVE` / `SIMULATED` badge on every panel.
18. Fix the `available=True` mislabel at `mcp_client.py:212-221` (see §7.5).
19. Correct C9–C12 in `README.md` / `DEMO_SCRIPT.md`.
20. Fill `SECURITY.md` (A7).

**Deferred to their own tracks:** the mapping layer and streaming (T4), SigNoz
end-to-end (T2), tests + CI (T7).

---

## 10 — DEFINITION-OF-VERIFIED STATUS FOR T0

Per `03_CORE_CONTRACT.md` §3, stated plainly:

| # | Condition | Status |
|---|---|---|
| 1 | Build passes | **RED** — frontend typecheck fails (5 errors); backend cannot be imported (B4/B5) |
| 2 | Tests for the touched area pass | **N/A** — no tests exist; T0 touched no implementation code |
| 3 | Behaviour executed, real output in the report | **GREEN** — every command in §2 was executed and its real output pasted, including a backend boot and six live endpoint calls (§2.3b). **No live LLM scan was executed** (no Groq key) and **no container was built or run** (no Docker daemon); both stated rather than papered over. |
| 4 | No previously working screen or endpoint regressed | **GREEN** — no implementation file was modified. The only additions are `docs/AUDIT.md`, `docs/HANDOFF.md`, `docs/audit-evidence/`, and the `DISCLOSURE.md` draft. |
| 5 | An artifact exists on disk | **GREEN** — `docs/audit-evidence/` holds six raw JSON responses, the backend boot log, and the full frontend typecheck/build output, all third-party inspectable. |

**T0 is complete as an audit.** The repository it audits is **not** in a verified
state, and this document does not claim otherwise.
