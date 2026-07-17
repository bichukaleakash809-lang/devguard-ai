# DevGuard AI — 2-Minute Demo Script

> Goal: make judges *feel* the engineering weight and leave them with one quotable differentiator. Every second is budgeted. Rehearse until you hit 1:55, leaving 5s of buffer.

---

### `0:00 – 0:15` — The hook (problem + cost)
> "Manual security review costs eighty to a hundred and twenty dollars an hour, and human reviewers still miss roughly a third of injection bugs under deadline pressure. DevGuard does that review in under a second, for a fraction of a cent — and it proves its own work."

*(On screen: Page 1 landing, cursor ready in the code box.)*

---

### `0:15 – 0:45` — Page 1: the scan
> "I'll paste a login function with a classic SQL injection."

- Paste the vulnerable snippet. Click **Run Scan**.
- **Let the laser-scan animation play** — don't talk over the first beat.
> "Watch the agents light up live — scanner, then fix agent, then the validator. This is real-time status streamed over a WebSocket, not a loading spinner."

---

### `0:45 – 1:30` — Page 2: the payoff (the money segment)
*(Page transitions; cinematic staggered entrance plays.)*

> "Here's the report. On the left, the exact diff — before and after, with the vulnerable lines flagged. Top right, the CVSS score dropped from 7.8 HIGH to 1.2 LOW."

- Point to the metric cards counting up.
> "Latency, tokens, and cost — counting up live. This scan cost fractions of a cent versus eighty-five dollars for an hour of human review."

**⭐ THE WOW MOMENT — slow down, point directly at the reflection panel:**
> "This is what nobody else built. The Fix Agent's *first* attempt didn't pass — see it? Attempt one scored 74. So the system **critiqued its own fix and retried**, and attempt two passed at 91. This is a self-correcting AI that refuses to ship work it can't validate."

- Then point at the benchmark strip:
> "And this isn't vibes — the Scanner Agent is benchmarked at 92% accuracy, 95% recall against labeled OWASP snippets. There's the number."

---

### `1:30 – 1:50` — The proof: real distributed tracing
- Click **Investigate in SigNoz**.
> "Every agent step emits an OpenTelemetry span. One click and we're in a real distributed trace in SigNoz — scanner, fix, the retry, the validator, cost calc. This is production observability, live, not a screenshot."

*(Show the trace tree for ~5 seconds.)*

---

### `1:50 – 2:00` — The close (the differentiator line)
> **"DevGuard doesn't just generate a fix — it validates, retries, and proves its own work, hash-chained and fully traced, the way a real fintech compliance system would demand. That's the difference between a demo and a product."**

*(End on the audit-trail footer: ✅ Chain Verified.)*

---

## Delivery notes
- **Pause after the laser scan and after the reflection reveal** — those two silences are where judges form their impression. Don't rush them.
- If live deploy stalls, cut to `docker compose up` locally without breaking narration — the script is identical.
- Have the SigNoz tab pre-authenticated so the CTA lands instantly; a login screen kills momentum.
- Keep the tab count to two (app + SigNoz). Zero fumbling.
