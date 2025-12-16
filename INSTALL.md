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

### 1. Install Python and System Dependencies

```bash
sudo apt update
sudo apt upgrade -y
sudo apt install -y python3 python3-pip python3-venv git
```

**Optional:** Install Qt dependencies (may help avoid issues):
```bash
sudo apt install -y libgl1-mesa-dev libxkbcommon-x11-0 libdbus-1-3
```

### 2. Clone the Repository

```bash
cd ~
git clone https://github.com/UserRmM/ntrip-checker-pro.git
cd ntrip-checker-pro
```

### 3. Create Virtual Environment (Recommended)

```bash
python3 -m venv venv
source venv/bin/activate
```

### 4. Install Python Packages

```bash
pip3 install -r requirements.txt
```

**Note:** Installation may take 5-10 minutes (PyQt6 packages are large).

### 5. Run the Application

```bash
python3 ntrip_checker_pro_v5_0.py
```

### 6. Create a Desktop Launcher (Optional)

Create a file `~/.local/share/applications/ntrip-checker.desktop`:

```ini
[Desktop Entry]
Type=Application
Name=NTRIP Checker PRO
Comment=GNSS NTRIP Client
Exec=/home/YOUR_USERNAME/ntrip-checker-pro/venv/bin/python3 /home/YOUR_USERNAME/ntrip-checker-pro/ntrip_checker_pro_v5_0.py
Icon=network-wireless
Terminal=false
Categories=Utility;Network;
```

**Note:** Replace `YOUR_USERNAME` with your actual username. If not using venv, use:
```ini
Exec=python3 /home/YOUR_USERNAME/ntrip-checker-pro/ntrip_checker_pro_v5_0.py
```

Then make it executable:
```bash
chmod +x ~/.local/share/applications/ntrip-checker.desktop
```

The app will appear in your application menu.

---

## Raspberry Pi

### 1. Prerequisites

**Minimum Requirements:**
- Raspberry Pi 4 (4GB RAM or more recommended)
- Raspberry Pi OS (64-bit recommended for better performance)
- Active internet connection

```bash
# Update system
sudo apt update
sudo apt upgrade -y

# Install build dependencies
sudo apt install -y python3 python3-pip python3-dev git \
  build-essential cmake libgl1-mesa-dev libxkbcommon-x11-0 \
  libdbus-1-3 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 \
  libxcb-randr0 libxcb-render-util0 libxcb-xinerama0 libxcb-xfixes0
```

### 2. Clone the Repository

```bash
cd ~
git clone https://github.com/UserRmM/ntrip-checker-pro.git
cd ntrip-checker-pro
```

### 3. Install Python Dependencies

```bash
pip3 install -r requirements.txt --break-system-packages
```

**Note:** 
- Installation may take **15-30 minutes** on Raspberry Pi (compiling PyQt6 from source)
- PyQt6-QtWebEngine (needed for the Map tab) is very resource-intensive
- If installation fails due to memory constraints, try increasing swap space:
  ```bash
  sudo dphys-swapfile swapoff
  sudo nano /etc/dphys-swapfile  # Set CONF_SWAPSIZE=2048
  sudo dphys-swapfile setup
  sudo dphys-swapfile swapon
  ```

### 4. Run the Application

```bash
python3 ntrip_checker_pro_v5_0.py
```

**Requirements:**
- HDMI display + keyboard/mouse, OR
- SSH with X11 forwarding for remote desktop

### 5. Start on Boot (Optional)

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

### ImportError: cannot import name 'uic' from 'PyQt6' (Raspberry Pi/Linux)

This occurs when system-installed PyQt6 is incomplete. 

**Solution 1: Use Virtual Environment (Recommended)**
```bash
cd ~/ntrip-checker-pro
python3 -m venv venv
source venv/bin/activate
pip3 install -r requirements.txt
python3 ntrip_checker_pro_v5_0.py
```

**Solution 2: Reinstall PyQt6 via pip**
```bash
# Remove system PyQt6 packages
sudo apt remove python3-pyqt6 python3-pyqt6.qtwebengine

# Install complete PyQt6 from pip
pip3 install --upgrade PyQt6 PyQt6-Qt6 PyQt6-WebEngine --break-system-packages
```

### ModuleNotFoundError: No module named 'PyQt6.QtWebEngineWidgets'

**Solution:**
```bash
pip3 install PyQt6-WebEngine --break-system-packages
```

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
