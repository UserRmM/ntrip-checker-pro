# NTRIP Checker PRO v5.3
# A professional GNSS NTRIP client with real-time satellite tracking and RTCM message analysis

__version__ = "5.3"
__author__ = "Raine Mustonen"
__github__ = "https://github.com/UserRmM/ntrip-checker-pro"

import sys, io, base64, socket, threading, json, os, time, logging
from logging.handlers import RotatingFileHandler
from datetime import datetime, timedelta
from functools import partial
from pyrtcm import RTCMReader
from html import escape
import urllib.request
import urllib.error
from PyQt6.QtWidgets import (
    QApplication, QWidget, QTabWidget, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QMessageBox, QPushButton, QHeaderView, QDialog, QFormLayout,
    QLineEdit, QSpinBox, QHBoxLayout, QSizePolicy, QComboBox, QTextBrowser, QMenuBar, QMenu
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject, QUrl
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtGui import QColor, QDesktopServices
from qt_material import apply_stylesheet

def get_casters_file_path():
    """Get path to casters.json file. Checks environment variable first, then uses default."""
    env_path = os.environ.get('NTRIP_CASTERS_PATH')
    if env_path:
        print(f"INFO: Using casters file from environment variable: {env_path}")
        return env_path
    
    # Default: casters.json in script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    default_path = os.path.join(script_dir, "casters.json")
    print(f"INFO: Using default casters file: {default_path}")
    return default_path

CASTERS_FILENAME = get_casters_file_path()

# Satellite data extraction
def extract_satellite_info(parsed):
    """Extract satellite and signal information from RTCM message."""
    satellites = {
        'GPS': set(),
        'GLONASS': set(),
        'Galileo': set(),
        'BeiDou': set(),
        'QZSS': set(),
        'SBAS': set()
    }
    
    signals = {
        'GPS': set(),
        'GLONASS': set(),
        'Galileo': set(),
        'BeiDou': set(),
        'QZSS': set(),
        'SBAS': set()
    }
    
    # Signal ID to frequency name mapping per constellation
    signal_map = {
        'GPS': {1: 'L1 C/A', 2: 'L1 P(Y)', 3: 'L1 M', 4: 'L2 P(Y)', 5: 'L2 C', 6: 'L2 M', 7: 'L5 I', 8: 'L5 Q'},
        'GLONASS': {1: 'G1 C/A', 2: 'G1 P', 3: 'G2 C/A', 4: 'G2 P', 5: 'G3 I', 6: 'G3 Q'},
        'Galileo': {1: 'E1 C', 2: 'E1 A', 3: 'E1 B', 4: 'E5a I', 5: 'E5a Q', 6: 'E5b I', 7: 'E5b Q', 8: 'E6 C'},
        'BeiDou': {1: 'B1 I', 2: 'B1 Q', 3: 'B2 I', 4: 'B2 Q', 5: 'B3 I', 6: 'B3 Q'},
        'QZSS': {1: 'L1 C/A', 2: 'L1 S', 4: 'L2 C', 5: 'L2 L', 7: 'L5 I', 8: 'L5 Q', 9: 'L6 I', 10: 'L6 Q'},
        'SBAS': {1: 'L1 C/A', 7: 'L5 I', 8: 'L5 Q'}
    }
    
    msg_type = getattr(parsed, "identity", "")
    
    # MSM messages (1071-1127) contain satellite and signal info
    # Handle both string and int types
    msg_type_str = str(msg_type)
    try:
        msg_num = int(msg_type_str)
        if 1071 <= msg_num <= 1127:
            constellation_id = (msg_num - 1071) // 10
            
            # Map constellation ID to name
            constellation_map = {
                0: 'GPS',      # 1071-1077
                1: 'GLONASS',  # 1081-1087
                2: 'Galileo',  # 1091-1097
                3: 'SBAS',     # 1101-1107
                4: 'QZSS',     # 1111-1117
                5: 'BeiDou'    # 1121-1127
            }
            
            constellation = constellation_map.get(constellation_id)
            if constellation:
                # Extract satellite PRNs from PRN_XX fields (most reliable method)
                nsat = getattr(parsed, 'NSat', 0)
                if nsat > 0:
                    for i in range(1, nsat + 1):
                        prn_field = f'PRN_{i:02d}'
                        if hasattr(parsed, prn_field):
                            prn = getattr(parsed, prn_field)
                            if isinstance(prn, int) and prn > 0:
                                satellites[constellation].add(prn)
                
                # Extract signal information
                nsig = getattr(parsed, 'NSig', 0)
                if nsig > 0 and constellation in signal_map:
                    # Try to get signal mask or individual signal IDs
                    sig_mask = getattr(parsed, 'DF395', None)
                    if sig_mask and isinstance(sig_mask, int):
                        # Parse signal mask to get signal IDs
                        for sig_id in range(1, 33):  # Up to 32 signals
                            if sig_mask & (1 << (sig_id - 1)):
                                sig_name = signal_map[constellation].get(sig_id, f'Signal {sig_id}')
                                signals[constellation].add(sig_name)
                
                # If no PRN fields found, try bit mask method
                if not satellites[constellation]:
                    sat_mask = getattr(parsed, 'DF394', None)
                    if sat_mask is not None and isinstance(sat_mask, int) and sat_mask > 0:
                        for prn in range(1, 65):
                            if sat_mask & (1 << (prn - 1)):
                                satellites[constellation].add(prn)
                    
    except (ValueError, AttributeError) as e:
        logging.debug(f"Error extracting satellite info: {e}")
    
    return satellites, signals

# Color palette for RTCM message types
def get_color_for_msg_type(msg_type):
    """Get color for RTCM message type based on constellation (MSM messages color-coded)."""
    try:
        msg_num = int(msg_type)
        # MSM messages: color-code by constellation
        if 1071 <= msg_num <= 1077:  # GPS
            return "#4DAF4A"  # Green
        elif 1081 <= msg_num <= 1087:  # GLONASS
            return "#E41A1C"  # Red
        elif 1091 <= msg_num <= 1097:  # Galileo
            return "#377EB8"  # Blue
        elif 1101 <= msg_num <= 1107:  # SBAS
            return "#FFFF33"  # Yellow
        elif 1111 <= msg_num <= 1117:  # QZSS
            return "#984EA3"  # Purple
        elif 1121 <= msg_num <= 1127:  # BeiDou
            return "#FF7F00"  # Orange
    except (ValueError, TypeError):
        pass
    
    # Non-MSM messages: use hash-based color
    colors = [
        "#66C2A5", "#FC8D62", "#8DA0CB", "#E78AC3", "#A6D854", 
        "#FFD92F", "#B2DF8A", "#FB9A99", "#CAB2D6", "#999999"
    ]
    return colors[hash(str(msg_type)) % len(colors)]

def get_rtcm_description(msg_type):
    """Get description for RTCM message type."""
    descriptions = {
        # Station information
        "1005": "Station coordinates (stationary RTK reference station)",
        "1006": "Station coordinates with antenna height",
        "1007": "Antenna descriptor",
        "1008": "Antenna descriptor & serial number",
        "1033": "Receiver and antenna descriptors",
        
        # GPS MSM (Multiple Signal Messages)
        "1071": "GPS MSM1 - Compact pseudoranges",
        "1072": "GPS MSM2 - Compact phase ranges",
        "1073": "GPS MSM3 - Compact pseudoranges and phase ranges",
        "1074": "GPS MSM4 - Full pseudoranges and phase ranges",
        "1075": "GPS MSM5 - Full pseudoranges, phase ranges, phase range rate, and CNR",
        "1076": "GPS MSM6 - Full pseudoranges and CNR (high resolution)",
        "1077": "GPS MSM7 - Full pseudoranges, phase ranges, phase range rate, and CNR (high resolution)",
        
        # GLONASS MSM
        "1081": "GLONASS MSM1 - Compact pseudoranges",
        "1082": "GLONASS MSM2 - Compact phase ranges",
        "1083": "GLONASS MSM3 - Compact pseudoranges and phase ranges",
        "1084": "GLONASS MSM4 - Full pseudoranges and phase ranges",
        "1085": "GLONASS MSM5 - Full pseudoranges, phase ranges, phase range rate, and CNR",
        "1086": "GLONASS MSM6 - Full pseudoranges and CNR (high resolution)",
        "1087": "GLONASS MSM7 - Full pseudoranges, phase ranges, phase range rate, and CNR (high resolution)",
        
        # Galileo MSM
        "1091": "Galileo MSM1 - Compact pseudoranges",
        "1092": "Galileo MSM2 - Compact phase ranges",
        "1093": "Galileo MSM3 - Compact pseudoranges and phase ranges",
        "1094": "Galileo MSM4 - Full pseudoranges and phase ranges",
        "1095": "Galileo MSM5 - Full pseudoranges, phase ranges, phase range rate, and CNR",
        "1096": "Galileo MSM6 - Full pseudoranges and CNR (high resolution)",
        "1097": "Galileo MSM7 - Full pseudoranges, phase ranges, phase range rate, and CNR (high resolution)",
        
        # SBAS MSM
        "1101": "SBAS MSM1 - Compact pseudoranges",
        "1102": "SBAS MSM2 - Compact phase ranges",
        "1103": "SBAS MSM3 - Compact pseudoranges and phase ranges",
        "1104": "SBAS MSM4 - Full pseudoranges and phase ranges",
        "1105": "SBAS MSM5 - Full pseudoranges, phase ranges, phase range rate, and CNR",
        "1106": "SBAS MSM6 - Full pseudoranges and CNR (high resolution)",
        "1107": "SBAS MSM7 - Full pseudoranges, phase ranges, phase range rate, and CNR (high resolution)",
        
        # QZSS MSM
        "1111": "QZSS MSM1 - Compact pseudoranges",
        "1112": "QZSS MSM2 - Compact phase ranges",
        "1113": "QZSS MSM3 - Compact pseudoranges and phase ranges",
        "1114": "QZSS MSM4 - Full pseudoranges and phase ranges",
        "1115": "QZSS MSM5 - Full pseudoranges, phase ranges, phase range rate, and CNR",
        "1116": "QZSS MSM6 - Full pseudoranges and CNR (high resolution)",
        "1117": "QZSS MSM7 - Full pseudoranges, phase ranges, phase range rate, and CNR (high resolution)",
        
        # BeiDou MSM
        "1121": "BeiDou MSM1 - Compact pseudoranges",
        "1122": "BeiDou MSM2 - Compact phase ranges",
        "1123": "BeiDou MSM3 - Compact pseudoranges and phase ranges",
        "1124": "BeiDou MSM4 - Full pseudoranges and phase ranges",
        "1125": "BeiDou MSM5 - Full pseudoranges, phase ranges, phase range rate, and CNR",
        "1126": "BeiDou MSM6 - Full pseudoranges and CNR (high resolution)",
        "1127": "BeiDou MSM7 - Full pseudoranges, phase ranges, phase range rate, and CNR (high resolution)",
    }
    return descriptions.get(str(msg_type), "RTCM correction data")

def get_constellation_description(constellation):
    """Get description for GNSS constellation."""
    descriptions = {
        "GPS": "Global Positioning System (USA) - 31 operational satellites providing global coverage with L1, L2, and L5 signals.",
        "Galileo": "European GNSS constellation - Provides high-precision positioning with E1, E5a, E5b, and E6 signals.",
        "GLONASS": "Russian GNSS constellation - 24 satellites providing global coverage with L1 and L2 signals on FDMA frequencies.",
        "BeiDou": "Chinese Navigation Satellite System - Global coverage with B1, B2, and B3 signals from MEO, IGSO, and GEO satellites.",
        "QZSS": "Quasi-Zenith Satellite System (Japan) - Regional system enhancing GPS in Asia-Oceania with L1, L2, and L5 signals.",
        "SBAS": "Satellite-Based Augmentation System - Geostationary satellites providing correction data for improved GPS accuracy."
    }
    return descriptions.get(constellation, "GNSS satellite constellation")

def get_text_color_for_background(hex_color):
    """Calculate optimal text color (black or white) based on background color luminance.
    Uses W3C relative luminance formula for accessibility."""
    # Remove # if present
    hex_color = hex_color.lstrip('#')
    
    # Convert hex to RGB (0-255)
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    
    # Convert to 0-1 range
    r = r / 255.0
    g = g / 255.0
    b = b / 255.0
    
    # Apply gamma correction
    r = r / 12.92 if r <= 0.03928 else ((r + 0.055) / 1.055) ** 2.4
    g = g / 12.92 if g <= 0.03928 else ((g + 0.055) / 1.055) ** 2.4
    b = b / 12.92 if b <= 0.03928 else ((b + 0.055) / 1.055) ** 2.4
    
    # Calculate relative luminance
    luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b
    
    # Return black for light backgrounds, white for dark backgrounds
    return "black" if luminance > 0.5 else "white"

# ---------- Signals ----------
class NTRIPSignals(QObject):
    status_signal = pyqtSignal(str, str)
    data_signal = pyqtSignal(str, bytes)
    disconnect_signal = pyqtSignal(str)

# ---------- NTRIP Client ----------
class NTRIPClient(threading.Thread):
    def __init__(self, caster, signals: NTRIPSignals):
        super().__init__(daemon=True)
        self.caster = caster
        self.signals = signals
        self.running = False
        self.total_bytes = 0
        self.socket = None
        self.reconnect_attempts = 0
        self.stop_event = threading.Event()
        self.lock = threading.Lock()
        self.buffer = bytearray()
        self.user_stopped = False  # Track if user manually disconnected

    def run(self):
        while self.reconnect_attempts <= 3 and not self.stop_event.is_set() and not self.user_stopped:
            try:
                auth = base64.b64encode(f"{self.caster['user']}:{self.caster['password']}".encode()).decode()
                request = (
                    f"GET /{self.caster['mount']} HTTP/1.0\r\n"
                    f"User-Agent: NTRIP-PyChecker/5.0\r\n"
                    f"Authorization: Basic {auth}\r\n\r\n"
                )
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(10)
                s.connect((self.caster['host'], int(self.caster['port'])))
                s.sendall(request.encode())
                header = s.recv(1024)
                if b"ICY 200 OK" not in header and b"200 OK" not in header:
                    raise Exception("NTRIP server rejected connection")

                self.socket = s
                self.running = True
                self.reconnect_attempts = 0
                self.signals.status_signal.emit(self.caster['name'], "✅ Connection OK")

                while self.running and not self.stop_event.is_set():
                    try:
                        data = s.recv(4096)
                    except socket.timeout:
                        continue
                    except Exception:
                        # Socket error while reading - check if user stopped
                        if self.user_stopped:
                            break
                        raise  # Re-raise for reconnect logic
                    if not data:
                        # Connection closed - check if user stopped
                        if self.user_stopped:
                            break
                        # Otherwise treat as network error
                        raise Exception("Connection closed by server")
                    # update counters thread-safely
                    with self.lock:
                        self.total_bytes += len(data)
                        # append to per-client buffer; parsing moved to main (GUI) thread
                        self.buffer.extend(data)
                    # Notify main thread that new data is available (payload unused)
                    self.signals.data_signal.emit(self.caster['name'], b"")
                break

            except Exception as e:
                # Check if this was a user-initiated stop
                if self.user_stopped:
                    break
                
                # Check if this is a socket closure error during shutdown
                error_msg = str(e).lower()
                is_shutdown_error = (
                    "winerror 10038" in error_msg or  # Socket closed on Windows
                    "bad file descriptor" in error_msg or  # Socket closed on Linux
                    "not a socket" in error_msg or
                    self.stop_event.is_set()  # Explicit stop requested
                )
                
                if is_shutdown_error:
                    # Expected error during shutdown - log as debug only
                    logging.debug("Socket closed for %s (expected during shutdown)", self.caster.get('name'))
                    break
                
                # Log unexpected errors
                logging.exception("NTRIPClient error for %s", self.caster.get('name'))
                
                # Determine error type for user feedback
                if "rejected" in error_msg or "401" in error_msg or "unauthorized" in error_msg:
                    error_type = "Authentication failed"
                elif "timeout" in error_msg or "timed out" in error_msg:
                    error_type = "Connection timeout"
                elif "refused" in error_msg:
                    error_type = "Connection refused"
                else:
                    error_type = "Network error"
                
                self.signals.status_signal.emit(self.caster['name'], f"⚠️ {error_type}")
                self.reconnect_attempts += 1
                
                if not self.user_stopped and self.reconnect_attempts <= 3:
                    self.signals.status_signal.emit(self.caster['name'], f"🟡 Reconnecting ({self.reconnect_attempts}/3)...")
                    # wait with event so stop() can interrupt the sleep
                    if self.stop_event.wait(10):
                        break
                else:
                    if not self.user_stopped:
                        self.signals.status_signal.emit(self.caster['name'], f"🔴 Disconnected ({error_type})")
                    break
            finally:
                self.running = False
                try:
                    if self.socket:
                        self.socket.close()
                except Exception:
                    logging.debug("Exception while closing socket", exc_info=True)
        self.signals.disconnect_signal.emit(self.caster['name'])

    def stop(self, user_initiated=False):
        self.running = False
        self.user_stopped = user_initiated
        self.stop_event.set()
        try:
            if self.socket:
                try:
                    self.socket.shutdown(socket.SHUT_RDWR)
                except Exception:
                    pass
                self.socket.close()
        except Exception:
            logging.debug("Exception in stop() while closing socket", exc_info=True)

# ---------- About Dialog ----------
class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About NTRIP Checker PRO")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)
        
        layout = QVBoxLayout()
        
        # Title
        title = QLabel(f"<h1>NTRIP Checker PRO</h1>")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: #4fc3f7; margin: 10px;")
        layout.addWidget(title)
        
        # Version
        version_label = QLabel(f"<h2>Version {__version__}</h2>")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_label.setStyleSheet("color: #ffffff; margin: 5px;")
        layout.addWidget(version_label)
        
        # Description
        desc = QLabel("Professional NTRIP client for GNSS base stations")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setStyleSheet("color: #b0b0b0; margin: 10px;")
        layout.addWidget(desc)
        
        # Info text browser
        info_browser = QTextBrowser()
        info_browser.setOpenExternalLinks(True)
        info_html = f"""
        <div style="color: #ffffff; font-size: 12px; line-height: 1.6;">
        <p><b>Author:</b> {__author__}</p>
        <p><b>GitHub:</b> <a href="{__github__}" style="color: #4fc3f7;">{__github__}</a></p>
        <p><b>License:</b> MIT</p>
        <br>
        <p><b>Features:</b></p>
        <ul>
        <li>Real-time NTRIP stream monitoring</li>
        <li>RTCM message analysis</li>
        <li>Satellite constellation tracking</li>
        <li>Interactive map with RTK coverage</li>
        <li>Automatic mountpoint discovery</li>
        </ul>
        </div>
        """
        info_browser.setHtml(info_html)
        info_browser.setMaximumHeight(200)
        info_browser.setStyleSheet("background-color: #2b2b2b; border: 1px solid #444; padding: 10px;")
        layout.addWidget(info_browser)
        
        layout.addStretch()
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.check_update_btn = QPushButton("Check for Updates")
        self.check_update_btn.setStyleSheet("background-color: #4fc3f7; color: #000; font-weight: bold; padding: 8px;")
        self.check_update_btn.clicked.connect(self.check_for_updates)
        button_layout.addWidget(self.check_update_btn)
        
        close_btn = QPushButton("Close")
        close_btn.setStyleSheet("background-color: #555; color: #fff; padding: 8px;")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def check_for_updates(self):
        """Check GitHub API for latest release version."""
        self.check_update_btn.setEnabled(False)
        self.check_update_btn.setText("Checking...")
        
        try:
            # GitHub API endpoint for latest release
            api_url = "https://api.github.com/repos/UserRmM/ntrip-checker-pro/releases/latest"
            req = urllib.request.Request(api_url)
            req.add_header('User-Agent', f'NTRIP-Checker-PRO/{__version__}')
            
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())
                
                latest_version = data.get('tag_name', '').lstrip('v')
                release_url = data.get('html_url', __github__)
                release_notes = data.get('body', 'No release notes available.')
                published_at = data.get('published_at', '')
                
                # Compare versions
                current = __version__
                
                if latest_version and latest_version != current:
                    # New version available
                    msg = QMessageBox(self)
                    msg.setWindowTitle("Update Available")
                    msg.setIcon(QMessageBox.Icon.Information)
                    msg.setText(f"<h3>🎉 New version available!</h3>")
                    
                    # Truncate release notes if too long
                    notes_preview = release_notes[:500] + "..." if len(release_notes) > 500 else release_notes
                    
                    msg.setInformativeText(
                        f"<p><b>Current version:</b> {current}</p>"
                        f"<p><b>Latest version:</b> {latest_version}</p>"
                        f"<p><b>Published:</b> {published_at[:10]}</p>"
                        f"<br>"
                        f"<p><b>What's new:</b></p>"
                        f"<p style='color: #b0b0b0;'>{notes_preview}</p>"
                    )
                    
                    msg.setStandardButtons(QMessageBox.StandardButton.Ok)
                    view_btn = msg.addButton("View on GitHub", QMessageBox.ButtonRole.ActionRole)
                    
                    msg.exec()
                    
                    # If user clicked "View on GitHub"
                    if msg.clickedButton() == view_btn:
                        QDesktopServices.openUrl(QUrl(release_url))
                
                else:
                    # Up to date
                    QMessageBox.information(
                        self,
                        "No Updates",
                        f"<p>You are running the latest version ({current}).</p>"
                        f"<p>Check <a href='{__github__}'>GitHub</a> for development versions.</p>"
                    )
        
        except urllib.error.URLError as e:
            QMessageBox.warning(
                self,
                "Connection Error",
                f"<p>Could not check for updates.</p>"
                f"<p>Error: {str(e)}</p>"
                f"<p>Please check your internet connection.</p>"
            )
        except Exception as e:
            QMessageBox.warning(
                self,
                "Error",
                f"<p>An error occurred while checking for updates.</p>"
                f"<p>Error: {str(e)}</p>"
            )
        finally:
            self.check_update_btn.setEnabled(True)
            self.check_update_btn.setText("Check for Updates")

