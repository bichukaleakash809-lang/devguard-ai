# TRACK FINAL — RELEASE CANDIDATE · v2.0
### DevGuard Platform · Release Engineering & Public Launch Contract
**Terminal track of `DEVGUARD_PLATFORM_MASTER_PROMPT_v3.md`. Supersedes Track Final v1.0.**
This is the last thing you build, and the track that most decides your score — because it is the only track a judge is guaranteed to experience.

---

## §F0 — ENTRY GATE (hard — do not start this track early)

Begins only when **all seven** are true, each proven by an artifact on disk, not asserted in a report.

| # | Condition | Required proof |
|---|---|---|
| 1 | **Scanner complete** | Clean-clone run: paste code → scan → fix → validate → result, zero console errors. Output captured. |
| 2 | **Nexus complete** | Five modules execute concurrently; every panel renders **mapped live data** with a correct `LIVE`/`SIMULATED` badge. Recording captured. |
| 3 | **Enterprise complete** | Full hero loop end to end, twice, from clean state. `timings.json` written both times. |
| 4 | **DataHub verified** | Real URNs from real calls: incident raised **and** resolved, runbook published, column annotated, structured property set. Raw responses committed. |
| 5 | **SigNoz verified** | One real distributed trace visible in the SigNoz UI with the pipeline spans. Screenshot committed. Log↔trace correlation working, or the claim removed. |
| 6 | **Tests passing** | CI green: lint, typecheck, backend tests, frontend build, secret scan. Run URL or full output pasted. |
| 7 | **Demo verified** | `make demo` succeeds on a machine that has never seen the project. |

**If any condition fails, do not start Track Final. Report which one and stop.** Release engineering on an unfinished implementation produces documentation that lies — which converts a rough project into a dishonest one, and that is a far worse position.

---

## §F1 — THE PRIME RULE OF THIS TRACK

> **No documentation, README, screenshot, GIF, diagram, deployment, or marketing asset is final until the implementation is complete and verified. Every artifact is generated from the verified implementation and its proof artifacts — never from intent, plan, or assumption.**

Operationally:
- Every number in every document is read from `artifacts/timings.json`, the eval report, the benchmark report, or a captured API response. **Zero hand-typed figures.**
- Every screenshot, GIF, and diagram is produced from the running system in its final state — never mocked, never from an earlier build, never edited beyond cropping and redaction.
- Every code sample is executed before publication; the output shown is the real output.
- Every feature claim carries a file path or demo timestamp in `JUDGING_MATRIX.md`.
- If a document describes something the implementation does not do, **the document is wrong**. Fix the document. There is no "ship it and fix it later."
- Anything unevidenced goes in **Limitations**, plainly. That section is a strength, not an apology.

---

## §F2 — THE JUDGE EXPERIENCE CONTRACT (the standard everything else is measured against)

Three audiences, three time budgets. Every asset in this track exists to serve one of them.

| Audience | Budget | Must understand | Served by |
|---|---|---|---|
| **GitHub visitor** | **15 seconds** | *What is this?* | Hero banner, one-sentence thesis, badges, the write-back GIF |
| **Recruiter / engineer skimming** | **30 seconds** | *What did they build, and is it real?* | Above-the-fold block, the three-module table, the agent count, one screenshot of DataHub changed by an agent |
| **Hackathon judge** | **60 seconds** | *What does it do, why does it matter, how do I try it?* | Everything above + write-back table + results table + Try-it-yourself with a zero-setup URL |

**These are testable, and you will test them (§F11.4).** Hand the README to someone who knows nothing about the project, start a timer, stop them at 15 / 30 / 60 seconds, and ask what they understood. Whatever they could not answer is a README defect — not a them defect.

Design consequence, applied everywhere in this track: **the top of every surface answers "what is this" before it answers anything else.** No table of contents above the fold, no origin story, no philosophy, no "in today's fast-moving data landscape."

---

## §F3 — ORDER OF OPERATIONS

Deployment moves early: the live URLs are **inputs** to the README, the video, and the submission. Producing docs before you have URLs means producing them twice.

