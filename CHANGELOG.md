# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-11-02

### Fixed
- **Portability** — Removed hardcoded `base_dir` from `config/settings.yaml` and hardcoded `Python314\Scripts` PATH from `osint.bat`; both now resolve from the project root / system PATH
- **Config consistency** — `settings.yaml` `default_timeout` aligned to 20s (was 25); confidence weights now match `core/process.py` actual values; version bumped to 0.2.0
- **Resource leak** — `core/services.py`: service log file handle no longer left open after `Popen`
- **Config dead code** — `CERT_TIMEOUT` env var in `modules/collectors.py` now actually used for the TLS handshake timeout (was declared but unused)
- **Dead imports** — Removed unused `subprocess` (osint.py), `datetime` (collectors.py), `send_keys` (qa/qa_driver.py)
- **Logic bug** — `osint.py` menu option 13 and CLI `graph`/`report` commands opened the file before checking existence
- **QA portability** — `qa/final_test.py` uses project-relative paths instead of absolute `C:\...` paths

### Added
- `CHANGELOG.md` (Keep a Changelog format)
- `DESCRIPTION.md` — one-paragraph repository description
- Configurable environment variables: `OSINT_HTTP_TIMEOUT`, `OSINT_DNS_LIFETIME`, `OSINT_CERT_TIMEOUT`, `OSINT_SUBDOMAIN_LIMIT`, `OSINT_HARVESTER_LIMIT`

### Removed
- Stray untracked files (screenshots, HTML artifacts, test output) from the main working tree

## [0.1.3-security] - 2026-11-02

### Security
- **XSS Prevention** — HTML reports now escape all dynamic content using `html.escape()` (`core/report.py`)
- **SpiderFoot XSS Fix** — `sf.replace_sfurltag()` in `tools/spiderfoot-src/spiderfoot/static/js/spiderfoot.js` now sanitizes URLs before interpolating into HTML links
- **D3 Visualization XSS Fix** — Tooltip rendering in `tools/spiderfoot-src/spiderfoot/static/js/viz.js` uses `.text()` instead of `.html()`; all data fields in `buildPopupMessage()` are escaped
- **CSRF Mitigation** — `sf.deleteScan()` and `sf.stopScan()` in `spiderfoot.js` switched from GET to POST with JSON body
- **Tabnabbing Protection** — All `target="_blank"` links now include `rel="noopener noreferrer"`

### Fixed
- **Logic Bug in Filter** — `tools/spiderfoot-src/spiderfoot/static/js/spiderfoot.scanlist.js`: Fixed `$.inArray()` check from truthy to `!== -1` (first matching type was incorrectly skipped)
- **Storage Bug** — `core/storage.py`: Removed undefined variable `p` in `create_investigation()`; metadata now writes directly to the correct path
- **Orchestrator Timeout** — `core/orchestrator.py`: Added 30-second per-task timeout for parallel collection to prevent hanging workers
- **Python 3 Syntax** — `tools/theHarvester/theHarvester/lib/api/harvestview.py`: Fixed Python 2 syntax `except OSError, ValueError` to Python 3 `except (OSError, ValueError)`

### Changed
- Repository cleaned of stray files (screenshots, test scripts, temp files)
- `README.md` updated with Security Hardening section and new version history entry
- New `CHANGELOG.md` added for release tracking

## [0.1.2-fixes] - 2026-11-02

### Fixed
- File handle leaks in HTTP client and storage layers
- Improved resource management in orchestrator and service manager
- Added proper cleanup for temporary files

## [0.1.1] - 2026-11-01

### Added
- Enhanced health monitoring with per-source status tracking
- RIPEstat ASN/prefix intelligence source
- Source registry with 50+ candidate sources

## [0.1.0] - 2026-10-05

### Added
- Initial release with core pipeline: detect → plan → parallel collect → normalize → dedupe → correlate → confidence → graph → report
- Native Windows service management for SearXNG and SpiderFoot (no Docker)
- Multi-source OSINT collection: DNS, WHOIS/RDAP, crt.sh, IP intelligence, username, email, URL metadata
- Local file EXIF analysis via ExifTool/Pillow
- Evidence-based reporting with contradiction detection

[0.2.0]: https://github.com/sazid63/OSINT-Workstation/compare/v0.1.3-security...v0.2.0
[0.1.3-security]: https://github.com/sazid63/OSINT-Workstation/compare/v0.1.2-fixes...v0.1.3-security
[0.1.2-fixes]: https://github.com/sazid63/OSINT-Workstation/compare/v0.1.1...v0.1.2-fixes
[0.1.1]: https://github.com/sazid63/OSINT-Workstation/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/sazid63/OSINT-Workstation/releases/tag/v0.1.0