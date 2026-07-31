# Judging matrix — DevGuard V2 (05_DATAHUB_MASTER §13)

One row per **shipped** feature. A self-score without a linked artifact is
**automatically one point lower** (§13), so the Evidence column is not optional.

| Criterion | Feature | Demo moment (mm:ss) | Evidence artifact | Source file | Self-score |
|---|---|---|---|---|---|
| _(empty — nothing DataHub-facing has shipped yet)_ | | | | | |

## Anchored self-score — D0

Scored against §13's descriptors. These are deliberately low because **nothing
against the DataHub contract has been built yet**; scoring anything else would be
the fabrication LAW 3 forbids.

| # | Criterion | Score | Anchor met | Evidence |
|---|---|---|---|---|
| 1 | Use of DataHub | **0** | Not even 1 ("read-only single tool") — no DataHub call has been made | — |
| 2 | Technical Execution | **3** | "clean-clone reproducible" — 306 tests, CI green, clean-clone quickstart verified. Not 4+: nothing DataHub-facing is tested | `.github/workflows/ci.yml` |
| 3 | Originality | **0** | Nothing of §2's seven differentiators exists yet | — |
| 4 | Real-World Usefulness | **1** | The existing scanner is real but is not the submitted thesis | — |
| 5 | Submission Quality | **1** | "README only" — no video, description, examples or replay URL | `README.md` |

**Lowest score → tomorrow's primary objective** (§13): criteria 1 and 3, both at
**0**, and both unlocked by the same thing — a first real DataHub call. That is
D0.3 (bring up DataHub Core, dump the tool list) followed by D1 (prove the write
path).
