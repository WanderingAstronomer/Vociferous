#!/usr/bin/env bash
# Install a macOS launcher shortcut for Vociferous.
# Creates ~/Applications/Vociferous.command and a Desktop symlink.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
APP_DIR="$HOME/Applications"
COMMAND_TARGET="$APP_DIR/Vociferous.command"
DESKTOP_LINK="$HOME/Desktop/Vociferous.command"

mkdir -p "$APP_DIR"

cat > "$COMMAND_TARGET" <<EOF
#!/usr/bin/env bash
set -euo pipefail
cd "$PROJECT_DIR"
exec ./vociferous.sh
EOF

chmod +x "$COMMAND_TARGET"

if [[ -d "$HOME/Desktop" ]]; then
    ln -sfn "$COMMAND_TARGET" "$DESKTOP_LINK"
fi

echo "Installed macOS launcher: $COMMAND_TARGET"
if [[ -L "$DESKTOP_LINK" ]]; then
    echo "Desktop shortcut: $DESKTOP_LINK"
fi
