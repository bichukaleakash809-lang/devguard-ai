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
