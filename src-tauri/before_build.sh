#!/usr/bin/env bash
# Pre-build script for Tauri. Runs before `cargo build` during `tauri build`.
# Tauri executes beforeBuildCommand from the src-tauri/ directory.
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TARGET_TRIPLE="$(rustc -vV | grep 'host:' | awk '{print $2}')"

# 1. Fetch process-wick if not present
PROCESS_WICK_PATH="$(dirname "$0")/target/process-wick-$TARGET_TRIPLE"
if [ ! -f "$PROCESS_WICK_PATH" ]; then
    mkdir -p "$(dirname "$PROCESS_WICK_PATH")"
    echo "Downloading process-wick for $TARGET_TRIPLE..."
    curl -fsSL -o "$PROCESS_WICK_PATH" \
        "https://github.com/itstauq/process-wick/releases/latest/download/process-wick-$TARGET_TRIPLE"
    chmod +x "$PROCESS_WICK_PATH"
    echo "process-wick downloaded to $PROCESS_WICK_PATH"
else
    echo "process-wick already present"
fi

# 2. Build backend with PyInstaller
cd "$PROJECT_ROOT"
uv run pyinstaller backend/syft-space.spec

# 3. Copy backend binary with target triple suffix
cp dist/syft-space "src-tauri/target/syft-space-$TARGET_TRIPLE"

# 4. Build frontend
VITE_API_BASE_URL=http://localhost:8080/api/v1 bun run --cwd frontend build
