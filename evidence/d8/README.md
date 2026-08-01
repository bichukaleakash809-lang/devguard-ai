# D8 — the fault-injection evaluation suite (§9B)

**Date:** 2026-08-05 · Scope: **§9B only**, as instructed. §11's security work
and the live injection demo are not in this phase.

D8's gate: *"5–8 scripted faults, each with an expected root-cause label …
Publish accuracy, false-positive rate, and per-fault results as a README table.
`make eval` runs it."*

**Published: `examples/eval/` — `results.json` and a generated `README.md`.
`make eval` runs it. 7 faults, all really injected into a real PostgreSQL.**

```
accuracy            : 7/7 = 100.0%
false positives     : 0/2 = 0.0%
false negatives     : 0
faults with a signal: 5/7
```

---

## Do not quote 7/7 as the result

It is the least interesting number here and I want that on the record before
anything else.

Seven hand-written faults, scored by a classifier written in the same
repository, is **weak evidence by construction**. The classifier genuinely does
not know which fault was injected — it sees only `dbt build` output — so the
score is falsifiable rather than circular. But the fault set and the signature
set were written by the same author, and a perfect score on a suite you also
wrote demonstrates that the patterns match these errors, not that DevGuard
diagnoses arbitrary incidents.

Two results carry real weight:

**The false-positive rate is 0/2.** §9B's control — real database activity, no
real fault — got `INSUFFICIENT_EVIDENCE`. A system that invents a root cause
when nothing is wrong is worse than one that detects nothing.

**`silent_value_drift` was invisible, and DevGuard said so.** Every
`amount_cents` multiplied by 100: every model builds, every test passes, and
every downstream number — including the ML model's features — is wrong by two
orders of magnitude. DevGuard answered `INSUFFICIENT_EVIDENCE`. That is scored
correct because refusing is right when you cannot see something, and it is
**also a real limitation**: there is no distribution or range check wired in, so
this whole class of fault is invisible to DevGuard today. Counting it correct is
not a claim that it is handled.

**5 of 7 faults produced any runtime signal at all.** That is deliberate. An
eval where everything is detectable measures nothing about when a system should
decline to answer.

## Also not a measurement of LLM diagnosis

§9B is written for a system whose root cause comes from the Diagnostician. That
agent still cannot run — `api.groq.com` denied at CONNECT — so this scores
**DevGuard's deterministic detection-and-classification path**. `results.json`
carries that sentence in a `measures` field so it travels with the data, and a
test asserts it is there.

## The seven faults

| fault | category | expected | signal? |
|---|---|---|---|
| `column_rename` | schema | `COLUMN_RENAMED` | yes |
| `type_change` | schema | `TYPE_CHANGED` | yes |
| `upstream_table_dropped` | schema | `UPSTREAM_TABLE_MISSING` | yes |
| `permission_revoked` | access | `PERMISSION_DENIED` | yes |
| `null_rate_spike` | data-quality | `NULL_CONSTRAINT_VIOLATED` | yes |
| `silent_value_drift` | data-quality | `INSUFFICIENT_EVIDENCE` | **none** |
| `control_no_fault` | control | `INSUFFICIENT_EVIDENCE` | **none** |

Every one is real DDL or DML against real tables holding real rows. Nothing is
mocked and nothing is replayed from a fixture.

## Classifier rules that cost accuracy and are kept anyway

* **No failure signal → `INSUFFICIENT_EVIDENCE`.** Never a best guess.
* **A failure it cannot name → `UNKNOWN_FAILURE`**, never a plausible label.
  Guessing between `COLUMN_RENAMED` and `TYPE_CHANGED` on a message supporting
  neither is exactly how an eval scores well and an on-call engineer gets sent
  to the wrong table. `UNKNOWN_FAILURE` is deliberately a distinct answer from
  `INSUFFICIENT_EVIDENCE`: "nothing is wrong" and "something is wrong and I
  cannot name it" must never collapse into each other.

## Isolation — and two things that forced its design

Faults hit **`raw_eval`**, a real clone of `raw` rebuilt per run. Models build
into `analytics_eval*` as the **non-superuser role `devguard_eval`**. Everything
is dropped in a `finally`.

Two constraints made that necessary rather than tidy, and both were found by
running it:

1. **`REVOKE` against a superuser is a silent no-op.** The substrate's `devguard`
   role is a superuser, so `permission_revoked` would have "passed" by never
   breaking anything. It needs a real, unprivileged role.
2. **PostgreSQL refuses `ALTER COLUMN … TYPE` while any view depends on the
   column.** The first two attempts at `type_change` died on
   `analytics_eval_staging.stg_orders`, then on the *production*
   `analytics_staging.stg_orders`. An eval sharing `raw` cannot inject a type
   change without first destroying hero-loop state that D3–D7's evidence
   depends on. Cloning the schema removes the conflict entirely.

**Verified after the run** — the hero-loop substrate is untouched:

```
users 2000 | orders 20000 | null amounts 0 | mart rows 1715
leftover schemas 0 | leftover roles 0
substrate is in the BROKEN (hero-loop) state: True
```

## A green baseline runs before any fault

`dbt build` with nothing injected, captured to
`evidence/proof-pack/eval/eval/baseline/`. If it is not green the eval **refuses
to score anything** and exits 3. Without that check, a pre-existing failure
would be attributed to whichever fault happened to be running.

## Substrate changes this phase made

Two additive changes, neither of which alters `dbt run` behaviour, so D3–D7
evidence stays reproducible:

* **`substrate/dbt/models/staging/schema.yml`** — the standard `unique` /
  `not_null` tests a competent analytics project has anyway. Without any tests
  `dbt build` is identical to `dbt run` and no data-quality fault produces a
  signal, which would leave the eval scoring schema faults only. They are not
  tuned to the injected faults: `null_rate_spike` is caught by `not_null`
  because that is what `not_null` is for, and `silent_value_drift` is caught by
  nothing — reported as a miss rather than patched over with a bespoke range
  check written after seeing the fault.
* **`sources.yml`** — the raw schema is now `env_var('SUBSTRATE_RAW_SCHEMA',
  'raw')`, which is what lets the eval point at the clone. Defaults to `raw`.

## §12 — the published table is generated

`examples/eval/README.md` is rendered from `results.json` by
`scripts/render_eval_readme.py`, marked `GENERATED FILE — DO NOT EDIT`, and
`--check` is the one-line diff §12 asks CI for. A hand-edited number fails the
suite.

## Honest limitations

* **The score is weak evidence.** Same author wrote the faults and the patterns.
* **Not LLM diagnosis.** The Diagnostician still cannot run.
* **Silent data corruption is invisible to DevGuard.** No distribution checks.
  `silent_value_drift` is the proof, and it is counted correct only because
  refusing is the right response to not being able to see.
* **`null_rate_spike` reverts arithmetically**, restoring plausible values rather
  than the exact originals. It operates on the throwaway clone, so nothing real
  is affected — but the revert is not byte-exact and the fault library says so.
* **One substrate, one dbt project.** These faults are PostgreSQL/dbt-shaped.
* **§11's security work and the live injection demo are not in this phase**, per
  the instruction to complete §9B only. §11.7's injection beat remains unbuilt
  for an eighth phase, as does §11.4's least-privilege service account.
