# Changelog

All notable changes to NTRIP Checker PRO are documented in this file.

## [5.1] — December 2024

### Added
- **Sourcetable Browser Tab** — Automatically fetch mountpoint lists from NTRIP casters
  - Direct HTTP connection to caster sourcetable (GET / request)
  - Parse and display all available mountpoints with details
  - Table columns: Mountpoint, Description, Format, Location (Lat/Lon), Systems, Carrier
  - Real-time search/filter functionality across all fields
  - Multi-select mountpoints and add to Casters with one click
  - Automatic coordinate extraction from STR lines
  - Auto-generated caster names (host_mountpoint format)
  - Duplicate prevention when adding mountpoints
  - Threading for non-blocking fetch operations
  - Comprehensive error handling (auth failures, timeouts, connection errors)
  - Automatically adds mountpoints to all tab comboboxes (Messages, Map, Satellites)
  - Switches to Casters tab after successful addition

### Changed
- **Tab Order** — Added Sourcetable as 5th tab: Casters → Messages → Satellites → Map → Sourcetable
- **Caster Addition** — Now possible to add mountpoints from sourcetable in addition to manual entry

### Fixed
- **Sourcetable Parsing** — Robust STR line parsing with error tolerance for malformed entries

## [5.0] — December 2024

### Added
- **Satellites Tab** with real-time GNSS constellation tracking
  - Live satellite counting per constellation (GPS, GLONASS, Galileo, BeiDou, QZSS, SBAS)
  - Interactive donut chart showing satellite distribution
  - Color-coded constellation cards matching satellite chart
  - Clear and Debug functions for troubleshooting
  - MSM message parsing (1071-1127) with PRN extraction
- **Map Tab** with interactive Leaflet map and caster location markers
- **Messages Tab** with RTCM message statistics and pie chart visualization
- **Station Selector** comboboxes on all tabs (Messages, Map, Satellites) with cross-tab synchronization
- **Edit Caster** functionality — modify existing caster configurations
- **Delete Caster** with confirmation dialog
- **Connect All** button — manually trigger connection to all disconnected casters
- **User-Controlled Disconnect** — stop reconnection attempts after manual disconnect
- **Rotating File Logger** — logs up to 5 MB per file, keeps 3 backups
- **Threading Safety** — per-caster buffer with locks, safe RTCM parsing in main thread
- **MSM Constellation Color-Coding** — Messages tab shows constellation-specific colors for MSM messages (1071-1127)
- **Enhanced UI** — dark theme, improved typography, better contrast

### Changed
- **Tab Layout** — Messages and Satellites tabs now use side-by-side layout (chart left, data right)
- **Chart Styling** — Unified dark background (#1e1e1e) and consistent sizing (400x400) for all donut charts
- **Tab Order** — Reordered to: Casters → Messages → Satellites → Map
- **Error Messages** — More descriptive connection errors (Authentication failed, Connection timeout, etc.)
- **Color Palette** — Constellation colors unified across Messages MSM display and Satellites cards
- **Dark Theme** — dark_teal.xml with custom stylesheet overrides for readability
- **Tab Headers** — larger, bold font (14px, weight 600)
- **Text Colors** — all text set to light (#ffffff or #e6eef3) for dark background compatibility
- **Caster Table Layout** — optimized column widths (Mount fixed, B/s fixed, Actions wide)
- **Row Height** — increased to 40px for better spacing and visibility
- **Reconnection Logic** — replaced `time.sleep()` with `threading.Event.wait()` for responsive stop
- **Status Messages** — all status strings now in English
- **RTCM Parsing** — moved from worker thread to GUI thread using per-caster buffer snapshots
- **BeiDou Parsing** — Fixed to handle MSM messages 1121-1127 (not just "10XX" prefix)

### Fixed
- **BeiDou Satellites** — Now correctly parsing MSM messages 1121-1127 (previously showed 0)
- **Socket Errors on Shutdown** — Suppressed WinError 10038 during graceful shutdown
- **Window Jumping** — Fixed layout flash when switching to Satellites/Map tabs
- **PyQt Silent Crashes** — Added custom exception hook to display PyQt errors
- **IndentationError** in `update_map_view()` method
- **Color Contrast** — fixed white-on-white popup text (now black on white background)
- **Tab Visibility** — ensured tab text is visible on dark theme
- **Modal Dialog Colors** — QLineEdit, QComboBox text forced to light colors
- **Bare Exceptions** — replaced all bare `except:` with typed `except Exception:`

### Security
- HTML escaping for caster names in map popups (prevents injection)
- Sensitive data (casters.json) recommended for .gitignore

### Tech Details
- **Threading**: Daemon threads per caster with `threading.Event` and `threading.Lock`
- **Signaling**: Qt signals for thread-safe GUI updates
- **Logging**: basicConfig + RotatingFileHandler (console + file, 5MB/file, 3 backups)
- **RTCM**: Buffered, consumed-byte removal after parsing
- **SVG**: Inline SVG donut chart generation (no heavy dependencies)

---

## [4.0] — Previous Release

(Earlier version history not included in this document)

---

## Notes

- This version introduces significant architectural changes (threading, buffering, logging)
- Full backward compatibility with caster.json format maintained
- All UI strings translated to English for international audience

---

## Future Roadmap

- [ ] Configuration profiles (save/load setups)
- [ ] Data export (CSV, JSON)
- [ ] Web dashboard (Flask)
- [ ] Alert system (connection loss, anomalies)
- [ ] Advanced filtering & search in Messages tab
- [ ] Performance optimizations for high-frequency streams

---

**Version**: 5.0  
**Release Date**: December 2024  
**Python**: 3.8+  
**License**: MIT
