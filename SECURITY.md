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

---

# DevGuard V2 — the DataHub agent posture (05_DATAHUB_MASTER §11)

Everything above concerns the T-track scanner. This section covers the V2 agent
that reads a shared catalog and writes back to it — a different threat surface,
because the untrusted input is *metadata other people wrote* and the privileged
action is *mutating a shared catalog*.

Every claim below names the command that verifies it.

## 1. Threat model (§11.1)

| # | Threat | Realistic path | Control | Verified by |
|---|---|---|---|---|
| T1 | **Prompt injection via catalog free-text** | Anyone with catalog write access edits a dataset/column description, glossary term or Context Document, and the text reaches an agent's prompt | Screened and fenced as `UNTRUSTED_TEXT`; the agent that reads it holds **zero tools** | `scripts/run_injection_demo.py` (live) · `tests/test_sentinel_fencing.py` · `tests/test_diagnostician_refusal.py` |
| T2 | **Over-broad mutation** | A bug or a manipulated agent writes to assets it was never meant to touch, or deletes one | Three-axis allowlist (tools, entity types, exact URNs) enforced *before* any I/O, plus a server-side Access Policy | `scripts/verify_least_privilege.py` (live) · `tests/test_security_posture.py` |
| T3 | **Runaway autonomy** | A fix is applied nobody approved, or knowledge is written about a fix that did not work | `AUTONOMY_POLICY` — nothing is autonomous, CRITICAL has no approver; write-back refuses without a verified recovery **and** a named approver | `tests/test_writeback_rules.py` · `evidence/proof-pack/d6-fail-the-fix/` (zero artifacts written) |
| T4 | **Token leakage** | A GMS or LLM token reaches a log, an evidence file, or a commit | Redaction at capture time; tokens read from a file outside the repo; secret scan over working tree and full history | `tests/test_proof_pack_redaction.py` · `make scan-secrets` |
| T5 | **MCP server supply chain** | `uvx mcp-server-datahub` runs third-party code with a live token piped to it | Pinned version (`versions.env`); mutation tools gated off unless explicitly enabled; the client speaks exactly three JSON-RPC methods | `backend/v2/datahub_client.py` · `tests/test_agent_allowlists.py` |
| T6 | **Escalation of its own grants** | The agent creates a policy granting itself more | `MANAGE_POLICIES` never granted; verified as a live DENY | `scripts/verify_least_privilege.py` |

## 2. Untrusted-content boundary (§11.2)

All catalog free-text is `UNTRUSTED_TEXT` by construction — the `Evidence` model
refuses to let a `DATAHUB_DOCUMENT` item claim `TRUSTED_SYSTEM`. The only
prompt-ready representation is `ScreenedText.fenced`; there is no accessor
returning the raw string for prompt use.

**The defence is architectural, not textual.** Detection is a signal; what makes
an injection harmless is that the Diagnostician holds no tools and cannot obtain
any — its constructor takes no client and the module never imports one (asserted
by AST, not string match).

Measured live against the real catalog (§11.7, `scripts/run_injection_demo.py`):

```
Sentinel verdict           : LIKELY
  override-previous, role-reassignment, action-directive,
  suppress-findings, exfiltration, tool-naming
untrusted evidence fenced  : True
raw payload in the prompt  : False      <- stronger than fenced
instruction obeyed         : False
  certified tag applied    : False
  mutating tool calls      : 0 of 2 total
```

The payload never reaches the reasoning prompt at all: evidence claims are
one-line summaries, so the attacker's text stays in the proof pack as a subject
of analysis rather than an input to it. The hostile description is reverted at
the end of the run.

## 3. Mutation allowlist (§11.3)

Three axes, all enforced in `DataHubMCPClient.call` **before** the request is
written to the pipe.

| axis | value | where |
|---|---|---|
| tools | `add_tags`, `update_description`, `save_document`, `add_structured_properties`, `add_owners` — held by **Scribe only** | `AGENT_TOOL_ALLOWLISTS` |
| entity types | `dataset`, `document` | `MUTABLE_ENTITY_TYPES` |
| scope | five named dataset URNs | `MUTATION_SCOPE_URNS` |

Reads are deliberately unrestricted: the blast radius of reading a dataset
DevGuard does not own is nil, and narrowing reads would break lineage traversal.

This duplicates the server-side Access Policy on purpose, and in D9 that stopped
being theoretical — see §4.

## 4. Least privilege (§11.4)

Service account **`urn:li:corpuser:devguard_agent`**
(`scripts/setup_service_account.py`), replacing `urn:li:corpuser:__datahub_system`,
which D1–D8 used and which holds `manageIngestion` and `managePolicies`.

