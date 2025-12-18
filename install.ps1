# NTRIP Checker PRO - Automatic Installer for Windows
# Version 5.3 Development

$ErrorActionPreference = "Stop"

# Colors
function Write-Info { Write-Host $args -ForegroundColor Cyan }
function Write-Success { Write-Host "✓ $args" -ForegroundColor Green }
function Write-Warning { Write-Host "⚠ $args" -ForegroundColor Yellow }
function Write-Error { Write-Host "✗ $args" -ForegroundColor Red }

# Banner
Write-Host ""
Write-Info "╔════════════════════════════════════════╗"
Write-Info "║   NTRIP Checker PRO - Installer       ║"
Write-Info "║   Version 5.3 Development             ║"
Write-Info "╚════════════════════════════════════════╝"
Write-Host ""

# Get script directory
$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
$PYTHON_SCRIPT = Join-Path $SCRIPT_DIR "ntrip_checker_pro_v5_2.py"
$ICON_FILE = Join-Path $SCRIPT_DIR "icon.png"

# Check Python
Write-Info "[1/5] Checking Python installation..."
try {
    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if (-not $pythonCmd) {
        $pythonCmd = Get-Command python3 -ErrorAction SilentlyContinue
    }
    
    if (-not $pythonCmd) {
        Write-Error "Python not found!"
        Write-Host ""
        Write-Host "Please install Python 3.9 or later from:"
        Write-Host "  https://www.python.org/downloads/"
        Write-Host ""
        Write-Host "During installation, check 'Add Python to PATH'"
        exit 1
    }
    
    $pythonVersion = & $pythonCmd.Source --version 2>&1
    Write-Success "Python found: $pythonVersion"
} catch {
    Write-Error "Failed to check Python: $_"
    exit 1
}

# Check pip
Write-Host ""
Write-Info "[2/5] Checking pip..."
try {
    $pipVersion = & $pythonCmd.Source -m pip --version 2>&1
    Write-Success "pip found: $pipVersion"
} catch {
    Write-Warning "pip not found, installing..."
    & $pythonCmd.Source -m ensurepip --upgrade
}

# Install Python packages
Write-Host ""
Write-Info "[3/5] Installing Python packages..."
Write-Warning "This may take 5-10 minutes..."
Write-Host ""

try {
    Push-Location $SCRIPT_DIR
    & $pythonCmd.Source -m pip install --upgrade pip setuptools wheel
    & $pythonCmd.Source -m pip install -r requirements.txt
    Write-Host ""
    Write-Success "Python packages installed successfully"
} catch {
    Write-Host ""
    Write-Error "Failed to install Python packages: $_"
    Write-Host ""
    Write-Host "Try manual installation:"
    Write-Host "  pip install -r requirements.txt"
    Pop-Location
    exit 1
} finally {
    Pop-Location
}

# Create desktop shortcut
Write-Host ""
Write-Info "[4/5] Creating desktop shortcut..."

try {
    # Find pythonw.exe (GUI mode without console)
    $pythonwPath = $pythonCmd.Source -replace "python\.exe$", "pythonw.exe"
    if (-not (Test-Path $pythonwPath)) {
        $pythonwPath = $pythonCmd.Source
        Write-Warning "pythonw.exe not found, using python.exe (console will show)"
    }
    
    $desktop = [Environment]::GetFolderPath('Desktop')
    $shortcutPath = Join-Path $desktop "NTRIP Checker PRO.lnk"
    
    $WshShell = New-Object -ComObject WScript.Shell
    $Shortcut = $WshShell.CreateShortcut($shortcutPath)
    $Shortcut.TargetPath = $pythonwPath
    $Shortcut.Arguments = "`"$PYTHON_SCRIPT`""
    $Shortcut.WorkingDirectory = $SCRIPT_DIR
    $Shortcut.Description = "Professional NTRIP client for GNSS base stations"
    
    # Set icon if exists
    if (Test-Path $ICON_FILE) {
        # Convert PNG to ICO is complex, use Python icon for now
        $Shortcut.IconLocation = "$pythonwPath,0"
    }
    
    $Shortcut.Save()
    
    Write-Success "Desktop shortcut created: $shortcutPath"
} catch {
    Write-Warning "Failed to create desktop shortcut: $_"
    Write-Host "You can launch manually: python $PYTHON_SCRIPT"
}

# Ask about autostart
Write-Host ""
Write-Info "[5/5] Autostart configuration"
Write-Host ""
$response = Read-Host "Do you want NTRIP Checker PRO to start automatically on login? (y/N)"

if ($response -match "^[Yy]") {
    try {
        $startupPath = [Environment]::GetFolderPath('Startup')
        $startupShortcut = Join-Path $startupPath "NTRIP Checker PRO.lnk"
        
        $WshShell = New-Object -ComObject WScript.Shell
        $Shortcut = $WshShell.CreateShortcut($startupShortcut)
        $Shortcut.TargetPath = $pythonwPath
        $Shortcut.Arguments = "`"$PYTHON_SCRIPT`""
        $Shortcut.WorkingDirectory = $SCRIPT_DIR
        $Shortcut.Save()
        
        Write-Success "Autostart enabled (Startup folder)"
        Write-Warning "To disable: Delete shortcut from: $startupPath"
    } catch {
        Write-Warning "Failed to enable autostart: $_"
    }
} else {
    Write-Warning "Autostart disabled"
}

# Installation complete
Write-Host ""
Write-Host ""
Write-Success "╔════════════════════════════════════════╗"
Write-Success "║   Installation Complete! 🎉           ║"
Write-Success "╚════════════════════════════════════════╝"
Write-Host ""
Write-Host "Launch the application:"
Write-Host "  • Double-click desktop icon: NTRIP Checker PRO"
Write-Host "  • From terminal: python $PYTHON_SCRIPT"
Write-Host ""
Write-Warning "Note: Configuration saved in: $SCRIPT_DIR\casters.json"
Write-Host ""
