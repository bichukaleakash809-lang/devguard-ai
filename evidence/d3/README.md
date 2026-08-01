# D3 — the ML model registered, the queries verified, the loop broken

**Date:** 2026-08-01 · **DataHub:** v1.6.0 · **MCP server:** `mcp-server-datahub@0.6.0`

D3's contract gate (§14, Jul 30–31 row): *"ML model trained and registered with
lineage. Execute the rename; make it really break."*

**Result: all three of D3's asks are done, and one of them came out differently
from what the contract predicted.** That difference is documented rather than
smoothed over.

---

## 0. Before any of it — the indices were silently empty

Found while verifying step 1, and it invalidates nothing in D2 but corrects
D2's explanation of its own screenshot. Every D2 ingestion and today's first
`mlModel` write reached MySQL and never reached OpenSearch, because all 82
indices carried a flood-stage `read_only_allow_delete` block. Full diagnosis,
including why it recurred and how it was fixed:
**`00-opensearch-flood-stage-diagnosis.md`** · **`00-restore-indices.log`**

```
before:  datasetindex_v2  1   mlmodelindex_v2 0   graph_service_v1  20
after:   datasetindex_v2 10   mlmodelindex_v2 1   graph_service_v1 172
```

## 1. The ML model is registered, with lineage that a blast radius can traverse

| | |
|---|---|
| Model | `urn:li:mlModel:(urn:li:dataPlatform:devguard_ml,devguard_churn_risk,PROD)` |
| Platform | `devguard_ml` — a custom platform, **not** `mlflow`. We do not run MLflow, and an mlflow URN would claim a tool that is not in this stack. |
| Training job | `urn:li:dataJob:(urn:li:dataFlow:(devguard_ml,substrate_ml,PROD),train_churn_model)` — corresponds to `substrate/ml/train_churn_model.py` |
| Every property | read from `substrate/ml/artifacts/model_metadata.json`, which the training run wrote |

Two live-server facts shaped this and are logged as integration findings 13–14:

* `upstreamLineage` is **not** a valid aspect for `mlModel` — GMS returns 422.
* `mlModelTrainingData`, which *is* valid, stores the reference but **creates no
  graph edge**. Declared training data is not traversable lineage.

So the model carries both: `mlModelTrainingData` for the documentary record of
*why* that table is the source, and `mlModelProperties.trainingJobs` +
`dataJobInputOutput` for the edge impact analysis actually walks.

**The chain resolves end to end** (`03-blast-radius-raw-users-BEFORE-break.json`):

```
hop 1  raw.users            (postgres / dbt)
hop 2  stg_users
hop 3  user_order_features
hop 4  train_churn_model    DATA_JOB
hop 5  devguard_churn_risk  MLMODEL
```

Evidence: `01-mlmodel-entity.json` · `01b-mlmodeltrainingdata-raw-aspect.json` ·
`02-lineage-featuretable-to-model.json` · `03-blast-radius-raw-users-BEFORE-break.json`

## 2. `get_dataset_queries` — verified, and it returns real SQL

§3 required *"either genuine query history or deleting the 'real SQL touching the
dead column' claim."* **The claim survives.** (`04-get_dataset_queries.json`)

| call | total |
|---|---|
| `get_dataset_queries(urn=raw.users)` | **1** |
| `get_dataset_queries(urn=raw.users, column="user_id")` | **1** |
| `get_dataset_queries(urn=user_order_features)` | 0 |

The one query is real, `source: SYSTEM`, actor `urn:li:corpuser:_ingestion` —
derived by the PostgreSQL ingestion from the view definition, not written by us:

```sql
SELECT user_id, email, country, signup_ts, is_active
FROM raw.users
WHERE is_active
```

That is SQL touching `user_id` on the exact table the rename targets, and the
`column="user_id"` filter genuinely narrows to it. The feature table returns 0,
honestly: it is a table, not a view, so there is no definition to derive a query
from and no query-log ingestion is configured.

The same query entity appears **inside the column-level lineage path** in step 4,
which is what ties "there is SQL touching this column" to "here is where it goes".

## 3. The break — executed, and it did not do what §4 predicted

