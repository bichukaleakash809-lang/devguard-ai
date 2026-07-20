
# 🎬 DevGuard AI — 2-Minute Demo Script

**Prep before recording:**
- Terminal with backend running (visible if you want to flash to it)
- Browser: Page 1 open, tab for SigNoz Traces ready
- Have TWO code snippets ready to paste: (1) a `critical` SQLi snippet, (2) a `low/medium` MD5 snippet — the contrast is the whole point of the wow moment
- Set `COST_BUDGET_USD_PER_30MIN` low enough beforehand that the second scan visibly triggers an override (or just run a few scans before recording to naturally cross the threshold)

---

## 0:00 – 0:15 | The Hook (cost/problem framing)

**Say:**
> "Manual security code review costs about $85 an hour and doesn't scale with how fast teams ship. DevGuard AI does it in seconds — and unlike a typical AI wrapper, it proves its own work, and it watches its own telemetry to decide how to spend its budget. Let me show you."

**Show:** DevGuard AI Page 1, clean and idle.

---

## 0:15 – 0:45 | Page 1 — Scan a critical vulnerability

**Do:** Paste the SQLi snippet, click **"Run DevGuard AI Agent."**

**Say (while the laser-scan animation runs):**
> "This is a real SQL injection. Watch the live agent status — Scanner, Fixer, Validator, all traced end-to-end."

**Show:** Live status text updating, then the transition to Page 2.

---

## 0:45 – 1:30 | Page 2 — The reveal (the core "wow")

**Say:**
> "Here's the diff — parameterized query, fix applied. Latency, tokens, cost, all real."

**Point at the "Model routing & self-correction" panel:**
> "Because this is critical severity, it routed to the strongest model — and that's a hard-coded safety floor. Cost pressure can NEVER downgrade a critical fix. Watch what happens with a lower-severity scan."

**Do:** Click "New scan," paste the MD5/weak-hash snippet, run it.

**Say (on Page 2, pointing at the self-observation panel/routing override):**
> "This one is medium severity — and here, the agent checked its own recent spend through SigNoz's MCP server, saw it was over budget, and downgraded the model itself. That decision — 'cost_budget_exceeded' — isn't something I coded as a fixed rule for this snippet. It's the agent reading its own telemetry and deciding, live, in the same request. This is the differentiator: DevGuard doesn't just get observed — it observes itself, and adapts."

**Show:** The benchmark accuracy strip (92% / 88% / 95% / 5% FPR) — one beat, don't dwell.

---

## 1:30 – 1:50 | SigNoz — the proof

**Do:** Click **"Investigate this trace in SigNoz."**

**Say:**
> "And here's the real trace — Scanner, Fixer, Validator as nested spans, plus the routing-override decision stamped right onto the trace. Nothing hidden, fully reproducible — the whole SigNoz stack is deployed via Foundry, `casting.yaml` is in the repo, you can spin up the exact same setup yourself."

**Show:** SigNoz Trace Detail waterfall, briefly hover the routing-override span attribute if visible.

---

## 1:50 – 2:00 | Close — the differentiator line

**Say (straight to camera):**
> "DevGuard doesn't just get observed — it observes itself, and adapts. That's DevGuard AI."

**Show:** README/GitHub repo page for one beat as the final frame.

---

## Timing Cheat Sheet

| Time | Beat |
|---|---|
| 0:00–0:15 | Hook |
| 0:15–0:45 | Page 1, critical scan |
| 0:45–1:10 | Page 2 reveal, safety floor explained |
| 1:10–1:30 | Second scan, self-observation override — **the wow moment** |
| 1:30–1:50 | SigNoz trace proof |
| 1:50–2:00 | Differentiator line + close |

## If something breaks live

- If the cost override doesn't trigger on camera: mention it happened during rehearsal and show a screenshot/pre-recorded clip of the JSON response with `routing_override` populated — don't waste demo time debugging live.
- If SigNoz is slow to load: have the Trace Detail screenshot ready as a fallback cut.