```
RC-1   FREEZE FEATURES        no new functionality from this point
RC-2   GENERATE EVIDENCE      proof pack, timings, eval, benchmark, performance reports
RC-3   DEPLOY (§F9)           frontend, backend, replay URL, health verified, SHA pinned
RC-4   STRUCTURE + GENERATE   folder layout, examples/, OpenAPI, all diagrams (§F6)
RC-5   WRITE DOCUMENTS        README, governance docs, runbooks, disclosure — from RC-2/RC-3 outputs
RC-6   CAPTURE VISUALS        screenshots, GIF journey, banners, previews (§F5)
RC-7   RECORD VIDEO           frozen build, frozen numbers, live URLs
RC-8   SUBMIT                 Devpost draft complete and saved — early, not on the last day
RC-9   GITHUB POLISH (§F10)   About, topics, social preview, pinned items, release tag
RC-10  QA + AUDIT + FREEZE    cold machine, cold eyes, 15/30/60, adversarial, health score
```

**RC-1 is not negotiable.** Every hour of feature work after RC-1 invalidates screenshots, numbers, and video takes you already produced. The most common way a strong project ships a weak submission is re-opening the code during release engineering.

---

## §F4 — ARTIFACT REGISTER (tiered — build in tier order)

**T0 = rules-mandated or directly scored · T1 = high judge impact · T2 = professional polish.**
Never build a T2 artifact while a T0 artifact is incomplete. That is the exact trade that loses hackathons.

| Artifact | Tier | Serves | Est. | Done when |
|---|---|---|---|---|
| `LICENSE` (Apache-2.0) | **T0** | binary requirement | 5 m | renders in the GitHub **About** panel — verified visually |
| **Live demo / replay URL** | **T0** | rules + Criterion 5 | §F9 | reachable from a clean browser, no login, no setup |
| `README.md` | **T0** | Criterion 5 | 3–4 h | §F5 spec satisfied and passes the 15/30/60 test |
| Demo video (<3:00) | **T0** | Criterion 5 | 3–4 h | public, captioned, no copyrighted music, frozen numbers |
| Devpost description | **T0** | Criterion 5 | 45 m | generated from README |
| `DISCLOSURE.md` | **T0** | eligibility | 45 m | component table + start-of-work SHA + AI-assistance line |
| `JUDGING_MATRIX.md` | **T0** | all five | 1 h | every row has real evidence; zero TODOs |
| `SUBMISSION_CHECKLIST.md` | **T0** | eligibility | 30 m | every item mapped to a literal path or URL, all ✅ |
| `examples/` | **T0** | Criteria 1, 5 | 1 h | real artifacts, each labelled with the call that produced it |
| Proof pack | **T0** | Criterion 2 | ✓ RC-2 | redacted, size-capped, complete for the recorded run |
| Screenshots (dark) | **T0** | Criterion 5 | 1 h | frozen build, real data, redacted |
| **Journey GIF** (§F5.2) | **T0** | Criterion 5 | 1.5 h | Home → Scanner → Nexus → Enterprise → Write-back → Replay |
| **Write-back GIF** | **T0** | Criterion 1 | 30 m | DataHub's own UI changing because an agent wrote to it |
| **Architecture SVG** | **T1** | Criteria 2, 5 | 1.5 h | legible at 1080p, generated from source (§F6) |
| **Agent-flow SVG** | **T1** | Criteria 2, 3 | 1 h | canonical roster, tool allowlists visible |
| **Data-flow SVG** | **T1** | Criterion 1 | 1 h | read path and write-back path visually distinct |
| **Sequence diagram** | **T1** | Criterion 2 | 45 m | one incident, agent by agent, with the DataHub calls named |
| **Deployment diagram** | **T1** | Criterion 2 | 45 m | matches §F9 exactly — what actually runs where |
| Hero banner | **T1** | Criterion 5 | 1 h | name + one-line thesis, legible as a thumbnail |
| `DEMO_RUNBOOK.md` | **T1** | Criterion 2 | 45 m | exact commands + real timings + reset procedure |
| Evaluation report | **T1** | Criteria 2, 4 | ✓ RC-2 | accuracy, FP rate, per-fault table, control case |
| Benchmark report | **T1** | Criteria 2, 4 | ✓ RC-2 | latency and cost per stage, sample size stated |
| Performance report | **T1** | Criterion 2 | 1 h | cold start, p50/p95, graph fps, memory ceiling |
| API docs + OpenAPI | **T1** | Criterion 2 | 1 h | `/docs` live; spec exported to `docs/openapi.json` |
| `SECURITY.md` | **T1** | Criterion 4 | 45 m | threat model, untrusted-content boundary, least privilege |
| Shields.io badges | **T1** | Criterion 5 | 15 m | **only true badges** + a live **Demo badge** linking to the URL |
| GitHub topics + About | **T1** | discoverability | 10 m | §F10 |
| Feature icons | **T2** | polish | 45 m | one consistent set, SVG, same stroke weight |
| Module diagrams (3) | **T2** | Criterion 5 | 1 h | one per module, same visual grammar |
| Mobile preview | **T2** | polish | 30 m | only if the UI is genuinely responsive — see §F5.4 |
| Light-mode preview | **T2** | polish | — | **only if light mode genuinely exists** — see §F5.4 |
| Social preview image | **T2** | polish | 30 m | 1280×640, readable when a link is shared |
| Pinned release / docs / discussion | **T2** | polish | 20 m | §F10 |
| `CONTRIBUTING.md` | **T2** | professionalism | 30 m | setup, conventions, test requirement, PR checklist |
| `CODE_OF_CONDUCT.md` | **T2** | professionalism | 10 m | Contributor Covenant, real contact |
| `CHANGELOG.md` | **T2** | professionalism | 30 m | Keep-a-Changelog, honest history |
| `ROADMAP.md` | **T2** | Criterion 4 | 30 m | derived from Limitations, so the two agree |
| Release notes + GitHub Release | **T2** | professionalism | 30 m | tag `v2.0.0`, notes from CHANGELOG |
| Class diagram | **T2** | — | 30 m | **only if it earns its place** — see §F6.7 |
| Repository health score | **T2** | self-QA | 30 m | §F12 rubric scored honestly |

