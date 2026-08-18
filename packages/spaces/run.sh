#!/bin/bash

# Run from this script's own directory (packages/spaces) so the relative
# backend/ path resolves no matter where it's invoked from.
cd "$(dirname "$0")"

# Remove old venv and artifacts
rm -rf .venv

# Create venv and install backend package
uv venv -p 3.12
uv pip install -e "backend/.[dev]"

# Set default port if not provided
SYFT_PORT=${SYFT_PORT:-8080}

# Run uvicorn with new module path
uv run uvicorn syft_space.main:app --reload --host 0.0.0.0 --port $SYFT_PORT
