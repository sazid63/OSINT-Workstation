# OSINT Workstation

**A unified local-first OSINT platform** — CLI orchestrator + optional PySide6 desktop GUI — for Windows 11 (also runs on Linux/macOS).

- **CLI (`osint`)** — Native pipeline: `TARGET → detect → plan → parallel collect → normalize → dedupe → correlate → confidence → graph → report`
- **GUI (`osint-toolkit-gui`)** — PySide6 desktop app with AI agent, MCP server, tool catalog, web UI, and safety guardrails
- **Services** — Native SearXNG (:8888) + SpiderFoot (:5001) managed as local processes (no Docker)
- **All local, keyless, privacy-first** — Data never leaves your machine

**Version:** v0.2.0 | **License:** MIT | **Python:** ≥ 3.11 | **Platform:** Windows 11 (primary)

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         OSINT Workstation v0.2.0                            │
├──────────────────────────────┬──────────────────────────────────────────────┤
│           CLI (osint)         │           GUI (osint-toolkit)               │
├──────────────────────────────┼──────────────────────────────────────────────┤
│  Detect → Plan → Collect     │  Dashboard · Tools · Run · Results          │
│  Normalize → Correlate       │  Assistant (AI agent) · Settings            │
│  Graph → Report              │  MCP server · Web UI (FastAPI)              │
└──────────────┬───────────────┴──────────────────────────────────────────────┘
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
| **Metasearch** | SearXNG (:8888) | Multi-engine aggregation, no API keys |
| **Engine** | SpiderFoot (:5001) | Automated reconnaissance framework |
| **DNS/WHOIS** | Native Python | Direct resolver queries, free tier APIs |
| **Certificates** | crt.sh + TLS handshake | Certificate transparency & live verification |
| **IP Intelligence** | ipinfo.io, RIPEstat | Geo-IP and ASN lookup |
| **Username** | Sherlock, GitLab/GitHub APIs | Cross-platform handle detection |
| **Metadata** | ExifTool + Pillow | File EXIF extraction (local only) |
| **AI Agent** | Ollama + guardrails | Evidence-grounded analysis only |

---

## 🚀 Quick Start

```powershell
# 1. Clone with submodules (tools downloaded at runtime)
git clone https://github.com/sazid63/OSINT-Workstation.git
cd OSINT-Workstation

# 2. Install dependencies (CLI + optional GUI)
pip install -r requirements.txt
# For GUI:
pip install -e .[gui]

# 3. Install ExifTool (one-time, requires admin)
winget install --id OliverBetz.ExifTool --source winget

# 4. Start services (SearXNG + SpiderFoot)
python osint.py services up

# 5. Run your first investigation
python osint.py investigate example.com

# 6. Or launch the GUI
run_gui.bat
# or: python -m osint_toolkit
```

**Stop services when done:**
```powershell
python osint.py services down
```

---

## 📁 Project Structure

```
OSINT-Workstation/
├── .github/                    # CI workflows
├── core/                       # CLI orchestrator
│   ├── analyst.py              # Local AI analysis (Ollama)
│   ├── clients.py              # HTTP clients for SearXNG/SpiderFoot
│   ├── detect.py               # Target type detection & planning
│   ├── health.py               # Source health monitoring
│   ├── http.py                 # Rate-limited HTTP with caching
│   ├── orchestrator.py         # Investigation pipeline
│   ├── process.py              # Normalization & correlation
│   ├── report.py               # Report generation (MD/HTML/JSON)
│   ├── services.py             # Service manager (native, no Docker)
│   └── storage.py              # Investigation storage
├── modules/
│   └── collectors.py           # Individual data collectors
├── config/
│   ├── settings.yaml           # Global config
│   ├── sources.yaml            # Source configuration
│   ├── source_registry.yaml    # 50+ source registry
│   └── source_health.json      # Last health check (git-ignored)
├── osint_toolkit/              # GUI package (folded in, no submodule)
│   ├── ai/                     # AI agent + providers
│   ├── catalog/                # Tool catalog (YAML definitions)
│   ├── core/                   # Registry, runner, safety, workspace
│   ├── engine/                 # Tool execution engine
│   ├── mcp/                    # MCP server for OpenCode
│   ├── ui/                     # PySide6 app (pages, theme, workers)
│   ├── web/                    # FastAPI web UI + MCP
│   ├── cli.py                  # Toolkit CLI entry
│   └── config.py               # Toolkit config
├── tools/                      # Vendored at runtime (git-ignored)
│   ├── searxng/                # Self-hosted SearXNG instance
│   ├── spiderfoot-src/         # SpiderFoot framework
│   └── theHarvester/           # Email/subdomain aggregation
├── secrets/
│   └── .env.example            # API key template
├── packaging/                  # Inno Setup installer
├── docs/                       # Extra docs (toolkit, contributing, security)
├── tests/                      # CLI tests
├── osint_toolkit/              # Toolkit tests
├── .github/workflows/          # CI
├── LICENSE                     # MIT
├── CHANGELOG.md                # Release history
├── pyproject.toml              # Modern packaging
├── requirements.txt            # All deps (CLI + GUI + MCP)
├── run_cli.bat                 # CLI launcher
├── run_gui.bat                 # GUI launcher
├── run_web.bat                 # Web UI launcher
└── osint.py                    # Main CLI entry point
```

---

## ⚙️ Configuration

### Sources
- `config/sources.yaml` — Enable/disable sources, configure timeouts
- `secrets/.env` — Copy from `.env.example`, add optional API keys

