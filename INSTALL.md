# Installation Guide

## Windows

### Option 1: Direct Installation (Recommended)

1. **Install Python 3.9 or later**
   - Download from [python.org](https://www.python.org/downloads/)
   - During installation, check **"Add Python to PATH"**

2. **Install Dependencies**
   - Open PowerShell or Command Prompt
   - Navigate to the project folder:
     ```powershell
     cd path\to\ntrip-checker-pro
     ```
   - Install required packages:
     ```powershell
     pip install -r requirements.txt
     ```

3. **Run the Application**
   ```powershell
   python ntrip_checker_pro_v5_0.py
   ```

### Option 2: Desktop Shortcut (No Console)

Create a desktop shortcut that launches the app directly without a console window:

```powershell
# Run this in PowerShell (adjust Python path if needed)
$pythonw = (Get-Command pythonw -ErrorAction SilentlyContinue).Source
if (-not $pythonw) {
  $pythonw = "C:\Users\$env:USERNAME\AppData\Local\Programs\Python\Python311\pythonw.exe"
}

$script = "C:\path\to\ntrip-checker-pro\ntrip_checker_pro_v5_0.py"
$desktop = [Environment]::GetFolderPath('Desktop')
$lnk = Join-Path $desktop "NTRIP Checker PRO.lnk"

$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($lnk)
$Shortcut.TargetPath = $pythonw
$Shortcut.Arguments = '"' + $script + '"'
$Shortcut.WorkingDirectory = Split-Path $script
$Shortcut.Save()

Write-Output "Shortcut created: $lnk"
```

Double-click the shortcut on your desktop to launch the app.

---

## Linux / Ubuntu

### 1. Install Python and Dependencies

```bash
sudo apt update
sudo apt upgrade -y
sudo apt install -y python3 python3-pip python3-pyqt6 python3-pyqt6.qtwebengine
```

### 2. Install Python Packages

```bash
cd /path/to/ntrip-checker-pro
pip3 install -r requirements.txt
```

### 3. Run the Application

```bash
python3 ntrip_checker_pro_v5_0.py
```

### 4. Create a Desktop Launcher (Optional)

Create a file `~/.local/share/applications/ntrip-checker.desktop`:

```ini
[Desktop Entry]
Type=Application
Name=NTRIP Checker PRO
Comment=GNSS NTRIP Client
Exec=python3 /full/path/to/ntrip_checker_pro_v5_0.py
Icon=network-wireless
Terminal=false
Categories=Utility;Network;
```

Then make it executable:
```bash
chmod +x ~/.local/share/applications/ntrip-checker.desktop
```

The app will appear in your application menu.

---

## Raspberry Pi

### 1. Prerequisites

```bash
# Update system
sudo apt update
sudo apt upgrade -y

# Install required packages
sudo apt install -y python3 python3-pip python3-pyqt6 python3-pyqt6.qtwebengine git
```

### 2. Install Python Dependencies

```bash
cd /path/to/ntrip-checker-pro
pip3 install -r requirements.txt
```

**Note:** Installation may take 5-10 minutes on Raspberry Pi (ARM processor is slower).

### 3. Run the Application

```bash
python3 ntrip_checker_pro_v5_0.py
```

**Requirements:**
- HDMI display + keyboard/mouse, OR
- SSH with X11 forwarding for remote desktop

### 4. Start on Boot (Optional)

Edit crontab:
```bash
crontab -e
```

Add at the end:
```
@reboot sleep 10 && DISPLAY=:0 python3 /full/path/to/ntrip_checker_pro_v5_0.py &
```

This will auto-launch the app 10 seconds after boot (adjust delay if needed).

---

## Troubleshooting

### ModuleNotFoundError: No module named 'PyQt6'

**Solution:**
```bash
pip install --upgrade PyQt6 PyQt6-Qt6
```

### "pythonw not found" (Windows)

**Solution:** Use full path to pythonw.exe:
```powershell
$pythonw = "C:\Users\YOUR_USERNAME\AppData\Local\Programs\Python\Python311\pythonw.exe"
# Then use this in the shortcut command above
```

### Permission Denied (Linux/Raspberry Pi)

**Solution:**
```bash
chmod +x ntrip_checker_pro_v5_0.py
python3 ./ntrip_checker_pro_v5_0.py
```

### QXcbConnection Error (Linux Remote)

**Solution:** Enable X11 forwarding when connecting via SSH:
```bash
ssh -X user@hostname
# Then run the app
```

### Application hangs on startup

**Solution:** Check system resources:
```bash
# Free up RAM and restart
free -h
```

On Raspberry Pi, consider disabling unnecessary services to free memory.

---

## Uninstall

### Windows

- Delete the project folder
- Delete the desktop shortcut

### Linux / Raspberry Pi

```bash
rm -rf /path/to/ntrip-checker-pro
pip3 uninstall PyQt6 pyrtcm qt-material
```

---

## Next Steps

1. Launch the application
2. Add your NTRIP caster details (see README.md Quick Start)
3. Start monitoring!

For issues, check `ntrip_checker.log` in the application directory.
