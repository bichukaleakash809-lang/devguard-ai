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

**Option B — Self-hosted (Docker Compose):**
```bash
git clone -b main https://github.com/SigNoz/signoz.git
cd signoz/deploy/docker
docker compose up -d
# SigNoz UI at http://localhost:3301, OTLP at http://localhost:4317
```
Then set `OTEL_EXPORTER_OTLP_ENDPOINT=http://<host>:4317`.

> **Recommendation:** Use **Cloud** for the demo. Self-hosting SigNoz pulls ~8 containers and can starve a laptop mid-judging. Keep self-host only for your local `docker compose` fallback.

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
- [ ] `curl $NEXT_PUBLIC_API_URL/audit-log/verify` returns `chain_verified: true`
- [ ] A test scan completes end-to-end on the deployed URL
- [ ] A trace appears in SigNoz for that scan
- [ ] Local `docker compose up` also works (**currently FAILS — see status note**)
- [ ] Demo video uploaded and linked in README
