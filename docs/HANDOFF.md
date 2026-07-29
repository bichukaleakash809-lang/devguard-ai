# DEVGUARD — SESSION HANDOFF

**Assume the next session has zero memory of this one. Read this file first.**

Protocol: `docs/03_CORE_CONTRACT.md` §6. First action of every session — read this
file. Last action — update it.

---

## CURRENT TRACK

**T0 — Audit. COMPLETE and approved.**
**T1 — Build + honesty pass. COMPLETE and verified. Awaiting approval for T2.**

Do **not** start T2 (SigNoz end to end + the MCP truth decision) until the human
approves. `docs/04_TRACK_FINAL.md` is **not to be executed** until the human says
"start the Final Release Track."

---

## T1 — WHAT WAS DONE (5 phases, one commit each)

| Phase | Commit | Content |
|---|---|---|
| 1 | `4ab24ba` | Backend importable without an API key |
| 2 | `3f885ff` | Nexus panels render real data or N/A; frontend TS errors fixed |
| 3 | `d7c4aa8` | Honesty pass: real status bar, both `data_source` mislabels fixed |
| 4 | `4c602d5` | ESLint config, `.env.example`, `.env.local` untracked, `.gitignore` BOM |
| 5 | *(this commit)* | README / DEMO_SCRIPT honesty pass, `SECURITY.md` filled |

### The substantive changes

- **`groq_client.py`** now builds `AsyncGroq` on first *use*, not at import. The
  backend previously could not be imported at all without a paid key. A minimal
  attribute-forwarding proxy keeps `groq_client.chat.completions.create(...)`
  identical.
- **`requirements.txt`** gained `opentelemetry-instrumentation-fastapi` and
  `-logging` (both imported by `main.py`; `-logging` was missing outright,
  `-fastapi` only arrived transitively via `chromadb`). BOM stripped.
- **All five Nexus panels rewritten** to read the snake_case shape the backend
  actually returns. The `{...DEFAULT_DATA, ...data}` merge is gone. New
  `components/nexus/_shared.tsx` makes fabrication structurally hard: `pick*`
  helpers return `null` rather than substituting, `<Value>` renders N/A on
  `null`, `<DataSourceBadge>` surfaces provenance, `<PanelEmptyState>` gives
  every panel a designed idle and error state.
- **Two backend LAW 4 breaches fixed.** `CostTrend` now carries an explicit
  `source` (`signoz_mcp` | `local_shadow`) because `available` only ever meant
  "safe to use"; and the executive roll-up's provenance is now the weakest of
  its sections rather than a function of whether anything errored.
- **`data_source` gained the third value** recommended in `AUDIT.md` §7.5:
  `live | local_shadow | synthetic | partial`, with a distinct `LOCAL` badge.

### Fabricated values removed

C1 Grand Finalist badge · C2 "Threats Blocked" random-walk counter · C3
`moneySavedUsd: 1250` · C4 health score 97% / "cost avoided $1,250" · C5 "View
GitHub PR #142" · C6 `eval_score 92/100` + latency ticker + 420/180/310ms trace
spans · C7 "OTel Mesh Connected" · C8 unconditional "Live" pill · C9 benchmark
strip "92%/88%/95%/5% FPR" · C10 "$85/hour" · C11 alerts described as shipped ·
C12 "Python 3.12". Also removed: scripted thinking-console narration, the
courtroom transcript, confidence/trust sparklines, the phone mock, the PDF
preview.

### Verification (all re-run at end of T1)

```
import backend.main with GROQ_API_KEY unset  -> PASS
npx tsc --noEmit                             -> zero errors (was 5)
npm run build                                -> Compiled successfully, 7/7 pages
npm run build without .env.local             -> PASS (clean-clone simulation)
npm run lint                                 -> No ESLint warnings or errors
docker compose config                        -> valid
GET  /slo-status                             -> 200
GET  /audit-log/verify                       -> {"valid":true,"entries_checked":35,"chain intact"}
POST /god-mode/simulate/error                -> 200  data_source=synthetic
POST /god-mode/simulate/cost-spike           -> 200  data_source=local_shadow   (was wrongly "live")
POST /god-mode/simulate/memory-leak          -> 200  data_source=synthetic
POST /god-mode/simulate/hallucination        -> 200  data_source=synthetic
POST /god-mode/simulate/god-mode             -> 200  data_source=partial        (was wrongly "live")
```

Evidence on disk: `docs/audit-evidence/` (T0 before-state) and
`docs/audit-evidence/t1-after/` (T1 after-state).

---

## WHAT IS STILL RED (deliberately out of T1 scope)