`ALTER TABLE raw.users RENAME COLUMN user_id TO customer_id;` at
**2026-08-01T02:16:51Z**.

§4 predicts *"dbt model + reporting query + feature job break."* One of the three
broke:

* **dbt: exit code 1.** `column "user_id" does not exist`, `stg_users` ERROR,
  `user_order_features` SKIP.
* **The reporting view did not break.** PostgreSQL binds views by attribute
  number and rewrote it to `SELECT customer_id AS user_id`. Still returns 1715 rows.
* **The feature job did not break.** The mart was SKIPped, not dropped, so it is
  frozen and still has a `user_id` column. The model retrained on stale data,
  reported the same **0.7995**, exit 0.

This is drift, not an outage, and it is the stronger story: the only signal in
the entire stack is one exit code, while everything downstream reports success on
data that no longer reflects its source. Full write-up and all five raw
transcripts: **`break/00-README.md`**

## 4. Blast radius, lineage impact, write-back

**Blast radius via the §4 step-6 tools** (`05-blast-radius-mcp.json`) — all six
calls green:

```
get_lineage(raw.users, column="user_id")   -> lineageColumns ["user_id"] on both hops
get_lineage(user_order_features, hops=2)   -> DATA_JOB, MLMODEL
get_lineage(devguard_churn_risk, upstream) -> DATA_JOB, user_order_features
```

**Column-level lineage impact** — `get_lineage_paths_between` with
`source_column="user_id"`, and note the **query entity in the middle of the path**:
it is the same `view_5ba31a4e…` that `get_dataset_queries` returned in step 2.

```
raw.users.user_id
  -> urn:li:query:view_5ba31a4e6865c40d…
  -> stg_users.user_id
  -> user_order_features.user_id   (dbt, then postgres)
```

Getting that call to work required finding a GMS bug first — see
`06-graphql-npe-proof.txt` and integration finding 16.

**Write-back** (`writeback/`) — deliberately narrower than §8's five-artifact
package, because §8 says that package is *post-verification only* and nothing
here is verified yet. What was written is §4 step 10, which legitimately precedes
remediation:

| Artifact | Result |
|---|---|
| `raiseIncident` on `raw.users`, left **ACTIVE** | `urn:li:incident:f01f744b-50fb-446d-96a1-4ecf43bc3001`, reads back `total: 1` |
| Column-level tag on `user_id` | `urn:li:tag:devguard_incident_impacted` |
| Column-level description on `user_id` | records the drift, the Postgres view rewrite, and the incident URN |
| `devguard.last_incident_id` | `f01f744b-50fb-446d-96a1-4ecf43bc3001` |

Not written, on purpose: `devguard.verified_at` and
`devguard.time_to_root_cause_s` (nothing is verified), the Context Document (it
is the verified-knowledge artifact), and `updateIncidentStatus(RESOLVED)` (the
incident is real and still open).

**The D1 smoke-test placeholders were removed.** `verified_at =
2026-07-31T12:45:00Z` and `time_to_root_cause_s = 42.0` were write-path proof
values sitting on a real dataset, where they read as real measurements. They are
gone. The definitions are now committed as code at
`recipes/structured_properties.yaml`, which closes §5's "register the definitions
in the repo" trap.

## 5. Honest limitations

* **The catalog has not been re-ingested since the break**, so DataHub still
  describes `raw.users.user_id`. That is deliberate — DevGuard's claim is that it
  detects from *runtime evidence*, not from a catalog diff, and the catalog being
  stale too is part of the incident. Nothing here claims the catalog noticed.
* **The UI lineage graph has not been re-screenshotted** since the index rebuild.
  `evidence/d2/screenshots/01-lineage.png` shows an empty graph pane and is now
  known to be a symptom of the flood-stage block, not of index lag. The
  corrected explanation is in `00-opensearch-flood-stage-diagnosis.md`; the
  screenshot itself is still stale and should be recaptured.
* **The credential is still `urn:li:corpuser:__datahub_system`.** §11.4's
  least-privilege service account remains outstanding, exactly as flagged in D1.
* **Nothing has been fixed.** The rename is still in place, dbt is still red, and
  the model is still training on a stale table. Remediation, verification and the
  five-artifact write-back are D4+.
