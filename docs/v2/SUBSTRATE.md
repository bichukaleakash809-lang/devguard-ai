# The substrate — what is real and what is seeded (05_DATAHUB_MASTER §3)

**Date:** 2026-07-31 (D2) · **DataHub:** v1.6.0 · **dbt:** 1.12.0 / dbt-postgres 1.11.0

> **All hero-path lineage was ingested from the running stack. No lineage was
> hand-authored.**

That sentence is §3's hard gate. It is true, and §4 of this document is the proof
rather than the assertion.

---

## 1. What is REAL

Everything in the hero path. A real PostgreSQL holding real rows, transformed by
real dbt models, terminating in a real trained model.

| Layer | What | Real? | Evidence |
|---|---|---|---|
| Storage | PostgreSQL 16, `localhost:5433`, db `devguard` | **Real** | `substrate/docker-compose.yml` |
| Rows | `raw.users` **2,000** · `raw.orders` **20,000** | **Real** | counted from the live DB, §2 below |
| Transform | dbt Core — `stg_users`, `stg_orders`, `user_order_features` | **Real** | `dbt run` → `PASS=3 WARN=0 ERROR=0` |
| Feature table | `analytics_marts.user_order_features`, **1,715 rows** | **Real** | built by dbt from the two staging views |
| ML terminus | scikit-learn `LogisticRegression`, test accuracy **0.7995** | **Real** | `substrate/ml/artifacts/model_metadata.json` |
| Catalog metadata | 5 postgres datasets + 5 dbt datasets | **Real, ingested** | `datahub ingest` × 2, §3 below |

## 2. What is SEEDED

**The row *values* are generated** — `generate_series` in
`substrate/seed/01_raw.sql` produces `user1@example.com`, deterministic
countries, and arithmetic order amounts. Nobody's real customers are in here.

That is **not** the dishonesty §3 warns about. §3's complaint is about presenting
*datapack metadata* — describing Snowflake systems you do not own — as if it were
your own stack. Here the **database, the schema, the transformations, the
failure, and the lineage are all genuinely ours**; only the cell values are
synthetic, which is the normal state of any demo dataset.

**No sample datapack has been ingested.** There is currently no
`SEEDED CATALOG CONTEXT` volume at all, so nothing in this DataHub instance is
mislabelled. If one is added later it must carry that label, per §3.

## 3. The commands, and their real output

```
$ docker compose -f substrate/docker-compose.yml up -d
$ psql -c "SELECT count(*) FROM raw.users"      ->  2000
$ psql -c "SELECT count(*) FROM raw.orders"     -> 20000

$ dbt run
  1 of 3 OK created sql view model analytics_staging.stg_orders ....... [CREATE VIEW in 0.23s]
  2 of 3 OK created sql view model analytics_staging.stg_users ........ [CREATE VIEW in 0.24s]
  3 of 3 OK created sql table model analytics_marts.user_order_features [SELECT 1715 in 0.14s]
  Completed successfully
  Done. PASS=3 WARN=0 ERROR=0 SKIP=0 TOTAL=3

$ dbt docs generate                              -> manifest.json (543,899 B), catalog.json (5,012 B)

$ datahub ingest -c recipes/postgres.yml
  Pipeline finished successfully; produced 63 events in 24.67 seconds.   (0 failures, 0 warnings)

$ datahub ingest -c recipes/dbt.yml
  Pipeline finished with at least 1 warnings; produced 20 events in 6.63 seconds.
  (0 failures; the single warning is "URN lowercasing not applied")

$ python substrate/ml/train_churn_model.py
  trained on 1715 rows from analytics_marts.user_order_features
  test accuracy: 0.7995
```

## 4. PROOF that the lineage is ingested, not hand-authored

Three independent checks. Any one of them alone would be weak; together they
close it.

**(a) Nothing in the repository authors lineage.** Searching every source and
config file for the APIs that would be required to write it by hand:

```
$ grep -rInE "upstreamLineage|fineGrainedLineage|UpstreamClass|FineGrainedLineage|add_lineage|emit_lineage" \
    --include=*.py --include=*.yml --include=*.yaml --include=*.json substrate/ recipes/ backend/
(no matches outside substrate/dbt/target/, which dbt generates)
```

**(b) The lineage encodes transformations only a SQL parser could know.** This is
the strongest evidence, because these mappings are *not* name-matching — they are
derived from the actual aggregate expressions in the model's SQL:

| upstream column | → downstream column | the SQL that implies it |
|---|---|---|
| `stg_orders.order_id` | `order_count` | `count(o.order_id)` |
| `stg_orders.amount_cents` | `lifetime_value_cents` | `sum(o.amount_cents)` |
| `stg_orders.amount_cents` | `avg_order_cents` | `avg(o.amount_cents)` — **same source, second target** |
| `stg_orders.status` | `refund_count` | `sum(case when o.status = 'refunded' …)` |
| `stg_orders.ordered_at` | `last_order_at` | `max(o.ordered_at)` |
| `stg_users.user_id` | `user_id` | direct select |
| `stg_users.country` | `country` | direct select |

`amount_cents` fanning out to **two differently-named** columns, and `status`
becoming `refund_count`, cannot be produced by any naming heuristic. DataHub
reports these at `confidenceScore: 0.9`, the value its SQL parser assigns —
hand-authored lineage is emitted at 1.0.

**(c) The full chain resolves end to end**, each hop with column-level edges:

```
raw.users   ──5 column edges──▶  stg_users   ─┐
                                              ├─7 column edges──▶  user_order_features
raw.orders  ──5 column edges──▶  stg_orders  ─┘                            │
                                                                           ▼
                                                          scikit-learn churn model
                                                          (trained on 1,715 rows)
```

Raw evidence: `evidence/d2/03-upstreamLineage-dbt-features.json`,
`evidence/d2/04-lineage-chain.json`.

## 5. Honest limitations

* **The DataHub UI lineage *graph* did not render the upstream nodes** in the
  screenshot captured at `evidence/d2/screenshots/01-lineage.png`. The page
  correctly shows the ingested model — `Columns 7`, `Properties 12`, and the real
  SQL under View Definition — but the graph pane is empty. **The lineage is
  proven through the API, not through that screenshot**, and this document does
  not claim otherwise.

  > **Corrected in D3.** This section originally attributed the empty graph pane
  > to DataHub's "graph index lagging behind the entity index". That was wrong.
  > The graph index had never been written: all 82 OpenSearch indices carried a
  > flood-stage `read_only_allow_delete` block, so every ingestion write in this
  > document reached MySQL and was rejected at the index layer. Diagnosis, proof
  > and fix: `evidence/d3/00-opensearch-flood-stage-diagnosis.md`. **The lineage
  > claims below are unaffected** — they were proven against the aspect store,
  > not the graph. The screenshot is still stale and should be recaptured.

* ~~**The ML model is not registered in DataHub as an `mlModel` entity yet.**~~
  **Done in D3.** `urn:li:mlModel:(urn:li:dataPlatform:devguard_ml,devguard_churn_risk,PROD)`,
  with a traversable 5-hop path from `raw.users`. See `evidence/d3/README.md` §1.
* ~~**`get_dataset_queries` has not been verified** against this substrate.~~
  **Verified in D3, and the claim survives:** it returns one real SYSTEM-sourced
  query selecting `user_id` from `raw.users`. See `evidence/d3/README.md` §2.
* ~~**The rename has not been executed.**~~ **Executed in D3** at
  2026-08-01T02:16:51Z. dbt goes red; the deployed view and the ML job do not —
  which turned out to be the more interesting result. See
  `evidence/d3/break/00-README.md`.