| ID | Item | Why deferred |
|---|---|---|
| B1/B2 | `backend/Dockerfile` copies `requirements.txt` from outside its build context; CMD targets `main:app` instead of `backend.main:app` | **Unverifiable here — there is no Docker daemon.** Fixing it blind would mean claiming a green I cannot demonstrate. Needs a machine with Docker. |
| A1 | No `frontend/Dockerfile` | Same. |
| A2 | No `otel-collector-config.yaml` | Belongs with T2 (SigNoz end to end). |
| B3 | `signoz-system` orphaned gitlink (160000, no `.gitmodules`) | Deleting a tracked path needs explicit approval (contract §6). **See open issue 1.** |
| A4 | No `LICENSE`; README previously said MIT, contract requires Apache-2.0 | Licence choice is the owner's decision, not mine. **See open issue 2.** |
| — | Zero tests, no CI, no Makefile | T7. |
| — | `chromadb` + `sentence-transformers` = 5.4 GiB install | Dependency *removal* needs explicit approval (contract §6). **See open issue 3.** |
| §3.B | MCP client still targets an invented transport at a non-SigNoz default URL | **This is exactly T2's decision** — prove it or rewrite the claim. Not pre-empted here. |
| — | Nexus still sends `{}`, so omni_heal/truth_serum can only ever return synthetic | Real streaming + wiring code through is T4. |

---

## EXACT NEXT COMMAND

T2 is *"SigNoz proven end to end + the MCP truth decision"*. It cannot start
until the infrastructure question is answered, because there is no Docker daemon
in this environment.

```bash
git checkout claude/track-t0-audit-evgu8j

# T2 cannot begin until open issue 4 is decided. Once there is a host with a
# working Docker daemon:
docker compose --profile obs up -d      # will fail until otel-collector-config.yaml exists (A2)
# then: emit one span, find it in SigNoz, screenshot it. LAW 5 — prove the
# capability before building anything on top of it.
```

---

## OPEN ISSUES — NEED A HUMAN DECISION

1. **Delete the `signoz-system` gitlink?** It is an orphaned submodule pointer
   with no `.gitmodules`, so `git clone --recurse-submodules` errors. Removing a
   tracked path needs approval per contract §6. Recommend: delete.
2. **Which licence?** `03_CORE_CONTRACT.md` §2 makes Apache-2.0 a hard T1b item
   and calls it a binary submission requirement; the README said MIT. I have
   changed the README to point at `LICENSE` and flagged its absence in
   Limitations rather than picking for you. Recommend: Apache-2.0.
3. **Cut `chromadb` + `sentence-transformers`?** 5.4 GiB including the full CUDA
   toolkit, for optional accelerators behind `try/except` with a working
   pure-Python fallback. Contract §6 forbids dependency removal without
   approval. **If you approve, they must be cut *after* the explicit
   instrumentation pins added in phase 1** — `chromadb` is what was transitively
   supplying `opentelemetry-instrumentation-fastapi`. Recommend: cut.
4. **Infrastructure (blocks T2 and T6).** Still unresolved from T0. No Docker
   daemon here; 15 GiB RAM / 27 GiB disk is below the DataHub + SigNoz +
   Postgres floor. Options: (a) cloud VM ≥ 32 GiB, (b) never co-run — one stack
   at a time, (c) managed cloud. Recommend **(b)**.
5. **Agent roster count.** Unresolved from T0. `03_CORE_CONTRACT.md` §5 says 12,
   `02_ADDENDUM.md` Part D says 11, `01_PLATFORM_MASTER.md` §6 lists a third set
   (has `Surgeon`, lacks `Strategist`/`Patchsmith`). Must be settled before any
   UI renders the number. Recommend 12 including Commander.
6. **Flagship name.** Unresolved from T0. Recommend **DevGuard Lineage Guard**.
7. **`DISCLOSURE.md` needs the hackathon-start SHA and the target hackathon.**
   Both still `<TBD>`. Note `9651db3` (cited in `01_PLATFORM_MASTER.md`) does not
   exist in this repo. Also: the README targets *Agents of SigNoz* while the
   contract targets *Build with DataHub* — one must be chosen.
8. **No Groq API key in this environment.** No live LLM scan has ever been
   executed. The Scanner's end-to-end path remains unproven, and the T1 work did
   not change that.
9. **`git push` is failing with HTTP 403** against the session's git relay
   (`http://local_proxy@127.0.0.1:41729/...`), across many retries. All T0 and T1
   commits exist locally and are signed, but **nothing has reached GitHub**. This
   container is ephemeral. Needs re-authorisation, or an explicit decision to
   push the files through the GitHub API instead (which would create new commit
   objects rather than transferring these).

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

*Last updated: 2026-07-29, end of T1 session.*
