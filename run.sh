#!/bin/bash

# Remove old venv and artifacts
rm -rf .venv

# Create venv and install backend package
uv venv -p 3.12
uv pip install -e "backend/.[dev]"

# Set default port if not provided
SYFTAI_PORT=${SYFTAI_PORT:-8080}

# Run uvicorn with new module path
uv run uvicorn syftai_space.main:app --reload --host 0.0.0.0 --port $SYFTAI_PORT
