# ============================================================================
# syft-benchmark — the measuring service
# ============================================================================
# One process: the control API, the job queue and the schedule. They are not
# split because a measurement spends almost all its time waiting on a socket,
# the queue is strictly sequential by design, and three containers would need a
# shared database to agree through anyway — which is what they already have.
#
# The image holds no credentials and no corpus. It reads the Space's index and
# hands the Space a card; what it needs to reach either comes from the
# environment and from the targets table.
#
# Neither `metrics` (bert-score drags in torch) nor `spacy` is installed: both
# are extras, both are gigabytes, and both are guarded at every use. A rig that
# wants them builds with --build-arg EXTRAS="--extra metrics".
#
# Usage:
#   docker build -t syft-benchmark .
#   docker compose --profile service up -d --build
# ============================================================================

ARG PYTHON_VERSION=3.12

# ============================================================================
# Stage 1: Dependencies
# ============================================================================
FROM cgr.dev/chainguard/wolfi-base AS builder

ARG PYTHON_VERSION
ARG EXTRAS=""
RUN apk update && apk add --no-cache \
    python-${PYTHON_VERSION} \
    python-${PYTHON_VERSION}-dev \
    py${PYTHON_VERSION}-pip \
    uv

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv

# The lockfile and the package's __init__ only: the dependency layer is then
# rebuilt when the dependencies change, not when the code does.
COPY pyproject.toml uv.lock README.md ./
COPY src/syft_benchmark/__init__.py ./src/syft_benchmark/

RUN uv sync --locked --no-dev --no-install-project ${EXTRAS}

# ============================================================================
# Stage 2: Production
# ============================================================================
FROM cgr.dev/chainguard/wolfi-base AS production

ARG PYTHON_VERSION
RUN apk update && apk add --no-cache python-${PYTHON_VERSION}

WORKDIR /app

COPY --from=builder /usr/bin/uv /usr/bin/uv
COPY --from=builder /app/.venv /app/.venv

# The migrations travel with the code and are run at startup: a service whose
# schema has to be brought up to date by hand from somewhere else is a service
# that comes up broken on the one deploy nobody was watching.
COPY pyproject.toml uv.lock README.md alembic.ini ./
COPY alembic/ ./alembic/
COPY src/ ./src/

RUN uv pip install --no-deps --python /app/.venv/bin/python -e . \
    # The registry file is a seed and is deliberately not baked in: targets are
    # created from the UI and live in the table. The directory exists so that a
    # rig which does configure by file has somewhere to mount it.
    && mkdir -p /app/config /app/reports \
    && chown -R 65532:65532 /app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    # The schedule is kept in UTC, so the container's clock is UTC too. Anything
    # else would mean the same schedule firing at different hours on two hosts.
    TZ=UTC \
    # Matplotlib wants a writable home for its font cache and warns on every
    # import without one. The reports are built in this process.
    MPLCONFIGDIR=/tmp/matplotlib \
    BENCH_CONTROL_HOST=0.0.0.0 \
    BENCH_CONTROL_PORT=8200

# No privileges are needed: the index is reached over HTTP on the shared
# network, and nothing here talks to the docker socket.
USER 65532

EXPOSE 8200

# /health is the one route that answers without a key — which is exactly what a
# health check should be able to reach, and nothing more.
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import os,urllib.request;urllib.request.urlopen('http://127.0.0.1:%s/health' % os.getenv('BENCH_CONTROL_PORT','8200'))"]

# A measurement that was running when the process stopped is closed on the next
# start (`service_restarted`), so an interrupted job is visible rather than
# eternally alive. The grace period in compose is what gives it the chance to
# finish the question it is on.
ENTRYPOINT ["/bin/sh", "-c", "alembic upgrade head && exec syft-benchmark serve"]
