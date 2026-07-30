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
  reports the first break if there is one.
- **Bounded agent loop.** Reflection retries are capped
  (`MAX_REFLECTION_RETRIES`); a circuit breaker (`backend/core/resilience.py`)
  opens on repeated upstream failure rather than retrying without limit.
- **Fail-safe telemetry.** Observability is never load-bearing: if the collector
  or the MCP path is unreachable, scans proceed unchanged.
- **Honest provenance.** Every god-mode response carries a `data_source` of
  `live`, `local_shadow`, `synthetic` or `partial`, and the UI renders it. An
  in-process estimate is never presented as retrieved telemetry.

## What is regression-protected

209 tests run on every push in CI, with no API key, no collector and no network
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
- **18 open advisories in the frontend dependency tree** (16 high, 2 moderate),
  all in `next` and in the `postcss` nested inside it. `next` resolves to
  **14.2.35 — the latest 14.x — so there is no in-range fix**; the only remedy is
  a breaking upgrade to `next@16`, which needs owner approval and its own
  verification pass, so nothing has been changed.

  Triaged rather than counted, because the raw number overstates the exposure.
  Verified absent from this app: `middleware.*`, any `"use server"` directive,
  i18n config, rewrites, and a Pages Router — and all five routes build as fully
  prerendered static. That structurally excludes the four Server-Action/Server-
  Function advisories and the two Pages-Router/rewrite ones. The three `postcss`
  advisories need attacker-controlled CSS *source* at build time, and the app's
  own top-level `postcss` (8.5.19) is already patched. What remains genuinely
  applicable is the response/RSC **cache-confusion** class (GHSA-wfc6-r584-vfw7,
  GHSA-68g3-v927-f742, GHSA-4633-3j49-mh5q), against a static frontend that
  serves no user-specific responses.

  Full per-advisory reasoning and the raw `npm audit` output:
  `docs/audit-evidence/t2/frontend-dependency-advisories.txt`.

## Dependencies

Pinned in `requirements.txt` and `frontend/package-lock.json`. `chromadb` and
`sentence-transformers` pull a very large transitive tree (~5.4 GiB including
CUDA); both are optional accelerators behind `try/except` in
`backend/core/rag_store.py`, and removing them is under consideration.

**Secret scanning runs in CI** on every push (`.github/workflows/ci.yml`): the
full git history is scanned for `gsk_*`, `sk-*`, `AKIA*` and PEM private-key
patterns, and the job fails if `.env` or `frontend/.env.local` is ever tracked
again. There is **no automated dependency-vulnerability scanning** yet
(Dependabot / `pip-audit` / `npm audit` in CI) — that remains open.
