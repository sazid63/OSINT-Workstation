<div align="center">

<img src="https://capsule-render.vercel.app/api?type=rect&color=0:08131B,25:122A3A,65:143D52,100:0C1B2E&height=180&section=header&text=OSINT%20WORKSTATION&font=Orbitron&fontSize=28&fontColor=CFE7FF&animation=fadeIn&fontAlignY=38&desc=LOCAL-FIRST%20INVESTIGATION%20PIPELINE&descAlignY=63&descSize=12" width="100%" alt="OSINT Workstation banner" />

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![SearXNG](https://img.shields.io/badge/SearXNG-Native-2B6CB0?style=flat-square)](#)
[![SpiderFoot](https://img.shields.io/badge/SpiderFoot-Native-5B8DEF?style=flat-square)](#)
[![Local only](https://img.shields.io/badge/Data-Local%20by%20default-1F7A8C?style=flat-square)](#)

</div>

# OSINT Workstation

**A unified local-first OSINT platform** — CLI orchestrator + optional PySide6 desktop GUI — for Windows 11 and also usable on Linux and macOS.

- **CLI (`osint`)** — native pipeline: `TARGET → detect → plan → parallel collect → normalize → dedupe → correlate → confidence → graph → report`
- **GUI (`osint-toolkit-gui`)** — PySide6 desktop app with AI agent, MCP server, tool catalog, web UI, and safety guardrails
- **Services** — native SearXNG (`:8888`) + SpiderFoot (`:5001`) managed as local processes
- **All local, keyless, privacy-first** — data never leaves your machine

**Version:** v0.2.0 | **License:** MIT | **Python:** >= 3.11 | **Platform:** Windows 11 (primary)

---

## Architecture

```text
┌────────────────────────────────────────────────────────────────────┐
│                        OSINT Workstation v0.2.0                   │
├──────────────────────────────┬────────────────────────────────────┤
│          CLI (osint)        │          GUI (osint-toolkit)          │
├──────────────────────────────┼────────────────────────────────────┤
│ Detect → Plan → Collect     │ Dashboard · Tools · Run · Results     │
│ Normalize → Correlate       │ Assistant (AI agent) · Settings       │
│ Graph → Report              │ MCP server · Web UI (FastAPI)         │
└──────────────┬───────────────┴────────────────────────────────────┘
               │
       ┌───────┴───────┐
       ▼               ▼
   ┌─────────┐    ┌─────────────┐
   │ SearXNG │    │ SpiderFoot  │
   │  :8888  │    │  :5001      │
   │ native  │    │  native     │
   └─────────┘    └─────────────┘
```

| Layer | Tool | Purpose |
|-------|------|---------|
| **Metasearch** | SearXNG (`:8888`) | Multi-engine aggregation, no API keys |
| **Engine** | SpiderFoot (`:5001`) | Automated reconnaissance framework |
| **DNS/WHOIS** | Native Python | Direct resolver queries, free tier APIs |
| **Certificates** | crt.sh + TLS handshake | Certificate transparency and live verification |
| **IP Intelligence** | ipinfo.io, RIPEstat | Geo-IP and ASN lookup |
| **Username** | Sherlock, GitLab/GitHub APIs | Cross-platform handle detection |
| **Metadata** | ExifTool + Pillow | File EXIF extraction locally |
| **AI Agent** | Ollama + guardrails | Evidence-grounded analysis only |

---

## Quick start

```bash
# 1. Clone the repo with submodules
git clone https://github.com/sazid63/OSINT-Workstation.git
cd OSINT-Workstation

# 2. Install dependencies
pip install -r requirements.txt

# 3. Install ExifTool (one-time, requires admin)
winget install --id OliverBetz.ExifTool -e -s winget

# 4. Start services (SearXNG + SpiderFoot)
python osint.py services up

# 5. Run your first investigation
python osint.py investigate example.com

# 6. Or launch the GUI
run_gui.bat
```

Stop services when done:

```bash
python osint.py services down
```

---

## Project structure

```text
OSINT-Workstation/
├── .github/                  # CI workflows
├── core/                     # CLI orchestrator
├── analytic.py               # Local AI analysis (Ollama)
├── clients.py                # HTTP clients for SearXNG/SpiderFoot
├── detect.py                 # Target type detection and planning
├── health.py                 # Source health monitoring
├── http.py                   # Rate-limited HTTP with caching
├── orchestrator.py            # Investigation pipeline
├── process.py                # Normalization and correlation
├── report.py                 # Report generation (MD/HTML/JSON)
├── services.py               # Service manager (native, no Docker)
├── storage.py                # Investigation storage
├── modules/                  # Data collectors
├── config/                  # Settings and source config
├── sources.yaml              # Source registry
├── source_health.json        # Last health check
├── osint_toolkit/            # GUI package (folded in)
├── ai/                       # AI agent and providers
├── mcp/                      # MCP server
├── ui/                       # PySide6 app (pages, themes, workers)
├── web/                      # FastAPI web UI + MCP
├── cli.py                    # Toolkit CLI entry point
├── config.py                 # Toolkit config
├── tools/                   # Vendored tools at runtime
├── searchng/                 # Self-hosted SearXNG instance
├── spiderfoot-src/           # SpiderFoot framework
├── docs/                    # Extra docs (toolkit, security, limits)
├── tests/                   # CLI tests
├── osint.py                  # Main CLI entry point
├── requirements.txt          # All deps (CLI + GUI + MCP)
├── run_cli.bat               # CLI launcher
├── run_gui.bat               # GUI launcher
├── LICENSE                   # MIT
├── CHANGELOG.md              # Release history
```

---

## Configuration

### Sources

- `config/sources.yaml` enables or disables sources, configure timeouts
- `secrets/.env` copy from `.env.example`, add optional API keys

### Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OSINT_HTTP_TIMEOUT` | 20 | HTTP request timeout in seconds |
| `OSINT_DNS_LIFETIME` | 10 | DNS query lifetime in seconds |
| `OSINT_SUBDOMAIN_LIMIT` | 200 | Max subdomains to collect |
| `OLLAMA_URL` | `http://localhost:11434` | Ollama endpoint for AI analysis |

---

## Security and privacy

- **Local-first**: all investigations are stored locally in `investigations/`
- **No cloud uploads**: data never leaves your machine
- **Polite crawling**: built-in rate limiting (1 req/s per host)
- **Keyless by design**: works without API keys; optional keys for enhanced coverage
- **Authorization only**: use only on targets you are authorized to investigate
- **Safety guardrails** (GUI): tool approval, safe/unsafe modes, MCP auth

See `CHANGELOG.md` for full release details.

---

## Version history

- **v0.2.0** (2026-11-02): Unified repo merge with CLI + GUI folder into a single repo, Python project unification, submodule removal, docs consolidation
- **v0.1.3-security** (2026-11-02): Security hardening with XSS, CSRF, timeouts, storage fix, Python 3
- **v0.1.2-fixes** (2026-11-02): File handle leaks, resource management
- **v0.1.1** (2026-11-01): Health monitoring, RIPEstat source
- **v0.1.0** (2026-10-05): Initial CLI orchestrator + native services

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/new-collector`)
3. Commit changes (`git commit -am 'Add new OSINT collector'`)
4. Push to the branch (`git push origin feature/new-collector`)
5. Open a Pull Request

**Code style:** `ruff` (line-length 100, py311). Tests: `pytest`

---

## Legal and ethical use

This tool is for authorized research only. The developer assumes no responsibility for misuse. Users must:

- Have explicit permission to investigate targets
- Comply with applicable laws and regulations
- Respect rate limits and robots.txt guidelines
- Never use for unauthorized access or harassment

---

## License

MIT. See [LICENSE](LICENSE) for details.
