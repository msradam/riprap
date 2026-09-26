# Riprap self-host image (FastAPI + SvelteKit).
#
# Runs the evidence pipeline on CPU. It does not ship an LLM: point
# RIPRAP_LLM_BASE_URL at an OpenAI-compatible endpoint, or set
# RIPRAP_RECONCILER_TIER=no_llm for the evidence-only briefing.
# See .env.example and docs/DEPLOY.md.
#
# Build:    docker build -t riprap -f Dockerfile.app .
# Run:      docker run --rm -p 7860:7860 --env-file .env riprap

# -----------------------------------------------------------------------
# Stage 1: build the SvelteKit static bundle
# -----------------------------------------------------------------------
FROM node:24-slim AS frontend-build

WORKDIR /build
RUN corepack enable
COPY web/sveltekit/package.json web/sveltekit/pnpm-lock.yaml web/sveltekit/pnpm-workspace.yaml web/sveltekit/.npmrc ./
RUN pnpm install --frozen-lockfile

COPY web/sveltekit/ ./
RUN pnpm build

# -----------------------------------------------------------------------
# Stage 2: Python runtime
# -----------------------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH=/app/.venv/bin:$PATH \
    PYTHONPATH=/app

# curl for healthchecks. GDAL, GEOS and PROJ come bundled in the
# rasterio, pyogrio, shapely and pyproj wheels; the rasterio wheel still
# links the system libexpat.
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates libexpat1 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /usr/local/bin/uv

WORKDIR /app

# Dependencies first so a code-only edit doesn't bust the layer cache.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# App code, manifests, fixtures and corpus.
COPY app/ ./app/
COPY riprap/ ./riprap/
COPY deployments/ ./deployments/
COPY web/__init__.py web/main.py ./web/
COPY web/static/ ./web/static/
COPY data/ ./data/
COPY corpus/ ./corpus/

# Pre-built SvelteKit bundle from stage 1.
COPY --from=frontend-build /build/build ./web/sveltekit/build

EXPOSE 7860

CMD ["uvicorn", "web.main:app", "--host", "0.0.0.0", "--port", "7860", \
     "--log-level", "info", "--proxy-headers"]
