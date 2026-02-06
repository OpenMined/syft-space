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
rm -rf dist/syft-space-backend build/syft-space-backend
uv run pyinstaller backend/syft-space-backend.spec

# 3. Copy the onedir output to src-tauri/target/syft-space-backend-dist/
#    Tauri resources don't use the target-triple suffix convention.
BACKEND_DIST="src-tauri/target/syft-space-backend-dist"
rm -rf "$BACKEND_DIST"
mkdir -p "$BACKEND_DIST"
cp -R dist/syft-space-backend/* "$BACKEND_DIST/"

# 4. Ensure the main executable is executable
chmod +x "$BACKEND_DIST/syft-space-backend${EXE_EXT}"

# 5. On macOS, codesign all binaries for notarization.
#    PyInstaller may hardlink _internal/Python -> Python.framework/Versions/X.Y/Python.
#    We sign the framework (which covers the hardlink too), then sign remaining
#    standalone Mach-O files, skipping any that are hardlinked into a framework.
if [[ "$TARGET_TRIPLE" == *"apple"* ]]; then
    ENTITLEMENTS="$PROJECT_ROOT/src-tauri/entitlements.plist"
    SIGN_IDENTITY="${APPLE_SIGNING_IDENTITY:--}"
    echo "Codesigning PyInstaller onedir output (identity: $SIGN_IDENTITY)..."

    # a) Sign .framework bundles first (covers hardlinked binaries like _internal/Python)
    find "$BACKEND_DIST" -type d -name "*.framework" | while read -r fw; do
        codesign --force --deep --options runtime --entitlements "$ENTITLEMENTS" \
            --sign "$SIGN_IDENTITY" "$fw"
    done

    # b) Sign remaining Mach-O files outside .framework bundles.
    #    Skip files that are hardlinked into a framework (link count > 1) —
    #    they already share the framework's signature via the same inode.
    find "$BACKEND_DIST" -type f ! -name "syft-space-backend" | while read -r f; do
        if [[ "$f" == *".framework/"* ]]; then
            continue
        fi
        if file "$f" | grep -q "Mach-O"; then
            link_count=$(stat -f '%l' "$f" 2>/dev/null || stat -c '%h' "$f" 2>/dev/null)
            if [ "$link_count" -gt 1 ]; then
                echo "Skipping hardlinked file: $f (link count: $link_count)"
                continue
            fi
            codesign --force --options runtime --entitlements "$ENTITLEMENTS" \
                --sign "$SIGN_IDENTITY" "$f"
        fi
    done

    # c) Sign the main executable last
    codesign --force --options runtime --entitlements "$ENTITLEMENTS" \
        --sign "$SIGN_IDENTITY" "$BACKEND_DIST/syft-space-backend${EXE_EXT}"
    echo "Codesigning complete."
fi

# 6. Build frontend
VITE_API_BASE_URL=http://localhost:8080/api/v1 bun run --cwd frontend build
