# D4 — the evidence chain forms

**Date:** 2026-08-01 · **DataHub:** v1.6.0 · **MCP server:** `mcp-server-datahub@0.6.0`

D4's half of the §14 gate for the D4–D5 row is **"Evidence chain formed"**.
(The other half, *"refusal demonstrated"*, is the Diagnostician and is D5.)

**Result: the chain forms, on real evidence, and it is sufficient under §7.**

```
evidence items      : 12
sources             : ['DATAHUB_GRAPH', 'RUNTIME']
chain digest        : a16d2927e4e56487
CHAIN IS SUFFICIENT : True
```

Reproduce it:

```bash
DATAHUB_TOKEN_FILE=<token> DBT_BIN=<dbt> \
  python scripts/run_d4_evidence_chain.py --run-id d4-evidence-chain
```

Proof pack: **`evidence/proof-pack/d4-evidence-chain/`** — 13 artifacts, every
one redacted at capture time.

---

## What was built

§4 steps 2 and 4–8, as five bounded roles with typed boundaries:

| §4 step | Agent | Module | Kind |
|---|---|---|---|
| 2 · REAL failure | Watcher | `backend/v2/agents/watcher.py` | deterministic |
| 4 · capability negotiation | Archivist | `backend/v2/agents/archivist.py` | tools |
| 5 · graph context | Cartographer | `backend/v2/agents/cartographer.py` | tools |
| 6 · blast radius | Pathfinder | `backend/v2/agents/pathfinder.py` | tools |
| 7 · untrusted-text screen | Sentinel | `backend/v2/sentinel.py` | deterministic |
| 8 · prior knowledge | Archivist | (as above) | tools |

