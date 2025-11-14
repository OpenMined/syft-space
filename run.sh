#!/bin/bash

rm -rf .venv
uv venv -p 3.12
uv pip install -e "backend/.[dev]"

# Set default port if not provided
SYFTAI_PORT=${SYFTAI_PORT:-8080}
uv run uvicorn backend.main:app --reload --host 0.0.0.0 --port $SYFTAI_PORT
