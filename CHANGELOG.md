# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.1] - 2026-11-24

Release-blocker pass. Focus: the tool now behaves the way the README says it does.

### Fixed — Blockers
- **`osint` console script was a no-op** — `osint.py:main()` parsed no arguments and
  dispatched nothing (`sys.argv[1:] = sys.argv[1:]`, `return ... and None`). Argument
  handling moved into `run(argv)` / `main(argv=None)`; `python -m` and the installed
  script now behave identically, and errors exit non-zero.
- **`osint.py` was missing from the wheel** — `[tool.hatch.build.targets.wheel]` listed
  only packages, so `osint:main` was not importable after `pip install`. Switched to
  `only-include` including `osint.py`; CI now asserts it is present in the built wheel.
- **Confidence inflation on metasearch results** — every SearXNG hit was stamped
  `DIRECTLY OBSERVED` and scored 0.8 ("MEDIUM CONFIDENCE") regardless of whether it
  mentioned the target. Findings now carry an independent `relevance`
  (`direct`/`partial`/`none`); unrelated hits are scored 0.0, marked `UNVERIFIED`, and
  moved into a separate report section (`normalized/noise.json`) instead of the
  findings list. `confidence_score()` scales class strength by relevance.
- **The 30-second collector timeout never fired** — `fut.result(timeout=30)` ran after
  `as_completed()` had already yielded a finished future, so one hung collector stalled
  the whole run. Collection now runs under a real wall-clock budget
  (`OSINT_COLLECT_TIMEOUT`, default 45s) via `concurrent.futures.wait`.
- **Silent normalisation failures** — `except Exception: pass` around `to_findings()`
  discarded a whole source's output with no trace. Failures are now recorded in
  `diagnostics` and surfaced in the report's "Collection errors" section.
- **UnicodeEncodeError on non-Latin findings (Windows)** — several writers used
  `open(path, 'w')` without `encoding='utf-8'`. On a cp1252 host the first Bengali/CJK
  character aborted the run at `findings.json`. All writers now pin UTF-8.

### Fixed — Correctness
- `detect_target()` no longer has a dead fall-through in the username branch; an
  `@`-prefixed clue is always a username.
- Multi-word targets are still inferred as `organization`, but the inference is now
  recorded (`meta.type_inferred`) and stated in the report rather than passing
  silently. New `--type` flag accepts `domain|ip|email|username|url|organization`.
- `correlate()` now always records full provenance (`tools`, `sources`) instead of only
  when promoting, and carries the weakest relevance of the merged group. Agreement
  between two unrelated hits no longer promotes to `CORRELATED`.
- `extract_entities()` placeholder-domain filter used `pass` where `continue` was
  meant, so `example.*` and short strings were never skipped.
- SpiderFoot results are a liveness probe, never a finding; the probe payload no longer
  pollutes the findings list, and it is reported separately from successful sources.

### Changed
- `pyproject.toml`: version 0.2.1; pytest `testpaths` no longer points at a
  nonexistent `osint_toolkit/tests`; added sdist include list.
- README corrected: SpiderFoot's real role, `core/analyst.py` (was `analytic.py`),
  accurate project tree, `--type` usage, confidence semantics, `OSINT_COLLECT_TIMEOUT`
  and the other configurable env vars.
- Added `.github/workflows/ci.yml` — offline tests on 3.11/3.12/3.13 plus a wheel
  content assertion.

### Added
- `tests/test_pipeline.py` — 28 offline tests covering target typing, relevance
  gating, confidence blending, dedupe/correlate provenance, entity extraction, UTF-8
  report output, noise separation, and the collection budget.

## [0.2.0] - 2026-11-04

### Added — Repo Unification (Major)
- **Single repo** — Merged `OSINT-Toolkit` (PySide6 GUI, AI agent, MCP server, tool catalog, web UI) into `OSINT-Workstation` as plain directory `osint_toolkit/` (git submodule removed)
- **Unified packaging** — `pyproject.toml` with optional `[gui]`, `[mcp]`, `[dev]` extras; `requirements.txt` covers CLI + GUI + MCP
- **Unified entry points** — `osint` (CLI), `osint-toolkit` (toolkit CLI), `osint-toolkit-gui` (GUI), `osint-toolkit-mcp` (MCP server)
- **Consolidated docs** — Toolkit README/SECURITY/CONTRIBUTING/DISCLAIMER/WINDOWS_RUN folded under `docs/`
- **Unified CI/CD** — Single workflow for lint, test, build

### Fixed
- **Portability** — Removed hardcoded `base_dir` from `config/settings.yaml` and hardcoded `Python314\Scripts` PATH from `osint.bat`; both now resolve from project root / system PATH
- **Config consistency** — `settings.yaml` `default_timeout` aligned to 20s (was 25); confidence weights match `core/process.py`; version bumped to 0.2.0
- **Resource leak** — `core/services.py`: service log file handle no longer left open after `Popen`
- **Config dead code** — `CERT_TIMEOUT` env var in `modules/collectors.py` now actually used for TLS handshake timeout (was declared but unused)
- **Dead imports** — Removed unused `subprocess` (osint.py), `datetime` (collectors.py), `send_keys` (qa/qa_driver.py)
- **Logic bug** — `osint.py` menu option 13 and CLI `graph`/`report` commands opened file before checking existence
- **QA portability** — `qa/final_test.py` uses project-relative paths instead of absolute `C:\...` paths

### Added
- `pyproject.toml` (modern packaging, hatchling backend)
- `run_cli.bat`, `run_gui.bat`, `run_web.bat` (Windows launchers)
- Optional extras: `[gui]` (PySide6), `[mcp]` (MCP), `[dev]` (pytest/ruff)
- Configurable env vars: `OSINT_HTTP_TIMEOUT`, `OSINT_DNS_LIFETIME`, `OSINT_CERT_TIMEOUT`, `OSINT_SUBDOMAIN_LIMIT`, `OSINT_HARVESTER_LIMIT`, `OLLAMA_URL`

### Removed
- Stray untracked files (screenshots, HTML artifacts, test output) from working tree
- Git submodule `osint-toolkit` (folded in as plain directory)
- Separate toolkit repo dependency

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