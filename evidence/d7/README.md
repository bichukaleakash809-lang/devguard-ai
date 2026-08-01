# D7 — the ablation, and an honest account of what it could not measure

**Date:** 2026-08-04 · **DataHub:** v1.6.0 · **MCP server:** `mcp-server-datahub@0.6.0`

D7's gate (§14): *"The ablation (§9A), N≥5 both arms. Cost/token accounting. Raw
runs into `examples/`."* → **`examples/ablation/` published**.

**Published: `examples/ablation/` — `timings.json`, a generated `README.md`, and
10 raw run files. N = 5 per arm, both arms, real clocks.**

**Not delivered, and it cannot be delivered here: the measurement §9A actually
wants.** The effect being ablated is mediated by the Diagnostician, which cannot
run. This document explains that rather than papering over it, and the published
artifact carries a machine-readable flag saying so.

---

## What ran

```
$ python scripts/run_ablation.py -n 5
[off 1/5] ttrc=  6.39s post= 2.99s tools=6 docs=0 verdict=REASONER_UNAVAILABLE
[ on 1/5] ttrc=  4.99s post= 2.04s tools=8 docs=5 verdict=REASONER_UNAVAILABLE
...
retrieval=on  n=5  ttrc median 5.14s (min 4.89 max 6.56)  post-detection median 1.98s  tools 8  tokens 0  $0.0
retrieval=off n=5  ttrc median 4.87s (min 4.72 max 6.39)  post-detection median 1.85s  tools 6  tokens 0  $0.0

delta ttrc median          : +0.2690s
delta post-detection median: +0.1279s
retrieval could affect root cause: False
```

Ten runs, **interleaved** (`off,on,off,on,…`) rather than blocked, so machine
load and catalog growth are shared between the arms instead of landing on
whichever ran last. Each run has its own proof pack under
`evidence/proof-pack/ablation/`.

## The thing this ablation could not measure

§9A asks whether retrieving DevGuard's own prior runbooks reduces
time-to-root-cause. That effect is mediated **entirely** by the Diagnostician:
retrieved runbooks enter its prompt, and a better prompt should shorten its
reasoning.

`api.groq.com` is denied at CONNECT in this environment. Every one of the ten
runs reports `REASONER_UNAVAILABLE`, and both arms produced the root cause the
same way — derived deterministically from runtime evidence.

**So the published numbers measure the *cost* of retrieval and cannot measure
its *benefit*.** This is weaker than the null result §9A anticipates. A null
would mean "we measured it and there was no effect"; what we have is "the
mechanism was switched off by the environment, so no effect was possible". Those
are different claims and conflating them would be the easy dishonesty here.

`timings.json` carries the distinction as data, not prose:

```json
"comparison": {
  "retrieval_could_affect_root_cause": false,
  "interpretation": "Both arms produced the root cause the same way, so this
                     delta is the COST of retrieval and says nothing about its
                     benefit."
}
```

`compare()` computes that flag from `model_calls_total > 0`. It flips to `true`
the moment a real model call happens, and a test asserts the current value is
`false` — so if someone re-runs this with a key and forgets to rewrite the
write-up, the test fails rather than the document silently lying.

## Two timings, because either alone misleads

| | median | min | max |
|---|---|---|---|
| **TTRC**, on | 5.14 s | 4.89 | 6.56 |
| **TTRC**, off | 4.87 s | 4.72 | 6.39 |
| **post-detection**, on | 1.98 s | 1.84 | 2.09 |
| **post-detection**, off | 1.85 s | 1.76 | 2.99 |

`time-to-root-cause` includes detection — a real `dbt run`, which takes seconds
and varies by more than the effect being measured. **The two arms' TTRC ranges
overlap almost completely (4.72–6.39 vs 4.89–6.56), so the +0.269 s TTRC delta
is not distinguishable from noise and is not quoted as a result.** That is the
same reasoning §9A uses to reject MTTR: a large, noisy component hides the
effect.

`post-detection` — failure observed → root cause available — is where the signal
is. Retrieval costs **+0.128 s** and **+2 MCP calls**, and adds **+4 evidence
items**.

The `off` arm's 2.99 s maximum is the first run of the session: cold `uvx`
resolve and cold caches. It is published rather than dropped, and the **median**
is the headline precisely so one cold start cannot move the result. A test pins
that the outlier survives into `max` while staying out of the median.

## Cost accounting (§9C)

| | on | off |
|---|---|---|
| model calls | 0 | 0 |
| tokens | 0 | 0 |
| USD | $0.00 | $0.00 |

Zero across the board, and **the reason is the whole story**:

* DevGuard's deterministic agents — Watcher, Sentinel, Referee, Magistrate,
  Surgeon, Scribe — genuinely cost nothing per incident beyond wall-clock time.
  They use no model at all. That is a real property of the design and it is the
  honest half of this table.
* The Diagnostician is the one agent that *would* cost money, and it is the one
  that could not run. **So the interesting half of "what does it cost at 200
  incidents a week" is unanswered.**

`cost_model.note` in `timings.json` says it in-band: *"Zero because zero model
calls were made in this environment, not because inference is free."*

## §12: the numbers are generated, not typed

§12 requires that published figures be templated from `timings.json` with a CI
diff check. `examples/ablation/README.md` is rendered by
`scripts/render_ablation_readme.py`, carries a `GENERATED FILE — DO NOT EDIT`
header, and `--check` is the one-line diff §12 asks for:

```
$ python scripts/render_ablation_readme.py --check
examples/ablation/README.md matches examples/ablation/timings.json
```

`tests/test_ablation.py::TestRenderedDocsMatchSource` runs that check, so a
hand-edited number in the README fails the suite. This is how LAW 5 ("a number
typed by hand is a LAW 3 violation") actually holds once a document has a dozen
figures in it.

## What the harness does and does not exercise

**Read side only — §4 steps 2–9.** The ablation measures time-to-root-cause, and
remediation plus write-back would add minutes of noise per run while mutating the
shared catalog ten times over. That is a deliberate scope decision, stated here
rather than left for a reader to infer from the numbers.

The `retrieval` flag lives on the Archivist and gates *only* document retrieval.
Capability negotiation still runs in both arms, because that is §4 step 4 and is
not what is being ablated. `PriorKnowledge.retrieval_enabled` is kept separate
from `documents_available` so the off-arm reports **"RETRIEVAL DISABLED — not a
miss: no lookup was attempted"** rather than being indistinguishable from a
broken catalog.

## Honest limitations

* **The headline measurement of §9A is not delivered.** Cost, yes; benefit, no.
  The harness is complete and the same command produces the real comparison on a
  machine with a working key.
* **N = 5 per arm on one machine, one incident, one substrate.** These figures
  characterise this setup and nothing else. They are a measurement of overhead,
  not an estimate of retrieval's value.
* **The on-arm document count grows over time.** It retrieved 5 documents per
  run here because earlier D6 runs wrote them. A fresh catalog would retrieve
  fewer and the retrieval cost would be lower — the number is a property of this
  catalog's history, not a constant.
* **§9B (the fault-injection eval suite) is not in D7.** §14 places it on D8.
* **§11.7's injection demo beat is still not built** — seventh phase.
* **Still `urn:li:corpuser:__datahub_system`** — §11.4's least-privilege service
  account, seventh phase.