---

## §F5 — README SPECIFICATION (the most-read artifact you will produce)

### F5.1 — Above the fold, in this exact order
1. **Hero banner** — product name, one-line thesis, restrained. Must read as a phone thumbnail.
2. **One-sentence thesis.** One sentence. Not a paragraph.
3. **Badge row** — Apache-2.0 · CI status · version · Python/Node · **`▶ Live Demo`** badge linking to the replay URL. Only badges that are true.
4. **The write-back GIF** — 15 seconds: DataHub's own UI changing because an agent wrote to it. This is the single most persuasive image in the repository.
5. **Links row** — ▶ Demo video · 🔗 Live demo · 🔁 Replay a recorded incident · 🏷 Category
6. **`⚡ Quickstart`** — five commands maximum, copyable.
7. **`🆕 New for this hackathon`** — three bullets + link to `DISCLOSURE.md`.

Nothing else above the fold. This block alone must satisfy the 15- and 30-second budgets in §F2.

### F5.2 — The journey GIF *(placed immediately after the module table)*
One continuous GIF, no cuts to black, showing the whole product in sequence:
```
Home  →  Scanner  →  Nexus  →  Enterprise  →  Write-back  →  Replay
```
≤30 s, ≤8 MB, no audio, legible at half size. Each stage holds long enough to read (~4 s). This is the asset that makes a visitor understand there are three real modules rather than one demo page. Split it into per-stage GIFs (≤15 s each) for use in the module sections below.

### F5.3 — Body sections, in order
- **The problem** — one short paragraph. What breaks in a real data platform when a column is renamed upstream. Concrete, no marketing adjectives.
- **The three modules** — a table: module · one line on what it does · what makes it non-obvious · where to try it. **Enterprise first.** Each row links to its module section with its own GIF and module diagram.
- **Architecture** — the architecture SVG (§F6.1), then one short paragraph on the runtime pieces and data flow. Not a wall of boxes.
- **What DevGuard writes back to DataHub** *(this section wins Criterion 1 — do not bury it)* — artifact · exact tool or mutation name · what appears in DataHub · a real example URN. Then the guard rule plainly: *nothing is written until recovery is verified*, and what that means in practice.
- **The evidence model** — the `Evidence` contract, source and trust enums, one worked root-cause chain. Two paragraphs and a code block.
- **🤖 The agent inventory** — §F5.5 below. Mandatory.
- **Results** — evaluation table, ablation table (medians, N stated in words), cost per incident with the model named, p50/p95 loop time. Every number from an artifact.
- **Try it yourself** — three paths by effort: **live replay URL** (zero setup) → **`make demo`** (one command) → **full local stack** (documented, with the honest RAM/disk floor). Include `make doctor` and `make reset-demo`.
- **Deployment** — the deployment diagram (§F6.5) and what is running where, with the pinned commit SHA.
- **Security & governance** — summary + link to `SECURITY.md`.
- **Limitations** — three to six specific things it does not do yet and why; sample sizes; anything simulated and how it is labelled; version requirements. A judge who reads a real limitations section trusts everything above it more.
- **Footer** — category · disclosure · OSS contribution · licence · acknowledgements.

