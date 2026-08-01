# Integration log — DevGuard V2 (05_DATAHUB_MASTER §16)

Every rough edge actually hit while integrating DataHub. This is simultaneously
the **OSS contribution candidate list** and the **Most Valuable Feedback survey**
material (10 × $50). §16: *"File the cheap one early — do not schedule the bonus
for the last day."*

Only real, encountered friction goes here. Nothing anticipated, nothing repeated
from documentation.

---

## D0 — 2026-07-31

| # | Surface | What happened | Contribution candidate? |
|---|---|---|---|
| 1 | Docker images | **`linkedin/datahub-gms` is stale.** Its newest semver tag is **v0.13.0**; there are no v1.x tags at all (6,250 tags checked, `head` and `latest` present). Current images live under **`acryldata/`** — `acryldata/datahub-gms` has v1.0.0 … **v1.6.0**. The contract's own §5 deployment snippet and much public material still reference the `linkedin/*` org, so anyone pinning from it silently gets a 2023-era build. | **Yes — docs fix.** Cheap, verifiable, exactly the §16-1 class ("documentation fix … verify it is still live first"). |

| 2 | `datahub docker quickstart` | **SystemUpdate crash-loops on a constrained disk, with an unactionable error.** `Failed Step 8/38: BuildIndicesStep` → `SystemUpdate completed with result FAILED` → compose restarts it forever. The surfaced log gives an OpenSearch stack trace with no reason string, so the actual cause is invisible from the failing container. It had to be read out of OpenSearch directly: `GET /_cluster/settings` showed **`"persistent": {"cluster.blocks.create_index": "true"}`**, and `GET /_cat/allocation` showed `disk.percent 97`. The flood-stage watermark had latched a persistent cluster-wide create-index block, and nothing in DataHub's output says so. Fix: clear `cluster.blocks.create_index` and raise the watermarks. | **Yes — two candidates.** (a) A docs note that a >95%-full disk latches a persistent index-creation block and how to clear it. (b) A genuine UX bug report: `BuildIndicesStep` should surface the OpenSearch `reason`, and quickstart should fail fast instead of restart-looping on a non-transient error. |
| 3 | Environment / `df` | **`df` understates disk pressure in a per-session-allowance sandbox.** `df -h /` reported 82% used with 6.8 GB avail; OpenSearch computed **97%** from the same filesystem and acted on that. Anyone sizing a DataHub deployment from `df` alone in a similar sandbox will hit the same wall. Recorded here because §18's row "DataHub + substrate exceed local RAM/disk" is exactly this risk, and the measurement that matters is OpenSearch's, not `df`'s. | Note for `RISKS.md`; not upstream-actionable |

| 4 | MCP tool set | **The live server exposes 18 tools; §5 lists 25.** Per §5 ("if the live server disagrees, the live server wins"), the live set is authoritative. Missing: `search_documents`, `grep_documents`, `get_me`, `list_pending_proposals`, `find_sql_context`, `draft_sql_for_tables`, `set_lifecycle_stage`. **`search_documents`/`grep_documents` being absent is EXPECTED and predicted** — §5's own trap says they are "automatically hidden when the catalog has no documents", and this instance is clean. That is capability negotiation working, not a fault, and it is why the Archivist must degrade deliberately rather than throw. The other five are genuine gaps against the contract's list. All 12 mutation tools DevGuard needs **are** present, including `save_document`. Evidence: `evidence/d0/mcp-tool-list.json` | **Yes** — the hidden-document-tools behaviour is §16-3's "docs note that document tools are hidden on an empty catalog", now confirmed first-hand rather than anticipated. |
| 5 | MCP server versioning | **The package version and the server's self-reported version disagree.** `mcp-server-datahub@0.6.0` from PyPI reports `serverInfo.version = "3.4.5"` over the wire. Anyone recording "MCP server version" from the handshake gets a number that cannot be installed, and anyone pinning from PyPI cannot match it to a running server. Minor, but it defeats the §5 requirement to "record resolved versions into every proof pack". | Possible small bug report |

