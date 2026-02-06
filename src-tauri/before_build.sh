#!/usr/bin/env bash
# Pre-build script for Tauri. Runs before `cargo build` during `tauri build`.
# Tauri executes beforeBuildCommand from the src-tauri/ directory.
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# Prefer Tauri's target triple over host triple (important for cross-compilation)
TARGET_TRIPLE="${TAURI_ENV_TARGET_TRIPLE:-$(rustc -vV | grep 'host:' | awk '{print $2}')}"

# Determine platform-specific extensions
if [[ "$TARGET_TRIPLE" == *"windows"* ]]; then
    EXE_EXT=".exe"
else
    EXE_EXT=""
fi

# 1. Fetch process-wick if not present
PROCESS_WICK_PATH="$(dirname "$0")/target/process-wick-${TARGET_TRIPLE}${EXE_EXT}"
if [ ! -f "$PROCESS_WICK_PATH" ]; then
    mkdir -p "$(dirname "$PROCESS_WICK_PATH")"
    echo "Downloading process-wick for $TARGET_TRIPLE..."
    curl -fsSL -o "$PROCESS_WICK_PATH" \
        "https://github.com/itstauq/process-wick/releases/latest/download/process-wick-${TARGET_TRIPLE}${EXE_EXT}"
    chmod +x "$PROCESS_WICK_PATH"
    echo "process-wick downloaded to $PROCESS_WICK_PATH"
else
    echo "process-wick already present"
fi

# 2. Build backend with PyInstaller
cd "$PROJECT_ROOT"
uv run pyinstaller backend/syft-space.spec

# 3. Copy backend binary with target triple suffix
mkdir -p src-tauri/target
cp "dist/syft-space${EXE_EXT}" "src-tauri/target/syft-space-${TARGET_TRIPLE}${EXE_EXT}"

# 4. Build frontend
VITE_API_BASE_URL=http://localhost:8080/api/v1 bun run --cwd frontend build
