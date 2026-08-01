# D6 — the loop closes, twice, from clean state

**Date:** 2026-08-03 · **DataHub:** v1.6.0 · **MCP server:** `mcp-server-datahub@0.6.0`

D6's gate (§14): *"Surgeon → Sentinel → Referee → Magistrate → approval →
remediation → verification → five-artifact write-back → retrieval on the next
run. The full §4 loop runs end to end."* … *"Loop completes twice from clean
state."*

**Result: steps 11–18 and the retrieval side run end to end, twice from clean
state, with all five §8 artifacts landing and the incident resolved in DataHub's
own UI. Step 9 — the Diagnostician's reasoning — remains blocked, so "the *full*
§4 loop" is not yet true, and this document does not claim it is.**

---

## The two passes

```
$ python scripts/reset_demo.py && python scripts/run_d6_loop.py --run-id d6-loop-pass1
[watcher]       exit=1 model=stg_users column=user_id
[probe]         raw.users: ('customer_id', 'email', 'country', 'signup_ts', 'is_active')
[archivist]     OK: PREVIOUS VERIFIED INCIDENT — 3 document(s) retrieved.
[pathfinder]    7 impacted, reaches_ml_model=True
[diagnostician] REASONER_UNAVAILABLE (is_refusal=False)
[surgeon]       OK: customer_id
[sentinel]      patch risk=LOW blocked=False
[referee]       validation passed=True (isolated schema analytics_devguard_check)
[magistrate]    risk=LOW mode=NAMED_OWNER owners=['DataHub']
[human]         approved by DataHub Admin (local operator)
[remediation]   applied devguard/fix-d6105859 to the working tree
[referee]       RECOVERY VERIFIED = True (exit 0, PASS=3)
[scribe]        incident raised: urn:li:incident:c2226569-…

   3. column-level annotation                       written
   2. verified post-mortem runbook (type: Analysis) written
   4. structured incident facts                     written
   5. ownership signal                              already_present
   1. incident resolved                             written
```

Pass 2 is identical in shape, from a fresh `reset_demo.py`, and finds **4**
documents instead of 3 — because pass 1 wrote one.

| Run | pack | outcome |
|---|---|---|
| pass 1 | `evidence/proof-pack/d6-loop-pass1/` | 4 written, 1 already_present, incident RESOLVED |
| pass 2 | `evidence/proof-pack/d6-loop-pass2/` | 4 written, 1 already_present, incident RESOLVED |
| failing fix | `evidence/proof-pack/d6-fail-the-fix/` | **zero** write-back artifacts |
| dry run | `evidence/proof-pack/d6-dry-run/` | 4 payloads captured, **nothing sent** |

**Live catalog state afterwards**, read back from GMS:

```
raw.users   RESOLVED incidents: 5   ACTIVE: 2   owner: urn:li:corpuser:datahub
```

The two ACTIVE incidents are both correct and both deliberate: D3's original
(never resolved, because D3 verified nothing) and the very first D6 run, which
§8's partial-failure policy held open when artifact 5 failed. Neither is a leak —
they are the policy working.

## §8's two required demonstrations

**"A deliberately failing fix writes nothing."** `--fail-the-fix` feeds the
Surgeon a column that does not exist. The patch is generated, scanned, and then
fails Referee validation in the throwaway schema:

```
[referee] validation passed=False (isolated schema analytics_devguard_check)
[loop] validation FAILED — no approval, no remediation, no write-back
```

The proof pack for that run contains **no `scribe/` directory at all**, the
working tree was never patched, and no approval was recorded. This is the line
between a useful agent and one that pollutes a shared catalog, and it is
verifiable by `ls`.

**Dry run shows the payloads and sends nothing.** `--dry-run` produces
`scribe/dry-run-*.json` for every artifact and issues zero mutations. Note that
`--dry-run` governs the **write-back**, per §8's `DEVGUARD_WRITEBACK=dry-run` — it
still applies and verifies the fix locally, because the point is to preview what
would reach the shared catalog.

## Three defects this phase found, all of them ours

None of these were caught by tests. All three needed the loop to actually run.

### 1. `add_owners` failed — and the partial-failure policy did its job

The first full run wrote four artifacts and then failed artifact 5:

```
5. ownership signal   failed   ownership_type: Missing required argument
1. incident resolved  failed   held ACTIVE on purpose: not every knowledge
                               artifact landed
```

I had **guessed** `add_owners`' arguments instead of reading the live
`inputSchema` — integration finding 18's exact lesson, repeated. `ownership_type`
is required on `add_owners` and optional on `remove_owners`, and the accepted
values are internal identifiers (`__system__technical_owner`). Logged as finding
21.

The silver lining is real evidence for §8: the partial-failure policy **held the
incident ACTIVE** rather than asserting a verified state whose supporting
knowledge was missing. That incident is still ACTIVE in the catalog today.

