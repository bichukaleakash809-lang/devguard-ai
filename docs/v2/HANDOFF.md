# DevGuard V2 handoff (05_DATAHUB_MASTER §19)

Assume the next session has zero memory of this one.

---

## Current day

**D0** — executed as far as it can go without a human decision. **STOPPED at the
§0 / §21 gate**, which is mandatory: *"Execute D0 only. Report. Wait for the
human. Do not begin D1 without explicit approval."*

Note the calendar: §14 dates D0 to Jul 28 and MWP LOCK to Aug 3. **Today is
Jul 31.** D0 is running three days late and D1–D3 have not happened.

## What is green

* Repository audited against the combined contract — `docs/v2/EXISTING_SYSTEM_AUDIT.md`
* **306 tests passing**, CI green on 4 jobs
* Environment measured: 15 GiB RAM, 16 GiB free disk, 4 CPUs, Docker 29.3.1
* **DataHub images are reachable** and sized (~1.4 GB compressed for the core)
* **All §5 tooling is reachable**: `mcp-server-datahub 0.6.0` (≥0.5.0 ✓),
  `datahub-agent-context 1.6.0.16`, `acryl-datahub 1.6.0.16`, uvx, npx,
  datahub-skills repo HTTP 200
* `versions.env` created with everything that could be honestly resolved
* Skeletons written: `JUDGING_MATRIX.md`, `SUBMISSION_CHECKLIST.md` (all ❌),
  `INTEGRATION_LOG.md`, `RISKS.md`, this file

## What is red

* **`api.groq.com` unreachable** — external egress denial, blocks every live LLM
  path. Not a code defect. `docs/TODO-BLOCKED.md`
* **DataHub Core has NOT been stood up.** §21.3 is unfinished: no tool list has
  been dumped, so `DATAHUB_VERSION` is deliberately blank in `versions.env`
* **No DataHub call has ever been made** — Criterion 1 self-scores **0**
* T2 §6.3 remains incomplete (four-agent trace)

## The exact next command

Blocked on a human decision first (§17 PATH A vs PATH B, and §3 substrate). Once
that is given, D0.3 is:

```bash
# 1. free disk — DataHub Core and the SigNoz stack do not fit together
docker compose -f signoz/deploy/docker-compose.yaml down
docker image prune -af

# 2. bring up DataHub Core, pinned, then record the REAL version into versions.env
#    (do not fill DATAHUB_VERSION from documentation — read it from the instance)

# 3. connect the MCP server and dump the tool list to disk, committed
uvx mcp-server-datahub@0.6.0     # env: DATAHUB_GMS_URL, DATAHUB_GMS_TOKEN
```

## Open questions for the human

1. **PATH A (new public repo) or PATH B (evolve this one)?** §17 defaults to A
   with a one-working-day carry-over cap. This decision gates everything.
2. **Substrate confirmation** (§3): Postgres + dbt Core + a trivial scikit-learn
   model, per the contract's table?
3. **Is `api.groq.com` going to be allowlisted?** If not, the §6 agent roster can
   be built and mock-tested but never demonstrated, and that changes what is
   worth building.
4. **Scope, given the slip.** Three days to MWP lock with D1–D3 outstanding.
