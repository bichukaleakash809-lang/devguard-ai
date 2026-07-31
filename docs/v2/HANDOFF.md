# DevGuard V2 handoff (05_DATAHUB_MASTER §19)

Assume the next session has zero memory of this one.

---

## Current day

**D1 — the write-path gate is MET.** D0.3 (stand up DataHub, dump the tool list)
was finished first, since D1 depends on it.

Calendar: §14 dates D0 to Jul 28 and **MWP LOCK to Aug 3**. Today is **Jul 31**.
D0+D1 are done; **D2–D3 (substrate ingestion) are not**.

## What is green

* **DataHub Core v1.6.0 running and healthy** — GMS + frontend healthy, version
  read back from the instance (`059a36c0b035…`), not from docs.
  `versions.env` `DATAHUB_VERSION` is now filled from that reading.
* **MCP connected; tool list dumped and committed** — `evidence/d0/mcp-tool-list.json`,
  18 tools, plus full input schemas in `mcp-tool-schemas.json`.
* **EVERY §8 WRITE PATH PROVEN with captured raw responses** (`evidence/d1/`):
  * `raiseIncident` → real incident URN
  * `updateIncidentStatus(RESOLVED)` → read back ACTIVE=0, RESOLVED=1
  * `add_tags` on a **column** → success
  * `update_description` on a **column** → success
  * `save_document` → real document URN
  * `devguard.*` structured property **definitions registered**, values set
* 306 backend tests still pass; nothing in T0–T2 was touched.

## What is red

* **Substrate NOT ingested.** `substrate/` (Postgres compose + seed SQL + dbt
  project + ML training script) and `recipes/*.yml` are **written but never run**.
  §3's hard gate — *"lineage in DataHub is ingested from the substrate,
  provably"* — is **NOT met**, and `docs/v2/SUBSTRATE.md` is deliberately not
  written yet because its required sentence would be false.
* **No least-privilege service account.** D1 used
  `urn:li:corpuser:__datahub_system` (manageIngestion + managePolicies) — the
  opposite of §11.4. Scoped account + Access Policies still to configure.
* **`api.groq.com` still unreachable** — blocks every LLM-backed agent in §6.
* **Disk: ~6 GB free.** DataHub is using ~11 GB of images. The substrate Postgres
  and dbt still have to fit. SigNoz is stopped (volumes preserved) to make room.

## The exact next command

```bash
docker compose -f substrate/docker-compose.yml up -d      # real Postgres, port 5433
cd substrate/dbt && dbt run                                # produces target/manifest.json
datahub ingest -c recipes/postgres.yml
datahub ingest -c recipes/dbt.yml                          # THIS is what makes lineage real
```

Then, and only then, write `docs/v2/SUBSTRATE.md` asserting *"All hero-path
lineage was ingested from the running stack. No lineage was hand-authored."*

## Open questions for the human

1. **Disk.** DataHub + substrate + SigNoz do not fit together. Confirm SigNoz
   stays down during DataHub work.
2. **`api.groq.com`** — still blocked. Every §6 LLM agent is buildable but not
   demonstrable until it is allowlisted.
3. **Scope, given the slip.** Three days to MWP lock with D2–D3 outstanding.
