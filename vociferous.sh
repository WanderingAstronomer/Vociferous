#!/usr/bin/env bash
# Vociferous v4.0 Launcher
# Runs the application using the project virtual environment.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PYTHON="$SCRIPT_DIR/.venv/bin/python"

# Use venv Python if available, otherwise system Python
if [[ -x "$VENV_PYTHON" ]]; then
    PYTHON="$VENV_PYTHON"
else
    PYTHON="$(command -v python3 || command -v python)"
    if [[ -z "$PYTHON" ]]; then
        echo "Error: Python not found. Run scripts/install.sh first." >&2
        exit 1
    fi
fi

# Build frontend if dist/ doesn't exist
if [[ ! -d "$SCRIPT_DIR/frontend/dist" ]] && [[ -f "$SCRIPT_DIR/frontend/package.json" ]]; then
    echo "Building frontend..."
    (cd "$SCRIPT_DIR/frontend" && npm install --silent && npx vite build)
fi

# NVIDIA DRM workaround: Disable WebKitGTK GPU acceleration to prevent
# kernel panic (nv_drm_revoke_modeset_permission crash on Wayland).
# See: NVIDIA driver 550.x has known DRM permission bugs with concurrent access.
export WEBKIT_DISABLE_COMPOSITING_MODE=1
export WEBKIT_DISABLE_DMABUF_RENDERER=1

# Change to script directory so Python can find the src module
cd "$SCRIPT_DIR"

exec "$PYTHON" -m src.main "$@"