### 2. The Archivist reported a false "NO PRIOR KNOWLEDGE"

Pass 2 said *"document retrieval ran and matched nothing"* — while
`search_documents` had returned `total: 2`, including the runbook pass 1 had
written minutes earlier.

This is the worst failure mode this agent has. A retrieval bug that raises is a
bug; one that reports a confident, clean **miss** is a system quietly telling an
organisation it has never seen an incident it has already solved.

The cause: the two document tools are a **two-stage** API and I had called them
as if they were independent.

```
search_documents(query)       -> URNs + titles, deliberately NO content
grep_documents(urns, pattern) -> content for those specific URNs
```

My parser looked for `documents` / `results` keys the server does not use, and
`grep_documents` was called without `urns` and failed. Fixed to chain the two
stages; logged as finding 22. Pass 1 now reports **`PREVIOUS VERIFIED INCIDENT —
3 document(s) retrieved`**, which is §8's *"what makes it a loop"* actually
closing.

**D4 and D5 were checked and are unaffected** — both genuinely returned
`total: 0`, so their "matched nothing" claims were true when made.

### 3. Dry run reported a partial failure that had not happened

`SKIPPED_DRY_RUN` was not counted as "landed", so a dry run cascaded into §8's
partial-failure message and reported artifact 1 as `failed`. Nothing had failed —
nothing had been attempted. Describing a fault that did not occur is a small
dishonesty in the evidence, so it is fixed and pinned.

## Design decisions that depart from the contract, and why

**The Surgeon is deterministic** where §6 lists it as "LLM + tools". For an
upstream rename the mapping is not a judgement call *when it is unambiguous*:
one column referenced-but-missing, one present-but-unreferenced. When there is
more than one candidate the Surgeon **refuses**, because a wrong column mapping
builds green and computes the wrong numbers, which is worse than staying red.
§6 explicitly licenses determinism where a model is not needed. The honest
caveat: this covers one fix class, and a general repair agent would need a model
— which could not have been demonstrated here anyway.

**The fix aliases rather than renames.** `customer_id as user_id` keeps the
contract `stg_users` publishes to `user_order_features` and the registered
mlModel, so the fix's own blast radius is one file. Renaming downstream would be
larger, riskier, and would break the model's feature contract.

**The Surgeon never touches the working tree.** `write_branch()` uses
`git hash-object` + a temporary index to commit the patched content to
`devguard/fix-<incident>` while the file on disk is unchanged. Remediation is a
separate, post-approval step. That is what "never apply" has to mean to be worth
saying.

**§11.5's autonomy table is the code.** `AUTONOMY_POLICY` is the object the
docs render *and* the object the code branches on, so the published policy
cannot drift from the enforced one. CRITICAL has **no approver** — and
`ApprovalRequest.approve()` raises `PermissionError` for it, so there is no
identity that can authorise destructive DDL.

## Step 9 is still blocked, and the loop says so

The Diagnostician is invoked on every run and reports `REASONER_UNAVAILABLE`.
The loop continues past it because **the Surgeon is driven by the typed evidence
chain, not by the Diagnostician's prose** — the fix derives from
`column "user_id" does not exist` plus a live `information_schema` probe, both
`RUNTIME` facts.

The `root_cause` string written into the runbook is composed deterministically
from those same facts and is labelled, in the artifact itself:

> *Derived deterministically from runtime evidence — NOT produced by a language
> model (Diagnostician verdict: REASONER_UNAVAILABLE).*

`--require-diagnosis` makes the whole run halt without a model-produced root
cause, for the day the key exists. `api.groq.com` remains denied at CONNECT
(`403`), with a control host returning 200 — re-probed in
`evidence/d5/02-groq-egress-probe.txt`.

## Honest limitations

* **"The full §4 loop runs end to end" is not yet true.** Step 9 does not run.
  Steps 2, 4–8 and 11–18 do.
* **The approver is the local operator**, `urn:li:corpuser:datahub`, supplied
  explicitly to the runner and recorded verbatim. It is a real recorded
  identity, not an inferred one, but it is not an independent human reviewing on
  a real team.
* **The asset became owned by the approver** in pass 1 (§8 artifact 5, "add_owners
  if unowned"). From pass 2 onward artifact 5 correctly reports
  `already_present`. That is idempotency working, but it also means the "unowned"
  branch only ever ran once — it is not exercised by later runs.
* **Only one fix class is covered.** See the Surgeon note above.
* **§11.7's injection demo beat is still not built.** No hostile description is
  seeded, so the Sentinel's catalog-text screen has still never fired on live
  data.
* **Still `urn:li:corpuser:__datahub_system`** for the agent's own credential.
  §11.4's least-privilege service account, outstanding for a sixth phase.
* **The repository is committed with the substrate BROKEN**, deliberately, so
  D3/D4/D5 evidence stays reproducible. The fix lives on the
  `devguard/fix-*` branches, which is where §4 step 11 says it belongs.
