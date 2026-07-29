# DEVGUARD — SESSION HANDOFF

**Assume the next session has zero memory of this one. Read this file first.**

Protocol: `docs/03_CORE_CONTRACT.md` §6. First action of every session — read this
file. Last action — update it.

---

## CURRENT TRACK

**T0 — Audit. COMPLETE. Awaiting human approval before T1a.**

Track order is `T0 → T1a → T1b → T2 → … → T8`, **one track per approval, never
two** (`03_CORE_CONTRACT.md` §2). Do **not** start T1a until the human has read
`docs/AUDIT.md` and approved.

`docs/04_TRACK_FINAL.md` is explicitly **not to be executed** until the human
says "start the Final Release Track."

---

## COMPLETED WORK (this session)

- Read `docs/01_PLATFORM_MASTER.md`, `docs/02_ADDENDUM.md`,
  `docs/03_CORE_CONTRACT.md` in order. Skimmed `04_TRACK_FINAL.md` for context
  only — **not executed**.
- Full repository audit. **No implementation file was modified.**
- Ran, with real output captured: `docker compose config`,
  `pip install -r requirements.txt`, backend import, backend boot, six live HTTP
  endpoint calls, `npm install`, `npx tsc --noEmit`, `npm run build`,
  `npm run lint`, full-history secret scan.
- Wrote `docs/AUDIT.md` — the T0 deliverable.
- Wrote `DISCLOSURE.md` (draft — needs a human decision on the hackathon-start SHA).
- Captured artifacts to `docs/audit-evidence/` (6 raw JSON responses, backend
  boot log, frontend build/typecheck output).

---

## WHAT IS GREEN

- Agent pipeline core, Pydantic contracts, telemetry layer, resilience/circuit
  breaker, hash-chained audit trail, benchmark harness. See `AUDIT.md` §4.
- Backend **boots** and serves once B4/B5 are worked around.
- `GET /slo-status` → 200. `GET /audit-log/verify` → `chain intact`, 35 entries.
- All five `/god-mode/*` endpoints respond without 500-ing.
- Frontend `✓ Compiled successfully` (fails later, at typecheck).
- Git history contains **no leaked credentials**.

## WHAT IS RED

| ID | Blocker |
|---|---|
| B4 | Backend unimportable without `GROQ_API_KEY` (`groq_client.py:18` raises at import) |
| B5 | `opentelemetry-instrumentation-logging` / `-fastapi` missing from `requirements.txt` |
| — | `npm run build` fails — 5 × TS2322 in `app/nexus/page.tsx:266,275,284,293,302` |
| B6 | No ESLint config — `npm run lint` is interactive, would hang CI |
| B1/B2 | `backend/Dockerfile` copies `requirements.txt` that is outside its build context, and its CMD targets the wrong module path |
| B3 | `signoz-system` is an orphaned gitlink (160000) with no `.gitmodules` |
| A1/A2/A3/A4 | No `frontend/Dockerfile`, no `otel-collector-config.yaml`, no `.env.example`, no `LICENSE` |
| D1/D2 | All five Nexus panels merge `{...DEFAULT_DATA, ...data}` and the key namespaces do not intersect → **every visible number is fabricated even after a real call** |
| §3.B | The SigNoz MCP client has never spoken to SigNoz; its default URL is DevGuard's own port; its cost path labels the local fallback `"live"` |
| — | Zero tests, no CI, no Makefile |
| — | **No Docker daemon in this environment**; 15 GiB RAM / 27 GiB disk is below the DataHub + SigNoz + Postgres floor |

---

## EXACT NEXT COMMAND

Nothing is executed until the human approves. On approval, the recommended first
action is **not** T1a as written — see `AUDIT.md` §7.3 for why the contract's
stated order cannot meet its own verification gate. The recommended slice:

```bash
git checkout claude/track-t0-audit-evgu8j

# T1b-minimal — make the tree verifiable before changing anything else:
#  1. requirements.txt: strip BOM; add opentelemetry-instrumentation-logging==0.41b0
#                       and opentelemetry-instrumentation-fastapi==0.41b0
#  2. groq_client.py:   make client construction lazy (no raise at import time)
#  3. nexus/page.tsx:   fix the 5 TS2322 errors
#  4. add .env.example  (root + frontend)
# then re-run the gate:
cd frontend && npm run build          # must reach "zero TypeScript errors"
cd .. && python -c "import backend.main"   # must succeed with NO GROQ_API_KEY set
```

Only once that is green does T1a (the honesty pass) become verifiable per
`03_CORE_CONTRACT.md` §3.

---

## OPEN ISSUES — NEED A HUMAN DECISION

These block specific tracks. They are listed in the order they will bite.

1. **Environment / infrastructure (blocks T2 and T6).** There is no Docker daemon
   here, and the box is under-specced for DataHub Core + SigNoz + Postgres
   together. Choose: **(a)** a cloud VM ≥ 32 GiB, **(b)** never co-run — bring up
   one stack at a time and capture evidence separately, or **(c)** DataHub Cloud
   + SigNoz Cloud. Recommendation: **(b)**, it is free and still satisfies the
   evidence gates. See `AUDIT.md` §1.
2. **Track order (blocks T1a).** Approve running a minimal T1b slice before T1a,
   per `AUDIT.md` §7.3 — otherwise T1a cannot be verified against a tree that
   does not build.
3. **Agent roster count.** The three contract documents disagree: 12 agents in
   `03_CORE_CONTRACT.md` §5, 11 in `02_ADDENDUM.md` Part D (which also says the
   status bar must read `11 registered`), and a third, different set in
   `01_PLATFORM_MASTER.md` §6 (contains `Surgeon`, omits `Strategist` and
   `Patchsmith`). The contract requires one count stated identically everywhere.
   **Must be resolved before any UI renders it.** Recommendation: 12, including
   Commander.
4. **`data_source` needs a third value.** `live | synthetic` cannot express "real
   measurement of this session, computed by a documented heuristic," which is what
   the cost path actually produces — and forcing it into `live` is precisely what
   caused the runtime mislabel. Recommend `live | local_shadow | synthetic`.
   See `AUDIT.md` §7.5.
5. **Flagship name (§1 of the master prompt).** Recommendation: **DevGuard Lineage
   Guard**. Not locked — §1 makes this a human decision.
6. **`DISCLOSURE.md` needs the hackathon-start commit SHA.** The draft marks it
   `<TBD>`. Note that `01_PLATFORM_MASTER.md` claims it audited commit `9651db3`,
   which **does not exist in this repository's history** — that SHA cannot be used.
7. **Foundry (`casting.yaml`, `pours/`) — keep or cut?** The README makes
   `foundryctl cast` a required quickstart step for a binary a judge will not
   have. `01_PLATFORM_MASTER.md` §6.1 already permits the lighter docker-compose
   path. Recommend cutting it from the hero path.
8. **No Groq API key in this environment.** No live LLM scan has ever been
   executed or verified in this session. Until a key is available, the Scanner's
   end-to-end path remains unproven.

---

## STANDING RULES (do not relearn these the hard way)

- Never `git push --force`, never rewrite published history, never delete files
  without approval.
- Commit and push at every track boundary. Never carry uncommitted work across a
  session.
- Never mark your own work green because the code looks correct. Green comes from
  pasted output. If the five conditions of §3 cannot all be met, the track is
  **reported as blocked**, never "complete with a caveat."
- Large outputs go to disk and are summarised into context.
- Work on branch `claude/track-t0-audit-evgu8j`.

---

*Last updated: 2026-07-29, end of T0 session. HEAD at audit: `3f590b1`.*
