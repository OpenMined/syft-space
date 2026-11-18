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
echo "Installing dependencies..."
uv sync --project backend --extra dev
echo "Dependencies installed successfully !!"

# Set default port if not provided
SYFT_PORT=${SYFT_PORT:-8080}

# --no-sync: the sync above already ran. Without it, uv run revalidates the
# en-core-web-sm wheel URL against GitHub first, which stalls on a slow
# or blocked link with no output.
echo "Starting server..."
uv run --no-sync --project backend uvicorn syft_space.main:app --reload --host 0.0.0.0 --port $SYFT_PORT
