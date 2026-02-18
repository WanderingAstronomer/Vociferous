#!/usr/bin/env bash
# Remove macOS launcher shortcut for Vociferous.

set -euo pipefail

APP_TARGET="$HOME/Applications/Vociferous.command"
DESKTOP_LINK="$HOME/Desktop/Vociferous.command"

rm -f "$DESKTOP_LINK"
rm -f "$APP_TARGET"

echo "Removed macOS launcher shortcuts"
