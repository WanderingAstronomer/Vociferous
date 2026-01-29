#!/usr/bin/env bash
set -euo pipefail

# run_tests.sh
# Helper wrapper to ensure tests run with the project's .venv Python and
# from the project root. Usage:
#   bash scripts/run_tests.sh [--force-ignore-running] [pytest-args...]

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

VENV_PY="$ROOT_DIR/.venv/bin/python"

FORCE_IGNORE=0
ARGS=()
for arg in "$@"; do
  case "$arg" in
    --force-ignore-running)
      FORCE_IGNORE=1
      ;;
    *)
      ARGS+=("$arg")
      ;;
  esac
done

if [ ! -x "$VENV_PY" ]; then
  echo "ERROR: Project virtualenv not found at .venv or not executable."
  echo "Install dependencies in the project's venv first:"
  echo "  python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
  exit 1
fi

# Optionally set VOCIFEROUS_TEST_IGNORE_RUNNING (for CI or headless test runners)
if [ "$FORCE_IGNORE" -eq 1 ]; then
  export VOCIFEROUS_TEST_IGNORE_RUNNING=1
fi

# Run pytest via the venv python from the project root
exec "$VENV_PY" -m pytest "${ARGS[@]}"