### F5.4 — Preview assets: the honest rule
- **Dark-mode previews: required.** The product is dark-themed; these are the real screenshots.
- **Light-mode preview: only if light mode genuinely exists and is maintained.** Do not build a light theme for the sake of a README image — that is scope creep with no criterion behind it, and a half-finished light mode looks worse than none. If light mode is not real, do not show one.
- **Mobile preview: only if the UI is genuinely responsive.** An instrument-panel UI is legitimately desktop-first; saying so in one line is more professional than shipping a squashed screenshot. If it is responsive, show the home page and one module.
- Same rule as everything else in this track: **the asset must depict something that is true.**

### F5.5 — 🤖 THE AGENT INVENTORY *(mandatory — a judge must never have to guess)*

States unambiguously, in one place: **how many agents exist across the platform, what each does, and what each is allowed to touch.**

- **One canonical count, identical everywhere** — README, UI status bar, video narration, Devpost description, agent-flow SVG. A count that differs between the UI and the README is exactly the detail that makes a careful judge start checking everything else.
- **Group by module**, since the modules are independent.
- **Mark model-backed vs deterministic.** "We did not put an LLM where an LLM was not needed" is a senior-engineering signal and it pre-empts the "is this just N prompt calls?" objection before it is raised.
- **Name the tool allowlist per agent.** This is what turns "multi-agent" from a buzzword into an architecture.
- **Disambiguate duplicate names across modules** (a Validator exists in both Scanner and Enterprise) — state that they are different components with different scopes, or rename one.

Table shape, one per module:

| # | Agent | Model-backed | Tool allowlist | Responsibility | Speaks / acts when |
|---|---|---|---|---|---|

Then three short subsections most submissions never write:
- **Why these boundaries** — why the pipeline is split this way rather than being one large prompt.
- **The two security-relevant facts** — the Diagnostician holds **zero tools** (text injected into a catalog description cannot cause an action), and the Scribe is the **only** agent that can write to DataHub, and only after verification.
- **How to see them work** — pointers to the live agent conversation, the decision drill-down, and the trace in SigNoz.

### F5.6 — Quality bar
No marketing adjective without a number attached · no "revolutionary / cutting-edge / game-changing" · emoji as section anchors only, never decoration · every image has alt text · every link tested · renders correctly on GitHub mobile · every code block copy-pastes and works · **passes the 15/30/60 test with a real human.**

---

## §F6 — GENERATED DIAGRAMS (produced in RC-4, before the prose that references them)

All diagrams are **generated from source files committed to the repo** (Mermaid, D2, or Graphviz in `docs/diagrams/`, rendered to SVG in `docs/assets/`), never hand-drawn in a tool nobody else can open. Source + rendered output both committed, with a `make diagrams` target. Same colour semantics as the product. All must be legible at 1080p and readable in GitHub's dark and light themes.

