# Risk register — DevGuard V2 (05_DATAHUB_MASTER §18)

Seeded from §18, then amended with what D0 actually measured. Rows marked
**[D0]** are new or materially changed based on evidence, not copied forward.

| # | Risk | Status | Mitigation |
|---|---|---|---|
| 1 | Hero loop cannot be honestly real without a substrate | **OPEN — decision required** | §3 resolved in D0; ingestion gate in D2 |
| 2 | **[D0] `api.groq.com` is unreachable from this environment** | **OPEN — external, blocking** | Not in the original §18. This is *not* "live API failure while recording" — the LLM is unreachable **at build time**, so every LLM-backed agent in §6 can be written and mock-tested but never demonstrated. Owner action: allowlist the hostname. See `docs/TODO-BLOCKED.md` |
| 3 | **[D0] Calendar has already slipped** | **OPEN — decision required** | §14 puts D0 on Jul 28 and MWP LOCK on Aug 3. Today is Jul 31 (= D3) and D0 is only now running. D1–D3 have not happened |
| 4 | **[D0] Disk, not RAM, is the binding constraint** | **OPEN** | 16 GiB free. DataHub Core (~5 GiB) **cannot coexist with the SigNoz stack** (3.9 GiB of images) plus the substrate. Prune between demos; state it in the README |
| 5 | Context Documents / mutation tools unavailable on the deployed version | OPEN | Pin in D0 (`versions.env`), smoke test in D1. `mcp-server-datahub 0.6.0` ≥ 0.5.0 ✓ |
| 6 | Structured properties not pre-registered | OPEN | Definitions registered D1 |
| 7 | Incident privileges missing | OPEN | Service account + policies configured D1 |
| 8 | Document tools hidden on a clean catalog | OPEN | Capability negotiation + deliberate degradation |
| 9 | `get_dataset_queries` returns empty | OPEN | Verified D4–D5; generate real history or delete the claim |
| 10 | `@latest` drift between record day and judge day | **MITIGATED (partial)** | `versions.env` created. `DATAHUB_VERSION` and `DATAHUB_SKILLS_REF` still unpinned — they require a running instance to resolve honestly |
| 11 | Token/PII leaked in the proof pack | OPEN | Redaction at capture; secret scan already in CI |
| 12 | Prompt injection via catalog text | **PARTIALLY MITIGATED** | §11's boundary already exists and is tested (`tests/test_prompt_injection_boundary.py`); Diagnostician-has-zero-tools still to build |
| 13 | Write-back concurrency / partial failure | OPEN | Idempotency keys + all-or-nothing resolve policy |
| 14 | Large lineage responses blow the agent context | OPEN | Write to disk, summarise into the prompt |
| 15 | Eligibility challenge over pre-existing code | **OPEN — decision required** | PATH A + carry-over cap + `DISCLOSURE.md` (§17) |
| 16 | UI absorbs the schedule | OPEN | Floor/Ceiling rule (§10) |
