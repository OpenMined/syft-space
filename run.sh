#!/bin/bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

MODE="${1:-dev}"

FRONTEND_DIR="$ROOT_DIR/frontend"
BACKEND_DIR="$ROOT_DIR/backend"
VENV_DIR="$ROOT_DIR/.venv"

# Set default port if not provided
SYFTBOX_ASSIGNED_PORT=${SYFTBOX_ASSIGNED_PORT:-8080}

command_exists() {
    command -v "$1" >/dev/null 2>&1
}

usage() {
  cat <<EOF
Usage: $(basename "$0") [dev|build|start|clean|help]

Commands:
  dev     Install deps and run frontend (Vite) + backend (Uvicorn) in watch mode
  build   Install deps and build frontend assets (served by backend at /syftai-server)
  start   Start backend only (serves prebuilt frontend from frontend/dist). Builds if missing
  clean   Remove virtualenv and frontend artifacts (node_modules, dist)
  help    Show this help

Environment:
  SYFTBOX_ASSIGNED_PORT   Backend port (default: 8080)
EOF
}

ensure_uv() {
    if ! command_exists uv; then
        echo "Error: 'uv' is required but not found. Install uv from https://docs.astral.sh/uv/" >&2
        exit 1
    fi
}

ensure_python_venv() {
    ensure_uv
    if [ ! -d "$VENV_DIR" ]; then
        if command_exists python3.12; then
            uv venv -p 3.12
        else
            echo "python3.12 not found; creating venv with default python" >&2
            uv venv
        fi
    fi
    # shellcheck disable=SC1091
    . "$VENV_DIR/bin/activate"
    uv pip install -e "$BACKEND_DIR"
}

detect_pkg_manager() {
    if command_exists bun; then
        echo bun
        elif command_exists pnpm; then
        echo pnpm
        elif command_exists yarn; then
        echo yarn
    else
        echo npm
    fi
}

frontend_install() {
    local pm
    pm="$(detect_pkg_manager)"
    (cd "$FRONTEND_DIR" && \
        case "$pm" in
            bun) bun install ;;
            pnpm) pnpm install ;;
            yarn) yarn install ;;
            npm) npm ci || npm install ;;
    esac)
}

frontend_build() {
    local pm
    pm="$(detect_pkg_manager)"
    (cd "$FRONTEND_DIR" && \
        case "$pm" in
            bun) bun run build ;;
            pnpm) pnpm run build ;;
            yarn) yarn run build ;;
            npm) npm run build ;;
    esac)
}

start_frontend_dev() {
    local pm
    pm="$(detect_pkg_manager)"
    (cd "$FRONTEND_DIR" && \
        case "$pm" in
            bun) bun run dev ;;
            pnpm) pnpm run dev ;;
            yarn) yarn run dev ;;
            npm) npm run dev ;;
    esac)
}

start_backend() {
    # shellcheck disable=SC1091
    . "$VENV_DIR/bin/activate"
    uv run uvicorn backend.main:app --reload --host 0.0.0.0 --port "$SYFTBOX_ASSIGNED_PORT"
}

cmd_dev() {
    ensure_python_venv
    frontend_install
    
    echo "Starting frontend dev server and backend API..."
    
    set +e
    start_frontend_dev &
    FE_PID=$!
    start_backend &
    BE_PID=$!
    
    trap 'kill "$FE_PID" "$BE_PID" 2>/dev/null || true' INT TERM EXIT
    # Portable wait loop for macOS bash 3.2 (no wait -n)
    while true; do
        if ! kill -0 "$FE_PID" 2>/dev/null; then
            # Frontend exited first
            wait "$FE_PID"
            FE_STATUS=$?
            kill "$BE_PID" 2>/dev/null || true
            wait "$BE_PID" 2>/dev/null || true
            exit "$FE_STATUS"
        fi
        if ! kill -0 "$BE_PID" 2>/dev/null; then
            # Backend exited first
            wait "$BE_PID"
            BE_STATUS=$?
            kill "$FE_PID" 2>/dev/null || true
            wait "$FE_PID" 2>/dev/null || true
            exit "$BE_STATUS"
        fi
        sleep 1
    done
}

cmd_build() {
    frontend_install
    frontend_build
    ensure_python_venv
    echo "Build complete. Static assets in frontend/dist; backend ready to serve at /syftai-server"
}

cmd_start() {
    ensure_python_venv
    if [ ! -d "$FRONTEND_DIR/dist" ]; then
        echo "No frontend build found; building now..."
        frontend_install
        frontend_build
    fi
    start_backend
}

cmd_clean() {
    echo "Cleaning virtualenv and frontend artifacts..."
    rm -rf "$VENV_DIR"
    rm -rf "$FRONTEND_DIR/node_modules"
    rm -rf "$FRONTEND_DIR/dist"
    echo "Done."
}

case "$MODE" in
    dev) cmd_dev ;;
    build) cmd_build ;;
    start) cmd_start ;;
    clean) cmd_clean ;;
    help|-h|--help) usage ;;
    *) echo "Unknown command: $MODE" >&2; echo; usage; exit 1 ;;
esac

