# DevGuard AI — Deployment Guide

> **⚠ STATUS: the container path in this guide is NOT currently working.**
> `backend/Dockerfile` copies `requirements.txt` from outside its build context
> and there is no `frontend/Dockerfile`, so **`docker compose up` fails** — the
> images have never built successfully. Every step below that depends on
> `docker compose` or on the backend image is therefore **unverified**.
>
> Fixing it requires pulling base images, which is blocked in the environment
> where this was audited (evidence:
> `docs/audit-evidence/t2/registry-egress-block.txt`). Tracked in
> `docs/HANDOFF.md` as findings B1, B2 and A1.
>
> **What does work today, and is verified:** running the backend and frontend
> directly — see the README Quickstart, or `make backend` / `make frontend`.
> Run `make doctor` first; it reports exactly what is missing.

This guide describes the intended deployment topology. Read the status note above first: the container-based paths are written but unverified, so treat them as a plan rather than a tested procedure.

---

## 0. Deployment topology

```
Vercel (frontend)  ──►  Railway/Render (FastAPI backend)  ──►  Groq API
                                     │
                                     ├──►  Upstash Redis (cache + scan state)
                                     └──►  SigNoz Cloud (OTLP traces)
```

Recommended for hackathon speed: **Vercel + Railway + Upstash + SigNoz Cloud**. All have free tiers and provision in minutes.

---

## 1. Redis — Upstash (free tier)

1. Create an account at https://upstash.com → **Create Database** → pick a region close to your backend.
2. Copy the **`UPSTASH_REDIS_URL`** (the `rediss://…` TLS URL).
3. Keep it — it becomes `REDIS_URL` on the backend.

> Alternative: add the **Railway Redis plugin** (one click) if you'd rather keep everything on Railway. It exposes `REDIS_URL` automatically.

---

## 2. Observability — SigNoz

**Option A — SigNoz Cloud (recommended for hackathons):**
1. Sign up at https://signoz.io/teams (free trial).
2. From **Settings → Ingestion**, copy your **ingestion endpoint** and **ingestion key**.
3. Backend env:
   ```
   OTEL_EXPORTER_OTLP_ENDPOINT=https://ingest.<region>.signoz.cloud:443
   OTEL_EXPORTER_OTLP_HEADERS=signoz-access-token=<your-key>
   ```
4. Set `NEXT_PUBLIC_SIGNOZ_URL` on the frontend to your SigNoz workspace URL so the "Investigate in SigNoz" CTA deep-links correctly.

**Option B — Self-hosted (Docker Compose). This is the one that is actually
verified.** A compose file lives in this repo, so there is no second clone:

```bash
# 1. Core services (ClickHouse + Keeper + Postgres + schema migrator + app)
docker compose -f signoz/deploy/docker-compose.yaml up -d signoz-signoz-0

# 2. First-run setup — REQUIRED, and not optional in the way it looks.
#    The OTLP collector fetches its pipeline config from the SigNoz server over
#    OpAMP, and the server will not register it until an organisation exists
#    ("cannot create agent without orgId"). Skip this and the collector comes up
#    "healthy" but never opens port 4317/4318 and silently drops every span.
curl -X POST http://localhost:3301/api/v1/register \
  -H 'Content-Type: application/json' \
  -d '{"name":"DevGuard","orgName":"devguard","email":"you@example.com","password":"<choose-one>"}'

# 3. Now start the ingester
docker compose -f signoz/deploy/docker-compose.yaml up -d

# SigNoz UI at http://localhost:3301, OTLP at localhost:4317 (gRPC) / 4318 (HTTP)
```

Then set `OTEL_EXPORTER_OTLP_ENDPOINT=http://<host>:4317`. **If your shell has an
HTTPS proxy configured, also set `no_grpc_proxy=localhost,127.0.0.1`** — gRPC
reads its own proxy variables and `NO_PROXY` alone does not cover it, so the
backend will report `exporter_configured: true`, log nothing, and export nothing.

To check the whole thing end to end, including that spans are genuinely stored:

```bash
./scripts/verify_signoz.sh     # tears down with -v, rebuilds, asserts, exits non-zero on failure
```

Pinned versions: `signoz/signoz:v0.135.0`, `signoz/signoz-otel-collector:v0.144.6`,
`signoz/signoz-schema-migrator:v0.144.6`, `clickhouse/clickhouse-server:25.12.5`,
`clickhouse/clickhouse-keeper:25.12.5`, `postgres:16`. Evidence, including the
non-obvious failure modes and screenshots of a real trace:
`docs/audit-evidence/t2/signoz-6.1-6.3-verified.txt`.

