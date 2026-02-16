#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# Vociferous v4.0 — Pre-Launch Purge Script
#
# Removes ALL data from previous Vociferous installations:
#   • Old configs (YAML format, Qt window state)
#   • Old databases and history
#   • Old CTranslate2/faster-whisper models (v4 uses GGML/GGUF)
#   • Cache files, logs, crash dumps
#   • HuggingFace Hub download cache
#   • Stale lockfiles and __pycache__
#
# Run from the project root:
#   bash scripts/purge_old_data.sh [--yes]
#
# Pass --yes to skip confirmation prompts.
# ──────────────────────────────────────────────────────────────
set -euo pipefail

RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

AUTO_YES=false
if [[ "${1:-}" == "--yes" ]]; then
    AUTO_YES=true
fi

# Resolve project root (script lives in scripts/)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo -e "${CYAN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║   Vociferous v4.0 — Pre-Launch Data Purge       ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════╝${NC}"
echo

# ── Directories to remove ──
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/vociferous"
CONFIG_DIR_QT="$HOME/.config/Vociferous"
DATA_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/vociferous"
CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/vociferous"
HF_CACHE="$HOME/.cache/huggingface"
LOCKFILE="/tmp/vociferous.lock"
VENV_DIR="$PROJECT_ROOT/.venv"

# ── Show what will be removed ──
echo -e "${YELLOW}The following will be PERMANENTLY DELETED:${NC}"
echo

total_size=0

show_target() {
    local path="$1"
    local desc="$2"
    if [[ -e "$path" ]]; then
        local size
        size=$(du -sh "$path" 2>/dev/null | cut -f1)
        echo -e "  ${RED}✗${NC} $path ${CYAN}($size)${NC} — $desc"
    else
        echo -e "  ${GREEN}✓${NC} $path — (not found, skipping)"
    fi
}

show_target "$CONFIG_DIR"    "Old v3 config (config.yaml)"
show_target "$CONFIG_DIR_QT" "Old Qt/PyQt5 window state"
show_target "$DATA_DIR"      "Old database, crash dumps, logs"
show_target "$CACHE_DIR"     "Old models (CTranslate2/faster-whisper), engine logs"
show_target "$HF_CACHE"      "HuggingFace Hub download cache"
show_target "$LOCKFILE"      "Stale lockfile"
show_target "$VENV_DIR"      "Python virtual environment (will be recreated)"

echo
echo -e "  ${YELLOW}+${NC} All __pycache__/ dirs under $PROJECT_ROOT"
echo

# ── Confirm ──
if [[ "$AUTO_YES" != true ]]; then
    echo -e "${RED}⚠  This cannot be undone. Old transcription history will be lost.${NC}"
    read -rp "Type 'PURGE' to confirm: " confirm
    if [[ "$confirm" != "PURGE" ]]; then
        echo -e "${YELLOW}Aborted.${NC}"
        exit 0
    fi
fi

echo
echo -e "${CYAN}Purging...${NC}"

# ── Remove directories ──
remove_if_exists() {
    local path="$1"
    if [[ -e "$path" ]]; then
        rm -rf "$path"
        echo -e "  ${GREEN}✓${NC} Removed $path"
    fi
}

remove_if_exists "$CONFIG_DIR"
remove_if_exists "$CONFIG_DIR_QT"
remove_if_exists "$DATA_DIR"
remove_if_exists "$CACHE_DIR"
remove_if_exists "$HF_CACHE"
remove_if_exists "$LOCKFILE"
remove_if_exists "$VENV_DIR"

# ── Clean __pycache__ from project ──
cache_count=$(find "$PROJECT_ROOT" -name __pycache__ -type d 2>/dev/null | grep -cv '.venv' || true)
find "$PROJECT_ROOT" -name __pycache__ -type d -not -path '*/.venv/*' -exec rm -rf {} + 2>/dev/null || true
echo -e "  ${GREEN}✓${NC} Removed $cache_count __pycache__ directories"

# ── Clean .pyc files ──
find "$PROJECT_ROOT" -name '*.pyc' -type f -not -path '*/.venv/*' -delete 2>/dev/null || true
echo -e "  ${GREEN}✓${NC} Removed stale .pyc files"

echo
echo -e "${GREEN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   Purge complete! Clean slate for v4.0           ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════╝${NC}"
echo
echo -e "Next steps:"
echo -e "  1. ${CYAN}python3 -m venv .venv && source .venv/bin/activate${NC}"
echo -e "  2. ${CYAN}pip install -r requirements.txt${NC}"
echo -e "  3. ${CYAN}./vociferous${NC}"
echo
