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

# 2. Build backend with PyInstaller (--onedir mode via .spec)
cd "$PROJECT_ROOT"
uv run pyinstaller --noconfirm backend/syft-space-backend.spec

# 3. Copy the onedir output to src-tauri/target/syft-space-backend-dist/
BACKEND_DIST="src-tauri/target/syft-space-backend-dist"
rm -rf "$BACKEND_DIST"
mkdir -p "$BACKEND_DIST"
# -L dereferences symlinks so Tauri's fs::copy won't break them later
cp -RL dist/syft-space-backend/* "$BACKEND_DIST/"
chmod +x "$BACKEND_DIST/syft-space-backend${EXE_EXT}"

# 4. On macOS, codesign all binaries for notarization.
if [[ "$TARGET_TRIPLE" == *"apple"* ]]; then
    ENTITLEMENTS="$PROJECT_ROOT/src-tauri/entitlements.plist"
    SIGN_IDENTITY="${APPLE_SIGNING_IDENTITY:--}"
    
    # Remove .framework bundles — cp -RL breaks their internal symlink structure,
    # making them fail notarization. The standalone binaries (e.g. _internal/Python)
    # are already independent copies and sufficient for runtime.
    find "$BACKEND_DIST" -type d -name "*.framework" -exec rm -rf {} +
    
    echo "Codesigning PyInstaller onedir output (identity: $SIGN_IDENTITY)..."
    find "$BACKEND_DIST" -type f ! -name "syft-space-backend" | while read -r f; do
        if file "$f" | grep -q "Mach-O"; then
            codesign --force --options runtime --entitlements "$ENTITLEMENTS" \
            --sign "$SIGN_IDENTITY" "$f"
        fi
    done
    
    # Sign main executable last
    codesign --force --options runtime --entitlements "$ENTITLEMENTS" \
    --sign "$SIGN_IDENTITY" "$BACKEND_DIST/syft-space-backend${EXE_EXT}"
    echo "Codesigning complete."
fi

# 5. Build frontend
bun run --cwd frontend build