# ---------- Add Caster Dialog ----------
class AddCasterDialog(QDialog):
    def __init__(self, parent=None, data=None):
        super().__init__(parent)
        self.setWindowTitle("Add caster")
        layout = QFormLayout()
        self.name_edit = QLineEdit()
        self.host_edit = QLineEdit()
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(2101)
        # ensure spinbox text is visible on all themes (use light color for dark theme)
        try:
            self.port_spin.setStyleSheet("color: #ffffff;")
        except Exception:
            pass
        self.mount_edit = QLineEdit()
        self.user_edit = QLineEdit()
        self.pass_edit = QLineEdit()
        self.pass_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.lat_edit = QLineEdit()
        self.lon_edit = QLineEdit()
        self.alt_edit = QLineEdit()

        # if data provided, prefill fields for edit
        if data:
            self.name_edit.setText(data.get("name", ""))
            self.host_edit.setText(data.get("host", ""))
            try:
                self.port_spin.setValue(int(data.get("port", 2101)))
            except Exception:
                self.port_spin.setValue(2101)
            self.mount_edit.setText(data.get("mount", ""))
            self.user_edit.setText(data.get("user", ""))
            self.pass_edit.setText(data.get("password", ""))
            if data.get("lat") is not None:
                self.lat_edit.setText(str(data.get("lat")))
            if data.get("lon") is not None:
                self.lon_edit.setText(str(data.get("lon")))
            if data.get("alt") is not None:
                self.alt_edit.setText(str(data.get("alt")))

        # Force QLineEdit text color to a light color to override dark theme placeholder/foreground colors
        for w in (
            self.name_edit, self.host_edit, self.mount_edit, self.user_edit,
            self.pass_edit, self.lat_edit, self.lon_edit, self.alt_edit
        ):
            try:
                w.setStyleSheet("color: #ffffff;")
            except Exception:
                pass

        layout.addRow("Name:", self.name_edit)
        layout.addRow("Host:", self.host_edit)
        layout.addRow("Port:", self.port_spin)
        layout.addRow("Mountpoint:", self.mount_edit)
        layout.addRow("User:", self.user_edit)
        layout.addRow("Password:", self.pass_edit)
        layout.addRow("Latitude:", self.lat_edit)
        layout.addRow("Longitude:", self.lon_edit)
        layout.addRow("Altitude (m):", self.alt_edit)

        btns = QHBoxLayout()
        self.save_btn = QPushButton("Save")
        self.cancel_btn = QPushButton("Cancel")
        btns.addWidget(self.save_btn)
        btns.addWidget(self.cancel_btn)
        layout.addRow(btns)
        self.setLayout(layout)
        self.save_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.reject)

    def get_data(self):
        def safe_float(v):
            try:
                return float(v)
            except Exception:
                return None
        return {
            "name": self.name_edit.text().strip(),
            "host": self.host_edit.text().strip(),
            "port": int(self.port_spin.value()),
            "mount": self.mount_edit.text().strip(),
            "user": self.user_edit.text().strip(),
            "password": self.pass_edit.text().strip(),
            "lat": safe_float(self.lat_edit.text()),
            "lon": safe_float(self.lon_edit.text()),
            "alt": safe_float(self.alt_edit.text())
        }

