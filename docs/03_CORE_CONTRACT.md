# DEVGUARD — CORE CONTRACT (re-paste this every session)

You are working on the DevGuard platform. This is the compressed contract. The full documents were provided separately; where they give more detail, follow them. Where anything conflicts, **this file wins**.

---

## 1 — THE LAWS

1. **PRESERVE FIRST.** The existing Scanner and Nexus Commander work. They are preserved. Additive over destructive. Never delete, regenerate, or "clean up" working code without explicit approval.
2. **CRITERION OR CUT.** Every feature must name the judging criterion it raises. If it raises none, it is not built.
3. **NEVER FABRICATE.** No invented metrics, counters, badges, awards, PR links, health scores, or savings figures — anywhere in UI, docs, or video.
4. **LIVE OR LABELLED.** Every number on screen is either computed from a real call in this session, or visibly badged `SIMULATED`. There is no third option.
5. **DE-RISK BEFORE YOU BUILD.** Any external capability a demo depends on is proven with one live call before anything is built on it.
6. **NUMBERS COME FROM THE MACHINE.** Every figure in docs, README, or video is rendered from an artifact file. A hand-typed number is a violation of Law 3.

---

## 2 — TRACK ORDER (one track per approval — never two)

| Track | Objective |
|---|---|
| **T0** | Audit. Verify the repo, run everything, report. **STOP.** |
| **T1a** | Honesty pass — remove every fabricated value |
| **T1b** | Fix blockers: Apache-2.0 `LICENSE`, `.env.example`, frontend Dockerfile, otel config, port unification, BOM, untrack `.env.local` |
| **T2** | SigNoz proven end to end + the MCP truth decision |
| **T3** | Extract the design system; refactor Scanner + Nexus onto shared primitives |
| **T4** | Nexus live: mapping layer, streaming, live state, concurrency timeline |
| **T5** | Home page: hero Enterprise card + two module cards + real status bar |
| **T6** | Enterprise (DataHub) module — the full contract |
| **T7** | Tests, CI, Docker, docs, security |
| **T8** | Release track — only after its entry gate passes |

**Cut order under time pressure:** UI ceiling → second scenario → OSS PR → UI polish. **Never** cut: the honesty pass, the Apache-2.0 licence, the DataHub write-back, or the submission package.

---

## 3 — DEFINITION OF "VERIFIED"

A track is complete only when **all five** hold, with output pasted in the report:

1. Build passes — backend imports, `npm run build`, zero TypeScript errors.
2. Tests for the touched area pass, and at least one covers the new behaviour.
3. The behaviour was **executed**, not just implemented, and real output is in the report.
4. No previously working screen or endpoint regressed — name which you checked and how.
5. An artifact exists on disk that a third party could inspect.

If all five cannot be met, the track is **reported as blocked**. Never marked complete with a caveat. Never mark your own work green because the code looks correct.

---

## 4 — KEY DECISIONS (already made — do not re-litigate)

- **Repository:** evolve the existing repo. `DISCLOSURE.md` carries the eligibility burden. The Enterprise module's directories contain no pre-existing code, so its history is unambiguously in-window.
- **Substrate:** real Postgres + dbt Core + real consumers + a real small ML model, with lineage **ingested** into DataHub via committed recipes. Sample datapacks are surrounding context only, labelled `SEEDED CATALOG CONTEXT`. Lineage is never hand-authored.
- **Write-back is the spine:** incident raised → resolved (GraphQL), runbook Context Document (`save_document`), column-level tag/description, structured properties (definitions registered first), ownership signal. **Nothing is written before recovery is verified.**
- **Graph is 2D**, WebGL-accelerated, with the reasoning choreography. 3D is out of scope.
- **Measurement is an ablation**, not an anecdote: same incident, retrieval on vs off, N≥5, medians reported.
- **Security:** catalog free-text is untrusted input. The Diagnostician holds **zero tools**. The Scribe is the **only** agent that can write to DataHub.

---

## 5 — CANONICAL AGENT ROSTER (Enterprise)

One count, stated identically in README, UI status bar, video, and Devpost.

| # | Internal id | Display name | Model-backed |
|---|---|---|---|
| 1 | `watcher` | Watcher | no |
| 2 | `archivist` | Archivist | yes |
| 3 | `cartographer` | Cartographer | yes |
| 4 | `pathfinder` | Pathfinder | yes |
| 5 | `sentinel` | Sentinel | partly |
| 6 | `diagnostician` | Diagnostician | yes, **zero tools** |
| 7 | `strategist` | Strategist | yes |
| 8 | `patchsmith` | Patchsmith | yes |
| 9 | `referee` | Validator | no |
| 10 | `magistrate` | Governor | partly |
| 11 | `scribe` | Scribe | yes, **only writer** |
| 12 | `auditor` | Commander | no |

Scanner's own Validator is a **different component** with a different scope — disambiguate it in the docs. Every agent has its own tool allowlist, enforced in code and asserted in tests.

---

## 6 — SESSION PROTOCOL

- **First action of every session:** read `docs/HANDOFF.md`. **Last action:** update it — current track, what is green, what is red, the exact next command, open questions. Assume the next session has zero memory of this one.
- Declare the file scope before starting a track. Commit and push at every track boundary. Never carry uncommitted work across a session.
- Large outputs go to disk and are summarised into context — never held raw.
- A track that will not fit in one session is split **before** it starts.
- Never `git push --force`, never rewrite published history, never delete files without approval.
- If uncertainty exists, **stop and ask**. A question costs minutes; a wrong assumption compounds across tracks.

---

## 7 — IF THIS IS THE FIRST SESSION

Before anything else, write the full contract documents into `docs/` so they survive this session, then work from those files rather than from chat context.

Then execute **T0 only**: read the whole repo, run build/tests/lint/`docker compose config`/both dev servers, paste real output including failures, report environment capacity (disk, RAM, Docker), and report what works · what is broken · what is fabricated · what is simulated but honest · what should be cut under Law 2 · top five risks · anything in this contract you would argue should change based on what you actually found.

**Then STOP.**
