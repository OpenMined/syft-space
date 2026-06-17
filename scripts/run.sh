#!/usr/bin/env bash
#
# Bootstrap and run the standalone upload service.
#
# Installs uv (if missing), pins Python 3.12, downloads upload_service.py, and
# runs it. The service itself prompts for the upload folder and auth token.
# Safe to pipe straight from curl:
#
#   curl -fsSL https://raw.githubusercontent.com/OpenMined/syft-space/upload-service/scripts/run.sh | bash
#
set -euo pipefail

PYTHON_VERSION="3.12"
# Branch and URL can be overridden via env, e.g. BRANCH=main.
BRANCH="${BRANCH:-upload-service}"
SCRIPT_URL="${SCRIPT_URL:-https://raw.githubusercontent.com/OpenMined/syft-space/${BRANCH}/scripts/upload_service.py}"

# --- download the service script -----------------------------------------
SERVICE_DIR="$(mktemp -d)"
SERVICE_SCRIPT="${SERVICE_DIR}/upload_service.py"
# shellcheck disable=SC2064
trap "rm -rf '${SERVICE_DIR}'" EXIT
echo "==> Downloading upload_service.py from ${SCRIPT_URL}"
curl -fsSL "${SCRIPT_URL}" -o "${SERVICE_SCRIPT}"

# --- ensure uv is installed ----------------------------------------------
if ! command -v uv >/dev/null 2>&1; then
  echo "==> Installing uv"
  curl -fsSL https://astral.sh/uv/install.sh | sh
  # uv installs to ~/.local/bin (or $XDG_BIN_HOME); make it available now.
  export PATH="${HOME}/.local/bin:${XDG_BIN_HOME:-}:${PATH}"
fi
command -v uv >/dev/null 2>&1 || { echo "error: uv not found on PATH after install" >&2; exit 1; }

# --- ensure Python 3.12 is available -------------------------------------
echo "==> Ensuring Python ${PYTHON_VERSION} (uv will download if needed)"
uv python install "${PYTHON_VERSION}"

# --- run ------------------------------------------------------------------
# Redirect stdin from the terminal so the service's interactive prompts work
# even when this script is piped via curl | bash (whose stdin is the pipe).
echo "==> Starting upload service"
if [ -e /dev/tty ]; then
  exec uv run --python "${PYTHON_VERSION}" "${SERVICE_SCRIPT}" "$@" < /dev/tty
else
  exec uv run --python "${PYTHON_VERSION}" "${SERVICE_SCRIPT}" "$@"
fi
