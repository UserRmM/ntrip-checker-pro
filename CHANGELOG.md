# Changelog

All notable changes to NTRIP Checker PRO are documented in this file.

## [5.0] — December 2024

### Added
- **Map Tab** with interactive Leaflet map and caster location markers
- **Messages Tab** with RTCM message statistics and pie chart visualization
- **Station Selector** comboboxes on both Messages and Map tabs with cross-tab synchronization
- **Edit Caster** functionality — modify existing caster configurations
- **Delete Caster** with confirmation dialog
- **Rotating File Logger** — logs up to 5 MB per file, keeps 3 backups
- **Threading Safety** — per-caster buffer with locks, safe RTCM parsing in main thread
- **Color-Coded Messages** — bright palette for RTCM message type visualization
- **Enhanced UI** — dark theme, improved typography, better contrast

### Changed
- **Dark Theme** — dark_teal.xml with custom stylesheet overrides for readability
- **Tab Headers** — larger, bold font (14px, weight 600)
- **Text Colors** — all text set to light (#ffffff or #e6eef3) for dark background compatibility
- **Caster Table Layout** — optimized column widths (Mount fixed, B/s fixed, Actions wide)
- **Row Height** — increased to 40px for better spacing and visibility
- **Reconnection Logic** — replaced `time.sleep()` with `threading.Event.wait()` for responsive stop
- **Status Messages** — all status strings now in English
- **RTCM Parsing** — moved from worker thread to GUI thread using per-caster buffer snapshots

### Fixed
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
