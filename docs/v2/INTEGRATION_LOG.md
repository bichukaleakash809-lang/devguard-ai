# Integration log — DevGuard V2 (05_DATAHUB_MASTER §16)

Every rough edge actually hit while integrating DataHub. This is simultaneously
the **OSS contribution candidate list** and the **Most Valuable Feedback survey**
material (10 × $50). §16: *"File the cheap one early — do not schedule the bonus
for the last day."*

Only real, encountered friction goes here. Nothing anticipated, nothing repeated
from documentation.

---

## D0 — 2026-07-31

| # | Surface | What happened | Contribution candidate? |
|---|---|---|---|
| 1 | — | _No DataHub integration attempted yet. DataHub Core has not been stood up._ | — |

### Carried in from the SigNoz track (same class of finding, different product)

Not DataHub feedback, but recorded because it is exactly the kind of entry this
log is for, and it demonstrates the habit is already running:

* SigNoz v0.135.0: `POST /api/v1/dashboards` returns `501 dashboard_deprecated`;
  v2 is required. `/api/v1/login` returns SPA HTML — the real endpoint is
  `POST /api/v2/sessions/email_password` and it **requires an `orgId`** that no
  unauthenticated endpoint exposes.
* SigNoz alert rules: `POST /api/v1/rules` rejects every payload with one opaque
  line naming no field; `/api/v2/rules` returns field-level errors. The schema was
  only recoverable from the shipped source maps.
* The signoz-otel-collector will not open its OTLP receiver until an
  organisation exists, while still logging *"Everything is ready"* and reporting
  healthy — a silent-drop failure mode.