Plus the two contracts everything else hangs off: `backend/v2/evidence.py` (§7)
and `backend/v2/handoff.py` (§6's envelope and the tool allowlists), and
`backend/v2/proofpack.py` (§12's redact-at-capture-time writer).

**None of these five agents calls an LLM**, and that is a deliberate, stated
choice rather than a workaround for the Groq blocker. §6 explicitly endorses it:
*"Several are deterministic and use no model at all — say so in the README,
because 'we did not put an LLM where an LLM was not needed' is a senior-
engineering signal."* Detection is an exit code; capability negotiation is a
tool list; URN resolution and lineage traversal are graph reads. A model would
make each of them less reliable, and the one thing §7 will not let a root cause
form without — `RUNTIME` evidence — is the last place anything probabilistic
belongs. The Diagnostician, which is where judgement actually happens, is D5.

## The chain, as it really came out

| id | source | claim |
|---|---|---|
| EV-D4-001 | RUNTIME | `` `dbt run` exited 1 (PASS=1 ERROR=1 SKIP=1) `` |
| EV-D4-002 | RUNTIME | model stg_users failed to build (models/staging/stg_users.sql) |
| EV-D4-003 | RUNTIME | database reports column "user_id" does not exist |
| EV-D4-004 | RUNTIME | 1 downstream model(s) SKIPped — not rebuilt, not dropped, therefore stale |
| EV-D4-005 | RUNTIME | MCP server offered 8 tools; document tools present |
| EV-D4-006 | DATAHUB_GRAPH | 'stg_users' resolves to `…postgres,devguard.analytics_staging.stg_users,PROD` |
| EV-D4-007 | DATAHUB_GRAPH | catalog schema for stg_users has 5 columns: country, email, is_active, signup_ts, **user_id** |
| EV-D4-008 | DATAHUB_GRAPH | 7 downstream entities impacted within 5 hops of devguard.raw.users (dataset-level) |
| EV-D4-009 | DATAHUB_GRAPH | 5 entities carry column user_id downstream of devguard.raw.users (column-level) |
| EV-D4-010 | DATAHUB_GRAPH | blast radius terminates at registered ML model `…devguard_ml,devguard_churn_risk,PROD` |
| EV-D4-011 | DATAHUB_GRAPH | column-level path is 5 hops via column user_id |
| EV-D4-012 | DATAHUB_GRAPH | 1 catalog query references user_id (source: SYSTEM) |

**EV-D4-007 is the incident in one line.** The catalog still lists `user_id`;
EV-D4-003 says the database does not have it. Nothing reconciles those two — the
gap between them is the drift, and an agent that "helpfully" smoothed it over
would destroy the finding.

**EV-D4-008 independently reproduces D3.** Seven impacted entities, terminating
at the mlModel — the same number D3 got through a completely different path
(raw GraphQL `searchAcrossLineage` rather than the MCP `get_lineage` tool).

## The handoff rail (§6's envelope, as captured)

```
watcher      -> cartographer   OK     0.8ms  tools=0  ev=4
archivist    -> cartographer   OK    57.0ms  tools=2  ev=1
cartographer -> pathfinder     OK   257.3ms  tools=2  ev=2
pathfinder   -> diagnostician  OK   852.2ms  tools=4  ev=5
```

Every duration is measured, never supplied — `AgentHandoff` has no settable
`duration_ms` field, and a test pins that. LAW 5.

## Two things the live system taught us, and one defect of our own

### 1. "Column-level, terminating at the ML model" is two queries, not one

§4 step 6 asks for a blast radius that is *"column-level … terminating at the ML
model"*. The live graph will not do both at once:

* **column-level** (`get_lineage(column="user_id")`) → **5 entities**, all
  datasets, each carrying `lineageColumns: ["user_id"]`, stopping at
  `user_order_features`.
* **dataset-level** (no `column`) → **7 entities**, continuing through
  `train_churn_model` to the mlModel at hop 5.

This is D3's finding 14 playing out: the model's edge is
`dataJob --Consumes--> dataset`, which is dataset-level, so a schemaField
traversal cannot reach it. The Pathfinder therefore runs **both** and reports
them as two distinct facts. Summing them would be a fabricated count; picking
one would either understate the impact or throw away the column precision.
Logged as integration finding 19.

### 2. Capability negotiation works, in both directions

D0 saw **18** tools; D4 saw **8**. Both are correct:

| | D0 | D4 |
|---|---|---|
| mutations enabled | yes | **no** (read-side agents) |
| documents in catalog | none | one (created in D1) |
| read tools | 6 | 6 |
| mutation tools | 12 | **0** |
| `search_documents` / `grep_documents` | **absent** | **present** |

D0 confirmed §5's trap from the "hidden" side. D4 confirms it from the other:
the document tools **appear** once a document exists. And
`TOOLS_IS_MUTATION_ENABLED=false` turns out to be real transport-level least
privilege — a read-only agent cannot see a mutation tool, never mind call one.
Logged as finding 20.

The Archivist reported **OK**, not DEGRADED, and correctly: retrieval ran and
matched nothing. That distinction is the point of the agent —
*"there is no prior runbook"* and *"retrieval is unavailable"* lead to different
downstream behaviour, and conflating them is how a system reports a clean bill
of health while its retrieval is down.

### 3. A defect of ours, found by running it

The first live run reported **9 impacted entities** where the server's own
`total` said **5**. The Pathfinder's parser walked the entire response and
counted the `entity` objects inside DataHub's **facet aggregations** — two
`dataPlatform` URNs and two `container` URNs — as impacted assets.

An inflated blast radius is a fabricated metric, and the plausible-looking kind
is the dangerous kind: 9 is not absurd, and nobody would have questioned it. The
tell was in the data — every spurious entry had `degree: null`, because facets
have no hop count.

Fixed to read `searchResults` only and cross-checked against the server's
`total`. Pinned by `tests/test_pathfinder_parsing.py` against the real captured
payload, so the exact response shape that caused it is now a regression fixture.

## Security properties, and where they are actually enforced

§6 promises four. Each is a property of the code, asserted in
`tests/test_agent_allowlists.py`:

| Promise | Where it lives | Test |
|---|---|---|
| Diagnostician has no tools | `AGENT_TOOL_ALLOWLISTS["diagnostician"] == frozenset()` | `test_diagnostician_refuses_every_tool` |
| Only Scribe can mutate | no other allowlist intersects `MUTATION_TOOLS` | `test_only_scribe_holds_mutation_tools` |
| Allowlist enforced, not documented | first statement of `DataHubMCPClient.call` | `test_call_checks_allowlist_first` (AST-parsed, so a comment cannot satisfy it) and `test_overreach_raises_without_a_running_server` (no subprocess is started) |
| Catalog text is never instruction | `ScreenedText` exposes `.fenced` and no raw prompt accessor | `test_there_is_no_raw_prompt_accessor` |

One refactor supports this: `UNTRUSTED_CONTENT_RULE` and `fence_untrusted()`
moved from `backend/core/ai_agent.py` into a new zero-import leaf module
`backend/core/untrusted.py`, re-exported so every existing caller and T1's
`tests/test_prompt_injection_boundary.py` are unchanged. They moved because
importing them dragged in OpenTelemetry and the whole LLM runtime — fencing a
catalog string should not require a working telemetry stack, and a security
primitive that is expensive to import is one people route around.

## Honest limitations

* **No LLM ran.** Five of the six agents here genuinely do not need one, but
  that is a claim about *these* agents, not about the loop. The Diagnostician
  does need one, and `api.groq.com` remains blocked by the environment's egress
  policy — unchanged since T2 §6.3. D5 will build the reasoning path and its
  refusal path, and the refusal path is testable without a live key while the
  success path is not.
* **`untrusted items : 0`** in this run. The Sentinel screened every catalog
  description the Cartographer read and found nothing, because nothing hostile
  has been seeded yet. §11.7's injection demo beat is not built. The screen is
  tested against the contract's own example string in
  `tests/test_sentinel_fencing.py`, but it has not yet met a hostile description
  *in the live catalog*, and this document does not claim it has.
* **The chain stops at step 8.** Steps 9–19 — root cause, incident, fix,
  validation, approval, remediation, recovery, write-back, ablation — are D5+.
  Nothing here diagnoses anything.
* **The substrate is still broken**, deliberately, from D3. The rename stands,
  `dbt run` still exits 1, and the ML model still trains on a stale table. That
  is what makes this run's evidence real; do not repair it before D5.
* **Still `urn:li:corpuser:__datahub_system`.** §11.4's least-privilege service
  account remains outstanding, now for the fourth phase running. The mutation
  gate demonstrated above is transport-level least privilege, which is *not* the
  same thing as a scoped DataHub Access Policy.
