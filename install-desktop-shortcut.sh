#!/bin/bash
# NTRIP Checker PRO - Desktop Shortcut Installer
# This script installs a desktop shortcut for easy application launching

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}NTRIP Checker PRO - Desktop Shortcut Installer${NC}"
echo "================================================="
echo ""

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
DESKTOP_FILE="$SCRIPT_DIR/ntrip-checker-pro.desktop"
ICON_FILE="$SCRIPT_DIR/icon.png"

# Check if .desktop file exists
if [ ! -f "$DESKTOP_FILE" ]; then
    echo -e "${RED}Error: ntrip-checker-pro.desktop not found in $SCRIPT_DIR${NC}"
    exit 1
fi

# Create applications directory if it doesn't exist
mkdir -p ~/.local/share/applications

# Create the desktop entry with absolute paths
cat > ~/.local/share/applications/ntrip-checker-pro.desktop << EOF
[Desktop Entry]
Version=5.2
Type=Application
Name=NTRIP Checker PRO
Comment=Professional NTRIP client for GNSS base stations
Exec=python3 $SCRIPT_DIR/ntrip_checker_pro_v5_2.py
Icon=$ICON_FILE
Path=$SCRIPT_DIR
Terminal=false
Categories=Science;Geography;Education;
Keywords=NTRIP;GNSS;GPS;RTK;Caster;
StartupNotify=true
EOF

# Make the desktop entry executable
chmod +x ~/.local/share/applications/ntrip-checker-pro.desktop

echo -e "${GREEN}✓${NC} Desktop shortcut installed successfully!"
echo ""
echo "The application should now appear in your application menu."
echo "You can search for 'NTRIP Checker PRO' or find it under:"
echo "  • Science"
echo "  • Geography"
echo ""

# Optional: Copy to Desktop
read -p "Do you want to create a shortcut on your Desktop? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    DESKTOP_DIR="$HOME/Desktop"
    if [ -d "$DESKTOP_DIR" ]; then
        cp ~/.local/share/applications/ntrip-checker-pro.desktop "$DESKTOP_DIR/"
        chmod +x "$DESKTOP_DIR/ntrip-checker-pro.desktop"
        
        # For Ubuntu 20.04+ with GNOME, allow launching
        if command -v gio &> /dev/null; then
            gio set "$DESKTOP_DIR/ntrip-checker-pro.desktop" metadata::trusted true
        fi
        
        echo -e "${GREEN}✓${NC} Desktop shortcut created at $DESKTOP_DIR"
    else
        echo -e "${RED}Warning: Desktop directory not found at $DESKTOP_DIR${NC}"
    fi
fi

echo ""
echo -e "${GREEN}Installation complete!${NC}"
echo ""
echo "Note: If you don't see an icon, make sure icon.png exists in:"
echo "  $SCRIPT_DIR"