| 6 | GraphQL incidents | **`updateIncidentStatus` takes `IncidentStatusInput!`, not `UpdateIncidentStatusInput!`.** The contract's §5 signature (taken from public material) is wrong: `Validation error (VariableTypeMismatch@[updateIncidentStatus]) : Variable 'input' of type 'UpdateIncidentStatusInput!' used in position expecting type 'IncidentStatusInput!'`. | **Yes — docs fix.** Cheap and verifiable. |
| 7 | Context Documents | **There is no `Runbook` document type.** §5 advertises "typed Runbook / FAQ / Policy / Decision Log" and §8 artifact 2 is literally "subtype Runbook". The live `save_document` enum is `Insight, Decision, FAQ, Analysis, Summary, Recommendation, Note, Context` — `Runbook`, `Policy` and `Decision Log` are all absent. This materially changes the write-back package design. DevGuard uses **`Analysis`** as the nearest honest alternative (§8: "implement the nearest honest alternative, never silently skip"). | **Yes — strong candidate.** Either a docs correction, or an RFC arguing `Runbook` is the obvious missing type for incident-response knowledge — which is exactly the §16-2 headline framing ("a genuine, usage-born gap"). |
| 8 | `add_tags` | **A tag entity must exist before it can be applied**, and the error does not say so: *"Failed to validate label with urn urn:li:tag:devguard_incident_impacted"*. §5 documents this trap for structured properties but not for tags, so it reads as a surprise. | Yes — docs note, same family as the structured-property trap already listed in §16-3 |
| 9 | `add_structured_properties` | **Two undocumented shape requirements.** Keys must be full URNs — a qualified name gives *"Urn doesn't start with 'urn:'"* — and every value must be a **list**, even for `SINGLE` cardinality (*"Input should be a valid list"*). Neither is in §5. | Yes — docs note |

| 10 | `datahub ingest` (postgres) | **The `postgres` source is not installed by `pip install acryl-datahub`.** First run died with `Failed to find a registered source for type postgres: postgres is disabled due to a missing dependency: sqlalchemy`. The error names the fix (`pip install 'acryl-datahub[postgres]'`), so this is minor — but the contract's §5 install line (`pip install datahub-agent-context`) does not mention that ingestion sources need extras, and a recipe committed per §3 will not run without them. | Docs note |
| 11 | `datahub ingest` | **`stateful_ingestion.enabled: true` silently requires a top-level `pipeline_name`.** Failure: `Failed to configure the source (postgres): pipeline_name must be provided if stateful ingestion is enabled.` The requirement is not in the recipe examples the contract quotes, and the field lives at the ROOT of the recipe, not under `source.config` where you would look for it. | Docs note |
| 12 | CLI log redaction | **The CLI redacts env-var *values* out of its own logs, including in URNs.** With `SUBSTRATE_PG_DB=devguard` exported, ingested URNs printed as `urn:li:dataset:(urn:li:dataPlatform:postgres,***REDACTED:SUBSTRATE_PG_DB***.raw.users,PROD)`. Good instinct, but it fires on any value that appears in output — here a database name that is also part of every URN — which makes logs hard to read and could mislead someone debugging URN mismatches. Cosmetic, recorded for completeness. | Low-value bug report |

## D3 — 2026-08-01

