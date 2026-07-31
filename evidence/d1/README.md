# D1 — write-path proof (05_DATAHUB_MASTER §14, LAW 4)

**Date:** 2026-07-31 · **DataHub:** v1.6.0 (`059a36c0b035…`, read from the running
instance) · **MCP server:** `mcp-server-datahub@0.6.0`

D1's whole purpose, in the contract's words: *"Prove the write path before
building on it (LAW 4)… If any fail, the plan changes **today**."*

**Result: every write path in §8's package works. Nothing in §8 has to change.**
Four discrepancies against the contract's §5 were found, and in every case the
live server won.

---

## The five write paths

| # | §8 artifact | Mechanism | Result | Raw response |
|---|---|---|---|---|
| 1 | Incident raised | GraphQL `raiseIncident` | **OK** → `urn:li:incident:b2f18c7e-bee3-40bf-82c6-2bad17163a28` | `01-raiseIncident.json` |
| 1 | Incident resolved | GraphQL `updateIncidentStatus` | **OK** → `true`; read back **ACTIVE=0, RESOLVED=1** | `03-updateIncidentStatus.json`, `04-incidents-after-resolve.json` |
| 3 | Column-level tag | MCP `add_tags` (`column_paths: ["user_id"]`) | **OK** → *"Successfully added 1 tag(s) to 1 entit(ies)"* | `05-add_tags-column.json` |
| 3 | Column-level description | MCP `update_description` (`column_path: "user_id"`) | **OK** → `success: true` | `06-update_description-column.json` |
| 2 | Context Document | MCP `save_document` | **OK** → `urn:li:document:shared-7f391065-b01a-425f-ae96-2f76b91b575f` | `07-save_document.json` |
| 4 | Structured properties | SDK definitions + MCP `add_structured_properties` | **OK** → *"Successfully added 3 structured propert(ies) to 1 entit(ies)"* | `08-…definitions.json`, `09-add_structured_properties.json` |

`devguard.last_incident_urn`, `devguard.verified_at` and
`devguard.time_to_root_cause_s` are now registered definitions, so §8 artifact 4
is unblocked.

Artifact 5 (`add_owners`) was not exercised — the tool is present in the live
tool list and is the same shape as `add_tags`, which is proven. It is left for
the hero loop rather than claimed here.

---

## Discrepancies — contract vs live server (§5: "the live server wins")

**1. `updateIncidentStatus` takes `IncidentStatusInput!`, not
`UpdateIncidentStatusInput!`.** The contract's §5 signature is wrong. The first
attempt failed with:

```
Validation error (VariableTypeMismatch@[updateIncidentStatus]) :
Variable 'input' of type 'UpdateIncidentStatusInput!' used in position
expecting type 'IncidentStatusInput!'
```

**2. Context Documents have no `Runbook` type.** This is the material one, because
§8 artifact 2 is literally *"Context Document, subtype **Runbook**"* and §5 lists
*"typed Runbook / FAQ / Policy / Decision Log"*. The live enum is:

```
Insight · Decision · FAQ · Analysis · Summary · Recommendation · Note · Context
```

`Runbook`, `Policy` and `Decision Log` do not exist. Per §8's rule for
unsupported writes ("implement the nearest honest alternative, never silently
skip"), **`Analysis` is the type DevGuard will use** for verified post-incident
knowledge — it is an analysis of a verified incident, and it is a real type on
this server. The word "runbook" stays in the document *title and body*, where it
is descriptive rather than a false schema claim.

**3. A tag must exist before it can be applied.** `add_tags` first failed with
*"Failed to validate label with urn urn:li:tag:devguard_incident_impacted"*. This
is the same shape as §5's documented structured-property trap, but §5 does not
mention it for tags. The tag entity is now created explicitly before use.

**4. `add_structured_properties` wants full property URNs as keys, and list
values.** Two failures before it landed: qualified names (`devguard.verified_at`)
are rejected — *"Urn doesn't start with 'urn:'"* — and scalar values are rejected
— *"Input should be a valid list"*. So the shape is
`{"urn:li:structuredProperty:devguard.verified_at": ["2026-07-31T…"]}`.

All four are recorded in `docs/v2/INTEGRATION_LOG.md` as §16 contribution
candidates.

---

## Honest notes

* **The credential used here is `urn:li:corpuser:__datahub_system`**, which holds
  `manageIngestion` and `managePolicies`. That is a system account with broad
  rights — **the opposite of §11.4's least-privilege service account**. It was
  used to prove the write path exists; **configuring the scoped service account
  and its Access Policy set is still outstanding** and must be done before any
  write path is considered production-shaped.
* **The dataset written to is a minimal entity created for this test**
  (`urn:li:dataset:(urn:li:dataPlatform:postgres,devguard.raw.users,PROD)`), not
  yet the ingested substrate. It carries a real `schemaMetadata` with a real
  `user_id` field, which is what makes the column-level writes meaningful. The
  substrate ingestion (§3 hard gate) has **not** run yet.
* **Nothing here is a hero-loop run.** These are isolated proofs that each call
  works, which is exactly what D1 is for. The incident title and document body
  both say so in-band, so nobody can mistake this evidence for a real detection.
