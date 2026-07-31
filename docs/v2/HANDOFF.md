# DevGuard V2 handoff (05_DATAHUB_MASTER §19)

Assume the next session has zero memory of this one.

---

## Current day

**D2 — the §3 substrate gate is MET.** Real Postgres, real dbt, real ingestion,
and column-level lineage **provably derived, not hand-authored**.

Calendar: §14 dates **MWP LOCK to Aug 3**. Today is **Jul 31**. D0, D1, D2 done;
**D3 (the hero-loop break) is next and is the MWP-critical one.**

## What is green

* **Substrate live** — PostgreSQL 16 on :5433, `raw.users` **2,000** rows,
  `raw.orders` **20,000** rows.
* **dbt runs clean** — `PASS=3 WARN=0 ERROR=0`; `user_order_features` built with
  **1,715** rows. `manifest.json` + `catalog.json` generated.
* **Postgres ingested** — 63 events, **0 failures, 0 warnings**.
* **dbt lineage ingested** — 20 events, 0 failures, 1 cosmetic warning.
* **Column-level lineage PROVEN auto-generated** — `amount_cents` fans out to
  BOTH `lifetime_value_cents` and `avg_order_cents`; `status` becomes
  `refund_count`. No naming heuristic produces that; DataHub reports
  `confidenceScore 0.9` (its SQL parser), and `grep` finds no lineage-authoring
  API anywhere in the repo.
* **Full chain resolves**: `raw.users`→`stg_users`(5 col edges),
  `raw.orders`→`stg_orders`(5), both →`user_order_features`(7).
* **ML terminus trained** — LogisticRegression, test accuracy **0.7995** on 1,715
  rows.
* `docs/v2/SUBSTRATE.md` written, and its required sentence is now TRUE.
* 306 backend tests still pass; T0–T2, D0, D1 untouched.

## What is red

* **DataHub UI lineage GRAPH did not render upstream nodes** in the captured
  screenshot — graph index lag. Lineage is proven via the API, and SUBSTRATE.md
  §5 says so explicitly rather than implying the screenshot shows it.
  **Re-capture in D3.**
* **ML model NOT registered as an `mlModel` entity.** §3 requires it with lineage
  to its feature source. Trained and real; catalog registration outstanding.
* **`get_dataset_queries` NOT verified** against this substrate. §3 requires
  either genuine query history or deleting the "real SQL touching the dead
  column" claim from §2 and the video.
* **No least-privilege service account** (§11.4). Still using
  `urn:li:corpuser:__datahub_system`.
* **`api.groq.com` still unreachable** — blocks every LLM-backed agent in §6.
* **Disk: ~4.3 GB free.** SigNoz stays stopped (volumes preserved).

## The exact next command (D3)

```bash
# 1. register the ML model as an mlModel with lineage to the feature table
# 2. verify get_dataset_queries returns anything for this substrate
# 3. THE HERO-LOOP BREAK (§4 step 1) — make it really fail:
docker exec devguard-substrate-postgres-1 psql -U devguard -d devguard \
  -c "ALTER TABLE raw.users RENAME COLUMN user_id TO customer_id;"
cd substrate/dbt && dbt run     # expect FAILURE — that is the runtime evidence
python substrate/ml/train_churn_model.py   # expect FAILURE — blast radius terminus
```

## Open questions for the human

1. **Disk (~4.3 GB).** D3 adds no images, but proof-pack capture grows. Confirm
   SigNoz stays down.
2. **`api.groq.com`** — still blocked; §6 agents buildable, not demonstrable.
3. **Scope.** MWP lock is Aug 3 and D4–D6 (the agents, the write-back loop) are
   all still ahead.
