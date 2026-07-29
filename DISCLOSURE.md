# DISCLOSURE

> **STATUS: DRAFT — produced during Track T0 (audit).** Two fields require a human
> decision before this file is publishable: the hackathon-start commit SHA, and
> the final hackathon/submission this repository is entered into. Both are marked
> `<TBD>`. Do not link this file from the README until they are resolved.

This project **evolves an existing repository** rather than starting a new one.
Per `01_PLATFORM_MASTER.md` §11, that choice moves the burden of proof onto this
disclosure, so it is written to be exact rather than reassuring.

---

## 1 — Commit marking the start of hackathon work

**`<TBD>`**

Everything at or before this SHA is pre-existing work. Everything after it was
authored during the Registration & Submission Period.

> **Note for whoever fills this in:** `docs/01_PLATFORM_MASTER.md` states it
> audited commit `9651db3`. That SHA **is not present in this repository's
> history** and must not be used here. The full history at the time of the T0
> audit was:
>
> ```
> 3f590b1  Create 04_TRACK_FINAL.md
> c37456a  Add core contract document for DevGuard platform
> 596b5c7  Create 02_ADDENDUM.md
> ec0e1f1  Update print statement from 'Hello' to 'Goodbye'
> 0f9012c  Final working code with AI Agent and Telemetry
> 8193728  feat: added ultra pro max landing page and nexus command center
> 702ae8c  Add 2-minute demo script
> 7bd6b7a  Update README: self-observing agent architecture + diagram
> 8798453  Add self-observing agent: SigNoz-telemetry-driven adaptive routing
> 46d792c  Fix CORS, SigNoz trace link, and telemetry integration
> 93ddb5c  Initial DevGuard AI commit
> ```
>
> The last four commits (`ec0e1f1` … `3f590b1`) contain only `docs/` contract
> files, no implementation. `0f9012c` is the last commit that changed application
> code.

---

## 2 — Component attribution

| Component | Path | Status | Notes |
|---|---|---|---|
| Scanner → Fixer → Validator pipeline | `backend/core/ai_agent.py` | **Pre-existing** | The reflection loop, bounded retries and eval-score gate. Reused because it is a working multi-agent loop with typed boundaries. |
| Typed agent contracts | `backend/core/schemas.py` | **Pre-existing** | Pydantic schemas at every agent boundary. |
| OpenTelemetry layer | `backend/core/telemetry.py` | **Pre-existing** | Traces, metrics, logs, W3C propagation, log↔trace bridge. |
| Circuit breaker / resilience | `backend/core/resilience.py` | **Pre-existing** | |
| Hash-chained audit trail | `backend/core/audit.py`, `data/audit_log.jsonl` | **Pre-existing** | |
| Accuracy benchmark harness | `backend/core/benchmark.py` | **Pre-existing** | Includes a negative control. Never yet run to an artifact. |
| RAG store | `backend/core/rag_store.py` | **Pre-existing** | |
| SigNoz MCP client | `backend/core/mcp_client.py` | **Pre-existing** | **Has never executed against a real SigNoz MCP server** — see §3. |
| Local cost shadow | `backend/core/local_telemetry.py` | **Pre-existing** | In-process estimate, not retrieved telemetry. |
| God-mode orchestrator + endpoints | `backend/core/god_mode_orchestrator.py`, `backend/api/god_mode_simulators.py` | **Pre-existing** | |
| Scanner UI, Nexus Commander UI, landing page | `frontend/app/`, `frontend/components/` | **Pre-existing** | |
| Contract documents | `docs/01_*`–`docs/04_*` | **Pre-existing** (committed before implementation) | Planning documents, no product code. |
| T0 audit + handoff + evidence | `docs/AUDIT.md`, `docs/HANDOFF.md`, `docs/audit-evidence/`, this file | **New** | First artifacts of the current work window. |
| **DevGuard Enterprise module** | `backend/enterprise/`, `frontend/app/enterprise/` | **New — not yet created** | Per `01_PLATFORM_MASTER.md` §11, these directories will contain **no** pre-existing code, so the flagship module's entire history sits inside the window. This is the strongest eligibility evidence and must be kept clean. |

---

## 3 — Claims corrected before submission

Stated here rather than buried, because the pre-existing README overclaims in
ways the T0 audit found and the submission must not repeat:

- The README's claim that DevGuard's agents *"query their own SigNoz telemetry
  via MCP"* is **not supported by the pre-existing code**. The client targets an
  invented HTTP transport at a default URL that points to DevGuard's own backend
  port, and it has never completed a round trip against a real SigNoz MCP server.
  See `docs/AUDIT.md` §3.B.
- Several UI values in the pre-existing frontend are fabricated (invented
  counters, savings figures, a health score, a non-existent PR link, an award
  claim). They are enumerated in `docs/AUDIT.md` §3.C and are scheduled for
  removal in Track T1a.
- Benchmark accuracy figures quoted in `DEMO_SCRIPT.md` are hand-typed and are
  not backed by any artifact on disk.

None of the above will appear in the submitted README, UI, or video.

---

## 4 — AI assistance

This project was developed with AI assistance (Claude Code). AI was used for
implementation, refactoring, auditing, and documentation, under human direction
and review. All output was reviewed by the author before commit. Stating this
plainly is permitted by the rules and is not a qualification of authorship.

---

## 5 — Hackathon

**`<TBD>`** — the repository's existing README references the *Agents of SigNoz*
hackathon, while `docs/01_PLATFORM_MASTER.md` targets the *Build with DataHub*
hackathon. **One must be chosen and stated consistently** across README, this
file, the UI and the submission. Shipping both names for one project is itself a
credibility problem.
