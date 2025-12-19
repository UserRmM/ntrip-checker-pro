#!/bin/bash
# NTRIP Checker PRO - Automatic Installer
# Supports: Ubuntu, Debian, Raspberry Pi OS

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
VENV_DIR="$SCRIPT_DIR/venv"
PYTHON_SCRIPT="$SCRIPT_DIR/ntrip_checker_pro_v5_2.py"

echo -e "${BLUE}"
echo "╔════════════════════════════════════════╗"
echo "║   NTRIP Checker PRO - Installer       ║"
echo "║   Version 5.3                         ║"
echo "╚════════════════════════════════════════╝"
echo -e "${NC}"
echo ""

# Check if running as root
if [ "$EUID" -eq 0 ]; then 
    echo -e "${RED}Error: Do not run this script as root (sudo)${NC}"
    echo "Run as normal user: ./install.sh"
    exit 1
fi

# Detect OS
echo -e "${BLUE}[1/7]${NC} Detecting system..."
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$NAME
    echo -e "  ${GREEN}✓${NC} Detected: $OS"
else
    echo -e "  ${YELLOW}⚠${NC} Unknown OS, continuing anyway..."
fi

# Check Python version
echo ""
echo -e "${BLUE}[2/7]${NC} Checking Python..."
if ! command -v python3 &> /dev/null; then
    echo -e "  ${RED}✗${NC} Python 3 not found"
    echo ""
    echo "Please install Python 3.9 or later:"
    echo "  sudo apt update"
    echo "  sudo apt install python3 python3-pip python3-venv"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | awk '{print $2}')
echo -e "  ${GREEN}✓${NC} Python $PYTHON_VERSION found"

# Install system dependencies
echo ""
echo -e "${BLUE}[3/7]${NC} Installing system dependencies..."
echo -e "  ${YELLOW}⚠${NC} This may require sudo password"
echo ""

PACKAGES="python3-pip python3-venv git"

# Raspberry Pi needs extra Qt dependencies
if echo "$OS" | grep -qi "raspberry"; then
    PACKAGES="$PACKAGES libgl1-mesa-dev libxkbcommon-x11-0 libdbus-1-3 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 libxcb-xinerama0 libxcb-xfixes0"
fi

if sudo apt update && sudo apt install -y $PACKAGES; then
    echo -e "  ${GREEN}✓${NC} System dependencies installed"
else
    echo -e "  ${YELLOW}⚠${NC} Some dependencies may have failed, continuing..."
fi

# Create virtual environment
echo ""
echo -e "${BLUE}[4/7]${NC} Creating virtual environment..."
if [ -d "$VENV_DIR" ]; then
    echo -e "  ${YELLOW}⚠${NC} Virtual environment already exists, skipping"
else
    python3 -m venv "$VENV_DIR"
    echo -e "  ${GREEN}✓${NC} Virtual environment created"
fi

# Activate venv and install Python packages
echo ""
echo -e "${BLUE}[5/7]${NC} Installing Python packages..."
echo -e "  ${YELLOW}⚠${NC} This may take 5-30 minutes depending on your system"
echo ""

source "$VENV_DIR/bin/activate"

if pip install --upgrade pip setuptools wheel && pip install -r "$SCRIPT_DIR/requirements.txt"; then
    echo ""
    echo -e "  ${GREEN}✓${NC} Python packages installed successfully"
else
    echo ""
    echo -e "  ${RED}✗${NC} Failed to install Python packages"
    echo ""
    echo "Try manual installation:"
    echo "  source venv/bin/activate"
    echo "  pip install -r requirements.txt"
    exit 1
fi

deactivate

# Create desktop shortcut
echo ""
echo -e "${BLUE}[6/7]${NC} Creating desktop shortcut..."

# Create applications directory
mkdir -p ~/.local/share/applications

# Create desktop entry with venv Python
cat > ~/.local/share/applications/ntrip-checker-pro.desktop << EOF
[Desktop Entry]
Version=5.3
Type=Application
Name=NTRIP Checker PRO
Comment=Professional NTRIP client for GNSS base stations
Exec=$VENV_DIR/bin/python3 $PYTHON_SCRIPT
Icon=$SCRIPT_DIR/icon.png
Path=$SCRIPT_DIR
Terminal=false
Categories=Science;Geography;Education;
Keywords=NTRIP;GNSS;GPS;RTK;Caster;
StartupNotify=true
EOF

chmod +x ~/.local/share/applications/ntrip-checker-pro.desktop

# Copy to Desktop if it exists
if [ -d "$HOME/Desktop" ]; then
    cp ~/.local/share/applications/ntrip-checker-pro.desktop "$HOME/Desktop/"
    chmod +x "$HOME/Desktop/ntrip-checker-pro.desktop"
    
    # For Ubuntu 20.04+ with GNOME
    if command -v gio &> /dev/null; then
        gio set "$HOME/Desktop/ntrip-checker-pro.desktop" metadata::trusted true 2>/dev/null || true
    fi
    
    echo -e "  ${GREEN}✓${NC} Desktop shortcut created (application menu + desktop)"
else
    echo -e "  ${GREEN}✓${NC} Desktop shortcut created (application menu)"
fi

# Ask about autostart
echo ""
echo -e "${BLUE}[7/7]${NC} Autostart configuration"
echo ""
read -p "Do you want NTRIP Checker PRO to start automatically on boot? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    # Add to crontab
    (crontab -l 2>/dev/null | grep -v "ntrip_checker_pro"; echo "@reboot sleep 10 && DISPLAY=:0 $VENV_DIR/bin/python3 $PYTHON_SCRIPT &") | crontab -
    echo -e "  ${GREEN}✓${NC} Autostart enabled (via crontab)"
    echo -e "  ${YELLOW}ℹ${NC} To disable: run 'crontab -e' and remove the ntrip_checker_pro line"
else
    echo -e "  ${YELLOW}⊘${NC} Autostart disabled"
fi

# Installation complete
echo ""
echo -e "${GREEN}"
echo "╔════════════════════════════════════════╗"
echo "║   Installation Complete! 🎉           ║"
echo "╚════════════════════════════════════════╝"
echo -e "${NC}"
echo ""
echo "Launch the application:"
echo "  • From application menu: Science → NTRIP Checker PRO"
echo "  • From desktop icon (double-click)"
echo "  • From terminal: $VENV_DIR/bin/python3 $PYTHON_SCRIPT"
echo ""
echo -e "${YELLOW}Note:${NC} Configuration saved in: $SCRIPT_DIR/casters.json"
echo ""