1. **Architecture SVG** — three modules, shared layers, external systems (DataHub, SigNoz, LLM provider, Postgres/dbt), and **the write-back path drawn as a visually distinct arrow**. The one diagram a judge will actually study.
2. **Agent-flow SVG** — the canonical roster as a pipeline: each agent, model-backed or not, its tool allowlist, and the handoff payload. Makes §F5.5 visual.
3. **Data-flow SVG** — read path (graph → agents) and write path (agents → graph) clearly separated, with the verification gate drawn as a gate.
4. **Sequence diagram** — one real incident end to end, agent by agent, with the actual DataHub tool and mutation names on the arrows. Generated from a real run's event log if possible, so it is evidence rather than illustration.
5. **Deployment diagram** — what actually runs where after §F9: hosts, services, ports, secrets boundary, which components are live in production vs local-only. **Must match reality exactly** — a deployment diagram that disagrees with the deployment is worse than none.
6. **Module diagrams (3)** — one per module, same visual grammar, for the module sections.
7. **Class diagram — only if it earns its place.** This codebase is largely functional Python and React components; a class diagram of it would be mostly boxes with no methods, which reads as filler. If there is genuinely a rich type hierarchy (the evidence/contract layer may qualify), generate a **type/contract diagram** of that instead and call it what it is. Do not generate a diagram to complete a checklist.

---

## §F7 — VISUAL ASSETS

**Screenshots** — final build only, real data, redacted (no tokens, no real emails, no internal hostnames). Required set: home page with the live status bar · Scanner result · Nexus with five modules mid-execution · Enterprise incident room · the living graph at the root-cause moment · the write-back panel with live URNs · **DataHub's own UI showing what DevGuard wrote** (the single most valuable image in the repo) · the decision drill-down · the refusal state.

**GIFs** — the journey GIF (§F5.2) plus per-stage cuts. Mandatory single-purpose GIFs: the write-back moment · the agent conversation streaming · the graph choreography at root cause · the injection attempt being caught.

**Hero banner** — name, one-line thesis, restrained. Phone-thumbnail legible.

**Feature icons** — one consistent SVG set, identical stroke weight and corner radius, semantic colours only. T2: skip entirely rather than shipping a mismatched set.

**Social preview** — 1280×640, set in repo settings so shared links render properly.

---

## §F8 — GOVERNANCE, EVIDENCE & SUBMISSION ARTIFACTS

**Governance:** `LICENSE` (Apache-2.0, correct copyright line, **verified rendering in the About panel** — the file existing is not the same as GitHub detecting it) · `SECURITY.md` (threat model: prompt injection via catalog text, over-broad mutation, runaway autonomy, token leakage, MCP supply chain; the untrusted-content boundary; mutation allowlist; least-privilege policy set; reporting address — it is currently 0 bytes, which is worse than absent) · `CONTRIBUTING.md` · `CODE_OF_CONDUCT.md` · `CHANGELOG.md` · `ROADMAP.md`.

**Evidence & reports (RC-2, before any prose):** proof pack (`evidence/proof-pack/<run-id>/` — raw MCP requests/responses with timestamps, GraphQL payloads and returned URNs, runtime evidence, capability report, resolved version matrix, before/after DataHub screenshots, `timings.json`; redacted at capture, size-capped) · evaluation report · benchmark report · performance report · API docs with `docs/openapi.json` exported · `examples/` with a README mapping each file to the call that produced it.

**Submission:** Devpost description (generated from README: thesis → problem → what it writes back naming exact DataHub surfaces → measured results → agent inventory with the canonical count → pre-existing vs new → limitations → links) · demo video (frozen build, frozen numbers, live URLs, <3:00, captions burned in, no copyrighted music, no mocked screens, speed-ups labelled) · `DEMO_RUNBOOK.md` · `JUDGING_MATRIX.md` final pass with zero TODOs · `DISCLOSURE.md` with real commit ranges · `SUBMISSION_CHECKLIST.md` all ✅ with literal paths.

---

## §F9 — LIVE DEPLOYMENT

Runs at **RC-3**, immediately after evidence generation, because the URLs are inputs to everything downstream.

### F9.1 — What must be publicly reachable
1. **The zero-setup demo (mandatory).** The replay build: the real Command Center UI driven from a committed proof pack, requiring **no DataHub, no LLM key, no database**. Static or single-container. Banner-labelled `REPLAY OF RECORDED RUN — NOT LIVE`. **This is the URL that goes in the submission**, because it is the only one guaranteed to work for a judge weeks from now.
2. **The live stack (best effort).** Frontend + backend + dependencies, if it can be hosted affordably and safely. Genuine, clearly labelled, and never the sole path a judge depends on.

