# NTRIP Checker PRO v5.3 Release Notes

**Release Date:** December 19, 2025  
**Status:** Development Branch

---

## 🎉 Major Features

### 1. Desktop Alerts & Notifications
Professional desktop notification system for 24/7 monitoring:

- **System Tray Icon** — Minimize to tray with context menu (Show/Hide/Quit)
- **4 Alert Types:**
  - ⚠️ **Connection Lost** — Immediate notification when mount point disconnects
  - ✓ **Connection Restored** — Notify when connection is re-established
  - ⚠️ **Low Data Rate** — Alert when data flow drops below threshold (30-second buffer)
  - ⚠️ **Low Satellites** — Alert when satellite count is insufficient
- **Smart Throttling** — 5-minute cooldown prevents alert spam
- **Configurable Settings** — File → Preferences dialog with 9 customizable options
- **Settings Persistence** — Preferences saved to `settings.json`

**Alert Behavior:**
- 15-second startup delay (no false positives on launch)
- 30-second buffer for low data rate (ignores temporary fluctuations)
- Cooldown system prevents duplicate alerts
- Proper cleanup on application close (no ghost notifications)

### 2. CSV Export System
Export monitoring data for external analysis:

- **File → Export Menu** with 5 options:
  - **Export Casters** — Name, host, status, uptime, data rate, coordinates
  - **Export Messages** — RTCM message types with descriptions and percentages
  - **Export Satellites** — Constellation counts with percentages
  - **Export Map Data** — Location data with connection status
  - **Export All Data** — All above exports to timestamped directory
- **UTF-8 Encoding** — Excel-compatible CSV files
- **Timestamps** — Every export includes date/time for tracking

### 3. Enhanced Connection Logic
Intelligent reconnection and idle detection:

- **Idle Timeout Detection** — Automatically detects when mount point stops sending data (10 seconds)
- **"Connected but no data" Status** — Clear indication of mount point issues (5-second warning)
- **Smart Reconnect Logic:**
  - Network errors: Reconnect 3 times (10-second intervals)
  - Idle timeout: NO reconnect (mount point issue, not network)
  - Mount point disconnected: NO reconnect (server-side closure)
  - Authentication errors: NO reconnect (credentials won't fix themselves)
- **Uptime Accuracy** — Pauses when no data flows, resets on disconnect
- **Proper Shutdown** — All threads terminate cleanly on application close

---

## 🔧 Technical Improvements

### Connection Management
- **Data Rate Calculation Fix** — Fixed critical bug where alerts always saw 0 B/s
- **Reconnect Attempt Tracking** — Only resets when data actually flows (not on TCP handshake)
- **Thread-Safe Shutdown** — Properly stops all client threads on exit
- **State Tracking** — Accurate connection status monitoring for alerts

### User Interface
- **Preferences Dialog** — Modern settings UI with grouped options
- **System Tray Integration** — Double-click to show/hide window
- **Menu Organization** — File → Export submenu, File → Preferences

### Alert System
- **False Positive Prevention:**
  - 15-second startup delay
  - First measurement initialization (no "restored" on startup)
  - 30-second data rate buffer
  - Connection status tracking (None vs False vs True)
- **Proper Throttling:**
  - Per-caster, per-alert-type cooldown
  - Flag system prevents duplicate alerts during low data periods

---

## 📝 Configuration Files

### New: settings.json
```json
{
  "alerts_enabled": true,
  "alert_connection_lost": true,
  "alert_connection_restored": true,
  "alert_low_data_rate": true,
  "alert_low_satellites": true,
  "low_data_rate_threshold": 100,
  "low_satellites_threshold": 4,
  "alert_cooldown_minutes": 5,
  "show_tray_icon": true
}
```

**Location:** Same directory as `ntrip_checker_pro_v5_2.py`  
**Auto-created:** On first launch with default values  
**User-editable:** Via File → Preferences or direct JSON editing

---

## 🐛 Bug Fixes

1. **Data Rate Alert Bug** — Fixed calculation that always showed 0 B/s in alerts
2. **Reconnect Loop** — Fixed infinite reconnect for mount point issues
3. **False Positive Alerts** — Fixed "Connection restored" on startup
4. **False Positive Alerts** — Fixed "Low data rate" on first measurement
5. **Ghost Notifications** — Fixed alerts continuing after app close
6. **Uptime Glitch** — Fixed uptime continuing when no data flows
7. **Satellite Count TypeError** — Fixed `sum()` of sets in satellite statistics

---

## ⚙️ Usage

### Enabling Desktop Alerts
1. **File → Preferences**
2. Check **"Enable desktop notifications"**
3. Select desired alert types
4. Adjust thresholds:
   - Low data rate: 10-1000 B/s (default: 100)
   - Low satellites: 1-20 (default: 4)
   - Cooldown: 1-60 minutes (default: 5)
5. Click **Save**

### System Tray
- **Double-click icon** — Show/hide window
- **Right-click icon** — Context menu
- **Hide tray icon** — File → Preferences → uncheck "Show tray icon"

### CSV Export
1. **File → Export → [Choose type]**
2. Select save location
3. Open in Excel, LibreOffice, or any CSV viewer

---

## 🔮 Planned for v5.4

**Auto-Reconnect Feature:**
- Optional background reconnection for mount point issues
- Configurable retry interval (1-60 minutes)
- Max attempts limit (1-100)
- User preference in Settings dialog

**Connection Statistics:**
- Reconnection count per caster
- Total downtime tracking
- Connection quality score (0-100%)
- Display in detail panel and CSV exports

---

## 📦 Installation

**Existing Users (v5.2 → v5.3):**
```bash
git checkout development
git pull
```

**New Users:**
See [INSTALL.md](INSTALL.md) for full installation instructions.

**Dependencies:** No changes from v5.2

---

## 🙏 Feedback

Report issues or suggest features:  
**GitHub:** https://github.com/UserRmM/ntrip-checker-pro/issues

---

**Full Changelog:** See [CHANGELOG.md](CHANGELOG.md)  
**Previous Release:** [v5.2](RELEASE_NOTES_v5.2.md)
