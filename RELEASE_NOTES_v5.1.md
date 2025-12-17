# NTRIP Checker PRO v5.1

**Release Date:** December 17, 2024

## 🎉 What's New

### Sourcetable Browser Tab

v5.1 introduces the **Sourcetable Browser** - a powerful new feature that automatically discovers and imports mountpoints from any NTRIP caster.

**Key Features:**
- 🔍 **Auto-Discovery** - Fetch complete mountpoint lists directly from NTRIP casters
- 📊 **Rich Details** - View mountpoint name, description, format, location, supported systems, and carrier
- 🌍 **Automatic Coordinates** - GPS coordinates extracted automatically from sourcetable
- 🔎 **Real-Time Search** - Filter mountpoints by any field (name, location, systems, etc.)
- ✅ **Multi-Select Add** - Select multiple mountpoints and add them all at once
- 🚫 **Duplicate Prevention** - Automatically prevents adding the same mountpoint twice
- ⚡ **Non-Blocking** - Threaded fetch operations keep UI responsive
- 🔒 **Error Handling** - Comprehensive handling for auth failures, timeouts, and connection errors

**How to Use:**
1. Open the **Sourcetable** tab
2. Enter caster host, port, username, and password
3. Click **Fetch Mountpoints**
4. Browse the list, use search to filter
5. Select one or more mountpoints
6. Click **Add Selected to Casters**
7. Mountpoints automatically appear in Casters tab with coordinates

This eliminates the need to manually enter mountpoint details and coordinates - just browse and add!

## 📋 Full Changelog

### Added
- **Sourcetable Browser Tab** for automatic mountpoint discovery
- Direct HTTP sourcetable fetching (GET / request with NTRIP authentication)
- STR line parsing with robust error handling
- 6-column table: Mountpoint, Description, Format, Location, Systems, Carrier
- Real-time search/filter across all table columns
- Multi-select mountpoint addition to Casters
- Automatic coordinate extraction from sourcetable
- Auto-generated caster names in `host_mountpoint` format
- Duplicate detection when adding mountpoints
- Threading for non-blocking network operations
- Integration with Messages, Map, and Satellites tab comboboxes

### Changed
- **Tab Order** - Added Sourcetable as 5th tab: Casters → Messages → Satellites → Map → Sourcetable
- **Caster Addition Workflow** - Two methods now available: manual entry or sourcetable browser

### Fixed
- Robust STR line parsing with tolerance for malformed entries

## 🔧 Technical Details

**Sourcetable Protocol:**
- HTTP GET request to caster root path (`/`)
- Basic authentication with user credentials
- Parses STR (stream) lines in format: `STR;mount;identifier;format;details;carrier;navSystem;network;country;lat;lon;...`
- 10-second timeout with connection error handling
- 1MB response size limit for safety

**Architecture:**
- `SourcetableFetchWorker` thread class for async fetching
- Qt signals for thread-safe GUI updates
- Proper error propagation and user feedback
- Integrated with existing caster management system

## 📦 Installation

### Windows
```bash
git clone https://github.com/UserRmM/ntrip-checker-pro.git
cd ntrip-checker-pro
pip install -r requirements.txt
python ntrip_checker_pro_v5_1.py
```

### Linux / Raspberry Pi
See [INSTALL.md](INSTALL.md) for detailed instructions.

## 📖 Documentation

- **README.md** - Updated with Sourcetable Browser documentation
- **CHANGELOG.md** - Complete version history
- **INSTALL.md** - Platform-specific installation guides

## 🐛 Bug Reports & Feature Requests

Found a bug or have a feature idea? Please open an issue on GitHub:
https://github.com/UserRmM/ntrip-checker-pro/issues

## 🙏 Acknowledgments

Special thanks to the GNSS and NTRIP community for feedback and testing.

---

**Previous Release:** [v5.0](https://github.com/UserRmM/ntrip-checker-pro/releases/tag/v5.0) - Satellites Tab, Map Tab, MSM Message Support
