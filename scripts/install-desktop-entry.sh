#!/bin/bash
# Install Vociferous desktop entry for Linux application launchers
# Works with GNOME, KDE, XFCE, and other XDG-compliant environments

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Resolve absolute path for desktop entry (required for portable installs)
ABS_VOCIFEROUS_PATH="$(cd "$PROJECT_DIR" && pwd)/vociferous"

# XDG paths
APPLICATIONS_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
ICONS_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor"

echo "Installing Vociferous desktop entry..."
echo "  Application path: $ABS_VOCIFEROUS_PATH"

# Create directories if they don't exist
mkdir -p "$APPLICATIONS_DIR"
mkdir -p "$ICONS_DIR/scalable/apps"
mkdir -p "$ICONS_DIR/48x48/apps"

# Copy the system tray icon (which we have)
if [ -f "$PROJECT_DIR/assets/icons/system_tray_icon.png" ]; then
    cp "$PROJECT_DIR/assets/icons/system_tray_icon.png" "$ICONS_DIR/48x48/apps/vociferous.png"
    echo "  ✓ Installed 48x48 icon"
else
    echo "  ⚠ Warning: system_tray_icon.png not found (optional)"
fi

# Create desktop entry with absolute path
cat > "$APPLICATIONS_DIR/vociferous.desktop" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Vociferous
Comment=Speech-to-text dictation using Whisper
Exec=sh -c "cd '$PROJECT_DIR' && '$ABS_VOCIFEROUS_PATH' >> /tmp/vociferous-launcher.log 2>&1"
Icon=vociferous
Terminal=false
Categories=Utility;
Keywords=speech;dictation;transcription;whisper;voice;
StartupNotify=true
StartupWMClass=vociferous
X-AppStream-Ignore=false
EOF

echo "  ✓ Created desktop entry"

# Validate desktop entry
if command -v desktop-file-validate &> /dev/null; then
    if desktop-file-validate "$APPLICATIONS_DIR/vociferous.desktop" 2>/dev/null; then
        echo "  ✓ Desktop entry is valid"
    else
        echo "  ⚠ Warning: Desktop entry validation found issues (may still work)"
    fi
fi

# Update icon cache if possible
if command -v gtk-update-icon-cache &> /dev/null; then
    gtk-update-icon-cache -f -t "$ICONS_DIR" 2>/dev/null || true
    echo "  ✓ Updated icon cache"
fi

# Update desktop database if possible
if command -v update-desktop-database &> /dev/null; then
    update-desktop-database "$APPLICATIONS_DIR" 2>/dev/null || true
    echo "  ✓ Updated desktop database"
fi

echo ""
echo "Installation complete!"
echo ""
echo "Vociferous should now appear in your application launcher."
echo "If it doesn't appear immediately:"
echo "  - Try logging out and back in"
echo "  - Run: killall -9 plasmashell  (for KDE Plasma)"
echo ""
echo "To verify the installation:"
echo "  grep Exec $APPLICATIONS_DIR/vociferous.desktop"
echo ""
echo "To uninstall, run: ./scripts/uninstall-desktop-entry.sh"