> **Which to use:** self-hosting pulls ~4 GB of images and runs 7 containers, so
> for a laptop demo **Cloud** is still the lighter choice. Option B is what this
> repo has actually verified, and it is the fallback that works with no account.

---

## 3. Backend — Railway (or Render)

The repo ships a [`backend/Dockerfile`](./backend/Dockerfile). **It does not build as committed** — its `COPY requirements.txt` reads from outside the `./backend` build context, and its `CMD` targets `main:app` rather than `backend.main:app`. Fix both before relying on any step below.

### Railway
1. https://railway.app → **New Project → Deploy from GitHub repo**.
2. Set the service root to `/backend` (or point it at the Dockerfile).
3. Add environment variables:
   ```
   GROQ_API_KEY=<your groq key>
   REDIS_URL=<upstash rediss:// url>
   OTEL_EXPORTER_OTLP_ENDPOINT=<signoz endpoint>
   OTEL_EXPORTER_OTLP_HEADERS=signoz-access-token=<key>   # cloud only
   PORT=8000
   ```
4. Deploy. Railway gives you a public URL like `https://devguard-api.up.railway.app`.
5. Confirm health: `curl https://devguard-api.up.railway.app/slo-status`.

### Render (alternative)
1. https://render.com → **New → Web Service** → connect repo → root `/backend`, environment **Docker**.
2. Same env vars as above.
3. Deploy; note the `onrender.com` URL.

---

## 4. Frontend — Vercel

1. https://vercel.com → **Add New → Project** → import the repo.
2. Set **Root Directory** to `frontend`.
3. Environment variables (Production + Preview):
   ```
   NEXT_PUBLIC_API_URL=https://devguard-api.up.railway.app
   NEXT_PUBLIC_SIGNOZ_URL=https://<your>.signoz.cloud
   ```
4. Deploy. Vercel gives you `https://devguard-ai.vercel.app`.

> **CORS:** ensure the backend allows the Vercel origin. In FastAPI:
> ```python
> from fastapi.middleware.cors import CORSMiddleware
> app.add_middleware(CORSMiddleware,
>   allow_origins=["https://devguard-ai.vercel.app", "http://localhost:3000"],
>   allow_methods=["*"], allow_headers=["*"])
> ```

---

## 5. Local fallback — one command

If live infra fails during judging, run everything locally with the provided [`docker-compose.yml`](./docker-compose.yml):

```bash
cp .env.example .env      # fill GROQ_API_KEY
docker compose up
```

Brings up:
- `frontend` → http://localhost:3000
- `backend` → http://localhost:8000
- `redis` → internal
- `signoz` (optional profile) → http://localhost:3301

To skip local SigNoz (lighter): `docker compose up frontend backend redis`.

---

## 6. Pre-demo checklist

- [ ] `curl $NEXT_PUBLIC_API_URL/slo-status` returns 200
- [ ] `curl $NEXT_PUBLIC_API_URL/audit-log/verify` returns `"valid": true` —
      **not** `chain_verified`, which this checklist previously named and which
      the endpoint has never returned. The real shape is
      `{"valid": true, "entries_checked": N, "broken_at": null, "reason": "chain intact"}`.
- [ ] `curl $NEXT_PUBLIC_API_URL/telemetry-status` — confirms what the OTLP
      exporter and the MCP path are *actually* configured with, rather than what
      you intended. `signoz_mcp.verified_against_real_server` is `false` in every
      deployment so far; see `docs/MCP_DECISION.md`.
- [ ] A test scan completes end-to-end on the deployed URL
- [ ] A trace appears in SigNoz for that scan
- [ ] `NEXT_PUBLIC_SIGNOZ_URL` is set on the frontend — the "Investigate this
      trace in SigNoz" CTA does not render without it (by design; it used to
      fall back to `cloud.signoz.io` and 404)
- [ ] Local `docker compose up` also works (**currently FAILS — see status note**)
- [ ] Demo video uploaded and linked in README

## 7. What the accuracy strip shows in a fresh deployment

Nothing — it reads "accuracy not measured". Figures reach the UI only from an
artifact a real benchmark run wrote:

```bash
python -m backend.core.benchmark --json data/benchmark_report.json   # needs GROQ_API_KEY
```

Point `DEVGUARD_BENCHMARK_ARTIFACT` at that file if you mount it elsewhere. The
harness refuses to write the artifact when any scan errored, so a run during a
provider outage cannot publish its depressed rates as the scanner's accuracy.
