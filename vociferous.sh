#!/usr/bin/env bash
# Vociferous v4.1 Launcher
# Runs the application using the project virtual environment.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PYTHON="$SCRIPT_DIR/.venv/bin/python"
FRONTEND_DIR="$SCRIPT_DIR/frontend"
FRONTEND_DIST_DIR="$FRONTEND_DIR/dist"
FRONTEND_BUILD_STAMP="$FRONTEND_DIST_DIR/.vociferous-build-stamp"

frontend_needs_build() {
    [[ ! -f "$FRONTEND_DIR/package.json" ]] && return 1

    if [[ ! -d "$FRONTEND_DIST_DIR" ]] || [[ ! -f "$FRONTEND_BUILD_STAMP" ]]; then
        return 0
    fi

    find \
        "$FRONTEND_DIR/src" \
        "$FRONTEND_DIR/index.html" \
        "$FRONTEND_DIR/package.json" \
        "$FRONTEND_DIR/package-lock.json" \
        "$FRONTEND_DIR/svelte.config.js" \
        "$FRONTEND_DIR/tsconfig.json" \
        "$FRONTEND_DIR/tsconfig.app.json" \
        "$FRONTEND_DIR/tsconfig.node.json" \
        "$FRONTEND_DIR/vite.config.js" \
        "$FRONTEND_DIR/vite.config.ts" \
        -type f -newer "$FRONTEND_BUILD_STAMP" -print -quit 2>/dev/null | grep -q .
}

build_frontend() {
    echo "Building frontend..."
    (cd "$FRONTEND_DIR" && npm install --silent && npx vite build)
    touch "$FRONTEND_BUILD_STAMP"
}

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

# Build frontend if dist/ is missing or stale
if frontend_needs_build; then
    build_frontend
fi

# NVIDIA DRM workaround: Disable WebKitGTK GPU acceleration to prevent
# kernel panic (nv_drm_revoke_modeset_permission crash on Wayland).
# See: NVIDIA driver 550.x has known DRM permission bugs with concurrent access.
export WEBKIT_DISABLE_COMPOSITING_MODE=1
export WEBKIT_DISABLE_DMABUF_RENDERER=1

# Change to script directory so Python can find the src module
cd "$SCRIPT_DIR"

exec "$PYTHON" -m src.main "$@"