| §8 artifact | privilege required |
|---|---|
| read: search, lineage, schema, queries | `VIEW_ENTITY_PAGE` |
| 1 — incident raised and resolved | `EDIT_ENTITY_INCIDENTS` |
| 2 — post-mortem runbook | `MANAGE_DOCUMENTS` (platform) |
| 3 — column-level tag | `EDIT_DATASET_COL_TAGS` |
| 3 — column-level description | `EDIT_DATASET_COL_DESCRIPTION` |
| 4 — structured properties | `EDIT_ENTITY_PROPERTIES` |
| 5 — ownership | `EDIT_ENTITY_OWNERS` |

Scoped to **five named dataset URNs**, not a domain. §11.4 says "scoped to one
domain"; this substrate has none, and inventing one purely to satisfy the wording
would scope the policy to a container existing only for the policy. A URN
allowlist is strictly narrower — a domain grants access to whatever is later
added to it.

**Never granted, each verified as a live DENY:** `DELETE_ENTITY`, `EDIT_LINEAGE`,
`EDIT_ENTITY_STATUS`, `MANAGE_POLICIES`, `MANAGE_INGESTION`,
`EDIT_ENTITY_GLOSSARY_TERMS`, `EDIT_DOMAINS_PRIVILEGE`.

```
$ python scripts/verify_least_privilege.py
ALLOW: 4/4 behaved as required
DENY : 5/5 correctly refused
```

**That script is why this section is trustworthy.** On its first run the account
passed all four ALLOW cases *and all five DENY cases also succeeded* — a failed
verification in which nothing errored. The cause: the DataHub quickstart ships
with **`METADATA_SERVICE_AUTH_ENABLED=false`**, under which Access Policies are
not enforced at all. For the whole of D1–D8 the server-side control was silently
absent. Enabling it is now a documented prerequisite.

## 5. Autonomy policy (§11.5)

`AUTONOMY_POLICY` in `backend/v2/agents/magistrate.py` is the same object the
docs render and the code branches on, so published and enforced cannot drift.

| risk | allowed action | who approves |
|---|---|---|
| LOW | propose + validate; apply only after approval | asset owner from the graph |
| MEDIUM | propose + validate; apply only after approval | asset owner from the graph |
| HIGH | propose + validate; apply only after approval | asset owner (always named) |
| CRITICAL | nothing applied; recorded and escalated | **nobody — no approval path exists** |

**Nothing is autonomous in this build**, asserted by a module-level `assert`.
`ApprovalRequest.approve()` raises `PermissionError` for CRITICAL, so no identity
can authorise destructive DDL, a data mutation, a permission change or a
hard-coded credential.

## 6. Auditability (§11.6)

Every tool call, prompt, decision and write lands in
`evidence/proof-pack/<run-id>/` with the evidence chain that justified it and the
approver's identity. `AgentHandoff` records `from_agent`, `to_agent`,
`evidence_ids`, `decision`, measured duration, tokens and model. Every write-back
artifact carries the §8 stamp with evidence ids and the chain digest.

## 7. Secret hygiene (§11.8)

* **Redaction at capture time** — `backend/v2/proofpack.py` is the only writer
  into `evidence/`, and it redacts bearer tokens, JWTs, API-key shapes,
  `*_TOKEN`/`*_SECRET`/`*_PASSWORD` assignments, and emails → `owner@example.com`.
  A token cannot reach an evidence file even if something logs it.
* **Secret scanning in `make verify`** — `make scan-secrets` runs
  `scripts/scan_secrets.py` over every tracked file (9 patterns, 2 documented
  allowlist entries). CI runs the same scanner plus the full-history scan.
* Tokens are read at runtime from `DATAHUB_TOKEN_FILE`, `chmod 600`, outside the
  repository. Never logged, never echoed, never committed.

Local throwaway credentials for the disposable substrate Postgres (`devguard`,
`devguard_eval`) **are** committed, deliberately, and documented in
`substrate/dbt/profiles.yml`. They reach a container holding generated rows.

## 8. Known gaps in the V2 posture

* **The injection screen is a shape-matcher.** Novel phrasings will pass it. The
  zero-tool Diagnostician is what actually holds.
* **`METADATA_SERVICE_AUTH_ENABLED` must be `true`.** The quickstart default is
  `false`, under which none of §4's policies do anything. Anyone reproducing this
  must check it.
* **The approver is the local operator** in every recorded run, not an
  independent reviewer on a real team.
* **`save_document` is granted platform-wide.** Documents are not
  resource-scoped in DataHub's privilege model, so no narrower grant exists for
  §8 artifact 2.
* **No defence against a compromised DataHub server.** DevGuard distrusts the
  catalog's free-text while trusting its structure — schemas, lineage, URNs.