**Be honest about the difference in the README.** A working replay URL plus a clear explanation beats a live URL that is down when the judge clicks it — and judging runs **weeks after submission**, so "it worked on submission day" is not a defence.

### F9.2 — Deployment checklist
- Deploy **frontend** from a **tagged commit**; render the commit SHA in the app footer.
- Deploy **backend** from the same tag. Health endpoint public; everything else rate-limited.
- **Production environment** configured from `.env.example` — every variable documented, none guessed.
- **Secrets:** server-side only. **No LLM key, DataHub token, or GMS URL ever reaches the browser bundle.** Audit the built bundle for leaked keys before going live — this is a five-minute check that prevents a catastrophic one.
- **Domain + SSL** — HTTPS everywhere, no mixed content, no certificate warnings.
- **Verify production health** — `/health/platform` returns real per-dependency status from the deployed instance.
- **Verify the replay URL** from a clean browser, incognito, on a different network, on a phone.
- **Verify the demo URL** end to end as a stranger would.
- **Verify DataHub connectivity** from production, or label it `SIMULATED`/`REPLAY` honestly if the production instance has no DataHub.
- **Verify SigNoz connectivity** from production, or label it honestly.
- **The public demo must match the repository exactly** — same tag, same commit SHA, visible in the footer, stated in the README. If they ever diverge, redeploy or fix the README; never let a judge test a build that is not the one you submitted.

### F9.3 — Cost, abuse, and survival *(the part most teams get wrong)*
- **A public endpoint that calls a paid LLM on demand is a bill and an abuse vector.** Either the public demo is replay-only (recommended), or live runs are hard rate-limited per IP, capped by a daily budget, and monitored. Never ship an unauthenticated endpoint that spends money per click.
- **CORS** narrowed from `*` to your actual origins for anything deployed.
- **The demo must stay alive through the entire Judging Period** — the rules require the project remain available for judging. Free tiers sleep, expire, or reclaim resources. Prefer a static replay deployment that cannot go to sleep; if the backend is on a free tier that idles, say so in the README and make sure the *submitted* URL does not depend on it.
- **Set a reminder to re-verify every public link on the first day of judging.** A dead link discovered by a judge scores zero regardless of what is behind it.

---

## §F10 — GITHUB REPOSITORY POLISH (RC-9)

The repo page is the 15-second surface. Treat it as product, not admin.

- **About panel:** a one-line description that is the thesis, not a category ("Closed-loop, governed incident agent that reads and writes back to the DataHub graph" — not "AI security tool"). **Website** field set to the live demo URL. **Licence detected and displayed.**
- **Topics:** `datahub` · `mcp` · `ai-agents` · `data-lineage` · `data-governance` · `observability` · `opentelemetry` · `signoz` · `llm` · `hackathon`.
- **Social preview image** uploaded, so every shared link renders as a card.
- **Pinned release** — `v2.0.0`, with notes generated from the CHANGELOG.
- **Pinned documentation** — link the docs index and `DEMO_RUNBOOK.md` prominently from the README; if using GitHub Pages for docs, set it up from `docs/` and link it in About.
- **Pinned discussion** — one thread, useful rather than promotional: "How DevGuard writes verified incident knowledge back to DataHub — design notes and open questions." A genuine technical discussion post reads as an engineer inviting review; a marketing post reads as noise.
- **Folder hygiene** — root holds only README, LICENSE, SECURITY, CONTRIBUTING, CODE_OF_CONDUCT, CHANGELOG, ROADMAP, DISCLOSURE, Makefile, compose files, `.env.example`. No build artifacts, no `.env.local`, no dead files, no commented-out blocks left as archaeology. **A cluttered repository root is the first impression of an engineering culture.**
- **Structure** a stranger can navigate:
```
backend/{core,api,enterprise}   frontend/{app,components,lib,shared}
docs/{diagrams,assets}  examples/  evidence/  recipes/  signoz/  scripts/  tests/  .github/workflows/
```

---

## §F11 — FINAL QA PROTOCOL

Four passes, in order. Each corrects a different kind of blindness.

**1. Cold machine.** A container or machine that has never seen the project. Clone → follow the README literally, typing nothing that is not written there → `make doctor` → `make demo` → `make replay` → `make eval`. Every deviation you have to make is a README bug. Fix the README, then repeat.

