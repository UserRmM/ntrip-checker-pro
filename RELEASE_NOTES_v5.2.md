# NTRIP Checker PRO v5.2 Release Notes

**Release Date:** December 18, 2025

## Overview

Version 5.2 brings significant enhancements to the interactive mapping system with real-time popup updates, RTK coverage visualization, and intelligent auto-zoom functionality. This release focuses on providing better situational awareness for GNSS reference station operators.

## 🎯 Key Features

### 1. Real-Time Map Popups
Map markers now display live-updating information without closing the popup:
- **Status Updates** — Connection status refreshes every second (green=connected, red=disconnected)
- **Uptime Tracking** — Live uptime counter showing session duration
- **Data Rate** — Real-time bytes per second display with accurate calculation
- **Satellite Info** — Dynamic satellite count with constellation breakdown (GPS, GLONASS, Galileo, BeiDou, QZSS, SBAS)
- **RTCM Messages** — Live list of detected message types

**Technical Implementation:**
- JavaScript `updatePopup()` function called every second from Python
- Separate `map_last_bytes` tracking dictionary prevents interference with main UI
- Popup stays open during updates for continuous monitoring
- All data fields update independently without full popup refresh

### 2. RTK Coverage Visualization
Visual representation of effective RTK correction range:
- **20 km Coverage Circles** — Semi-transparent circles around each station
- **Status-Colored Areas** — Green for connected, red for disconnected stations
- **Coverage Legend** — Fixed position legend (bottom-right) showing radius
- **Real-Time Updates** — Circle color changes with station connection status

**Why 20 km?**
This radius represents the practical effective range for RTK corrections, where accuracy remains within 1-2 cm horizontal and 2-3 cm vertical precision.

### 3. Intelligent Map Zoom
Automatic viewport adjustment based on station distribution:
- **Multiple Stations** — Uses Leaflet's `fitBounds()` to show all stations with 50px padding
- **Single Station** — Fixed zoom level (10) for optimal detail
- **"All stations" View** — Automatically calculates bounds from all station coordinates
- **Individual Station** — Centers on selected station with appropriate zoom

## 🔧 Technical Improvements

### Data Rate Calculation Fix
**Problem:** Map popups showed data rate as 0 B/s even when data was flowing.

**Root Cause:** The `update_map_popups()` function calculated `bps = total - last` but never updated the `last` tracking variable, causing every calculation to use stale data.

**Solution:** Implemented separate `map_last_bytes` dictionary independent from main UI tracking:
```python
if not hasattr(self, 'map_last_bytes'):
    self.map_last_bytes = {}
total = getattr(client, "total_bytes", 0)
last = self.map_last_bytes.get(caster_name, total)
bps = total - last
self.map_last_bytes[caster_name] = total  # Update for next calculation
```

### Satellite Section Updates
**Problem:** Satellite information in popups added new lines instead of replacing existing content.

**Fix:** Updated regex to use dotall flag `/s` and proper lookahead:
```javascript
var satRegex = /<hr[^>]*><b>🛰️ Satellites:<\/b> \d+.*?<br>(?=<hr|<\/div>)/s;
```

### Unicode Rendering
**Problem:** Dynamic emoji updates caused question marks to appear in popups.

**Fix:** Removed emoji icon updates from JavaScript, keeping emojis static in original HTML while only updating text and color values.

## 📋 Full Changelog

### Added
- Real-time popup updates for map markers (status, uptime, data rate, satellites, RTCM)
- 20 km RTK coverage circles with status-colored visualization
- Coverage radius legend showing effective range
- Intelligent auto-zoom with fitBounds() for multiple stations
- Separate data rate tracking for map popups
- Enhanced map info label explaining coverage circles

### Changed
- Map zoom behavior from fixed level to dynamic bounds calculation
- Coverage radius finalized at 20 km (changed from initial 25 km)
- Popup updates now handle multiline content properly

### Fixed
- Data rate calculation in map popups (separate tracking dictionary)
- Satellite section regex matching (dotall flag for multiline content)
- Unicode emoji rendering in JavaScript updates (static emojis only)
- Map viewport not showing all stations in "All stations" view

## 🚀 Installation

### Requirements
- Python 3.8+
- PyQt6
- PyQt6-WebEngine
- pyrtcm

### Install Dependencies
```bash
pip install -r requirements.txt
```

### Run Application
```bash
python ntrip_checker_pro_v5_2.py
```

## 📊 Usage Tips

### Map Tab
- **Click Markers** — Open popup with detailed real-time information
- **Leave Popup Open** — Watch live updates every second
- **Coverage Circles** — Visualize RTK correction range (20 km radius)
- **Station Selector** — Choose specific station or "All stations" to see full network

### Real-Time Monitoring
- **Status Color** — Green text = connected, Red text = disconnected
- **Uptime** — Shows session duration in HH:MM:SS format
- **Data Rate** — Displays bytes per second (B/s) with live updates
- **Satellites** — Count and constellation breakdown update dynamically
- **RTCM Messages** — List of detected message types refreshes automatically

### Coverage Visualization
- **Green Circles** — Connected stations with active RTK corrections
- **Red Circles** — Disconnected or inactive stations
- **Legend** — Bottom-right corner shows radius value
- **Overlap Areas** — Multiple coverage circles show network redundancy

## 🔄 Upgrading from v5.1

Version 5.2 is fully backward compatible with v5.1:
- Existing `casters.json` configuration works without changes
- All v5.1 features remain functional
- New map features activate automatically
- No configuration changes required

## 📖 Documentation

- **README.md** — Installation and usage guide
- **CHANGELOG.md** — Complete version history
- **INSTALL.md** — Detailed installation instructions

## 🔗 Related Releases

- [v5.1 Release Notes](RELEASE_NOTES_v5.1.md) — Sourcetable Browser
- [v5.0 Release Notes](RELEASE_NOTES_v5.0.md) — Initial release with mapping

## 🙏 Acknowledgments

This release includes significant improvements based on real-world usage feedback, particularly in:
- Real-time data visualization
- RTK coverage planning
- Multi-station network monitoring
- Operational situational awareness

---

**NTRIP Checker PRO** — Professional GNSS reference station monitoring  
Copyright © 2025 | Licensed under MIT
