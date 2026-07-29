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

70 tests run on every push in CI, with no API key, no collector and no network
(`.github/workflows/ci.yml`). They cover the typed agent boundaries, the audit
chain's tamper detection, the circuit-breaker state machine, telemetry
fail-safety, and the untrusted-content boundary above. CI also runs a real OTLP
export verification and the secret scan. So the properties claimed in this file
are checked mechanically rather than asserted once.

## Known weaknesses — not yet fixed

These are real and should be treated as open:

- **CORS is wide open.** `backend/main.py` sets `allow_origins=["*"]`. Acceptable
  for local use; it must be an explicit allowlist before any public deployment.
- **No authentication on any endpoint.** Anyone who can reach the backend can
  submit a scan, read the audit log, and approve or reject a gated fix. Do not
  expose this to the internet as-is.
- **No rate limiting or request size cap.** `POST /scan` accepts arbitrary code
  and forwards it to a paid LLM API, so an open instance is a cost-exhaustion
  target.
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
