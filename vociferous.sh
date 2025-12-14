#!/bin/bash
# Vociferous GPU-friendly launcher wrapper
# Sets LD_LIBRARY_PATH for venv-provided CUDA libs, then runs scripts/run.py

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
VENV_PATH="$PROJECT_ROOT/.venv"
PYTHON_BIN="$VENV_PATH/bin/python"

# Prefer venv python if available
if [[ -x "$PYTHON_BIN" ]]; then
  PYTHON_CMD="$PYTHON_BIN"
else
  PYTHON_CMD="python3"
fi

# Discover venv site-packages nvidia libs and patch LD_LIBRARY_PATH
LIB_DIR="$VENV_PATH/lib"
if [[ -d "$LIB_DIR" ]]; then
  PYTHON_DIR=$(ls -d "$LIB_DIR"/python3.* 2>/dev/null | head -n1 || true)
  if [[ -n "$PYTHON_DIR" ]]; then
    NVIDIA_DIR="$PYTHON_DIR/site-packages/nvidia"
    CUDNN_LIB="$NVIDIA_DIR/cudnn/lib"
    CUBLAS_LIB="$NVIDIA_DIR/cublas/lib"
    if [[ -d "$CUDNN_LIB" && -d "$CUBLAS_LIB" ]]; then
      export LD_LIBRARY_PATH="$CUDNN_LIB:$CUBLAS_LIB:${LD_LIBRARY_PATH:-}"
      export CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES:-0}
    fi
  fi
fi

# Run the application
exec "$PYTHON_CMD" "$PROJECT_ROOT/scripts/run.py" "$@"
