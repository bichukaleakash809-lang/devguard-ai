# Security

DevGuard is a privileged actor: it reads untrusted code, calls an external LLM,
and writes an audit trail. This file states what is actually true today. Where a
control is designed but not yet implemented, it says so rather than implying
coverage that does not exist.

## Reporting a vulnerability

Open a GitHub issue, or contact the maintainer directly for anything you believe
should not be public first. There is no SLA on this project — it is a hackathon
build, not a supported product.

## Supported versions

Only `main`. There are no released versions and no backported fixes.

## What is implemented today

- **Secrets are never committed.** `GROQ_API_KEY` is read from the environment
  only. `.env` and `.env.local` are git-ignored; `.env.example` documents the
  contract without carrying values. The full git history has been scanned for
  credential patterns (`gsk_*`, `sk-*`, `AKIA*`) and is clean.
- **The backend boots without a key.** No secret is required to import or start
  the application, so a reviewer never has to supply one to inspect it.
- **Tamper-evident audit trail.** Every scan appends a hash-chained record
  (`backend/core/audit.py`); `GET /audit-log/verify` re-verifies the chain and
  reports the first break if there is one. The record carries the pipeline's
  real decision — `pass`, `fail`, `no_findings` or `unvalidated`. Until recently
  it did not: the verdict was read off a field `PipelineResult` does not have, so
  **all 35 entries committed in this repository record `"unknown"`**. Those
  entries are deliberately not rewritten; editing a hash-chained audit log to
  look better is the act the chain exists to detect.
- **Human-in-the-loop approval gate.** Critical and high severity findings pause
  for an explicit `/approve` or `/reject` before the audit entry is written. The
  gate reads the Scanner's finding, not the request, so a caller cannot supply a
  low severity to bypass review — and an unrecognised severity gates rather than
  passing. This control **never fired before**: it read `severity` off
  `ScanRequest`, which has only `code` and `language`, so every scan
  auto-finalized. Asserted by `tests/test_approval_gate.py`.
- **Bounded agent loop.** Reflection retries are capped
  (`MAX_REFLECTION_RETRIES`); a circuit breaker (`backend/core/resilience.py`)
  opens on repeated upstream failure rather than retrying without limit.
- **Fail-safe telemetry.** Observability is never load-bearing: if the collector
  or the MCP path is unreachable, scans proceed unchanged.
- **Honest provenance.** Every god-mode response carries a `data_source` of
  `live`, `local_shadow`, `synthetic` or `partial`, and the UI renders it. An
  in-process estimate is never presented as retrieved telemetry.

## What is regression-protected

301 tests run on every push in CI, with no API key, no collector and no network
(`.github/workflows/ci.yml`). They cover the typed agent boundaries, the audit
chain's tamper detection, the circuit-breaker state machine, telemetry
fail-safety, the untrusted-content boundary above, and the `/scan` response
contract — including that no published number is a hard-coded constant, that the
audit-chain badge cannot claim a verified chain for an entry that has not been
written, and that a model cannot author DevGuard's own measurements
(`tokens_used`, `model_used`) through its JSON output. CI also runs a real OTLP
export verification and the secret scan. So the properties claimed in this file
are checked mechanically rather than asserted once.

## Known weaknesses — not yet fixed

These are real and should be treated as open:

- **CORS is wide open.** `backend/main.py` sets `allow_origins=["*"]`. Acceptable
  for local use; it must be an explicit allowlist before any public deployment.
- **No authentication on any endpoint.** Anyone who can reach the backend can
  submit a scan, read the audit log, and approve or reject a gated fix. Do not
  expose this to the internet as-is.
- **No rate limiting.** `POST /scan` forwards code to a paid LLM API with no
  per-caller quota, so an open instance is a cost-exhaustion target. A single
  request's blast radius is bounded (see below) but the request *rate* is not.

  This bullet previously also claimed there was **no request size cap**. That was
  wrong: `ScanRequest.code` carries `max_length=50_000`, enforced by Pydantic
  before any LLM call. Verified against a running server — 50,001 characters
  returns **HTTP 422**, and the rejection happens at the schema boundary, so an
  oversized payload never reaches a paid API or trips the circuit breaker.
  Evidence: `docs/audit-evidence/t2/live-degradation-and-size-cap.txt`. Note the
  cap is on the `code` field, not on total body bytes.