# ---------- Main ----------
class NTRIPCheckerPro(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"NTRIP Checker PRO v{__version__}")
        # Set fixed size to prevent window jumping when switching tabs
        self.setMinimumSize(1200, 800)
        self.resize(1200, 800)

        self.casters = []
        self.clients = {}
        self.start_times = {}
        self.last_bytes = {}
        # Removed auto-refresh counter - user has full control
        self.selected_caster = None
        self.selected_constellation = None  # Track selected constellation for detail panel
        self.rtcm_stats = {}
        self.satellite_stats = {}  # Track satellites per caster
        self.signal_stats = {}  # Track signals/frequencies per caster
        self.map_marker_ids = {}  # Track marker IDs for popup updates (marker_id -> caster_name)

        self.signals = NTRIPSignals()
        self.signals.status_signal.connect(self.on_status)
        self.signals.data_signal.connect(self.on_data)
        self.signals.disconnect_signal.connect(self.on_disconnect)

        self.load_casters()
        self.init_ui()
        self.init_timers()
        self.auto_connect_all()

    # ---------- Load ----------
    def get_casters_path(self):
        """Get absolute path to casters.json (from environment or script directory)"""
        return CASTERS_FILENAME
    
    def load_casters(self):
        casters_path = self.get_casters_path()
        
        if not os.path.exists(casters_path):
            with open(casters_path, "w", encoding="utf-8") as f:
                json.dump([], f)
        try:
            with open(casters_path, "r", encoding="utf-8") as f:
                self.casters = json.load(f)
            logging.info(f"Loaded casters from: {casters_path}")
        except Exception:
            logging.exception(f"Failed loading casters.json from: {casters_path}")
            self.casters = []

    # ---------- UI ----------
    def init_ui(self):
        # Create menu bar
        self.menu_bar = QMenuBar()
        
        # Help menu
        help_menu = self.menu_bar.addMenu("Help")
        about_action = help_menu.addAction("About")
        about_action.triggered.connect(self.show_about_dialog)
        
        self.tabs = QTabWidget()
        self.tabs.currentChanged.connect(self.on_tab_changed)
        layout = QVBoxLayout()
        layout.setMenuBar(self.menu_bar)
        layout.addWidget(self.tabs)
        self.setLayout(layout)

        # Casters tab - create container widget with summary cards and detail panel
        self.caster_tab_widget = QWidget()
        caster_tab_layout = QVBoxLayout()
        caster_tab_layout.setContentsMargins(8, 8, 8, 8)
        caster_tab_layout.setSpacing(8)
        self.caster_tab_widget.setLayout(caster_tab_layout)
        
        from PyQt6.QtWidgets import QFrame
        
        # Main content area: table + detail panel
        content_layout = QHBoxLayout()
        content_layout.setSpacing(10)
        
        # Casters table
        self.caster_list = QTableWidget()
        self.caster_list.setColumnCount(7)
        self.caster_list.setHorizontalHeaderLabels(["Name", "Address", "Mount", "Status", "B/s", "Uptime", "Actions"])
        # Set column widths: B/s narrow, Uptime normal, Actions wide
        self.caster_list.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)  # Name
        self.caster_list.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)  # Address
        self.caster_list.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)  # Mount (fixed)
        self.caster_list.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)  # Status
        self.caster_list.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Interactive)  # B/s (fixed)
        self.caster_list.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)  # Uptime (narrow)
        self.caster_list.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)  # Actions (wide)
        self.caster_list.setColumnWidth(2, 120)  # Mount fixed width
        self.caster_list.setColumnWidth(4, 70)  # B/s fixed width
        self.caster_list.setColumnWidth(5, 90)  # Uptime explicit minimum width
        self.caster_list.setStyleSheet("QTableWidget { color: #ffffff; selection-background-color: #3a6ea5; }")
        self.caster_list.setAlternatingRowColors(True)
        try:
            self.caster_list.setSelectionBehavior(self.caster_list.SelectionBehavior.SelectRows)
            self.caster_list.setSelectionMode(self.caster_list.SelectionMode.SingleSelection)
        except Exception:
            pass
        self.caster_list.verticalHeader().setDefaultSectionSize(40)
        self.caster_list.verticalHeader().setVisible(False)
        self.caster_list.cellClicked.connect(self.on_caster_selected)
        content_layout.addWidget(self.caster_list, 7)  # 70% width
        
        # Detail panel (hidden initially)
        self.detail_panel = QWidget()
        self.detail_panel.setMinimumWidth(250)
        self.detail_panel.setMaximumWidth(400)
        detail_layout = QVBoxLayout()
        detail_layout.setContentsMargins(10, 10, 10, 10)
        detail_layout.setSpacing(10)
        self.detail_panel.setLayout(detail_layout)
        self.detail_panel.setStyleSheet("""
            QWidget {
                background-color: #2d2d2d;
                border: 1px solid #3a3a3a;
                border-radius: 8px;
            }
        """)
        
        # Detail panel header with close button
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        self.detail_header = QLabel("Select a caster")
        self.detail_header.setStyleSheet("color: #ffffff; font-weight: bold; font-size: 16px; background: transparent; border: none;")
        self.detail_header.setWordWrap(True)
        header_layout.addWidget(self.detail_header)
        
        self.detail_close_btn = QPushButton("✕")
        self.detail_close_btn.setFixedSize(24, 24)
        self.detail_close_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #aaaaaa;
                border: none;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                color: #ffffff;
                background-color: #3a3a3a;
                border-radius: 4px;
            }
        """)
        self.detail_close_btn.clicked.connect(self.close_detail_panel)
        self.detail_close_btn.setToolTip("Close panel")
        header_layout.addWidget(self.detail_close_btn)
        
        detail_layout.addLayout(header_layout)
        
        # Detail panel status
        self.detail_status = QLabel("")
        self.detail_status.setStyleSheet("color: #aaaaaa; font-size: 13px; background: transparent; border: none;")
        self.detail_status.setWordWrap(True)
        detail_layout.addWidget(self.detail_status)
        
        # Separator line
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet("background-color: #3a3a3a; border: none;")
        detail_layout.addWidget(separator)
        
        # Detail panel stats
        self.detail_stats = QLabel("")
        self.detail_stats.setStyleSheet("color: #ffffff; font-size: 12px; background: transparent; border: none;")
        self.detail_stats.setWordWrap(True)
        detail_layout.addWidget(self.detail_stats)
        
        # RTCM messages section
        rtcm_label = QLabel("📡 RTCM Messages")
        rtcm_label.setStyleSheet("color: #ffffff; font-weight: bold; font-size: 13px; margin-top: 10px; background: transparent; border: none;")
        detail_layout.addWidget(rtcm_label)
        
        self.detail_rtcm = QLabel("No data")
        self.detail_rtcm.setStyleSheet("color: #cccccc; font-size: 11px; font-family: monospace; background: transparent; border: none;")
        self.detail_rtcm.setWordWrap(False)
        detail_layout.addWidget(self.detail_rtcm)
        
        # Satellites section
        self.detail_satellites = QLabel("")
        self.detail_satellites.setStyleSheet("color: #ffffff; font-size: 12px; margin-top: 10px; background: transparent; border: none;")
        self.detail_satellites.setWordWrap(True)
        detail_layout.addWidget(self.detail_satellites)
        
        detail_layout.addStretch()
        
        # Quick action buttons
        btn_layout = QHBoxLayout()
        self.detail_btn_messages = QPushButton("Messages")
        self.detail_btn_messages.setStyleSheet("background-color: #4b8cff; color: white; padding: 6px 12px; border-radius: 4px; border: none;")
        self.detail_btn_messages.clicked.connect(lambda: self.tabs.setCurrentWidget(self.msg_tab) if hasattr(self, 'msg_tab') else None)
        btn_layout.addWidget(self.detail_btn_messages)
        
        self.detail_btn_satellites = QPushButton("Satellites")
        self.detail_btn_satellites.setStyleSheet("background-color: #4b8cff; color: white; padding: 6px 12px; border-radius: 4px; border: none;")
        self.detail_btn_satellites.clicked.connect(lambda: self.tabs.setCurrentWidget(self.sat_tab) if hasattr(self, 'sat_tab') else None)
        btn_layout.addWidget(self.detail_btn_satellites)
        
        detail_layout.addLayout(btn_layout)
        
        self.detail_panel.hide()  # Hidden initially
        content_layout.addWidget(self.detail_panel, 3)  # 30% width
        
        caster_tab_layout.addLayout(content_layout)
        
        # Add info label at bottom
        info_label = QLabel("💡 Click a caster to view detailed statistics")
        info_label.setStyleSheet("color: #888888; font-size: 11px; margin-top: 5px;")
        caster_tab_layout.addWidget(info_label)
        
        self.tabs.addTab(self.caster_tab_widget, "Casters")
        for c in self.casters:
            self._insert_caster_row(c)

        # Buttons (corner)
        btn_panel = QWidget()
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(6, 6, 6, 6)
        btn_layout.setSpacing(8)
        btn_panel.setLayout(btn_layout)
        self.add_btn = QPushButton("+ Add caster")
        self.add_btn.clicked.connect(self.show_add_dialog)
        self.connect_all_btn = QPushButton("Connect All")
        self.connect_all_btn.clicked.connect(self.connect_all_disconnected)
        self.connect_all_btn.setToolTip("Connect all disconnected casters")
        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.connect_all_btn)
        btn_layout.addStretch()
        self.tabs.setCornerWidget(btn_panel, Qt.Corner.TopRightCorner)

        # Messages tab
        self.msg_tab = QWidget()
        self.msg_layout = QVBoxLayout()
        self.msg_layout.setContentsMargins(8, 8, 8, 8)
        self.msg_layout.setSpacing(8)
        self.msg_tab.setLayout(self.msg_layout)
        
        # Header with station label and caster selector
        msg_header_layout = QHBoxLayout()
        msg_label = QLabel("Station:")
        msg_label.setStyleSheet("color: #ffffff; font-weight: bold; font-size:15px; margin:6px;")
        self.msg_caster_combo = QComboBox()
        self.msg_caster_combo.setStyleSheet("color: #ffffff;")
        self.msg_caster_combo.addItem("(none)")
        self.msg_caster_combo.currentTextChanged.connect(self.on_msg_caster_changed)
        msg_header_layout.addWidget(msg_label)
        msg_header_layout.addWidget(self.msg_caster_combo)
        msg_header_layout.addStretch()
        self.msg_layout.addLayout(msg_header_layout)
        self.msg_header = msg_label  # keep reference for compatibility
        
        # Main content area: table + detail panel
        msg_content_layout = QHBoxLayout()
        msg_content_layout.setSpacing(10)
        
        # Left side: Messages table
        self.msg_table = QTableWidget()
        self.msg_table.setColumnCount(3)
        self.msg_table.setHorizontalHeaderLabels(["RTCM Message", "Last Time Received", "Counter"])
        self.msg_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.msg_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.msg_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self.msg_table.setColumnWidth(0, 120)
        self.msg_table.setColumnWidth(2, 100)
        self.msg_table.setStyleSheet("QTableWidget { color: #ffffff; selection-background-color: #3a6ea5; }")
        self.msg_table.setAlternatingRowColors(True)
        self.msg_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        try:
            self.msg_table.setSelectionBehavior(self.msg_table.SelectionBehavior.SelectRows)
            self.msg_table.setSelectionMode(self.msg_table.SelectionMode.SingleSelection)
        except Exception:
            pass
        self.msg_table.verticalHeader().setVisible(False)
        self.msg_table.cellClicked.connect(self.on_message_selected)
        msg_content_layout.addWidget(self.msg_table, 7)  # 70% width
        
        # Right side: Detail panel (hidden initially)
        self.msg_detail_panel = QWidget()
        self.msg_detail_panel.setMinimumWidth(250)
        self.msg_detail_panel.setMaximumWidth(400)
        msg_detail_layout = QVBoxLayout()
        msg_detail_layout.setContentsMargins(10, 10, 10, 10)
        msg_detail_layout.setSpacing(10)
        self.msg_detail_panel.setLayout(msg_detail_layout)
        self.msg_detail_panel.setStyleSheet("""
            QWidget {
                background-color: #2d2d2d;
                border: 1px solid #3a3a3a;
                border-radius: 8px;
            }
        """)
        
        # Detail panel header with close button
        msg_header_layout2 = QHBoxLayout()
        msg_header_layout2.setContentsMargins(0, 0, 0, 0)
        
        self.msg_detail_header = QLabel("Select a message")
        self.msg_detail_header.setStyleSheet("color: #ffffff; font-weight: bold; font-size: 16px; background: transparent; border: none;")
        self.msg_detail_header.setWordWrap(True)
        msg_header_layout2.addWidget(self.msg_detail_header)
        
        self.msg_detail_close_btn = QPushButton("✕")
        self.msg_detail_close_btn.setFixedSize(24, 24)
        self.msg_detail_close_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #aaaaaa;
                border: none;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                color: #ffffff;
                background-color: #3a3a3a;
                border-radius: 4px;
            }
        """)
        self.msg_detail_close_btn.clicked.connect(self.close_message_detail_panel)
        self.msg_detail_close_btn.setToolTip("Close panel")
        msg_header_layout2.addWidget(self.msg_detail_close_btn)
        
        msg_detail_layout.addLayout(msg_header_layout2)
        
        # Message type description
        self.msg_detail_description = QLabel("")
        self.msg_detail_description.setStyleSheet("color: #aaaaaa; font-size: 12px; background: transparent; border: none;")
        self.msg_detail_description.setWordWrap(True)
        msg_detail_layout.addWidget(self.msg_detail_description)
        
        # Separator line
        msg_separator = QFrame()
        msg_separator.setFrameShape(QFrame.Shape.HLine)
        msg_separator.setStyleSheet("background-color: #3a3a3a; border: none;")
        msg_detail_layout.addWidget(msg_separator)
        
        # Statistics
        self.msg_detail_stats = QLabel("")
        self.msg_detail_stats.setStyleSheet("color: #ffffff; font-size: 12px; background: transparent; border: none;")
        self.msg_detail_stats.setWordWrap(True)
        msg_detail_layout.addWidget(self.msg_detail_stats)
        
        msg_detail_layout.addStretch()
        
        # Total messages label at bottom
        self.msg_total_label = QLabel("Total messages: 0")
        self.msg_total_label.setStyleSheet("color: #aaaaaa; font-size: 11px; background: transparent; border: none;")
        msg_detail_layout.addWidget(self.msg_total_label)
        
        self.msg_detail_panel.hide()  # Hidden initially
        msg_content_layout.addWidget(self.msg_detail_panel, 3)  # 30% width
        
        self.msg_layout.addLayout(msg_content_layout)
        
        # Add info label at bottom
        msg_info_label = QLabel("💡 Click a message to view detailed statistics")
        msg_info_label.setStyleSheet("color: #888888; font-size: 11px; margin-top: 5px;")
        self.msg_layout.addWidget(msg_info_label)
        
        self.tabs.addTab(self.msg_tab, "Messages")
        self.selected_message = None

        # Map tab - simple version with just map view
        self.map_tab = QWidget()
        self.map_layout = QVBoxLayout()
        self.map_layout.setContentsMargins(8, 8, 8, 8)
        self.map_layout.setSpacing(8)
        self.map_tab.setLayout(self.map_layout)
        
        # Header with station label and caster selector
        map_header_layout = QHBoxLayout()
        map_label = QLabel("Station:")
        map_label.setStyleSheet("color: #ffffff; font-weight: bold; font-size:15px; margin:6px;")
        self.map_caster_combo = QComboBox()
        self.map_caster_combo.setStyleSheet("color: #ffffff;")
        self.map_caster_combo.addItem("(All stations)")
        self.map_caster_combo.currentTextChanged.connect(self.on_map_caster_changed)
        map_header_layout.addWidget(map_label)
        map_header_layout.addWidget(self.map_caster_combo)
        map_header_layout.addStretch()
        self.map_layout.addLayout(map_header_layout)
        
        # Map view (full width)
        self.map_view = QWebEngineView()
        self.map_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.map_view.setMinimumHeight(400)
        self.map_view.setHtml("<h3 style='color:#ffffff;margin:1rem;'>Loading map...</h3>")
        self.map_layout.addWidget(self.map_view)
        
        # Info label
        map_info_label = QLabel("💡 Click a marker to view station details • Coverage circles show 20 km RTK radius • 🟢 Connected • 🔴 Disconnected")
        map_info_label.setStyleSheet("color: #888888; font-size: 11px; margin-top: 5px;")
        self.map_layout.addWidget(map_info_label)
        
        # Satellites tab
        self.sat_tab = QWidget()
        self.sat_layout = QVBoxLayout()
        self.sat_layout.setContentsMargins(8, 8, 8, 8)
        self.sat_layout.setSpacing(8)
        self.sat_tab.setLayout(self.sat_layout)
        
        # Header with station label and caster selector
        sat_header_layout = QHBoxLayout()
        sat_label = QLabel("Station:")
        sat_label.setStyleSheet("color: #ffffff; font-weight: bold; font-size:15px; margin:6px;")
        self.sat_caster_combo = QComboBox()
        self.sat_caster_combo.setStyleSheet("color: #ffffff;")
        self.sat_caster_combo.addItem("(none)")
        self.sat_caster_combo.currentTextChanged.connect(self.on_sat_caster_changed)
        sat_header_layout.addWidget(sat_label)
        sat_header_layout.addWidget(self.sat_caster_combo)
        sat_header_layout.addStretch()
        self.sat_layout.addLayout(sat_header_layout)
        
        # Main content area: table + detail panel
        sat_content_layout = QHBoxLayout()
        sat_content_layout.setSpacing(10)
        
        # Left side: Constellations table
        self.sat_table = QTableWidget()
        self.sat_table.setColumnCount(4)
        self.sat_table.setHorizontalHeaderLabels(["Constellation", "Satellites", "Signals", "%"])
        self.sat_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.sat_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.sat_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.sat_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        self.sat_table.setColumnWidth(1, 100)
        self.sat_table.setColumnWidth(3, 80)
        self.sat_table.setStyleSheet("QTableWidget { color: #ffffff; selection-background-color: #3a6ea5; }")
        self.sat_table.setAlternatingRowColors(True)
        self.sat_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        try:
            self.sat_table.setSelectionBehavior(self.sat_table.SelectionBehavior.SelectRows)
            self.sat_table.setSelectionMode(self.sat_table.SelectionMode.SingleSelection)
        except Exception:
            pass
        self.sat_table.verticalHeader().setVisible(False)
        self.sat_table.cellClicked.connect(self.on_constellation_selected)
        sat_content_layout.addWidget(self.sat_table, 7)  # 70% width
        
        # Right side: Detail panel (hidden initially)
        self.sat_detail_panel = QWidget()
        self.sat_detail_panel.setMinimumWidth(250)
        self.sat_detail_panel.setMaximumWidth(400)
        sat_detail_layout = QVBoxLayout()
        sat_detail_layout.setContentsMargins(10, 10, 10, 10)
        sat_detail_layout.setSpacing(10)
        self.sat_detail_panel.setLayout(sat_detail_layout)
        self.sat_detail_panel.setStyleSheet("""
            QWidget {
                background-color: #2d2d2d;
                border: 1px solid #3a3a3a;
                border-radius: 8px;
            }
        """)
        
        # Detail panel header with close button
        sat_header_layout2 = QHBoxLayout()
        sat_header_layout2.setContentsMargins(0, 0, 0, 0)
        
        self.sat_detail_header = QLabel("Select a constellation")
        self.sat_detail_header.setStyleSheet("color: #ffffff; font-weight: bold; font-size: 16px; background: transparent; border: none;")
        self.sat_detail_header.setWordWrap(True)
        sat_header_layout2.addWidget(self.sat_detail_header)
        
        self.sat_detail_close_btn = QPushButton("✕")
        self.sat_detail_close_btn.setFixedSize(24, 24)
        self.sat_detail_close_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #aaaaaa;
                border: none;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                color: #ffffff;
                background-color: #3a3a3a;
                border-radius: 4px;
            }
        """)
        self.sat_detail_close_btn.clicked.connect(self.close_constellation_detail_panel)
        self.sat_detail_close_btn.setToolTip("Close panel")
        sat_header_layout2.addWidget(self.sat_detail_close_btn)
        
        sat_detail_layout.addLayout(sat_header_layout2)
        
        # Constellation description
        self.sat_detail_description = QLabel("")
        self.sat_detail_description.setStyleSheet("color: #aaaaaa; font-size: 12px; background: transparent; border: none;")
        self.sat_detail_description.setWordWrap(True)
        sat_detail_layout.addWidget(self.sat_detail_description)
        
        # Separator line
        sat_separator = QFrame()
        sat_separator.setFrameShape(QFrame.Shape.HLine)
        sat_separator.setStyleSheet("background-color: #3a3a3a; border: none;")
        sat_detail_layout.addWidget(sat_separator)
        
        # Statistics
        self.sat_detail_stats = QLabel("")
        self.sat_detail_stats.setStyleSheet("color: #ffffff; font-size: 12px; background: transparent; border: none;")
        self.sat_detail_stats.setWordWrap(True)
        sat_detail_layout.addWidget(self.sat_detail_stats)
        
        # PRN numbers section
        sat_prn_label = QLabel("🛰️ Satellite PRNs")
        sat_prn_label.setStyleSheet("color: #ffffff; font-weight: bold; font-size: 13px; margin-top: 10px; background: transparent; border: none;")
        sat_detail_layout.addWidget(sat_prn_label)
        
        self.sat_detail_prns = QLabel("No data")
        self.sat_detail_prns.setStyleSheet("color: #cccccc; font-size: 11px; font-family: monospace; background: transparent; border: none;")
        self.sat_detail_prns.setWordWrap(True)
        sat_detail_layout.addWidget(self.sat_detail_prns)
        
        # Signals section
        sat_sig_label = QLabel("📡 Detected Signals")
        sat_sig_label.setStyleSheet("color: #ffffff; font-weight: bold; font-size: 13px; margin-top: 10px; background: transparent; border: none;")
        sat_detail_layout.addWidget(sat_sig_label)
        
        self.sat_detail_signals = QLabel("No data")
        self.sat_detail_signals.setStyleSheet("color: #cccccc; font-size: 11px; background: transparent; border: none;")
        self.sat_detail_signals.setWordWrap(True)
        sat_detail_layout.addWidget(self.sat_detail_signals)
        
        sat_detail_layout.addStretch()
        
        # Total satellites label at bottom
        self.sat_total_label = QLabel("Total satellites: 0")
        self.sat_total_label.setStyleSheet("color: #aaaaaa; font-size: 11px; background: transparent; border: none;")
        sat_detail_layout.addWidget(self.sat_total_label)
        
        self.sat_detail_panel.hide()  # Hidden initially
        sat_content_layout.addWidget(self.sat_detail_panel, 3)  # 30% width
        
        self.sat_layout.addLayout(sat_content_layout)
        
        # Add info label at bottom
        sat_info_label = QLabel("💡 Click a constellation to view detailed satellite information")
        sat_info_label.setStyleSheet("color: #888888; font-size: 11px; margin-top: 5px;")
        self.sat_layout.addWidget(sat_info_label)
        
        self.tabs.addTab(self.sat_tab, "Satellites")
        self.tabs.addTab(self.map_tab, "Map")
        
        # Sourcetable tab
        self.sourcetable_tab = QWidget()
        self.sourcetable_layout = QVBoxLayout()
        self.sourcetable_tab.setLayout(self.sourcetable_layout)
        
        # Header with caster input fields
        st_header = QHBoxLayout()
        st_header_label = QLabel("Sourcetable Browser:")
        st_header_label.setStyleSheet("color: #ffffff; font-weight: bold; font-size:16px; margin:8px;")
        st_header.addWidget(st_header_label)
        st_header.addStretch()
        self.sourcetable_layout.addLayout(st_header)
        
        # Caster input row
        st_input_row = QHBoxLayout()
        
        st_host_label = QLabel("Host:")
        st_host_label.setStyleSheet("color: #ffffff; margin-left: 8px;")
        self.st_host_edit = QLineEdit()
        self.st_host_edit.setStyleSheet("color: #ffffff;")
        self.st_host_edit.setPlaceholderText("e.g., rtk.example.com")
        
        st_port_label = QLabel("Port:")
        st_port_label.setStyleSheet("color: #ffffff; margin-left: 8px;")
        self.st_port_spin = QSpinBox()
        self.st_port_spin.setRange(1, 65535)
        self.st_port_spin.setValue(2101)
        self.st_port_spin.setStyleSheet("color: #ffffff;")
        
        st_user_label = QLabel("User:")
        st_user_label.setStyleSheet("color: #ffffff; margin-left: 8px;")
        self.st_user_edit = QLineEdit()
        self.st_user_edit.setStyleSheet("color: #ffffff;")
        
        st_pass_label = QLabel("Pass:")
        st_pass_label.setStyleSheet("color: #ffffff; margin-left: 8px;")
        self.st_pass_edit = QLineEdit()
        self.st_pass_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.st_pass_edit.setStyleSheet("color: #ffffff;")
        
        self.st_fetch_btn = QPushButton("Fetch Mountpoints")
        self.st_fetch_btn.setStyleSheet("background-color: #4DAF4A; color: white; padding: 5px 15px; font-weight: bold;")
        self.st_fetch_btn.clicked.connect(self.fetch_sourcetable)
        
        st_input_row.addWidget(st_host_label)
        st_input_row.addWidget(self.st_host_edit)
        st_input_row.addWidget(st_port_label)
        st_input_row.addWidget(self.st_port_spin)
        st_input_row.addWidget(st_user_label)
        st_input_row.addWidget(self.st_user_edit)
        st_input_row.addWidget(st_pass_label)
        st_input_row.addWidget(self.st_pass_edit)
        st_input_row.addWidget(self.st_fetch_btn)
        st_input_row.addStretch()
        
        self.sourcetable_layout.addLayout(st_input_row)
        
        # Search and filter row
        st_filter_row = QHBoxLayout()
        
        st_search_label = QLabel("Search:")
        st_search_label.setStyleSheet("color: #ffffff; margin-left: 8px;")
        self.st_search_edit = QLineEdit()
        self.st_search_edit.setStyleSheet("color: #ffffff;")
        self.st_search_edit.setPlaceholderText("Filter mountpoints...")
        self.st_search_edit.textChanged.connect(self.filter_sourcetable)
        
        st_filter_row.addWidget(st_search_label)
        st_filter_row.addWidget(self.st_search_edit)
        st_filter_row.addStretch()
        
        self.sourcetable_layout.addLayout(st_filter_row)
        
        # Mountpoints table
        self.st_table = QTableWidget()
        self.st_table.setColumnCount(6)
        self.st_table.setHorizontalHeaderLabels(["Mountpoint", "Description", "Format", "Location", "Systems", "Carrier"])
        self.st_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.st_table.setStyleSheet("QTableWidget { color: #ffffff; }")
        self.st_table.setAlternatingRowColors(True)
        self.st_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.st_table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.st_table.verticalHeader().setVisible(False)
        self.st_table.setSortingEnabled(True)
        
        self.sourcetable_layout.addWidget(self.st_table)
        
        # Bottom row with selection info and Add button
        st_bottom_row = QHBoxLayout()
        
        self.st_selection_label = QLabel("Selected: None")
        self.st_selection_label.setStyleSheet("color: #ffffff; font-size: 12px; margin: 8px;")
        
        self.st_add_btn = QPushButton("Add Selected to Casters")
        self.st_add_btn.setStyleSheet("background-color: #377EB8; color: white; padding: 8px 20px; font-weight: bold;")
        self.st_add_btn.setEnabled(False)
        self.st_add_btn.clicked.connect(self.add_selected_mountpoints)
        
        st_bottom_row.addWidget(self.st_selection_label)
        st_bottom_row.addStretch()
        st_bottom_row.addWidget(self.st_add_btn)
        
        self.sourcetable_layout.addLayout(st_bottom_row)
        
        # Connect selection changed signal
        self.st_table.itemSelectionChanged.connect(self.update_sourcetable_selection)
        
        self.tabs.addTab(self.sourcetable_tab, "Sourcetable")

    def _insert_caster_row(self, c):
        row = self.caster_list.rowCount()
        self.caster_list.insertRow(row)
        self.caster_list.setItem(row, 0, QTableWidgetItem(c.get("name", "")))
        self.caster_list.setItem(row, 1, QTableWidgetItem(f"{c.get('host', '')}:{c.get('port', '')}"))
        self.caster_list.setItem(row, 2, QTableWidgetItem(c.get("mount", "")))
        self.caster_list.setItem(row, 3, QTableWidgetItem(""))
        self.caster_list.setItem(row, 4, QTableWidgetItem("0"))
        self.caster_list.setItem(row, 5, QTableWidgetItem("-"))
        self.caster_list.setCellWidget(row, 6, self._make_action_widget(c))

    def _make_action_widget(self, c):
        w = QWidget()
        h = QHBoxLayout()
        h.setContentsMargins(0, 0, 0, 0)
        btn_conn = QPushButton("Connect")
        btn_conn.clicked.connect(partial(self.manual_toggle_connection, c.get("name", ""), btn_conn))
        btn_conn.setFixedHeight(26)
        btn_conn.setStyleSheet("font-size:10px;padding:3px 8px;border-radius:5px;")
        btn_edit = QPushButton("Edit")
        btn_edit.clicked.connect(partial(self.show_edit_dialog, c.get("name", "")))
        btn_edit.setFixedHeight(26)
        btn_edit.setStyleSheet("font-size:10px;padding:3px 8px;border-radius:5px;background:#4b8cff;color:#fff;")
        btn_del = QPushButton("Delete")
        btn_del.clicked.connect(partial(self.remove_caster_by_name, c.get("name", "")))
        btn_del.setFixedHeight(26)
        btn_del.setStyleSheet("font-size:10px;padding:3px 8px;border-radius:5px;background:#d9534f;color:#fff;")
        h.addWidget(btn_conn)
        h.addWidget(btn_edit)
        h.addWidget(btn_del)
        w.setLayout(h)
        return w

    # ---------- Map Tab ----------
    def on_map_caster_changed(self, text):
        """Handle map caster selection change"""
        self.update_map_view()
    
    def update_map_view(self):
        """Update map to show selected caster or all casters with status colors and enriched popups"""
        if not self.casters:
            self.map_view.setHtml("<h3 style='color:#ffffff;margin:1rem;'>No stations configured. Add a station to see it on the map.</h3>")
            return
        
        # Get selected caster from combobox
        selected = self.map_caster_combo.currentText()
        
        # Find casters with valid coordinates
        if selected == "(All stations)":
            valid_casters = [c for c in self.casters if c.get('lat') is not None and c.get('lon') is not None]
        else:
            # Filter to show only selected caster
            valid_casters = [c for c in self.casters if c.get('name') == selected and c.get('lat') is not None and c.get('lon') is not None]
        
        if not valid_casters:
            self.map_view.setHtml("<h3 style='color:#ffffff;margin:1rem;'>No stations have location data. Edit stations to add coordinates.</h3>")
            return
        
        # Calculate map bounds to fit all markers
        if len(valid_casters) == 1:
            # Single marker - use center and fixed zoom
            center_lat = valid_casters[0]['lat']
            center_lon = valid_casters[0]['lon']
            use_bounds = False
            zoom = 10
        else:
            # Multiple markers - calculate bounds
            lats = [c['lat'] for c in valid_casters]
            lons = [c['lon'] for c in valid_casters]
            min_lat, max_lat = min(lats), max(lats)
            min_lon, max_lon = min(lons), max(lons)
            
            # Calculate center
            center_lat = (min_lat + max_lat) / 2
            center_lon = (min_lon + max_lon) / 2
            
            # Use bounds for fitting
            use_bounds = True
            bounds_sw = f"[{min_lat}, {min_lon}]"
            bounds_ne = f"[{max_lat}, {max_lon}]"
        
        # Build JavaScript for all markers
        markers_js = ""
        for caster in valid_casters:
            name = escape(caster['name'])
            lat = caster['lat']
            lon = caster['lon']
            alt = caster.get('alt', 'N/A')
            host = escape(caster.get('host', 'N/A'))
            port = caster.get('port', 'N/A')
            mount = escape(caster.get('mount', 'N/A'))
            
            # Get status and determine color
            client = self.clients.get(caster['name'])
            if client and getattr(client, 'running', False):
                # Check actual status from status text
                status_color = '#4CAF50'  # Green - connected
                status_icon = '🟢'
                status_text = 'Connected'
                
                # Get real-time stats
                start = self.start_times.get(caster['name'])
                uptime_str = 'N/A'
                if start:
                    uptime = datetime.now() - start
                    uptime_str = self.format_timedelta(uptime)
                
                total = getattr(client, "total_bytes", 0)
                last = self.last_bytes.get(caster['name'], 0)
                bps = total - last
            else:
                status_color = '#F44336'  # Red - disconnected
                status_icon = '🔴'
                status_text = 'Disconnected'
                uptime_str = '-'
                bps = 0
            
            # Get satellite count
            sat_count = 0
            sat_details = ''
            if caster['name'] in self.satellite_stats:
                sat_data = self.satellite_stats[caster['name']]
                sat_count = sum(len(sats) for sats in sat_data.values())
                sat_breakdown = []
                for const in ['GPS', 'Galileo', 'GLONASS', 'BeiDou', 'QZSS', 'SBAS']:
                    count = len(sat_data.get(const, set()))
                    if count > 0:
                        sat_breakdown.append(f"{const}: {count}")
                if sat_breakdown:
                    sat_details = '<br>' + ', '.join(sat_breakdown)
            
            # Get RTCM message types
            rtcm_msgs = ''
            if caster['name'] in self.rtcm_stats:
                msg_types = sorted(self.rtcm_stats[caster['name']].keys(), key=lambda x: str(x))
                if msg_types:
                    rtcm_msgs = ', '.join(str(m) for m in msg_types[:10])
                    if len(msg_types) > 10:
                        rtcm_msgs += f', ... ({len(msg_types)} total)'
            
            # Build enriched popup content
            popup_content = f"""
                <div style='background:#ffffff;padding:10px;font-family:Arial,sans-serif;min-width:250px;'>
                    <div style='font-weight:bold;color:#000000;font-size:16px;margin-bottom:8px;'>{status_icon} {name}</div>
                    <div style='color:#000000;font-size:12px;line-height:1.6;'>
                        <b>Status:</b> <span style='color:{status_color};font-weight:bold;'>{status_text}</span><br>
                        <b>Uptime:</b> {uptime_str}<br>
                        <b>Data rate:</b> <span id='data-rate-value'>{bps}</span> B/s<br>
                        <hr style='margin:6px 0;border:none;border-top:1px solid #ddd;'>
                        <b>📍 Location:</b><br>
                        Lat: {lat}° | Lon: {lon}°<br>
                        Alt: {alt} m<br>
                        <hr style='margin:6px 0;border:none;border-top:1px solid #ddd;'>
                        <b>Connection:</b><br>
                        {host}:{port}/{mount}<br>
                        {'<hr style="margin:6px 0;border:none;border-top:1px solid #ddd;"><b>🛰️ Satellites:</b> ' + str(sat_count) + sat_details + '<br>' if sat_count > 0 else ''}
                        {'<hr style="margin:6px 0;border:none;border-top:1px solid #ddd;"><b>📡 RTCM:</b> ' + rtcm_msgs if rtcm_msgs else ''}
                    </div>
                </div>
            """.replace('\n', ' ').replace("'", "\\'")
            
            # Create safe marker ID
            marker_id = caster['name'].replace(' ', '_').replace('-', '_').replace('.', '_').replace('/', '_').replace('\\', '_')
            
            # Store marker ID mapping for updates
            self.map_marker_ids[marker_id] = caster['name']
            
            markers_js += f"""
            // Coverage area (20 km radius)
            L.circle([{lat}, {lon}], {{
                radius: 20000,  // 20 km in meters
                color: '{status_color}',
                fillColor: '{status_color}',
                fillOpacity: 0.1,
                weight: 1,
                opacity: 0.4
            }}).addTo(map);
            
            // Station marker
            markers['{marker_id}'] = L.circleMarker([{lat}, {lon}], {{
                radius: 8,
                fillColor: '{status_color}',
                color: '#ffffff',
                weight: 2,
                opacity: 1,
                fillOpacity: 0.9
            }}).addTo(map).bindPopup('{popup_content}');
            """
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8"/>
            <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
            <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
            <style>
                html,body,#map{{height:100%;margin:0;}}
                .leaflet-popup-content-wrapper {{
                    border-radius: 8px;
                }}
                .coverage-legend {{
                    position: absolute;
                    bottom: 30px;
                    right: 10px;
                    background: rgba(255, 255, 255, 0.95);
                    padding: 10px 15px;
                    border-radius: 8px;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.2);
                    font-family: Arial, sans-serif;
                    font-size: 12px;
                    color: #333;
                    z-index: 1000;
                }}
                .coverage-legend-title {{
                    font-weight: bold;
                    margin-bottom: 5px;
                    font-size: 13px;
                }}
            </style>
        </head>
        <body>
        <div id="map"></div>
        <div class="coverage-legend">
            <div class="coverage-legend-title">📡 RTK Coverage</div>
            <div>Radius: 20 km</div>
        </div>
        <script>
        var map = L.map('map').setView([{center_lat}, {center_lon}], {'10' if not use_bounds else '2'});
        L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
            maxZoom: 19,
            attribution: '&copy; OpenStreetMap contributors'
        }}).addTo(map);
        
        {'// Fit map to show all markers' if use_bounds else ''}
        {'map.fitBounds([' + bounds_sw + ', ' + bounds_ne + '], {padding: [50, 50]});' if use_bounds else ''}
        
        // Store marker references for updates
        var markers = {{}};
        
        {markers_js}
        
        // Function to update popup content for a specific marker
        function updatePopup(markerId, statusColor, statusText, uptime, bps, satCount, satDetails, rtcmMsgs) {{
            var marker = markers[markerId];
            if (marker && marker.isPopupOpen()) {{
                // Get current popup content and update only dynamic parts
                var popup = marker.getPopup();
                var content = popup.getContent();
                
                // Update status text and color only (leave emoji icons untouched)
                content = content.replace(/(<span style='color:#[0-9A-Fa-f]{{6}};font-weight:bold;'>)[^<]+(<\/span>)/, 
                    function(match, p1, p2) {{ return p1 + statusText + p2; }});
                content = content.replace(/(color:)#[0-9A-Fa-f]{{6}}(;font-weight:bold;'>)/, 
                    function(match, p1, p2) {{ return p1 + statusColor + p2; }});
                
                // Update uptime
                content = content.replace(/(<b>Uptime:<\/b> )[^<]+(<br>)/, function(match, p1, p2) {{
                    return p1 + uptime + p2;
                }});
                
                // Update data rate value
                content = content.replace(/(<span id='data-rate-value'>)\d+(<\/span>)/, 
                    function(match, p1, p2) {{ return p1 + bps + p2; }});
                
                // Update satellites - match entire satellite section properly
                if (satCount > 0) {{
                    // Match satellite count and all details up to the next section or end
                    var satRegex = /<hr[^>]*><b>🛰️ Satellites:<\/b> \d+.*?<br>(?=<hr|<\/div>)/s;
                    var newSatSection = '<hr style="margin:6px 0;border:none;border-top:1px solid #ddd;"><b>🛰️ Satellites:</b> ' + satCount + satDetails + '<br>';
                    
                    if (content.match(satRegex)) {{
                        // Replace existing section
                        content = content.replace(satRegex, newSatSection);
                    }} else {{
                        // Add new section before RTCM or at end
                        var rtcmPos = content.indexOf('<hr style="margin:6px 0;border:none;border-top:1px solid #ddd;"><b>📡 RTCM:</b>');
                        if (rtcmPos > 0) {{
                            content = content.substring(0, rtcmPos) + newSatSection + content.substring(rtcmPos);
                        }} else {{
                            content = content.replace(/(<\/div>\s*<\/div>\s*)$/, newSatSection + '$1');
                        }}
                    }}
                }} else {{
                    // Remove satellite section if no satellites
                    content = content.replace(/<hr[^>]*><b>🛰️ Satellites:<\/b>.*?<br>(?=<hr|<\/div>)/s, '');
                }}
                
                // Update RTCM messages
                if (rtcmMsgs) {{
                    if (content.includes('<b>📡 RTCM:</b>')) {{
                        content = content.replace(/(<b>📡 RTCM:<\/b> )[^<]+(?=<)/, function(match, p1) {{ 
                            return p1 + rtcmMsgs; 
                        }});
                    }} else {{
                        // Add RTCM section if it wasn't there before
                        content = content.replace(/(<\/div>\s*<\/div>\s*)$/, 
                            '<hr style="margin:6px 0;border:none;border-top:1px solid #ddd;"><b>📡 RTCM:</b> ' + rtcmMsgs + '</div></div>');
                    }}
                }} else {{
                    // Remove RTCM section if no messages
                    content = content.replace(/<hr[^>]*><b>📡 RTCM:<\/b>[^<]*/, '');
                }}
                
                popup.setContent(content);
            }}
        }}
        </script>
        </body>
        </html>
        """
        self.map_view.setHtml(html)

    def update_map_popups(self):
        """Update popup content for all markers with open popups - called every second"""
        if not hasattr(self, 'map_marker_ids') or not self.map_marker_ids:
            return
        
        # Update each marker's popup if it's open
        for marker_id, caster_name in self.map_marker_ids.items():
            caster = next((c for c in self.casters if c.get('name') == caster_name), None)
            if not caster:
                continue
            
            # Get real-time data
            client = self.clients.get(caster_name)
            if client and getattr(client, 'running', False):
                status_color = '#4CAF50'
                status_icon = '🟢'
                status_text = 'Connected'
                
                start = self.start_times.get(caster_name)
                if start:
                    uptime = datetime.now() - start
                    uptime_str = self.format_timedelta(uptime)
                else:
                    uptime_str = 'N/A'
                
                # Calculate data rate (bytes per second)
                # NOTE: We use separate tracking from update_ui() to avoid interference
                if not hasattr(self, 'map_last_bytes'):
                    self.map_last_bytes = {}
                
                total = getattr(client, "total_bytes", 0)
                last = self.map_last_bytes.get(caster_name, total)  # Initialize to current if first time
                bps = total - last
                self.map_last_bytes[caster_name] = total  # UPDATE for next calculation!
            else:
                status_color = '#F44336'
                status_icon = '🔴'
                status_text = 'Disconnected'
                uptime_str = '-'
                bps = 0
            
            # Get satellite count
            sat_count = 0
            sat_details = ''
            if caster_name in self.satellite_stats:
                sat_data = self.satellite_stats[caster_name]
                sat_count = sum(len(sats) for sats in sat_data.values())
                sat_breakdown = []
                for const in ['GPS', 'Galileo', 'GLONASS', 'BeiDou', 'QZSS', 'SBAS']:
                    count = len(sat_data.get(const, set()))
                    if count > 0:
                        sat_breakdown.append(f"{const}: {count}")
                if sat_breakdown:
                    sat_details = '<br>' + ', '.join(sat_breakdown)
            
            # Get RTCM messages
            rtcm_msgs = ''
            if caster_name in self.rtcm_stats:
                msg_types = sorted(self.rtcm_stats[caster_name].keys(), key=lambda x: str(x))
                if msg_types:
                    rtcm_msgs = ', '.join(str(m) for m in msg_types[:10])
                    if len(msg_types) > 10:
                        rtcm_msgs += f', ... ({len(msg_types)} total)'
            
            # Escape strings for JavaScript
            uptime_str = uptime_str.replace("'", "\\'")
            sat_details = sat_details.replace("'", "\\'")
            rtcm_msgs = rtcm_msgs.replace("'", "\\'")
            status_text = status_text.replace("'", "\\'")
            
            # Call JavaScript function to update popup (no emoji icons to avoid Unicode rendering issues)
            js_code = f"updatePopup('{marker_id}', '{status_color}', '{status_text}', '{uptime_str}', {bps}, {sat_count}, '{sat_details}', '{rtcm_msgs}');"
            
            try:
                self.map_view.page().runJavaScript(js_code)
            except Exception:
                logging.debug(f"Failed to update popup for {marker_id}", exc_info=True)

    def on_tab_changed(self, index):
        if self.tabs.tabText(index) == "Map":
            self.update_map_view()
            # Setup JavaScript message handler for marker clicks
            if hasattr(self, 'map_view'):
                try:
                    from PyQt6.QtWebChannel import QWebChannel
                    # Note: Full implementation would require QWebChannel setup
                    # For now, markers will show popups on click
                except ImportError:
                    pass

    # ---------- Timers ----------
    def init_timers(self):
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_ui)
        self.timer.start(1000)

    # ---------- Connect / Auto connect ----------
    def auto_connect_all(self):
        for c in self.casters:
            self.start_connection(c)
        # populate combobox after loading casters
        for c in self.casters:
            self.msg_caster_combo.addItem(c.get("name", ""))
            self.map_caster_combo.addItem(c.get("name", ""))
            self.sat_caster_combo.addItem(c.get("name", ""))

    def start_connection(self, caster):
        name = caster["name"]
        if name in self.clients and getattr(self.clients[name], "running", False):
            return
        client = NTRIPClient(caster, self.signals)
        self.clients[name] = client
        self.start_times[name] = datetime.now()
        self.last_bytes[name] = 0
        client.start()
        self.on_status(name, "🟡 Connecting...")
        self.update_button_state(name, True)

    # ---------- Add / Remove ----------
    def show_add_dialog(self):
        dlg = AddCasterDialog(self)
        if dlg.exec():
            data = dlg.get_data()
            if not data["name"] or not data["host"] or not data["mount"]:
                return
            self.casters.append(data)
            with open(self.get_casters_path(), "w", encoding="utf-8") as f:
                json.dump(self.casters, f, indent=2, ensure_ascii=False)
            self._insert_caster_row(data)
            self.start_connection(data)
            # add to all comboboxes
            self.msg_caster_combo.addItem(data.get("name", ""))
            self.map_caster_combo.addItem(data.get("name", ""))
            self.sat_caster_combo.addItem(data.get("name", ""))

    def remove_caster_by_name(self, name):
        confirm = QMessageBox.question(
            self, "Confirm delete",
            f"Delete caster '{name}' permanently?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        client = self.clients.get(name)
        if client and client.running:
            client.stop()
            try:
                client.join(timeout=2)
            except Exception:
                logging.debug("Exception joining client on remove", exc_info=True)
        self.casters = [c for c in self.casters if c.get("name") != name]
        with open(self.get_casters_path(), "w", encoding="utf-8") as f:
            json.dump(self.casters, f, indent=2, ensure_ascii=False)
        for r in range(self.caster_list.rowCount()):
            if self.caster_list.item(r, 0).text() == name:
                self.caster_list.removeRow(r)
                break
        QMessageBox.information(self, "Caster removed", f"Caster '{name}' removed successfully.")
        # also remove any client entries
        try:
            client = self.clients.pop(name, None)
            if client:
                try:
                    client.stop()
                except Exception:
                    logging.debug("Error stopping client on remove", exc_info=True)
        except Exception:
            logging.debug("Error removing client entry", exc_info=True)
        # remove from all comboboxes
        idx = self.msg_caster_combo.findText(name)
        if idx >= 0:
            self.msg_caster_combo.removeItem(idx)
        idx2 = self.map_caster_combo.findText(name)
        if idx2 >= 0:
            self.map_caster_combo.removeItem(idx2)
        idx3 = self.sat_caster_combo.findText(name)
        if idx3 >= 0:
            self.sat_caster_combo.removeItem(idx3)

    # ---------- Cleanup ----------
    def cleanup(self):
        # Stop and join all running clients
        for name, client in list(self.clients.items()):
            try:
                if client and getattr(client, 'running', False):
                    client.stop()
                client.join(timeout=2)
            except Exception:
                logging.debug("Exception while cleaning up client %s", name, exc_info=True)

    # ---------- Manual connect/disconnect ----------
    def manual_toggle_connection(self, name, btn):
        client = self.clients.get(name)
        if client and client.running:
            client.stop(user_initiated=True)  # User manually disconnected
            try:
                client.join(timeout=2)
            except Exception:
                logging.debug("Exception joining client on manual toggle", exc_info=True)
            btn.setText("Connect")
            self.on_status(name, "🔴 Disconnected (User stopped)")
        else:
            caster = next((c for c in self.casters if c.get("name") == name), None)
            if caster:
                cli = NTRIPClient(caster, self.signals)
                self.clients[name] = cli
                self.start_times[name] = datetime.now()
                self.last_bytes[name] = 0
                cli.start()
                btn.setText("Disconnect")
                self.on_status(name, "🟡 Connecting...")

    def show_edit_dialog(self, old_name):
        caster = next((c for c in self.casters if c.get("name") == old_name), None)
        if not caster:
            return
        dlg = AddCasterDialog(self, data=caster)
        if dlg.exec():
            newdata = dlg.get_data()
            if not newdata["name"] or not newdata["host"] or not newdata["mount"]:
                QMessageBox.warning(self, "Error", "Name, host and mount cannot be empty.")
                return
            # replace caster in list
            for i, c in enumerate(self.casters):
                if c.get("name") == old_name:
                    self.casters[i] = newdata
                    break
            try:
                with open(self.get_casters_path(), "w", encoding="utf-8") as f:
                    json.dump(self.casters, f, indent=2, ensure_ascii=False)
            except Exception:
                logging.exception("Failed to write casters.json after edit")
            # update UI row and action widget
            for r in range(self.caster_list.rowCount()):
                if self.caster_list.item(r, 0).text() == old_name:
                    self.caster_list.setItem(r, 0, QTableWidgetItem(newdata.get("name", "")))
                    self.caster_list.setItem(r, 1, QTableWidgetItem(f"{newdata.get('host','')}:{newdata.get('port','')}"))
                    self.caster_list.setItem(r, 2, QTableWidgetItem(newdata.get("mount", "")))
                    # replace action widget (rebinds callbacks to new name)
                    self.caster_list.setCellWidget(r, 6, self._make_action_widget(newdata))
                    break
            # handle running client: restart if necessary
            client = self.clients.get(old_name)
            if client:
                try:
                    if getattr(client, 'running', False):
                        client.stop()
                        try:
                            client.join(timeout=2)
                        except Exception:
                            logging.debug("Exception joining client during edit", exc_info=True)
                except Exception:
                    logging.debug("Error stopping old client during edit", exc_info=True)
                # remove old entries
                self.clients.pop(old_name, None)
                self.start_times.pop(old_name, None)
                self.last_bytes.pop(old_name, None)
                self.rtcm_stats.pop(old_name, None)
                # start a new client under new name
                self.start_connection(newdata)
                # update combobox: remove old name, add new name if not present
                old_idx = self.msg_caster_combo.findText(old_name)
                if old_idx >= 0:
                    self.msg_caster_combo.removeItem(old_idx)
                new_idx = self.msg_caster_combo.findText(newdata.get("name", ""))
                if new_idx < 0:
                    self.msg_caster_combo.addItem(newdata.get("name", ""))
                # update map combobox similarly
                try:
                    if hasattr(self, 'map_caster_combo'):
                        old_idx2 = self.map_caster_combo.findText(old_name)
                        if old_idx2 >= 0:
                            self.map_caster_combo.removeItem(old_idx2)
                        if self.map_caster_combo.findText(newdata.get("name", "")) < 0:
                            self.map_caster_combo.addItem(newdata.get("name", ""))
                except Exception:
                    logging.debug("Failed updating map combobox during edit", exc_info=True)

    def update_button_state(self, name, connected):
        for r in range(self.caster_list.rowCount()):
            if self.caster_list.item(r, 0).text() == name:
                widget = self.caster_list.cellWidget(r, 6)
                if widget:
                    btn = widget.layout().itemAt(0).widget()
                    if btn:
                        btn.setText("Disconnect" if connected else "Connect")
                break

    # ---------- Status & Data handlers ----------
    def on_status(self, caster_name, status_text):
        for r in range(self.caster_list.rowCount()):
            it = self.caster_list.item(r, 0)
            if it and it.text() == caster_name:
                status_item = QTableWidgetItem(status_text)
                
                # Apply color coding based on status
                if "✅" in status_text or "Connection OK" in status_text:
                    status_item.setForeground(QColor(0, 255, 0))  # Green
                elif "🟡" in status_text or "Reconnecting" in status_text:
                    status_item.setForeground(QColor(255, 200, 0))  # Yellow/Orange
                elif "🔴" in status_text or "Disconnected" in status_text:
                    status_item.setForeground(QColor(255, 100, 100))  # Red
                elif "⚠️" in status_text or "Error" in status_text:
                    status_item.setForeground(QColor(255, 150, 0))  # Orange
                
                self.caster_list.setItem(r, 3, status_item)
                break
        if "✅" in status_text:
            self.update_button_state(caster_name, True)
        elif "🔴" in status_text:
            self.update_button_state(caster_name, False)

    def on_disconnect(self, caster_name):
        self.update_button_state(caster_name, False)

    def on_data(self, caster_name, data):
        try:
            client = self.clients.get(caster_name)
            if not client:
                return
            # copy buffer under lock so parsing happens on a stable snapshot
            with client.lock:
                buf = bytes(client.buffer)
            if not buf:
                return
            stream = io.BytesIO(buf)
            for _, parsed in RTCMReader(stream):
                msg_type = getattr(parsed, "identity", None)
                if not msg_type:
                    continue
                
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                # Update RTCM message stats
                if caster_name not in self.rtcm_stats:
                    self.rtcm_stats[caster_name] = {}
                caster_msgs = self.rtcm_stats[caster_name]
                if msg_type not in caster_msgs:
                    caster_msgs[msg_type] = {"count": 0, "last": now}
                caster_msgs[msg_type]["count"] += 1
                caster_msgs[msg_type]["last"] = now
                
                # Extract and update satellite and signal info
                sat_info, sig_info = extract_satellite_info(parsed)
                
                if caster_name not in self.satellite_stats:
                    self.satellite_stats[caster_name] = {
                        'GPS': set(), 'GLONASS': set(), 'Galileo': set(),
                        'BeiDou': set(), 'QZSS': set(), 'SBAS': set()
                    }
                if caster_name not in self.signal_stats:
                    self.signal_stats[caster_name] = {
                        'GPS': set(), 'GLONASS': set(), 'Galileo': set(),
                        'BeiDou': set(), 'QZSS': set(), 'SBAS': set()
                    }
                # Merge satellite and signal data (union of sets)
                for constellation, sats in sat_info.items():
                    if sats:  # Only update if satellites found
                        self.satellite_stats[caster_name][constellation].update(sats)
                for constellation, sigs in sig_info.items():
                    if sigs:  # Only update if signals found
                        self.signal_stats[caster_name][constellation].update(sigs)
            # remove consumed bytes from client's buffer
            consumed = stream.tell()
            if consumed:
                with client.lock:
                    client.buffer = client.buffer[consumed:]
            if caster_name == self.selected_caster:
                self.update_messages_view()
                self.update_satellites_view()
        except Exception:
            logging.exception("Error parsing RTCM in on_data for %s", caster_name)

    # ---------- UI update tick ----------
    def update_ui(self):
        now = datetime.now()
        for r in range(self.caster_list.rowCount()):
            name = self.caster_list.item(r, 0).text()
            client = self.clients.get(name)
            if not client:
                continue
            total = getattr(client, "total_bytes", 0)
            last = self.last_bytes.get(name, 0)
            bps = total - last
            self.last_bytes[name] = total
            self.caster_list.setItem(r, 4, QTableWidgetItem(str(bps)))
            start = self.start_times.get(name)
            if start and getattr(client, "running", False):
                uptime = now - start
                self.caster_list.setItem(r, 5, QTableWidgetItem(self.format_timedelta(uptime)))
            else:
                self.caster_list.setItem(r, 5, QTableWidgetItem("-"))
        
        # Update detail panel if a caster is selected
        if self.selected_caster and hasattr(self, 'detail_panel'):
            self.update_detail_panel()
        
        # Update map popups if Map tab is active
        if hasattr(self, 'tabs') and hasattr(self, 'map_tab'):
            try:
                if self.tabs.currentWidget() == self.map_tab and hasattr(self, 'map_view'):
                    self.update_map_popups()
            except Exception:
                logging.debug("Failed to update map popups", exc_info=True)
        
        # Auto-refresh removed - UI updates every second via update_display()
        # No automatic reconnection - user has full control

    def connect_all_disconnected(self):
        """Manually connect all disconnected casters"""
        connected_count = 0
        for c in self.casters:
            name = c["name"]
            client = self.clients.get(name)
            if not client or not getattr(client, "running", False):
                self.start_connection(c)
                connected_count += 1
        
        if connected_count > 0:
            logging.info(f"Connecting {connected_count} disconnected caster(s)")
        else:
            logging.info("All casters already connected")

    # ---------- About Dialog ----------
    def show_about_dialog(self):
        """Show About dialog with version info and update check"""
        dialog = AboutDialog(self)
        dialog.exec()

    # ---------- Messages ----------
    def close_detail_panel(self):
        """Close the caster detail panel"""
        if hasattr(self, 'detail_panel'):
            self.detail_panel.hide()
        self.selected_caster = None
        # Clear selection in table
        if hasattr(self, 'caster_list'):
            self.caster_list.clearSelection()
    
    def on_caster_selected(self, row, _col):
        try:
            clicked_caster = self.caster_list.item(row, 0).text()
            
            # Toggle: if clicking the same caster, close the panel
            if self.selected_caster == clicked_caster and hasattr(self, 'detail_panel') and self.detail_panel.isVisible():
                self.close_detail_panel()
                return
            
            self.selected_caster = clicked_caster
            # Stay on Casters tab, show detail panel instead
            self.update_detail_panel()
            # update comboboxes to match selected caster
        except Exception as e:
            logging.exception("Error in on_caster_selected")
            print(f"Error selecting caster: {e}")
            import traceback
            traceback.print_exc()
            return
        try:
            self.msg_caster_combo.blockSignals(True)
            idx = self.msg_caster_combo.findText(self.selected_caster)
            if idx >= 0:
                self.msg_caster_combo.setCurrentIndex(idx)
            self.msg_caster_combo.blockSignals(False)
        except Exception:
            logging.debug("Failed syncing messages combobox on caster select", exc_info=True)
        try:
            if hasattr(self, 'map_caster_combo'):
                self.map_caster_combo.blockSignals(True)
                idx2 = self.map_caster_combo.findText(self.selected_caster)
                if idx2 >= 0:
                    self.map_caster_combo.setCurrentIndex(idx2)
                self.map_caster_combo.blockSignals(False)
        except Exception:
            logging.debug("Failed syncing map combobox on caster select", exc_info=True)
        try:
            if hasattr(self, 'sat_caster_combo'):
                self.sat_caster_combo.blockSignals(True)
                idx3 = self.sat_caster_combo.findText(self.selected_caster)
                if idx3 >= 0:
                    self.sat_caster_combo.setCurrentIndex(idx3)
                self.sat_caster_combo.blockSignals(False)
        except Exception:
            logging.debug("Failed syncing satellites combobox on caster select", exc_info=True)
        try:
            self.update_messages_view()
        except Exception as e:
            logging.exception("Error in update_messages_view from on_caster_selected")
            print(f"Error updating messages view: {e}")
            import traceback
            traceback.print_exc()

    def update_messages_view(self):
        caster = self.selected_caster
        self.msg_table.setRowCount(0)
        if not caster or caster not in self.rtcm_stats:
            # sync combobox
            self.msg_caster_combo.blockSignals(True)
            self.msg_caster_combo.setCurrentIndex(0)  # (none)
            self.msg_caster_combo.blockSignals(False)
            self.msg_total_label.setText("Total messages: 0")
            return
        # sync combobox to current caster
        self.msg_caster_combo.blockSignals(True)
        idx = self.msg_caster_combo.findText(caster)
        if idx >= 0:
            self.msg_caster_combo.setCurrentIndex(idx)
        self.msg_caster_combo.blockSignals(False)
        total = 0
        for msg_type in sorted(self.rtcm_stats[caster].keys(), key=lambda x: str(x)):
            info = self.rtcm_stats[caster][msg_type]
            row = self.msg_table.rowCount()
            self.msg_table.insertRow(row)
            # color square for msg_type
            color = get_color_for_msg_type(msg_type)
            msg_type_item = QTableWidgetItem(str(msg_type))
            msg_type_item.setBackground(QColor(color))
            # Use automatic text color based on background luminance
            text_color = get_text_color_for_background(color)
            msg_type_item.setForeground(QColor(text_color))
            self.msg_table.setItem(row, 0, msg_type_item)
            self.msg_table.setItem(row, 1, QTableWidgetItem(info["last"]))
            self.msg_table.setItem(row, 2, QTableWidgetItem(str(info["count"])))
            total += info["count"]
        self.msg_total_label.setText(f"Total messages: {total}")

    def on_msg_caster_changed(self, caster_name):
        # called when user changes selection in Messages combobox
        if caster_name and caster_name != "(none)":
            self.selected_caster = caster_name
            # sync map combobox to same caster
            try:
                if hasattr(self, 'map_caster_combo'):
                    self.map_caster_combo.blockSignals(True)
                    idx = self.map_caster_combo.findText(caster_name)
                    if idx >= 0:
                        self.map_caster_combo.setCurrentIndex(idx)
                    self.map_caster_combo.blockSignals(False)
            except Exception:
                logging.debug("Failed syncing map combobox from messages", exc_info=True)
            # sync satellites combobox to same caster
            try:
                if hasattr(self, 'sat_caster_combo'):
                    self.sat_caster_combo.blockSignals(True)
                    idx2 = self.sat_caster_combo.findText(caster_name)
                    if idx2 >= 0:
                        self.sat_caster_combo.setCurrentIndex(idx2)
                    self.sat_caster_combo.blockSignals(False)
            except Exception:
                logging.debug("Failed syncing satellites combobox from messages", exc_info=True)
            self.update_messages_view()
        else:
            self.selected_caster = None
            self.msg_table.setRowCount(0)
            self.msg_total_label.setText("Total messages: 0")

    def on_map_caster_changed(self, caster_name):
        # called when user changes selection in Map combobox
        if caster_name and caster_name != "(none)":
            self.selected_caster = caster_name
            # sync messages combobox to same caster
            try:
                self.msg_caster_combo.blockSignals(True)
                idx = self.msg_caster_combo.findText(caster_name)
                if idx >= 0:
                    self.msg_caster_combo.setCurrentIndex(idx)
                self.msg_caster_combo.blockSignals(False)
            except Exception:
                logging.debug("Failed syncing messages combobox from map", exc_info=True)
            # sync satellites combobox to same caster
            try:
                if hasattr(self, 'sat_caster_combo'):
                    self.sat_caster_combo.blockSignals(True)
                    idx2 = self.sat_caster_combo.findText(caster_name)
                    if idx2 >= 0:
                        self.sat_caster_combo.setCurrentIndex(idx2)
                    self.sat_caster_combo.blockSignals(False)
            except Exception:
                logging.debug("Failed syncing satellites combobox from map", exc_info=True)
            self.update_map_view()
        else:
            self.selected_caster = None
            self.map_view.setHtml("<h3 style='color:#ffffff;margin:1rem;'>No caster selected.</h3>")
    
    # ---------- Satellites Tab ----------
    def on_sat_caster_changed(self, caster_name):
        """Called when user changes selection in Satellites combobox"""
        if caster_name and caster_name != "(none)":
            self.selected_caster = caster_name
            # sync messages combobox to same caster
            try:
                self.msg_caster_combo.blockSignals(True)
                idx = self.msg_caster_combo.findText(caster_name)
                if idx >= 0:
                    self.msg_caster_combo.setCurrentIndex(idx)
                self.msg_caster_combo.blockSignals(False)
            except Exception:
                logging.debug("Failed syncing messages combobox from satellites", exc_info=True)
            # sync map combobox to same caster
            try:
                if hasattr(self, 'map_caster_combo'):
                    self.map_caster_combo.blockSignals(True)
                    idx2 = self.map_caster_combo.findText(caster_name)
                    if idx2 >= 0:
                        self.map_caster_combo.setCurrentIndex(idx2)
                    self.map_caster_combo.blockSignals(False)
            except Exception:
                logging.debug("Failed syncing map combobox from satellites", exc_info=True)
            self.update_satellites_view()
        else:
            self.selected_caster = None
            self.sat_table.setRowCount(0)
            self.sat_total_label.setText("Total satellites: 0")
    
    def on_constellation_selected(self, row, _col):
        """Handle constellation selection in Satellites tab"""
        try:
            constellation = self.sat_table.item(row, 0).text()
            
            # Toggle: if clicking the same constellation, close the panel
            if self.selected_constellation == constellation and hasattr(self, 'sat_detail_panel') and self.sat_detail_panel.isVisible():
                self.close_constellation_detail_panel()
                return
            
            self.selected_constellation = constellation
            self.update_constellation_detail_panel()
        except Exception as e:
            logging.exception("Error in on_constellation_selected")
    
    def close_constellation_detail_panel(self):
        """Close the constellation detail panel"""
        if hasattr(self, 'sat_detail_panel'):
            self.sat_detail_panel.hide()
        self.selected_constellation = None
        # Clear selection in table
        if hasattr(self, 'sat_table'):
            self.sat_table.clearSelection()
    
    def update_constellation_detail_panel(self):
        """Update the constellation detail panel with information about selected constellation"""
        if not self.selected_constellation or not self.selected_caster:
            return
        
        if self.selected_caster not in self.satellite_stats:
            return
        
        sat_data = self.satellite_stats[self.selected_caster]
        sig_data = self.signal_stats.get(self.selected_caster, {})
        
        # Show panel
        if hasattr(self, 'sat_detail_panel'):
            self.sat_detail_panel.show()
        
        # Constellation colors
        colors = {
            'GPS': '#4DAF4A',
            'Galileo': '#377EB8',
            'GLONASS': '#E41A1C',
            'BeiDou': '#FF7F00',
            'QZSS': '#984EA3',
            'SBAS': '#FFFF33'
        }
        
        # Update header with color
        color = colors.get(self.selected_constellation, '#ffffff')
        self.sat_detail_header.setText(f"<span style='color:{color}'>{self.selected_constellation}</span>")
        
        # Get constellation description
        description = get_constellation_description(self.selected_constellation)
        self.sat_detail_description.setText(description)
        
        # Get satellite data for this constellation
        satellites = sat_data.get(self.selected_constellation, set())
        sat_count = len(satellites)
        
        # Calculate total for percentage
        total_sats = sum(len(sat_data.get(const, set())) for const in ['GPS', 'Galileo', 'GLONASS', 'BeiDou', 'QZSS', 'SBAS'])
        percentage = (sat_count / total_sats * 100) if total_sats > 0 else 0
        
        # Update stats
        stats_text = f"""<b>Satellites:</b> {sat_count}<br>
<b>Percentage:</b> {percentage:.1f}%<br>
<b>Total tracked:</b> {total_sats}"""
        self.sat_detail_stats.setText(stats_text)
        
        # Update PRN list
        if satellites:
            # Sort and format PRN numbers
            prn_list = sorted(str(prn) for prn in satellites)
            # Group into lines of ~8 PRNs
            prn_lines = []
            for i in range(0, len(prn_list), 8):
                prn_lines.append(", ".join(prn_list[i:i+8]))
            prn_text = "<br>".join(prn_lines)
            self.sat_detail_prns.setText(prn_text)
        else:
            self.sat_detail_prns.setText("No satellites detected")
        
        # Update signals
        signals = sig_data.get(self.selected_constellation, set())
        if signals:
            sig_list = sorted(signals)
            sig_text = "<br>".join([f"• {sig}" for sig in sig_list])
            self.sat_detail_signals.setText(sig_text)
        else:
            self.sat_detail_signals.setText("No signal data")
    
    def update_satellites_view(self):
        """Update satellite table for selected caster"""
        caster = self.selected_caster
        self.sat_table.setRowCount(0)
        
        if not caster or caster not in self.satellite_stats:
            # sync combobox
            self.sat_caster_combo.blockSignals(True)
            self.sat_caster_combo.setCurrentIndex(0)  # (none)
            self.sat_caster_combo.blockSignals(False)
            self.sat_total_label.setText("Total satellites: 0")
            return
        
        # sync combobox to current caster
        self.sat_caster_combo.blockSignals(True)
        idx = self.sat_caster_combo.findText(caster)
        if idx >= 0:
            self.sat_caster_combo.setCurrentIndex(idx)
        self.sat_caster_combo.blockSignals(False)
        
        sat_data = self.satellite_stats[caster]
        sig_data = self.signal_stats.get(caster, {})
        
        # Constellation colors
        colors = {
            'GPS': '#4DAF4A',
            'Galileo': '#377EB8',
            'GLONASS': '#E41A1C',
            'BeiDou': '#FF7F00',
            'QZSS': '#984EA3',
            'SBAS': '#FFFF33'
        }
        
        # Calculate total satellites
        total_sats = sum(len(sat_data.get(const, set())) for const in ['GPS', 'Galileo', 'GLONASS', 'BeiDou', 'QZSS', 'SBAS'])
        
        # Add rows for each constellation
        for const_name in ['GPS', 'Galileo', 'GLONASS', 'BeiDou', 'QZSS', 'SBAS']:
            satellites = sat_data.get(const_name, set())
            sat_count = len(satellites)
            
            # Get signals
            signals = sig_data.get(const_name, set())
            sig_text = ", ".join(sorted(signals)) if signals else "-"
            
            # Calculate percentage
            percentage = (sat_count / total_sats * 100) if total_sats > 0 else 0
            
            row = self.sat_table.rowCount()
            self.sat_table.insertRow(row)
            
            # Constellation name (colored)
            color = colors.get(const_name, '#ffffff')
            const_item = QTableWidgetItem(const_name)
            const_item.setBackground(QColor(color))
            # Use automatic text color based on background luminance
            text_color = get_text_color_for_background(color)
            const_item.setForeground(QColor(text_color))
            self.sat_table.setItem(row, 0, const_item)
            
            # Satellite count
            self.sat_table.setItem(row, 1, QTableWidgetItem(str(sat_count)))
            
            # Signals
            self.sat_table.setItem(row, 2, QTableWidgetItem(sig_text))
            
            # Percentage
            self.sat_table.setItem(row, 3, QTableWidgetItem(f"{percentage:.1f}%"))
        
        self.sat_total_label.setText(f"Total satellites: {total_sats}")
    
    def generate_satellite_donut_chart(self, sat_data, total):
        """Generate SVG donut chart for satellites (keeping for compatibility)"""
        if total == 0:
            return "<h3 style='color:#ffffff;margin:1rem;'>No satellite data available yet.</h3>"
        
        # Constellation colors matching the cards
        colors = {
            'GPS': '#4DAF4A',
            'Galileo': '#377EB8',
            'GLONASS': '#E41A1C',
            'BeiDou': '#FF7F00',
            'QZSS': '#984EA3',
            'SBAS': '#FFFF33'
        }
        
        # Calculate angles for each constellation
        segments = []
        start_angle = 0
        
        for const_name in ['GPS', 'Galileo', 'GLONASS', 'BeiDou', 'QZSS', 'SBAS']:
            count = len(sat_data.get(const_name, set()))
            if count > 0:
                angle = (count / total) * 360
                segments.append({
                    'name': const_name,
                    'count': count,
                    'color': colors[const_name],
                    'start': start_angle,
                    'angle': angle
                })
                start_angle += angle
        
        # Generate SVG paths
        svg_paths = []
        cx, cy, r_outer, r_inner = 200, 200, 150, 90
        
        for seg in segments:
            start_rad = (seg['start'] - 90) * 3.14159 / 180
            end_rad = (seg['start'] + seg['angle'] - 90) * 3.14159 / 180
            
            x1 = cx + r_outer * __import__('math').cos(start_rad)
            y1 = cy + r_outer * __import__('math').sin(start_rad)
            x2 = cx + r_outer * __import__('math').cos(end_rad)
            y2 = cy + r_outer * __import__('math').sin(end_rad)
            
            x3 = cx + r_inner * __import__('math').cos(end_rad)
            y3 = cy + r_inner * __import__('math').sin(end_rad)
            x4 = cx + r_inner * __import__('math').cos(start_rad)
            y4 = cy + r_inner * __import__('math').sin(start_rad)
            
            large_arc = 1 if seg['angle'] > 180 else 0
            
            path = f"""
                <path d="M {x1},{y1} A {r_outer},{r_outer} 0 {large_arc},1 {x2},{y2}
                         L {x3},{y3} A {r_inner},{r_inner} 0 {large_arc},0 {x4},{y4} Z"
                      fill="{seg['color']}" stroke="#1e1e1e" stroke-width="2"/>
            """
            svg_paths.append(path)
        
        svg_content = f"""
        <svg width="400" height="400" viewBox="0 0 400 400">
            {''.join(svg_paths)}
            <text x="200" y="190" text-anchor="middle" font-size="32" font-weight="bold" fill="#ffffff">
                {total}
            </text>
            <text x="200" y="220" text-anchor="middle" font-size="16" fill="#cccccc">
                Total
            </text>
        </svg>
        """
        
        return f"""
        <html>
        <head>
            <style>
                body {{ background-color: #1e1e1e; margin: 0; padding: 20px; 
                        display: flex; justify-content: center; align-items: center; }}
            </style>
        </head>
        <body>{svg_content}</body>
        </html>
        """

    def generate_pie_chart_svg(self, caster):
        """Generate SVG donut chart for RTCM message types."""
        if not caster or caster not in self.rtcm_stats or not self.rtcm_stats[caster]:
            return "<h3 style='color:#ffffff;margin:1rem;'>No message data available yet.</h3>"
        
        import math
        stats = self.rtcm_stats[caster]
        total = sum(info["count"] for info in stats.values())
        if total == 0:
            return "<h3 style='color:#ffffff;margin:1rem;'>No message data available yet.</h3>"
        
        # SVG setup - match satellite donut chart sizing
        size = 400
        cx, cy = size / 2, size / 2
        outer_r = 150
        inner_r = 90
        
        slices = []
        angle_start = -90  # start at top
        for msg_type in sorted(stats.keys(), key=lambda x: str(x)):
            count = stats[msg_type]["count"]
            angle_size = (count / total) * 360
            angle_end = angle_start + angle_size
            
            # calc start/end points on outer/inner circles
            def pol2cart(r, angle_deg):
                angle_rad = math.radians(angle_deg)
                return cx + r * math.cos(angle_rad), cy + r * math.sin(angle_rad)
            
            x1_outer, y1_outer = pol2cart(outer_r, angle_start)
            x2_outer, y2_outer = pol2cart(outer_r, angle_end)
            x1_inner, y1_inner = pol2cart(inner_r, angle_start)
            x2_inner, y2_inner = pol2cart(inner_r, angle_end)
            
            large_arc = 1 if angle_size > 180 else 0
            color = get_color_for_msg_type(msg_type)
            
            path = (
                f"M {x1_outer:.1f} {y1_outer:.1f} "
                f"A {outer_r} {outer_r} 0 {large_arc} 1 {x2_outer:.1f} {y2_outer:.1f} "
                f"L {x2_inner:.1f} {y2_inner:.1f} "
                f"A {inner_r} {inner_r} 0 {large_arc} 0 {x1_inner:.1f} {y1_inner:.1f} Z"
            )
            slices.append(f'<path d="{path}" fill="{color}" stroke="#1e1e1e" stroke-width="2"/>')
            
            angle_start = angle_end
        
        svg_content = f"""
        <svg width="{size}" height="{size}" viewBox="0 0 {size} {size}" xmlns="http://www.w3.org/2000/svg">
            {''.join(slices)}
            <text x="{cx:.0f}" y="{cy-10:.0f}" text-anchor="middle" font-size="32" font-weight="bold" fill="#ffffff">
                {total}
            </text>
            <text x="{cx:.0f}" y="{cy+20:.0f}" text-anchor="middle" font-size="16" fill="#cccccc">
                Total
            </text>
        </svg>
        """
        
        return f"""
        <html>
        <head>
            <style>
                body {{ background-color: #1e1e1e; margin: 0; padding: 20px; 
                        display: flex; justify-content: center; align-items: center; }}
            </style>
        </head>
        <body>{svg_content}</body>
        </html>
        """

    # ---------- Sourcetable Tab ----------
    def fetch_sourcetable(self):
        """Fetch mountpoints from NTRIP caster"""
        host = self.st_host_edit.text().strip()
        port = self.st_port_spin.value()
        user = self.st_user_edit.text().strip()
        password = self.st_pass_edit.text().strip()
        
        if not host:
            QMessageBox.warning(self, "Input Required", "Please enter a host address")
            return
        
        # Disable fetch button during operation
        self.st_fetch_btn.setEnabled(False)
        self.st_fetch_btn.setText("Fetching...")
        
        # Create worker thread
        worker = SourcetableFetchWorker(host, port, user, password)
        worker.finished.connect(self.on_sourcetable_fetched)
        worker.error.connect(self.on_sourcetable_error)
        worker.start()
        
        # Store worker reference to prevent garbage collection
        self._sourcetable_worker = worker
    
    def on_sourcetable_fetched(self, mountpoints):
        """Handle successful sourcetable fetch"""
        self.st_fetch_btn.setEnabled(True)
        self.st_fetch_btn.setText("Fetch Mountpoints")
        
        # Clear existing table
        self.st_table.setRowCount(0)
        self.st_table.setSortingEnabled(False)
        
        # Populate table
        for mp in mountpoints:
            row = self.st_table.rowCount()
            self.st_table.insertRow(row)
            
            self.st_table.setItem(row, 0, QTableWidgetItem(mp.get('mount', '')))
            self.st_table.setItem(row, 1, QTableWidgetItem(mp.get('name', '')))
            self.st_table.setItem(row, 2, QTableWidgetItem(mp.get('format', '')))
            
            # Location
            lat = mp.get('lat')
            lon = mp.get('lon')
            if lat is not None and lon is not None:
                loc_text = f"{lat:.4f}, {lon:.4f}"
            else:
                loc_text = "Unknown"
            self.st_table.setItem(row, 3, QTableWidgetItem(loc_text))
            
            self.st_table.setItem(row, 4, QTableWidgetItem(mp.get('nav_systems', '')))
            self.st_table.setItem(row, 5, QTableWidgetItem(mp.get('carrier', '')))
            
            # Store full data in row
            self.st_table.item(row, 0).setData(Qt.ItemDataRole.UserRole, mp)
        
        self.st_table.setSortingEnabled(True)
        
        logging.info(f"Loaded {len(mountpoints)} mountpoints from sourcetable")
    
    def on_sourcetable_error(self, error_msg):
        """Handle sourcetable fetch error"""
        self.st_fetch_btn.setEnabled(True)
        self.st_fetch_btn.setText("Fetch Mountpoints")
        
        QMessageBox.critical(self, "Fetch Error", f"Failed to fetch sourcetable:\n\n{error_msg}")
        logging.error(f"Sourcetable fetch error: {error_msg}")
    
    def filter_sourcetable(self):
        """Filter sourcetable rows based on search text"""
        search_text = self.st_search_edit.text().lower()
        
        for row in range(self.st_table.rowCount()):
            match = False
            for col in range(self.st_table.columnCount()):
                item = self.st_table.item(row, col)
                if item and search_text in item.text().lower():
                    match = True
                    break
            
            self.st_table.setRowHidden(row, not match)
    
    def update_sourcetable_selection(self):
        """Update selection label when table selection changes"""
        selected = self.st_table.selectedItems()
        if not selected:
            self.st_selection_label.setText("Selected: None")
            self.st_add_btn.setEnabled(False)
            return
        
        # Count unique rows
        selected_rows = set()
        for item in selected:
            selected_rows.add(item.row())
        
        count = len(selected_rows)
        if count == 1:
            # Show details for single selection
            row = list(selected_rows)[0]
            mount_item = self.st_table.item(row, 0)
            name_item = self.st_table.item(row, 1)
            if mount_item and name_item:
                self.st_selection_label.setText(f"Selected: {mount_item.text()} - {name_item.text()}")
        else:
            self.st_selection_label.setText(f"Selected: {count} mountpoints")
        
        self.st_add_btn.setEnabled(True)
    
    def add_selected_mountpoints(self):
        """Add selected mountpoints to Casters tab"""
        selected = self.st_table.selectedItems()
        if not selected:
            return
        
        # Get unique selected rows
        selected_rows = set()
        for item in selected:
            selected_rows.add(item.row())
        
        host = self.st_host_edit.text().strip()
        port = self.st_port_spin.value()
        user = self.st_user_edit.text().strip()
        password = self.st_pass_edit.text().strip()
        
        added_count = 0
        for row in selected_rows:
            mount_item = self.st_table.item(row, 0)
            if not mount_item:
                continue
            
            # Get stored data
            mp_data = mount_item.data(Qt.ItemDataRole.UserRole)
            if not mp_data:
                continue
            
            # Create caster entry
            caster_name = f"{host}_{mp_data.get('mount', '')}"
            
            # Check if already exists
            if any(c.get('name') == caster_name for c in self.casters):
                logging.info(f"Caster {caster_name} already exists, skipping")
                continue
            
            caster_data = {
                'name': caster_name,
                'host': host,
                'port': port,
                'mount': mp_data.get('mount', ''),
                'user': user,
                'password': password,
                'lat': mp_data.get('lat'),
                'lon': mp_data.get('lon'),
                'alt': mp_data.get('alt')
            }
            
            self.casters.append(caster_data)
            self._insert_caster_row(caster_data)
            added_count += 1
        
        # Save casters
        if added_count > 0:
            try:
                with open(CASTERS_FILENAME, "w", encoding="utf-8") as f:
                    json.dump(self.casters, f, indent=2, ensure_ascii=False)
                
                # Add to comboboxes
                for row in selected_rows:
                    mount_item = self.st_table.item(row, 0)
                    if mount_item:
                        mp_data = mount_item.data(Qt.ItemDataRole.UserRole)
                        if mp_data:
                            caster_name = f"{host}_{mp_data.get('mount', '')}"
                            self.msg_caster_combo.addItem(caster_name)
                            if hasattr(self, 'map_caster_combo'):
                                self.map_caster_combo.addItem(caster_name)
                            if hasattr(self, 'sat_caster_combo'):
                                self.sat_caster_combo.addItem(caster_name)
                
                QMessageBox.information(self, "Success", 
                    f"Added {added_count} mountpoint{'s' if added_count != 1 else ''} to Casters")
                logging.info(f"Added {added_count} mountpoints from sourcetable")
                
                # Switch to Casters tab to show new entries
                self.tabs.setCurrentIndex(0)
            except Exception as e:
                QMessageBox.critical(self, "Save Error", f"Failed to save casters:\n\n{e}")
                logging.exception("Failed to save casters after adding from sourcetable")

    # ---------- Detail Panel ----------
    def close_detail_panel(self):
        """Close the detail panel and clear selection"""
        if hasattr(self, 'detail_panel'):
            self.detail_panel.hide()
        self.selected_caster = None
        # Clear table selection
        if hasattr(self, 'caster_list'):
            self.caster_list.clearSelection()
    
    def close_message_detail_panel(self):
        """Close the message detail panel and clear selection"""
        if hasattr(self, 'msg_detail_panel'):
            self.msg_detail_panel.hide()
        self.selected_message = None
        if hasattr(self, 'msg_table'):
            self.msg_table.clearSelection()
    
    def on_message_selected(self, row, _col):
        """Handle message selection in Messages tab"""
        try:
            msg_type = self.msg_table.item(row, 0).text()
            
            # Toggle: if clicking the same message, close the panel
            if self.selected_message == msg_type and hasattr(self, 'msg_detail_panel') and self.msg_detail_panel.isVisible():
                self.close_message_detail_panel()
                return
            
            self.selected_message = msg_type
            self.update_message_detail_panel()
        except Exception as e:
            logging.exception("Error in on_message_selected")
    
    def update_message_detail_panel(self):
        """Update the message detail panel with information about selected message"""
        if not self.selected_message or not self.selected_caster:
            return
        
        if self.selected_caster not in self.rtcm_stats:
            return
        
        stats = self.rtcm_stats[self.selected_caster]
        if self.selected_message not in stats:
            return
        
        msg_info = stats[self.selected_message]
        
        # Show panel
        if hasattr(self, 'msg_detail_panel'):
            self.msg_detail_panel.show()
        
        # Update header
        self.msg_detail_header.setText(f"RTCM {self.selected_message}")
        
        # Get message description
        description = get_rtcm_description(self.selected_message)
        self.msg_detail_description.setText(description)
        
        # Calculate statistics
        count = msg_info["count"]
        last_time = msg_info["last"]
        
        # Calculate percentage
        total_messages = sum(info["count"] for info in stats.values())
        percentage = (count / total_messages * 100) if total_messages > 0 else 0
        
        # Update stats
        stats_text = f"""<b>Count:</b> {count:,}<br>
<b>Percentage:</b> {percentage:.1f}%<br>
<b>Last received:</b> {last_time}"""
        self.msg_detail_stats.setText(stats_text)
    
    def update_detail_panel(self):
        """Update detail panel with selected caster information"""
        try:
            if not self.selected_caster:
                self.detail_panel.hide()
                return
            
            self.detail_panel.show()
            
            # Find caster
            caster = next((c for c in self.casters if c.get("name") == self.selected_caster), None)
            if not caster:
                self.detail_panel.hide()
                return
            
            # Update header
            name = caster.get("name", "Unknown")
            host = caster.get("host", "")
            port = caster.get("port", "")
            mount = caster.get("mount", "")
            self.detail_header.setText(f"▶ {name}")
            self.detail_status.setText(f"📍 {host}:{port}/{mount}")
            
            # Get client info
            client = self.clients.get(self.selected_caster)
            if client and getattr(client, "running", False):
                # Get status
                status_item = None
                for r in range(self.caster_list.rowCount()):
                    if self.caster_list.item(r, 0).text() == self.selected_caster:
                        status_item = self.caster_list.item(r, 3)
                        break
                
                status_text = status_item.text() if status_item else "Unknown"
                
                # Get data rate from table (updated every second in update_ui)
                bps = 0
                for r in range(self.caster_list.rowCount()):
                    if self.caster_list.item(r, 0).text() == self.selected_caster:
                        bps_item = self.caster_list.item(r, 4)
                        if bps_item:
                            try:
                                bps = int(bps_item.text())
                            except ValueError:
                                bps = 0
                        break
                
                # Get total bytes
                total = getattr(client, "total_bytes", 0)
                
                # Get uptime
                start = self.start_times.get(self.selected_caster)
                uptime_str = "00:00:00"
                if start:
                    uptime = datetime.now() - start
                    uptime_str = self.format_timedelta(uptime)
                
                # Format total data
                total_mb = total / (1024 * 1024)
                
                stats_text = f"""Status: {status_text}
Uptime: {uptime_str}
Data Rate: {bps} B/s
Total Received: {total_mb:.2f} MB"""
                self.detail_stats.setText(stats_text)
            else:
                self.detail_stats.setText("Status: 🔴 Offline\nNo data available")
            
            # Update RTCM messages
            if self.selected_caster in self.rtcm_stats:
                rtcm_msgs = self.rtcm_stats[self.selected_caster]
                # Get all messages sorted by message number
                sorted_msgs = sorted(rtcm_msgs.items(), key=lambda x: str(x[0]))
                if sorted_msgs:
                    rtcm_text = ""
                    max_count = max(info["count"] for _, info in sorted_msgs)
                    for msg_type, info in sorted_msgs:
                        count = info["count"]
                        # Ensure at least 1 bar if count > 0
                        bar_length = max(1, int((count / max_count) * 8)) if max_count > 0 and count > 0 else 0
                        bar = "█" * bar_length
                        rtcm_text += f"{str(msg_type):<4} {count:>6}  {bar}\n"
                    self.detail_rtcm.setText(rtcm_text.strip())
                else:
                    self.detail_rtcm.setText("No messages yet")
            else:
                self.detail_rtcm.setText("No data")
            
            # Update satellites
            if self.selected_caster in self.satellite_stats:
                sat_data = self.satellite_stats[self.selected_caster]
                total_sats = sum(len(sats) for sats in sat_data.values())
                if total_sats > 0:
                    sat_text = f"🛰️ {total_sats} satellites tracked\n"
                    for const_name in ['GPS', 'Galileo', 'GLONASS', 'BeiDou', 'QZSS', 'SBAS']:
                        count = len(sat_data.get(const_name, set()))
                        if count > 0:
                            sat_text += f"   {const_name}: {count}   "
                    self.detail_satellites.setText(sat_text.strip())
                else:
                    self.detail_satellites.setText("🛰️ No satellites tracked")
            else:
                self.detail_satellites.setText("🛰️ No satellite data")
        except Exception:
            logging.debug("Error updating detail panel", exc_info=True)
    
    # ---------- Utils ----------
    def format_timedelta(self, td: timedelta):
        s = int(td.total_seconds())
        return f"{s // 3600:02}:{(s % 3600) // 60:02}:{s % 60:02}"

# ---------- Sourcetable Fetch Worker ----------
from PyQt6.QtCore import QObject, pyqtSignal

class SourcetableFetchWorker(QObject):
    """Properly implemented worker with Qt signals"""
    finished = pyqtSignal(list)
    error = pyqtSignal(str)
    
    def __init__(self, host, port, user, password):
        super().__init__()
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self._thread = None
    
    def start(self):
        """Start the worker in a separate thread"""
        self._thread = threading.Thread(target=self.run, daemon=True)
        self._thread.start()
    
    def run(self):
        """Run the sourcetable fetch operation"""
        try:
            mountpoints = self._fetch_sourcetable()
            self.finished.emit(mountpoints)
        except Exception as e:
            self.error.emit(str(e))
    
    def _fetch_sourcetable(self):
        """Fetch sourcetable from NTRIP caster"""
        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            sock.connect((self.host, self.port))
            
            auth = base64.b64encode(f"{self.user}:{self.password}".encode()).decode()
            request = f"GET / HTTP/1.1\r\nHost: {self.host}\r\nNtrip-Version: Ntrip/2.0\r\nUser-Agent: NTRIP NTRIPCheckerPro/5.2\r\nAuthorization: Basic {auth}\r\n\r\n"
            sock.sendall(request.encode())
            
            response = b""
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                response += chunk
                if len(response) > 1024 * 1024:  # 1MB limit
                    break
            
            response_str = response.decode('utf-8', errors='ignore')
            lines = response_str.split('\n')
            
            mountpoints = []
            for line in lines:
                line = line.strip()
                if not line or line.startswith('STR;'):
                    parts = line.split(';')
                    if len(parts) < 10:
                        continue
                    try:
                        mp = {
                            'mount': parts[1],
                            'name': parts[2],
                            'format': parts[3],
                            'carrier': parts[5] if len(parts) > 5 else '',
                            'nav_systems': parts[6] if len(parts) > 6 else '',
                            'lat': float(parts[9]) if parts[9] and parts[9] != '0' else None,
                            'lon': float(parts[10]) if parts[10] and parts[10] != '0' else None,
                            'alt': None
                        }
                        mountpoints.append(mp)
                    except (ValueError, IndexError):
                        continue
            
            return mountpoints
        finally:
            if sock:
                try:
                    sock.close()
                except Exception:
                    pass

# ---------- Run ----------
if __name__ == "__main__":
    # configure basic logging (console) and a rotating file handler
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    try:
        log_file = os.path.join(os.path.dirname(__file__), "ntrip_checker.log")
        fh = RotatingFileHandler(log_file, maxBytes=5 * 1024 * 1024, backupCount=3)
        fh.setLevel(logging.INFO)
        fh.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
        logging.getLogger().addHandler(fh)
    except Exception:
        logging.exception("Failed to set up RotatingFileHandler for logging")
    
    # Custom exception hook to catch PyQt errors
    def exception_hook(exctype, value, tb):
        print(f"\n{'='*80}")
        print(f"UNHANDLED EXCEPTION: {exctype.__name__}: {value}")
        print(f"{'='*80}")
        import traceback
        traceback.print_exception(exctype, value, tb)
        print(f"{'='*80}\n")
        logging.exception("Unhandled exception", exc_info=(exctype, value, tb))
    
    sys.excepthook = exception_hook
    
    app = QApplication(sys.argv)
    apply_stylesheet(app, theme='dark_teal.xml')
    app.setStyleSheet("""
    /* General UI sizing */
    QWidget { font-size: 12px; background: #16181a; color: #e6eef3; }
    /* Tab bar and tabs - dark background with clear selected state */
    QTabWidget::pane { border-top: 1px solid #2b2b2b; background: #16181a; }
    QTabBar { background: #2b2f33; }
    QTabBar::tab { height: 36px; padding: 8px 14px; font-size:14px; font-weight:600; color: #cfd8dc; background: #2b2f33; border: 1px solid #3a3f44; border-bottom: none; border-top-left-radius:6px; border-top-right-radius:6px; }
    QTabBar::tab:selected { background: #3a6ea5; color: #ffffff; }
    QTabBar::tab:!selected { color: #bfc6cc; }
    QTabBar::tab:hover { background: #344044; }

    QHeaderView::section { font-size: 12px; background: #2c2f33; color: #ffffff; padding: 6px; }
    QTableWidget { background: #141618; alternate-background-color: #1b1f22; gridline-color: #222426; }
    QTableWidget::item { padding: 4px; }
    QTableView::item:selected { background: #3a6ea5; color: white; }
    QPushButton { font-size: 11px; padding: 6px 10px; border-radius: 6px; }
    QPushButton:hover { background: rgba(255,255,255,0.02); }
    QPushButton:pressed { background: rgba(255,255,255,0.04); }
    QComboBox { min-height: 26px; color: #e6eef3; }
    QLineEdit { color: #e6eef3; }
    QLabel { color: #e6eef3; }
    """)
    try:
        win = NTRIPCheckerPro()
        # ensure clients are stopped on application exit
        app.aboutToQuit.connect(win.cleanup)
        win.show()
        sys.exit(app.exec())
    except Exception as e:
        print(f"\n{'='*80}")
        print(f"FATAL ERROR: {e}")
        print(f"{'='*80}\n")
        import traceback
        traceback.print_exc()
        input("Press Enter to exit...")