### Environment Variables
| Variable | Default | Description |
|----------|---------|-------------|
| `OSINT_HTTP_TIMEOUT` | 20 | HTTP request timeout (seconds) |
| `OSINT_DNS_LIFETIME` | 10 | DNS query lifetime (seconds) |
| `OSINT_SUBDOMAIN_LIMIT` | 200 | Max subdomains to collect |
| `OSINT_HARVESTER_LIMIT` | 50 | Max results from theHarvester |
| `OLLAMA_URL` | `http://localhost:11434` | Ollama endpoint for AI analyst |

### Install Extras
```powershell
# GUI (PySide6)
pip install -e .[gui]

# MCP server
pip install -e .[mcp]

# Dev tools
pip install -e .[dev]
```

---

## 🔐 Security & Privacy

- **Local-first**: All investigations stored locally in `investigations/`
- **No cloud uploads**: Data never leaves your machine
- **Polite crawling**: Built-in rate limiting (1 req/s per host)
- **Keyless by design**: Works without API keys; optional keys for enhanced coverage
- **Authorization only**: Use only on targets you're authorized to investigate
- **Safety guardrails** (GUI): Tool approval dialog, safe/unsafe mode, MCP auth

---

## 🛡️ Security Hardening (v0.1.3-security)

- **XSS prevention** — All dynamic HTML content escaped with `html.escape()`
- **CSRF mitigation** — State-changing ops switched from GET to POST with JSON body
- **Race-condition fix** — `$.inArray()` filter corrected from truthy to `!== -1`
- **Resource management** — Parallel collection tasks have 30-second timeout
- **Storage bug fix** — Undefined variable removed from `core/storage.py`
- **Python 3 syntax** — Corrected `except OSError, ValueError` syntax

See [CHANGELOG.md](CHANGELOG.md) for full details.

---

## 🛠️ CLI Commands (`osint`)

```powershell
# Investigation
osint investigate <target>          # Standard investigation
osint investigate --deep <target>   # Deep analysis (includes chaining)
osint investigate --ai <target>     # With AI analysis (requires Ollama)

# Services
osint services up|down|status       # Manage SearXNG/SpiderFoot
osint services start <name>         # Start single service

# Quick single-source checks
osint dns|ip|email|username <target>
osint search <query>                # SearXNG search
osint metadata <file>               # Local file EXIF analysis
osint harvester <domain>            # Passive email/host aggregation

# Reports
osint graph <investigation-id>      # View investigation graph
osint report <investigation-id>     # View report markdown

# Source management
osint health                        # Live health check of all sources
osint sources                       # List all registered sources
osint tools                         # List native tools

# Toolkit delegation (GUI, MCP, Web)
osint toolkit list                  # List toolkit tools
osint gui                           # Launch GUI
osint mcp                           # Start MCP server
osint web                           # Start web UI
```

---

## 🖥️ GUI Commands (`osint-toolkit-gui`)

```powershell
# Full GUI
run_gui.bat
# or
python -m osint_toolkit

# CLI mode
run_cli.bat list
python -m osint_toolkit list

# MCP server for OpenCode
run_web.bat mcp
python -m osint_toolkit.mcp.server

# Web UI
run_web.bat
python -m osint_toolkit.web.server
```

**GUI Features:**
- Dashboard with stats & quick actions
- Tool catalog with safety badges (safe/unsafe/needs-approval)
- Run page with live logs & progress
- Results browser with exports
- AI Assistant (Ollama) with evidence-grounded responses
- Settings: API keys, tool approval, workspace, safety

---

## 📦 Installation Methods

| Method | Command | Best For |
|--------|---------|----------|
| **Editable (dev)** | `pip install -e .[gui,mcp]` | Development |
| **User install** | `pipx install -e .[gui]` | Isolated app |
| **Portable (Windows)** | `packaging/OSINT-Toolkit.iss` | Inno Setup installer |
| **Minimal (CLI only)** | `pip install -r requirements.txt` | Servers/headless |

---

## 🔄 Version History

- **v0.2.0** (2026-11-02): Unified repo merge — CLI + GUI folded into single repo, pyproject.toml, requirements unified, submodule removed, docs consolidated
- **v0.1.3-security** (2026-11-02): Security hardening — XSS, CSRF, timeouts, storage fix, Python 3
- **v0.1.2-fixes** (2026-11-02): File handle leaks, resource management
- **v0.1.1** (2026-11-01): Health monitoring, RIPEstat source
- **v0.1.0** (2026-10-05): Initial CLI orchestrator + native services

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/new-collector`)
3. Commit changes (`git commit -am 'Add new OSINT collector'`)
4. Push to branch (`git push origin feature/new-collector`)
5. Open a Pull Request

**Code style:** `ruff` (line-length 100, py311) · Tests: `pytest`

---

## ⚠️ Legal & Ethical Use

This tool is for **authorized research only**. The developer assumes no responsibility for misuse. Users must:
- Have explicit permission to investigate targets
- Comply with applicable laws and regulations
- Respect rate limits and robots.txt guidelines
- Never use for unauthorized access or harassment

---

## 📄 License

This project is licensed under the MIT License - see [LICENSE](LICENSE) for details.

---

**Built with:** Python 3.11+, dnspython, requests, Jinja2, PySide6, SearXNG, SpiderFoot, theHarvester, Ollama (optional)  
**Platform:** Windows 11 (primary), Linux, macOS (CLI)  
**Repository:** https://github.com/sazid63/OSINT-Workstation