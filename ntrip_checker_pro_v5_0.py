# ntrip_checker_pro_v5_0_fixed.py
import sys, io, base64, socket, threading, json, os, time, logging
from logging.handlers import RotatingFileHandler
from datetime import datetime, timedelta
from functools import partial
from pyrtcm import RTCMReader
from html import escape
from PyQt6.QtWidgets import (
    QApplication, QWidget, QTabWidget, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QMessageBox, QPushButton, QHeaderView, QDialog, QFormLayout,
    QLineEdit, QSpinBox, QHBoxLayout, QSizePolicy, QComboBox
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtGui import QColor
from qt_material import apply_stylesheet

CASTERS_FILENAME = "casters.json"

# Color palette for RTCM message types
def get_color_for_msg_type(msg_type):
    """Generate a consistent color for an RTCM message type."""
    # simple hash-based color generation
    hash_val = hash(str(msg_type)) % 360  # hue 0-360
    # brighter, saturated palette
    colors = [
        "#E41A1C", "#377EB8", "#4DAF4A", "#984EA3", "#FF7F00",
        "#FFFF33", "#A65628", "#F781BF", "#999999", "#66C2A5",
        "#FC8D62", "#8DA0CB", "#E78AC3", "#A6D854", "#FFD92F",
        "#1F78B4", "#B2DF8A", "#33A02C", "#FB9A99", "#CAB2D6"
    ]
    return colors[hash(msg_type) % len(colors)]

CASTERS_FILENAME = "casters.json"

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
                logging.exception("NTRIPClient error for %s", self.caster.get('name'))
                
                # Determine error type for user feedback
                error_msg = str(e).lower()
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
        self.setWindowTitle("NTRIP Checker PRO v5.0")
        self.resize(1200, 800)

        self.casters = []
        self.clients = {}
        self.start_times = {}
        self.last_bytes = {}
        # Removed auto-refresh counter - user has full control
        self.selected_caster = None
        self.rtcm_stats = {}

        self.signals = NTRIPSignals()
        self.signals.status_signal.connect(self.on_status)
        self.signals.data_signal.connect(self.on_data)
        self.signals.disconnect_signal.connect(self.on_disconnect)

        self.load_casters()
        self.init_ui()
        self.init_timers()
        self.auto_connect_all()

    # ---------- Load ----------
    def load_casters(self):
        if not os.path.exists(CASTERS_FILENAME):
            with open(CASTERS_FILENAME, "w", encoding="utf-8") as f:
                json.dump([], f)
        try:
            with open(CASTERS_FILENAME, "r", encoding="utf-8") as f:
                self.casters = json.load(f)
        except Exception:
            logging.exception("Failed loading casters.json")
            self.casters = []

    # ---------- UI ----------
    def init_ui(self):
        self.tabs = QTabWidget()
        self.tabs.currentChanged.connect(self.on_tab_changed)
        layout = QVBoxLayout()
        layout.addWidget(self.tabs)
        self.setLayout(layout)

        # Casters tab
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
        self.tabs.addTab(self.caster_list, "Casters")
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
        self.msg_tab.setLayout(self.msg_layout)
        # header with station label and caster selector
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
        self.msg_table = QTableWidget()
               # 3 columns: type, last time, count
        self.msg_table.setColumnCount(3)
        self.msg_table.setHorizontalHeaderLabels(["RTCM Message", "Last Time Received", "Counter"])
        self.msg_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.msg_table.setStyleSheet("QTableWidget { color: #ffffff; }")
        self.msg_table.setAlternatingRowColors(True)
        try:
            self.msg_table.setSelectionBehavior(self.msg_table.SelectionBehavior.SelectRows)
            self.msg_table.setSelectionMode(self.msg_table.SelectionMode.SingleSelection)
        except Exception:
            pass
        self.msg_table.verticalHeader().setVisible(False)
        self.msg_layout.addWidget(self.msg_table)
        self.msg_total_label = QLabel("Total messages: 0")
        self.msg_total_label.setStyleSheet("color: #ffffff;")
        self.msg_layout.addWidget(self.msg_total_label)
        self.tabs.addTab(self.msg_tab, "Messages")
        
        # pie chart view for messages
        self.msg_chart_view = QWebEngineView()
        self.msg_chart_view.setMinimumHeight(350)
        self.msg_layout.insertWidget(2, self.msg_chart_view)  # insert before table

        # Map tab
        self.map_tab = QWidget()
        self.map_layout = QVBoxLayout()
        self.map_tab.setLayout(self.map_layout)
        self.map_info = QLabel("Station: (none)")
        # larger, clearer header for the map tab
        self.map_info.setStyleSheet("color: #ffffff; font-weight: bold; font-size:16px; margin:8px;")
        self.map_info.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        # header layout with station label + combobox
        map_header = QHBoxLayout()
        map_header.addWidget(self.map_info)
        self.map_caster_combo = QComboBox()
        self.map_caster_combo.setStyleSheet("color: #e6eef3; min-width:160px; margin-right:8px;")
        self.map_caster_combo.addItem("(none)")
        self.map_caster_combo.currentTextChanged.connect(self.on_map_caster_changed)
        map_header.addWidget(self.map_caster_combo)
        map_header.addStretch()
        self.map_layout.addLayout(map_header)
        self.map_view = QWebEngineView()
        # ensure the map view expands to fill available space
        self.map_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.map_view.setMinimumHeight(320)
        # add with stretch so map gets most space in the layout
        self.map_layout.addWidget(self.map_view, 1)
        self.tabs.addTab(self.map_tab, "Map")

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
    def update_map_view(self):
        if not self.selected_caster:
            self.map_info.setText("Station: (none)")
            self.map_view.setHtml("<h3 style='color:#ffffff;margin:1rem;'>No caster selected.</h3>")
            return
        caster = next((c for c in self.casters if c.get("name") == self.selected_caster), None)
        if not caster:
            self.map_info.setText("Station: (none)")
            self.map_view.setHtml("<h3 style='color:#ffffff;margin:1rem;'>No caster selected.</h3>")
            return
        lat, lon, alt = caster.get("lat"), caster.get("lon"), caster.get("alt")
        self.map_info.setText(f"Station: {caster['name']}")
        if lat is None or lon is None:
            self.map_view.setHtml(f"<h3 style='color:#ffffff;margin:1rem;'>No location data for caster '{escape(caster['name'])}'.</h3>")
            return
        name_esc = escape(caster['name'])
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8"/>
            <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
            <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
            <style>
                html,body,#map{{height:100%;margin:0;}}
                .leaflet-popup-content, .leaflet-popup-content-wrapper {{
                    color: #ffffff !important;
                    background: #ffffff !important;
                }}
            </style>
        </head>
        <body>
        <div id="map"></div>
        <script>
        var map = L.map('map').setView([{lat}, {lon}], 13);
        L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
            maxZoom: 19,
            attribution: '&copy; OpenStreetMap contributors'
        }}).addTo(map);
                L.marker([{lat}, {lon}]).addTo(map)
                    .bindPopup(
                        "<div style='background:#ffffff;padding:6px;font-family:Arial,sans-serif;'>"
                        + "<div style='font-weight:bold;color:#000000 !important;margin-bottom:4px;'>{name_esc}</div>"
                        + "<div style='color:#000000 !important;'>Lat: {lat}</div>"
                        + "<div style='color:#000000 !important;'>Lon: {lon}</div>"
                        + "<div style='color:#000000 !important;'>Alt: {(alt if alt is not None else '-') } m</div>"
                        + "</div>"
                    )
          .openPopup();
        </script>
        </body>
        </html>
        """
        self.map_view.setHtml(html)

    def on_tab_changed(self, index):
        if self.tabs.tabText(index) == "Map":
            self.update_map_view()

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
            try:
                # add to map combobox if available
                if hasattr(self, 'map_caster_combo'):
                    self.map_caster_combo.addItem(c.get("name", ""))
            except Exception:
                logging.debug("Failed adding caster to map combobox", exc_info=True)

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
            with open(CASTERS_FILENAME, "w", encoding="utf-8") as f:
                json.dump(self.casters, f, indent=2, ensure_ascii=False)
            self._insert_caster_row(data)
            self.start_connection(data)
            # add to messages combobox
            self.msg_caster_combo.addItem(data.get("name", ""))
            # add to map combobox as well
            try:
                if hasattr(self, 'map_caster_combo'):
                    self.map_caster_combo.addItem(data.get("name", ""))
            except Exception:
                logging.debug("Failed to add new caster to map combobox", exc_info=True)

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
        with open(CASTERS_FILENAME, "w", encoding="utf-8") as f:
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
        # remove from messages combobox
        idx = self.msg_caster_combo.findText(name)
        if idx >= 0:
            self.msg_caster_combo.removeItem(idx)
        # remove from map combobox
        try:
            if hasattr(self, 'map_caster_combo'):
                idx2 = self.map_caster_combo.findText(name)
                if idx2 >= 0:
                    self.map_caster_combo.removeItem(idx2)
        except Exception:
            logging.debug("Failed removing caster from map combobox", exc_info=True)

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
                with open(CASTERS_FILENAME, "w", encoding="utf-8") as f:
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
                if caster_name not in self.rtcm_stats:
                    self.rtcm_stats[caster_name] = {}
                caster_msgs = self.rtcm_stats[caster_name]
                if msg_type not in caster_msgs:
                    caster_msgs[msg_type] = {"count": 0, "last": now}
                caster_msgs[msg_type]["count"] += 1
                caster_msgs[msg_type]["last"] = now
            # remove consumed bytes from client's buffer
            consumed = stream.tell()
            if consumed:
                with client.lock:
                    client.buffer = client.buffer[consumed:]
            if caster_name == self.selected_caster:
                self.update_messages_view()
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

    # ---------- Messages ----------
    def on_caster_selected(self, row, _col):
        self.selected_caster = self.caster_list.item(row, 0).text()
        self.tabs.setCurrentWidget(self.msg_tab)
        # update comboboxes to match selected caster
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
        self.update_messages_view()

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
            msg_type_item.setForeground(QColor("white"))
            self.msg_table.setItem(row, 0, msg_type_item)
            self.msg_table.setItem(row, 1, QTableWidgetItem(info["last"]))
            self.msg_table.setItem(row, 2, QTableWidgetItem(str(info["count"])))
            total += info["count"]
        self.msg_total_label.setText(f"Total messages: {total}")
        # update pie chart
        svg = self.generate_pie_chart_svg(caster)
        html = f"<html><body style='background:#f0f0f0;margin:0;padding:10px;'>{svg}</body></html>"
        self.msg_chart_view.setHtml(html)

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
            self.update_map_view()
        else:
            self.selected_caster = None
            self.map_view.setHtml("<h3 style='color:#ffffff;margin:1rem;'>No caster selected.</h3>")

    def generate_pie_chart_svg(self, caster):
        """Generate SVG donut chart for RTCM message types."""
        if not caster or caster not in self.rtcm_stats or not self.rtcm_stats[caster]:
            return "<svg></svg>"
        
        import math
        stats = self.rtcm_stats[caster]
        total = sum(info["count"] for info in stats.values())
        if total == 0:
            return "<svg></svg>"
        
        # SVG setup
        size = 300
        cx, cy = size / 2, size / 2
        outer_r = 100
        inner_r = 60
        
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
            slices.append(f'<path d="{path}" fill="{color}" stroke="white" stroke-width="2"/>')
            
            angle_start = angle_end
        
        svg = f"""
        <svg width="{size}" height="{size}" viewBox="0 0 {size} {size}" xmlns="http://www.w3.org/2000/svg">
            <style>
                text {{ font-family: Arial, sans-serif; font-size: 14px; fill: white; text-anchor: middle; }}
            </style>
            {''.join(slices)}
            <text x="{cx:.0f}" y="{cy-10:.0f}" font-weight="bold">Total</text>
            <text x="{cx:.0f}" y="{cy+15:.0f}" font-size="20px" font-weight="bold">{total}</text>
        </svg>
        """
        return svg

    # ---------- Utils ----------
    def format_timedelta(self, td: timedelta):
        s = int(td.total_seconds())
        return f"{s // 3600:02}:{(s % 3600) // 60:02}:{s % 60:02}"

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
    win = NTRIPCheckerPro()
    # ensure clients are stopped on application exit
    app.aboutToQuit.connect(win.cleanup)
    win.show()
    sys.exit(app.exec())
