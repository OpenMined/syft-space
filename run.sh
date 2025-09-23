#!/bin/bash

rm -rf .venv
uv venv -p 3.12
uv pip install -e backend/

# Set default port if not provided
SYFTBOX_ASSIGNED_PORT=${SYFTBOX_ASSIGNED_PORT:-8080}
uv run uvicorn backend.main:app --reload --host 0.0.0.0 --port $SYFTBOX_ASSIGNED_PORT