| # | Surface | What happened | Contribution candidate? |
|---|---|---|---|
| 13 | Entity model — `mlModel` | **`upstreamLineage` is not a valid aspect for `mlModel`.** The obvious way to give a model lineage to its feature table is rejected: `Unable to emit metadata to DataHub GMS: Unknown aspect upstreamLineage for entity mlModel` (HTTP 422). The live entity registry — read from GMS's own `/openapi/v3/api-docs/openapi-v3`, which is the only place it is enumerable — lists **`mlmodeltrainingdata`** instead (SDK: `TrainingDataClass`, `ASPECT_NAME = mlModelTrainingData`). | Docs note. The 422 names the aspect but not the alternative; a one-line "use `mlModelTrainingData`" would have saved the whole investigation. |
| 14 | Entity model — `mlModel` | **`mlModelTrainingData` produces no graph edge.** The aspect stores and reads back correctly over REST (`evidence/d3/01b-…`), but after emitting it `graph_service_v1` contains **zero** edges touching the model, `GET /openapi/v3/relationship/mlmodel/<urn>` returns `{"results":[]}`, and the feature table's `lineage(DOWNSTREAM)` does not reach it. So a blast radius **cannot traverse to a model through its declared training data** — the aspect is documentary only. The traversable modelling is `mlModel --TrainedBy--> dataJob --Consumes--> dataset`, via `mlModelProperties.trainingJobs` + `dataJobInputOutput`. | **Yes — strong candidate.** Either the relationship annotation is missing on `BaseData.dataset`, or the docs should say plainly that training-data lineage is not graph lineage. This is the difference between "the model is catalogued" and "impact analysis finds the model". |
| 15 | GraphQL — `mlModel.trainingData` | **Reads back `null` for an aspect that is definitely stored.** `GET /openapi/v3/entity/mlmodel/<urn>/mlmodeltrainingdata` returns the full payload; the GraphQL field `mlModel { trainingData { dataset motivation preProcessing } }` returns `null` for the same entity at the same moment. A mapper gap, not a write failure. | Yes — bug report, small and precise |
| 16 | GraphQL — structured properties | **A string-valued structured property whose value looks like a URN 500s `searchAcrossLineage`.** `devguard.last_incident_urn` (declared `datahub.string`, `SINGLE`) held `urn:li:incident:b2f18c7e-…`. Any lineage search whose results include that dataset died with `Cannot invoke "…generated.Entity.getUrn()" because "entity" is null` at path `searchAcrossLineage.searchResults[3].entity.structuredProperties.properties[2].valueEntities`. **That takes down the MCP tool `get_lineage_paths_between`**, which §4 step 6 depends on. Proven by removing only that one property value and re-running the same call: error → success, nothing else changed (`evidence/d3/06-graphql-npe-proof.txt`). | **Yes — the strongest candidate so far.** A 500 NPE, reachable from ordinary user data, that silently disables impact analysis. The resolver appears to attempt entity resolution on any string that parses as a URN and does not null-check the result. |
| 17 | `mcp-server-datahub` on a restricted network | **The server blocks ~90 s per tool call retrying Mixpanel telemetry.** `get_lineage` completes server-side in ~0.2 s (`get_lineage downstreams: Returned 2/2 entities`), then the process stalls on `POST /mp/track` and `/mp/engage` with four urllib3 retries each, because this environment 403s them at CONNECT. Every call looked like a hang. `DATAHUB_TELEMETRY_ENABLED=false` fixes it completely. | Yes — telemetry should be fire-and-forget or short-timeout; it should never sit on the response path. |
| 18 | MCP argument names | **Three more tools whose argument names cannot be guessed**, continuing the D1 pattern: `get_dataset_queries` takes `urn` (not `dataset_urn`); `get_lineage_paths_between` takes `source_urn`/`target_urn` (not upstream/downstream); `add_structured_properties` takes `property_values` while `remove_structured_properties` takes `property_urns` + `entity_urns`. Every one of these was a validation error before reading the live `inputSchema`. | Recorded as a habit note rather than a bug: **always read `inputSchema` from the running server.** |

## D4 — 2026-08-01

| # | Surface | What happened | Contribution candidate? |
|---|---|---|---|
| 19 | `get_lineage` | **Column-level and dataset-level lineage have different termini, so §4 step 6's "blast radius, column-level, terminating at the ML model" is not satisfiable in one call.** `get_lineage(urn=raw.users, column="user_id", max_hops=5)` returns **5 entities**, all datasets, every one carrying `lineageColumns: ["user_id"]`, stopping at `user_order_features`. The same call *without* `column` returns **7**, continuing through `train_churn_model` (dataJob) to the mlModel at hop 5. Neither is wrong: this is finding 14's direct consequence — the model's edge is `dataJob --Consumes--> dataset`, which is dataset-level, so a schemaField traversal cannot reach it. DevGuard therefore runs **both** traces and reports them as two separate facts; summing them would be a fabricated count and picking one would either understate impact or lose column precision. | **Yes — docs, and possibly a feature.** Impact analysis is the headline use case, and "the precise answer and the complete answer are different queries" is not stated anywhere. Ideally column-level lineage would traverse dataset-level edges when no column edge exists, and mark those hops as column-unknown. |
| 20 | MCP capability negotiation | **The tool set is dynamic in both directions, and D0 vs D4 demonstrates both.** D0 saw **18** tools (mutations enabled, empty catalog) — 6 read + 12 mutation, with `search_documents`/`grep_documents` **absent**. D4 saw **8** (mutations disabled, one document now exists) — the same 6 read tools plus the 2 document tools, with every mutation tool gone. So §5's documented trap is confirmed from the side D0 could not show: the document tools **appear** once the catalog holds a document. Worth stating plainly because a client that caches its tool list, or asserts a fixed count, is wrong on both axes. The corollary is a pleasant one: `TOOLS_IS_MUTATION_ENABLED=false` is genuine transport-level least privilege — a read-only agent cannot see a mutation tool, let alone call it. | Docs note. The mutation gate deserves a sentence in §5 as a security control, not just a feature flag. |