- **Submitted code is sent to a third party.** Anything pasted into the Scanner
  is transmitted to Groq. Do not submit proprietary or sensitive source.
- **Prompt injection is mitigated, not solved.** Code under review is untrusted
  input that reaches the model. There is now an explicit boundary at every agent
  prompt: each system prompt carries `UNTRUSTED_CONTENT_RULE` declaring fenced
  content to be data rather than instruction, and `fence_untrusted()` wraps that
  content in sentinel markers (rather than a ``` block, which untrusted code can
  close early to break out). The Fixer's own free-text output is fenced too,
  since it is model-generated from untrusted input and inherits that taint.
  Asserted by `tests/test_prompt_injection_boundary.py`.

  **This raises the cost of an injection; it does not make one impossible.** No
  prompt-level defence does. The residual risk is a false negative — an attacker
  talking the Scanner out of reporting a finding — and it is not eliminated.
  A determined attacker with knowledge of the prompt may still succeed.
- **Docker images do not build**, so the non-root user and reduced attack surface
  described in `backend/Dockerfile` are not in effect anywhere. Blocked on
  container-registry access; see `docs/audit-evidence/t2/registry-egress-block.txt`.
- **14 open advisories in the frontend dependency tree** (12 high, 2 moderate),
  down from 18 after the approved `next` 14 → 16 upgrade. **None of them is in
  Next.js's own code any more.** `next` carried **21 distinct advisories** at
  14.2.35 — the latest 14.x, so there was no in-range fix — and now carries
  **zero**; it appears in the report only because of packages below it in the
  tree. Evidence, including the full list of 21 and the measured proof that the
  app behaves identically: `docs/audit-evidence/t2/dep-step3-nextjs.txt`.

  What remains, triaged rather than counted:

  - **`sharp` <0.35.0 (high, 4 inherited libvips CVEs).** This is a **new
    exposure that the upgrade introduced** — Next 16 depends on `sharp` for
    image optimization where Next 14 used a bundled wasm path. There is no
    in-range fix (`npm audit fix --force` "resolves" it by downgrading `next` to
    9.3.3). It is not invoked here: the app renders no `next/image` and no remote
    images, so the optimizer never processes one. That is a fact about this
    app's current shape, not a clean bill of health for `sharp` — adding a single
    `next/image` would make it reachable.
  - **Nine ESLint-toolchain packages (high).** `eslint`, `eslint-config-next`,
    `eslint-plugin-*`, `minimatch`, `brace-expansion`, `@eslint/*` — a
    brace-expansion DoS reached through glob matching. These were **already
    present before the upgrade** and are lint-time only; none reaches shipped
    code.
  - **`postcss` <=8.5.17 (high, 3 advisories), nested inside `next`.** Needs
    attacker-controlled CSS *source* at build time. The app's own top-level
    `postcss` (8.5.19) is patched.
  - **`monaco-editor` → `dompurify` (moderate).** Pre-existing, editor-only.

  `npm audit fix` without `--force` now clears nothing further, so 14 is the
  floor without another breaking change.

  Earlier per-advisory reasoning for the Next 14 tree is retained in
  `docs/audit-evidence/t2/frontend-dependency-advisories.txt`.

- **Seven ESLint findings are demoted to warnings**, not fixed. The ESLint 9
  flat-config migration that `next@16` forced brought much newer
  `eslint-plugin-react-hooks` and `@next/eslint-plugin-next` rule sets, and four
  rules that did not exist under the old config now fire on pre-existing code:
  `react-hooks/set-state-in-effect` (×4), `react-hooks/refs`,
  `react-hooks/immutability`, and `@next/next/no-html-link-for-pages`. They are
  demoted rather than suppressed — no `eslint-disable` anywhere, still printed on
  every lint run and in CI output — with the reasoning in
  `frontend/eslint.config.mjs`. Two are genuine minor defects that predate all of
  this: a bare `<a href="/">` to an internal route (full page reload instead of
  client-side navigation) and a ref assigned during render.

## Dependencies

Pinned in `requirements.txt` and `frontend/package-lock.json`. `chromadb` and
`sentence-transformers` pull a very large transitive tree (~5.4 GiB including
CUDA); both are optional accelerators behind `try/except` in
`backend/core/rag_store.py`, and removing them is under consideration.

**Secret scanning runs in CI** on every push (`.github/workflows/ci.yml`): the
full git history is scanned for `gsk_*`, `sk-*`, `AKIA*` and PEM private-key
patterns, and the job fails if `.env` or `frontend/.env.local` is ever tracked
again.

**Dependency scanning also runs in CI** on every push — `pip-audit` against
`requirements.txt` and `npm audit` against `frontend/package-lock.json`, with
both reports uploaded as build artifacts. It is deliberately **report-only and
does not gate the build**: both trees still carry known advisories with no
in-range fix even after the three approved upgrades (`sharp` and the ESLint
toolchain on the frontend; `transformers` via the unimportable
`sentence-transformers` on the backend), so gating would leave CI red with no
code change available to fix it, and would go red again on any upstream
publication against a pinned version. **Do not read a green tick on that job as
"no advisories" — read the report.**

### Python dependency advisories — 56 → 8, and the rest triaged

`requirements.txt` had never been audited. `pip-audit` reported **56 known
vulnerabilities in 7 packages**. **Now 8 in 4**, after two approved changes:
removing a redundant `aiohttp` pin, then moving FastAPI/Starlette to a patched
pairing. Triaged per advisory against this codebase rather than reported as a
count:

| Package | Pinned | Advisories | Reachable here? |
|---|---|---|---|
| ~~`aiohttp`~~ | *unpinned* | ~~30~~ **0** | **Fixed.** The pin could never have removed the package — it arrives transitively via `chromadb → kubernetes → aiohttp<4.0.0,>=3.9.0`. All the pin did was hold a dependency nothing imports at the *oldest* version in that range. Dropping it lets the resolver pick **3.14.3**, above every fix version. Evidence: `docs/audit-evidence/t2/dep-step1-aiohttp.txt` |
| ~~`starlette`~~ | **1.3.1** | ~~7 unique~~ **0** | **Fixed.** 1.3.1 is the lowest version clearing all seven — PYSEC-2026-249 is fixed only there. Reaching it required `fastapi` 0.104.1 → **0.136.0**, and *not* the latest 0.141.1: that introduces `_IncludedRouter` in `app.routes`, which the pinned `opentelemetry-instrumentation-fastapi==0.41b0` crashes on — measured as **HTTP 500 on every request**. 0.136.0 is the newest release without it that still allows starlette unbounded. `starlette` is now pinned explicitly, because 0.136.0 asks only for `>=0.46.0` and the package carrying the advisories must not drift. Evidence: `docs/audit-evidence/t2/dep-step2-fastapi-starlette.txt` |
| `transformers` | 4.57.6 | 5 | **No** — arrives via `sentence-transformers`, which is itself unimportable |
| ~~`fastapi`~~ | **0.136.0** | ~~1~~ **0** | **Fixed** by the same bump. (The advisory was the `python-multipart` ReDoS, and that package is not installed here anyway.) |
| `protobuf` | 4.25.9 | 1 | **No** — `json_format.ParseDict` is never called |
| `python-dotenv` | 1.0.0 | 1 | **No** — `set_key`/`unset_key` are never called |
| `pytest` | 8.4.2 | 1 | **No** — test-only, not shipped |

Reachability was established from the code, not assumed: the runtime import graph
(measured by importing the real app and inspecting `sys.modules`) shows
`aiohttp`, `transformers`, `torch`, `chromadb`, `sentence_transformers` and
`multipart` are **never loaded** — 35 of the 56 sit in code that does not run.
For Starlette, the three multipart advisories need form parsing that this
JSON-only API cannot perform (`python-multipart` is absent, no route declares
`Form`/`File`/`UploadFile`); `StaticFiles` is never mounted; no `HTTPEndpoint`
subclass exists; and nothing reads `request.url`.

**Stated carefully:** every one is unreachable *given the code as it stands
today*. That is a fact about this application's current shape, not a clean bill of
health for the dependencies. The `starlette` `request.url` pair
(PYSEC-2026-161, PYSEC-2026-248) is the most likely to become reachable — any
future route that reconstructs a URL from the request would light it up.

**Nothing has been changed** (contract §13.1: no dependency changes without
explicit approval). Recommended order when approved: drop `aiohttp` (30
advisories, zero functionality), then bump `starlette` via a compatible
`fastapi`, then resolve `chromadb`/`sentence-transformers`. Full per-advisory
reasoning and raw output:
`docs/audit-evidence/t2/python-dependency-advisories.txt`.
