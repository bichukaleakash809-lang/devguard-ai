# D10 — §10, the Command Center and replay mode

**Date:** 2026-08-05 · Scope: §10's **Floor** (all eleven items) and §10.11's
zero-infrastructure replay.

**Result: the Floor is built and verified in a real browser against the real
static export. 14/14 UI checks pass, 48 bundle tests pass, and the full suite
stays green at 676 tests.**

---

## Read this first: the phase numbering does not match the calendar

§14's calendar assigns **§10 (UI Floor + replay) to D9** and **reproducibility to
D10**. The repository did something different:

| Calendar | Contract content | What the repo actually did |
|---|---|---|
| D8 | §9B eval suite **+ §11 security** | `40ccd58` — §9B only |
| D9 | **§10 UI Floor + replay** | `5267251` — §11 security (calendar D8's other half) |
| D10 | Reproducibility day | **this commit — §10 UI Floor + replay** |

So the calendar's D8 was split across two phases, and §10 was never executed.
This phase closes that gap. **Calendar-D10 (reproducibility day: fresh
container, clean clone, `make doctor` / `demo` / `reset-demo` / `eval` /
`verify`, redaction pass, version matrix into the README) has NOT been done and
is still outstanding.** Do not read "D10" in this filename as "reproducibility
day is finished".

---

## What was built

### The bundle — `backend/v2/replay.py`, `scripts/build_replay.py`

`make replay` compiles each committed proof pack into one self-contained JSON in
`frontend/public/replay/`. Seven packs build:

```
[ok]   d6-loop-pass2         30 evidence   32 artifacts    159.5 KiB
[ok]   d6-loop-pass1         29 evidence   31 artifacts    151.9 KiB
[ok]   d6-dry-run            31 evidence   32 artifacts    165.3 KiB
[ok]   d6-fail-the-fix       24 evidence   24 artifacts    140.5 KiB
[ok]   d5-refusal             4 evidence    5 artifacts     22.5 KiB
[ok]   d5-full               12 evidence   13 artifacts     78.4 KiB
[ok]   d4-evidence-chain     12 evidence   12 artifacts     77.0 KiB
```

Two design constraints drove it, both from §10.11's "zero infrastructure":

* **Every raw payload is embedded**, keyed by the same `raw_ref` string
  `INDEX.json` and the evidence chain already use. A bundle that pointed at
  `evidence/proof-pack/...` at render time would need a filesystem and a server,
  which is precisely what the requirement rules out. Clicking an evidence chip
  is a dictionary lookup.
* **Nothing is computed that the pack does not contain.** Missing values are
  `null`, and every `null` has a reason recorded in `bundle.missing`, which the
  UI renders as a hoverable `N/A` and lists in full at the bottom of the screen.

The blast-radius numbers are parsed with **Pathfinder's own parsers**
(`_impacted`, `_path_hops`, `_queries`) rather than a second implementation.
`_impacted` carries a hard-won correction — it reads only `searchResults`,
because an earlier version swept up DataHub's facet aggregations and reported a
real 5-dataset radius as 9. Re-deriving those numbers here would have meant
re-acquiring that bug, and a panel that disagrees with the evidence chain beside
it is worse than no panel.

### The UI — `frontend/app/command/page.tsx` + `frontend/components/command/`

All eleven Floor items, at `/command?run=<run-id>`:

| § | Item | Where |
|---|---|---|
| 10.1 | Incident header + state machine + mode banners | `IncidentHeader.tsx` |
| 10.2 | Agent handoff rail | `HandoffRail.tsx` |
| 10.3 | Evidence ledger + raw viewer | `EvidenceLedger.tsx`, `RawViewer.tsx` |
| 10.4 | Graph & blast radius | `BlastRadius.tsx` |
| 10.5 | Prior-knowledge banner | `RootCause.tsx` |
| 10.6 | Root cause, incl. the refusal state | `RootCause.tsx` |
| 10.7 | Policy & approval | `PolicyApproval.tsx` |
| 10.8 | Write-back | `WriteBack.tsx` |
| 10.9 | Security panel | `SecurityMetrics.tsx` |
| 10.10 | Metrics strip | `SecurityMetrics.tsx` |
| 10.11 | Replay mode | the page itself + `next.config.js` export mode |

`NEXT_OUTPUT=export` switches the Next build from `standalone` (which
`frontend/Dockerfile` needs) to a static export. The page is a client component
that fetches two JSON files; no route does server-side data access, so the whole
thing renders from files on any static host.

---

## The four judgement calls, and why

These are the places where the honest rendering and the impressive rendering
differ. Each went to the honest one.

**1. Cost renders `N/A`, not `$0.00`.** No model was invoked in any captured
run — every handoff records `model: null` and the Diagnostician reports
`REASONER_UNAVAILABLE`, because Groq is unreachable from this environment
(`docs/TODO-BLOCKED.md`, blocker 1). `$0.00` would read as "this loop was free".
It was not free; it was never measured. Same for tokens: `0` is recorded, and
the strip says so in words rather than presenting it as a measurement.

**2. A refusal reports no time-to-root-cause.** The first version summed the
elapsed span for `d5-refusal` and displayed **33.05 s** as time-to-root-cause —
a headline success metric sitting directly above a full-width INSUFFICIENT
EVIDENCE panel, on the one run that deliberately produced no root cause. It is
now `null` with the reason recorded. Total loop duration still shows, because
that span really did elapse.

**3. `BLOCKED` is not drawn as a refusal.** The D6 Diagnostician stops with
`BLOCKED` and its own rationale is explicit: *"the evidence chain is sufficient,
so this is NOT a refusal — the question was never asked."* Only
`INSUFFICIENT_EVIDENCE` gets §10.6's refusal treatment. Collapsing the two would
claim a governance decision the run never made — and it would be the flattering
error, since the refusal is the better demo beat.

**4. The Sentinel is `ran`, not `idle`.** It writes `patch-scan.json` but the
Surgeon owns the handoff edge into it, so it emits no `AgentHandoff` of its own.
Marking it `idle` would claim a security control did not run when it did; giving
it the Surgeon's duration would invent a measurement. It renders as `ran` with
duration `N/A`.

---

## Two real bugs the verification found

**The prior-knowledge banner asserted the opposite of what happened.**
`_document_urns` looked for a flat `documents` list; DataHub returns
`searchResults[].entity` with the title nested at `info.title`. So it found
nothing and rendered **NO PRIOR VERIFIED INCIDENTS FOR THIS ASSET** — on a run
whose Archivist had, in the same screen, reported *"PREVIOUS VERIFIED INCIDENT —
4 document(s) retrieved."* Two panels contradicting each other, with the wrong
one stated more prominently. Fixed against the payload the pack actually
contains; `test_prior_knowledge_agrees_with_the_archivist` pins it.

**Every panel "open raw" button was dead.** The panels emitted refs shaped
`<run-id>/pathfinder/…` while the `raw` map is keyed
`evidence/proof-pack/<run-id>/pathfinder/…`. The evidence chips worked, so the
failure was invisible unless you clicked a panel link specifically — and a dead
button renders as a button, not as an error. There is now one canonical spelling
(`_ref`) and `test_every_raw_ref_resolves` checks every ref in every pack.

A third, smaller one: the blast-radius list rendered
`devguard.analytics_staging.stg_users` twice, because a dbt trace returns the
same logical table under `dataPlatform:dbt` and `dataPlatform:postgres` and
`shortUrn` collapsed both to one label. A correct 7-entity radius read as four
entities and three duplicated rows. Entities now carry their platform.

---

## Verification

### `make verify-replay-ui` — the built site, driven in a real browser

Not a compile check. It serves `frontend/out/` over plain HTTP with **no
backend, no DataHub, no Postgres and no API key running**, and asserts the
behaviour §10.11 actually promises:

```
verify_replay_ui: http://localhost:8931/command/

  [PASS] page renders with no backend running — 10869 chars
  [PASS] replay banner is present and unmissable
  [PASS] all six state-machine states render
  [PASS] cost is N/A rather than a placeholder zero
  [PASS] evidence chip opens the raw payload viewer
  [PASS] the viewer shows real captured bytes — 1427 chars
  [PASS] Escape closes the viewer
  [PASS] a rail node opens its AgentHandoff record
  [PASS] a tool call opens its recorded MCP response — 8307 chars
  [PASS] the run picker reaches the refusal
  [PASS] the refusal names the missing evidence class
  [PASS] a refused run reports no time-to-root-cause
  [PASS] no uncaught page errors
  [PASS] no failed requests

14/14 checks passed
```

The 1427 chars opened by the evidence chip are the real `watcher/dbt-run.txt`
bytes — the same byte count `INDEX.json` records for that artifact.

Screenshots (full page, 1680px): `screenshots/d6-loop-pass2.png` (the complete
loop through write-back) and `screenshots/d5-refusal.png` (the refusal).

### `tests/test_replay_bundle.py` — 48 tests

Parametrised across all seven packs. The properties worth naming: every
`raw_ref` resolves; cost is never a placeholder; every `None` metric has a
recorded reason; a refusal names its missing class and reports no
time-to-root-cause; a partial pack does not claim states its artifacts do not
justify; the rail has one node per §6 agent in order; the blast-radius counts
match the Pathfinder's own rationale string.

That last one is the useful one — it asserts the panel and the agent that
produced it cannot disagree on screen.

### Regression check

```
$ python -m pytest
676 passed, 1 warning in 32.06s
```

`npm run lint` — 8 warnings, all pre-existing in `app/page.tsx`,
`app/result/page.tsx` and `app/scanner/page.tsx`; **zero from the new code**. `python scripts/scan_secrets.py` —
643 tracked files, clean.

---

## What is deliberately not here

* **The Ceiling** (§10's evaluation dashboard, ablation view, timeline scrubber,
  theming, animated transitions, multi-incident history). §10 says the Ceiling
  is touched "only after Aug 6, and only if the Floor is frozen", and the cut
  order puts UI Ceiling first out. Not started.
* **A deployed replay URL.** The static export builds and is verified locally;
  publishing it is submission-package work (§15), not §10.
* **Live mode.** Every capture in this repository is a recorded run, and the
  banner says so unconditionally. Wiring the same components to a live loop is
  real work that is not done, and the UI does not pretend otherwise.
* **Committed bundles.** `frontend/public/replay/` is generated and gitignored.
  Committing it would put a second copy of the evidence in the repository, and a
  second copy is one that can drift from the pack it claims to render.

## Reproducing

```bash
make replay              # bundles from the committed proof packs
make replay-serve        # static export + http.server; open /command/
make verify-replay-ui    # the 14 checks above, in a real browser
python -m pytest tests/test_replay_bundle.py -q
```

None of these need DataHub, Postgres, a Groq key or the backend.
