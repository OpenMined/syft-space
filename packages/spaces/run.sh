#!/bin/bash

# Run from this script's own directory (packages/spaces) so the relative
# backend/ path resolves no matter where it's invoked from.
cd "$(dirname "$0")"

# The en-core-web-sm wheel is a 12MB direct URL download; uv's 30s default
# timeout trips on slow links and aborts the whole install.
export UV_HTTP_TIMEOUT=${UV_HTTP_TIMEOUT:-600}

# Install from backend/uv.lock, so this venv holds the versions the container
# image ships. `uv pip install` ignores the lockfile and re-resolves the
# ranges against PyPI, drifting the local env to newer releases. uv sync also
# prunes what the lockfile does not name, so the venv needs no wipe first.
export UV_PROJECT_ENVIRONMENT="$PWD/.venv"
uv sync --project backend --extra dev

# Set default port if not provided
SYFT_PORT=${SYFT_PORT:-8080}

# Run uvicorn with new module path
uv run --project backend uvicorn syft_space.main:app --reload --host 0.0.0.0 --port $SYFT_PORT