### A DevGuard defect this phase found in our own code, recorded here for symmetry

Not DataHub friction, but it belongs next to the findings above because it was
caught by the same discipline and would have produced a fabricated number.

**`get_lineage` responses embed `entity` objects inside their facet
aggregations** — the platform and container filter chips. DevGuard's first
Pathfinder parser walked the whole response and counted those as impacted
assets, so a trace that genuinely touched **5** datasets was reported as **9
impacted**, having swept in `urn:li:dataPlatform:postgres`,
`urn:li:dataPlatform:dbt` and two container URNs. An inflated blast radius is a
LAW 3 violation, and the plausible-looking kind is the dangerous kind. The tell
was in the data: every spurious entry had `degree: null`, because facets have no
hop count. Fixed to read `searchResults` only, cross-checked against the
server's own `total`, and pinned by `tests/test_pathfinder_parsing.py` using the
real captured payload.

## D6 — 2026-08-03

| # | Surface | What happened | Contribution candidate? |
|---|---|---|---|
| 21 | `add_owners` | **`ownership_type` is REQUIRED on `add_owners` and OPTIONAL on `remove_owners`**, and the accepted values are internal identifiers, not the friendly names the description uses. The first full write-back run failed artifact 5 with `ownership_type: Missing required argument`; the live enum turns out to be `__system__technical_owner` / `__system__business_owner` / `__system__data_steward`, while the field's own description talks about `TECHNICAL_OWNER`, `BUSINESS_OWNER`, `DATA_STEWARD`. D1 deliberately left this tool unexercised ("the same shape as `add_tags`, which is proven") — and it was not the same shape. | **Yes — two.** (a) The add/remove asymmetry deserves a line in the docs. (b) The description names three values the enum does not accept; either the description or the enum should change. |
| 22 | `search_documents` + `grep_documents` | **They are a two-stage API and nothing says so.** `search_documents(query)` returns `searchResults[].entity` with `urn`, `subType` and `info.title` — and deliberately **no content** ("to avoid context bloat", per the shipped GraphQL comment). `grep_documents` then requires `urns` **and** `pattern`, so it cannot be called standalone: its input is the previous tool's output. A client that calls them independently, as ours did, gets a hit list it cannot read and a grep that fails validation. The symptom was the dangerous kind — DevGuard reported a confident "NO PRIOR KNOWLEDGE" while the runbook it had written minutes earlier was in the result set. | **Yes — docs.** The retrieval half of the hero loop depends on this pairing, and the dependency is invisible from either tool's schema alone. A one-line "use the URNs from `search_documents`" in `grep_documents`' description would have prevented it. |

### DevGuard defects this phase found in our own code

Recorded here for symmetry, and because each needed the loop to actually run —
no test would have caught them.

1. **`add_owners` arguments were guessed, not read.** Finding 18's lesson,
   repeated by us. The upside was real evidence for §8: the partial-failure
   policy correctly **held the incident ACTIVE** rather than asserting a
   verified state whose supporting knowledge was missing.
2. **A false "NO PRIOR KNOWLEDGE".** See finding 22. The worst failure mode
   this agent has, and it reported success while doing it. D4 and D5 were
   re-checked and are unaffected — both genuinely returned `total: 0`.
3. **A dry run reported a partial failure that never happened.**
   `SKIPPED_DRY_RUN` was not counted as "landed", so a preview cascaded into
   §8's partial-failure path. Nothing had failed; nothing had been attempted.

### Carried in from the SigNoz track (same class of finding, different product)

Not DataHub feedback, but recorded because it is exactly the kind of entry this
log is for, and it demonstrates the habit is already running:

* SigNoz v0.135.0: `POST /api/v1/dashboards` returns `501 dashboard_deprecated`;
  v2 is required. `/api/v1/login` returns SPA HTML — the real endpoint is
  `POST /api/v2/sessions/email_password` and it **requires an `orgId`** that no
  unauthenticated endpoint exposes.
* SigNoz alert rules: `POST /api/v1/rules` rejects every payload with one opaque
  line naming no field; `/api/v2/rules` returns field-level errors. The schema was
  only recoverable from the shipped source maps.
* The signoz-otel-collector will not open its OTLP receiver until an
  organisation exists, while still logging *"Everything is ready"* and reporting
  healthy — a silent-drop failure mode.
