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

# Copy lockfile, pyproject.toml, and minimal source for uv sync
COPY backend/pyproject.toml backend/uv.lock backend/README.md ./backend/
COPY backend/syft_space/__init__.py ./backend/syft_space/

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

# Install all deps (including libs) from lockfile.
# CPU-only torch/torchvision is enforced by [tool.uv.sources] in pyproject.toml.
ENV UV_PROJECT_ENVIRONMENT=/app/.venv
RUN cd backend && uv sync --extra libs --no-install-project

# ============================================================================
# Stage 2: Production
# Minimal image with only Python runtime
# ============================================================================
FROM cgr.dev/chainguard/wolfi-base AS production

ARG PYTHON_VERSION
RUN apk update && apk add --no-cache \
    python-${PYTHON_VERSION} \
    docker-cli \
    docker-compose \
    # Required for docling document processing
    libxcb \
    libglvnd \
    glib \
    freetype \
    fontconfig \
    libxml2 \
    libxslt \
    && mkdir -p /usr/local/lib/docker/cli-plugins \
    && ln -s /usr/bin/docker-compose /usr/local/lib/docker/cli-plugins/docker-compose

WORKDIR /app

# Copy uv from builder stage
COPY --from=backend-builder /usr/bin/uv /usr/bin/uv

# Copy Python virtual environment
COPY --from=backend-builder /app/.venv /app/.venv

# Copy backend source
COPY backend/ ./backend/

# Install the project itself (source-only, deps already in venv)
RUN uv pip install --no-deps --python /app/.venv/bin/python -e ./backend

# Copy pre-built frontend (must run: cd frontend && bun run build)
COPY frontend/dist ./frontend/dist

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    SYFT_PORT=8080 \
    SYFT_SQLITE_DB_PATH=/data/app.db \
    SYFT_LOG_FILE=/data/logs/syft-space-server.log \
    DOCKER_NETWORK_HOST=host.docker.internal

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import os; import urllib.request; urllib.request.urlopen(f'http://localhost:{os.getenv(\"SYFT_PORT\", \"8080\")}/api/v1/health')" || exit 1

ENTRYPOINT ["/bin/sh", "-c", "exec python -m uvicorn syft_space.main:app --host 0.0.0.0 --port ${SYFT_PORT:-8080}"]
