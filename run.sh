#!/bin/bash

# Remove old venv and artifacts
rm -rf .venv

# Create venv and install backend package
uv venv -p 3.12
# Keep runtime deps minimal so startup doesn't depend on heavy optional libs
# (e.g. torch/torchvision from the "libs"/"dev" extras).
uv pip install -e "backend/"

# Set default port if not provided
SYFT_PORT=${SYFT_PORT:-8080}

# Force runtime state into the repo workspace (some environments restrict writes
# to user home directories like ~/.syft-space).
DATA_DIR="${PWD}/.syft-space"
mkdir -p "${DATA_DIR}/logs"
export SYFT_SQLITE_DB_PATH="${DATA_DIR}/app.db"
export SYFT_LOG_FILE="${DATA_DIR}/logs/syft-space-server.log"

# Run uvicorn with new module path
uv run uvicorn syft_space.main:app --reload --host 0.0.0.0 --port $SYFT_PORT
