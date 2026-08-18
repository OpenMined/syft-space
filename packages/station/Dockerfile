# ============================================================================
# Syft Station — control plane image
# ============================================================================
# One self-contained build: the Vue frontend is compiled in its own stage and
# served statically by the backend, so the station runs as a single pod.
#
# Usage:
#   docker build -t syft-station station/
#   docker run -p 8090:8090 -v station-data:/data syft-station
#
# The server runs pending migrations at startup; `syft-station upgrade-db`
# is also available to run them as a standalone step.
# ============================================================================

ARG PYTHON_VERSION=3.12

# ============================================================================
# Stage 1: Frontend build
# ============================================================================
FROM oven/bun:1 AS frontend-builder

WORKDIR /app/frontend

COPY frontend/package.json frontend/bun.lock ./
RUN bun install --frozen-lockfile

COPY frontend/ ./
# build-only: vue-tsc (the `build` script's typecheck half) needs Node and
# misbehaves under bun's shim — type-checking is CI's job, not the image's.
RUN bun run build-only

# ============================================================================
# Stage 2: Backend dependencies
# ============================================================================
FROM cgr.dev/chainguard/wolfi-base AS backend-builder

ARG PYTHON_VERSION
RUN apk update && apk add --no-cache \
    python-${PYTHON_VERSION} \
    python-${PYTHON_VERSION}-dev \
    py${PYTHON_VERSION}-pip \
    uv

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv

COPY backend/pyproject.toml backend/uv.lock ./backend/
RUN cd backend && uv sync --no-dev --no-install-project

# ============================================================================
# Stage 3: Production
# ============================================================================
FROM cgr.dev/chainguard/wolfi-base AS production

ARG PYTHON_VERSION
RUN apk update && apk add --no-cache python-${PYTHON_VERSION}

WORKDIR /app

COPY --from=backend-builder /usr/bin/uv /usr/bin/uv
COPY --from=backend-builder /app/.venv /app/.venv

COPY backend/ ./backend/
RUN uv pip install --no-deps --python /app/.venv/bin/python -e ./backend

# The backend serves the built frontend from syft_station/ui (see main.py)
COPY --from=frontend-builder /app/frontend/dist ./backend/syft_station/ui

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    SYFT_STATION_SQLITE_DB_PATH=/data/app.db

EXPOSE 8090

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8090/healthz')" || exit 1

ENTRYPOINT ["syft-station"]
CMD ["server"]