**2. Cold browser.** Incognito, different network, phone. Open the demo URL, the replay URL, the video, every README link, the OpenAPI docs. Anything that requires your cookies, your VPN, or your machine is broken for a judge.

**3. The 15/30/60 test.** A real person who knows nothing about the project. Timer running. At 15 s: what is this? At 30 s: what did they build, is it real? At 60 s: what does it do, why does it matter, how would you try it? Every unanswered question is a README defect. Fix and re-test with a different person.

**4. Adversarial.** Re-read the whole submission as a judge trying to reject it. Hunt specifically for: any number without a source · any claim without an artifact · any screenshot that does not match the current build · any feature named in the README the demo does not show · any leftover fabricated value · any 404 · the video's public visibility · whether the licence actually renders in About · whether the deployed SHA matches the submitted tag.

---

## §F12 — REPOSITORY HEALTH SCORE (`docs/HEALTH.md`)

| Dimension | Points | Full marks means |
|---|---|---|
| Clean-clone reproducibility | 18 | works on a fresh machine with nothing but the README |
| **Public demo reliability** | **12** | zero-setup URL, correct SHA, verified from a clean browser, survives the judging window |
| Test coverage of demoed paths | 13 | every path in the video is covered by a test |
| Documentation accuracy | 13 | every claim maps to code or an artifact |
| Evidence completeness | 13 | every number traceable to a machine-written file |
| Security hygiene | 10 | no secrets in the bundle or repo, redaction working, least privilege documented |
| Structure and readability | 8 | a stranger finds any file in under 30 seconds |
| Judge-experience test | 5 | passes 15/30/60 with someone who has never seen it |
| CI health | 4 | green, real, and the badge is honest |
| Governance docs | 2 | licence, security, contributing, conduct present and real |
| Release discipline | 2 | tagged, changelog accurate, notes published |

**Below 80 means the submission is not ready.** Score it honestly, name the two weakest dimensions, fix those first. Do not round up in your own favour — the point of a self-score is to find the gap before a judge does.

---

## §F13 — FREEZE PROTOCOL

After RC-8 (draft submitted):
- **Code freeze.** No commits to application code. Documentation typos and broken links only.
- Any bug found now goes into **Limitations**, not into a fix. A late fix invalidates the video, the numbers, and the deployed SHA.
- If a deployment must be redeployed, redeploy the **same tag**. Never deploy a hotfix that diverges from the submitted commit.
- The last day is verification only: every link, the video's public visibility, the licence in About, the demo and replay URLs, the repo being public.
- **Do not touch the code on the final day.** More submissions are lost to a last-minute change than to a missing feature.
- **After submission, set one reminder:** re-verify all public URLs on the first day of the judging period.

---

## §F14 — DEFINITION OF RELEASE

Released when a judge who has never spoken to you can, in this order and without help:

1. **15 s** — land on the repo and know what this is: banner, thesis, badges, live-demo badge, write-back GIF.
2. **30 s** — know what was built and that it is real: three modules, the agent count, DataHub visibly changed by an agent.
3. **60 s** — know what it does, why it matters, which category it entered, and how to try it.
4. Click the **live demo URL** and watch a real recorded incident with zero setup, in an incognito window.
5. Read one table and know exactly how many agents exist, what each does, and which one is allowed to write.
6. Run `make demo` on their own machine and get the same result.
7. Open DataHub and see the incident, the runbook, the annotated column, and the structured property an agent wrote.
8. Reproduce every published number from artifacts in the repo.
9. Watch a sub-3-minute video showing that exact loop with those exact numbers.
10. Read the Limitations section and find it honest.
11. Confirm the deployed build is the submitted commit.
12. Find nothing anywhere — UI, docs, diagrams, video, badges, deployment — that is invented.

If all twelve hold, the submission is finished. If any fails, that is the next task, and it outranks everything else.

---

**FREEZE THE CODE. GENERATE THE EVIDENCE. DEPLOY. THEN WRITE THE WORDS.**
**FIFTEEN SECONDS TO UNDERSTAND. SIXTY TO BELIEVE. EVERY NUMBER FROM A FILE, EVERY AGENT NAMED AND COUNTED.**
