# ============================================================================
# SyftAI Space Server - Production Dockerfile
# ============================================================================
# Builds a minimal production image with pre-built frontend.
#
# Prerequisites:
#   cd frontend && bun install && bun run build
#
# Usage:
#   docker build -t syft-space-server .
#   docker build --build-arg PYTHON_VERSION=3.12 -t syft-space-server .
# ============================================================================

ARG PYTHON_VERSION=3.12

# ============================================================================
# Stage 1: Backend Builder
# Installs Python dependencies using uv
# ============================================================================
FROM cgr.dev/chainguard/wolfi-base AS backend-builder

ARG PYTHON_VERSION
RUN apk update && apk add --no-cache \
    python-${PYTHON_VERSION} \
    python-${PYTHON_VERSION}-dev \
    py${PYTHON_VERSION}-pip \
    uv \
    git

WORKDIR /app

COPY backend/pyproject.toml backend/README.md ./backend/
COPY backend/syft_space/__init__.py ./backend/syft_space/

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
RUN uv venv /app/.venv --python python${PYTHON_VERSION} && \
    uv pip install --python /app/.venv/bin/python -e "./backend/" --no-cache

# ============================================================================
# Stage 2: Production
# Minimal image with only Python runtime
# ============================================================================
FROM cgr.dev/chainguard/wolfi-base AS production

ARG PYTHON_VERSION
RUN apk update && apk add --no-cache python-${PYTHON_VERSION}

WORKDIR /app

# Copy Python virtual environment
COPY --from=backend-builder /app/.venv /app/.venv

# Copy backend source
COPY backend/ ./backend/

# Copy pre-built frontend (must run: cd frontend && bun run build)
COPY frontend/dist ./frontend/dist

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    SYFT_PORT=8080 \
    SQLITE_DB_PATH=/data/app.db

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

ENTRYPOINT ["python", "-m", "uvicorn", "syft_space.main:app", "--host", "0.0.0.0", "--port", "8080"]
