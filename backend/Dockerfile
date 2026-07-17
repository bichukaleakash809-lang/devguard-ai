# DevGuard AI — backend production image.
# Multi-stage: build wheels in one layer, ship a slim runtime.

# ---- Stage 1: build dependencies ----
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps some wheels need (kept minimal).
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip wheel --wheel-dir /wheels -r requirements.txt

# ---- Stage 2: runtime ----
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

WORKDIR /app

# Non-root user for a smaller attack surface.
RUN useradd --create-home --uid 1000 appuser

COPY --from=builder /wheels /wheels
COPY requirements.txt .
RUN pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.txt \
    && rm -rf /wheels

COPY . .

USER appuser

EXPOSE 8000

# Healthcheck lets Railway/Render/Compose know when we're actually ready.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,os; urllib.request.urlopen(f'http://localhost:{os.getenv(\"PORT\",\"8000\")}/slo-status')" || exit 1

# Shell form so ${PORT} expands (Railway/Render inject their own PORT).
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT} --workers 2
