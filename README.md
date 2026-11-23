<div align="center">

<img src="https://capsule-render.vercel.app/api?type=rect&color=0:08131B,25:122A3A,65:143D52,100:0C1B2E&height=180&section=header&text=OSINT%20WORKSTATION&font=Orbitron&fontSize=28&fontColor=CFE7FF&animation=fadeIn&fontAlignY=38&desc=LOCAL-FIRST%20INVESTIGATION%20PIPELINE&descAlignY=63&descSize=12" width="100%" alt="OSINT Workstation banner" />

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![SearXNG](https://img.shields.io/badge/SearXNG-Native-2B6CB0?style=flat-square)](#)
[![SpiderFoot](https://img.shields.io/badge/SpiderFoot-Native-5B8DEF?style=flat-square)](#)
[![Local only](https://img.shields.io/badge/Data-Local%20by%20default-1F7A8C?style=flat-square)](#)

</div>

# OSINT Workstation

**A unified local-first OSINT platform** — CLI orchestrator + optional PySide6 desktop GUI — for Windows 11 and also usable on Linux and macOS.

- **CLI (`osint`)** — native pipeline: `TARGET → detect → plan → parallel collect → normalize → dedupe → correlate → relevance → confidence → graph → report`
- **GUI (`osint-toolkit-gui`)** — PySide6 desktop app with AI agent, MCP server, tool catalog, web UI, and safety guardrails
- **Services** — native SearXNG (`:8888`) used as the metasearch source; SpiderFoot (`:5001`) managed as a local process and checked for liveness (not driven by the CLI pipeline)
- **All local, keyless, privacy-first** — data never leaves your machine

**Version:** v0.2.2 | **License:** MIT | **Python:** >= 3.11 | **Platform:** Windows 11 (primary)

---
## Production readiness (authorized use)

OSINT Workstation is built for authorized, lawful investigations only —
public-source reconnaissance on assets you own or are engaged to assess.

- **Authorization gate.** `osint investigate` refuses to run without an
  explicit acknowledgement of a lawful basis: `--authorized` or
  `OSINT_AUTHORIZED=1`. Interactive mode asks "type 'yes'"; non-interactive
  mode prints the refusal and exits non-zero.
- **Audit trail.** Every run appends a JSONL record (`data_dir/audit.jsonl`)
  documenting who ran what, when, from which host, targeting what, and whether
  authorization was acknowledged. `osint audit [n]` shows the last `n`.
- **Preflight doctor.** `osint doctor` verifies Python, dependencies,
  data-directory writability, service liveness, and tool presence, with fix
  instructions for each failure. Use it before trusting any report.
- **Data outside the source tree.** Investigations live under
  `OSINT_DATA_DIR` / `$LOCALAPPDATA/OSINT-Workstation` /
  `$XDG_DATA_HOME/osint-workstation` / `~/.osint-workstation` — never inside
  the package directory — so reports survive an upgrade.

Usage:

```bash
# Verify the installation before trusting any output
osint doctor

# Run an investigation (attest a lawful basis)
osint investigate --authorized example.com

# See the last few runs
osint audit

# Print a stored report
osint report 2026-11-24_example.com
```

---

## Architecture

```text
┌────────────────────────────────────────────────────────────────────┐
│                        OSINT Workstation v0.2.1                   │
├──────────────────────────────┬────────────────────────────────────┤
│          CLI (osint)        │          GUI (osint-toolkit)          │
├──────────────────────────────┼────────────────────────────────────┤
│ Detect → Plan → Collect     │ Dashboard · Tools · Run · Results     │
│ Normalize → Correlate       │ Assistant (AI agent) · Settings       │
│ Relevance → Graph → Report  │ MCP server · Web UI (FastAPI)         │
└──────────────┬───────────────┴────────────────────────────────────┘
               │
       ┌───────┴───────┐
       ▼               ▼
   ┌─────────┐    ┌─────────────┐
   │ SearXNG │    │ SpiderFoot  │
   │  :8888  │    │  :5001      │
   │ source  │    │  liveness   │
   │  (used) │    │  probe only │
   └─────────┘    └─────────────┘
```

| Layer | Tool | Purpose |
|-------|------|---------|
| **Metasearch** | SearXNG (`:8888`) | Multi-engine aggregation, no API keys |
| **Engine** | SpiderFoot (`:5001`) | Managed local process; CLI checks liveness only — no scan is submitted and no results are ingested |
| **DNS/WHOIS** | Native Python | Direct resolver queries, free tier APIs |
| **Certificates** | crt.sh + TLS handshake | Certificate transparency and live verification |
| **IP Intelligence** | ipinfo.io, RIPEstat | Geo-IP and ASN lookup |
| **Username** | Sherlock, GitLab/GitHub APIs | Cross-platform handle detection |
| **Metadata** | ExifTool + Pillow | File EXIF extraction locally |
| **AI Agent** | Ollama + guardrails | Evidence-grounded analysis only |

---

## Quick start

```bash
# 1. Clone the repo
git clone https://github.com/sazid63/OSINT-Workstation.git
cd OSINT-Workstation

# 2. Install dependencies
pip install -r requirements.txt
# ...or install the package itself to get the `osint` command on PATH:
# pip install -e .

# 3. Install ExifTool (one-time, requires admin)
winget install --id OliverBetz.ExifTool -e -s winget

# 4. Start services (SearXNG + SpiderFoot)
python osint.py services up

# 5. Run your first investigation
python osint.py investigate example.com
#    or, if installed:  osint investigate example.com

# 6. Or launch the GUI
run_gui.bat
```

State the target type explicitly when the clue is a name rather than a domain:

```bash
osint investigate --type organization "Bangladesh Bank"
```

Stop services when done:

```bash
python osint.py services down
```

---

## Project structure

```text
OSINT-Workstation/
├── .github/workflows/        # CI: lint + tests on push/PR
├── core/
│   ├── orchestrator.py       # Investigation pipeline
│   ├── detect.py             # Target type detection and planning
│   ├── process.py            # Normalisation, dedupe, correlation, relevance, confidence
│   ├── report.py             # Report generation (MD/HTML/JSON + graph)
│   ├── storage.py            # Investigation storage layout
│   ├── http.py               # Rate-limited HTTP with disk cache
│   ├── clients.py            # SearXNG / SpiderFoot clients
│   ├── health.py             # Source health monitoring
│   ├── services.py           # Service manager (native, no Docker)
│   └── analyst.py            # Local AI analysis (Ollama)
├── modules/collectors.py     # Data collectors (DNS, WHOIS, cert, IP, URL, …)
├── config/
│   ├── settings.yaml         # Settings
│   ├── sources.yaml          # Enabled sources and timeouts
│   └── source_registry.yaml  # Candidate source registry
├── osint_toolkit/            # GUI package (PySide6 app, AI agent, MCP, web UI)
├── qa/                       # GUI smoke-test driver and screenshots helpers
├── services/                 # SearXNG settings and limiter config
├── secrets/                  # .env.example templates (no secrets committed)
├── docs/                     # Toolkit README, security, Windows run notes
├── tests/                    # Offline unit tests (pytest)
├── osint.py                  # Main CLI entry point (`osint`)
├── osint.bat                 # CLI wrapper
├── pyproject.toml            # Packaging + entry points
├── requirements.txt          # All deps (CLI + GUI + MCP)
├── run_cli.bat / run_gui.bat / run_web.bat
├── LICENSE
└── CHANGELOG.md
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
| `OSINT_CERT_TIMEOUT` | 10 | TLS handshake timeout for certificate checks |
| `OSINT_SUBDOMAIN_LIMIT` | 200 | Max subdomains to collect |
| `OSINT_HARVESTER_LIMIT` | 50 | Max results requested from theHarvester |
| `OSINT_COLLECT_TIMEOUT` | 45 | Wall-clock budget for the parallel collection phase (whole phase, not per tool) |
| `OLLAMA_URL` | `http://localhost:11434` | Ollama endpoint for AI analysis |

---

## Target types and confidence

Supported target types are **domain, ip, email, username, url, organization**.
There is no person target type: name-to-person resolution is out of scope for
this pipeline. Multi-word input is inferred as `organization`, the report says
so explicitly, and `--type` overrides the inference.

Every finding carries two independent properties:

- **class** — `FACT` / `DIRECTLY OBSERVED` / `CORRELATED` / `INFERRED` / `UNVERIFIED`
- **relevance** — `direct` / `partial` / `none`, i.e. how tightly the record is tied to the target

Confidence is the class strength scaled by relevance. Metasearch results that
mention no target token are scored `0.0`, marked `UNVERIFIED`, and moved out of
the findings list into a separate "excluded: unrelated search results" section
(retained in `normalized/noise.json` for audit). Two unrelated hits agreeing
with each other is not corroboration.

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

- **v0.2.1** (2026-11-24): Fixed the `osint` entry point (was a no-op and absent from the wheel), relevance-gated confidence for metasearch results, a real collection time budget, silent normalisation failures, UTF-8 output on non-Latin content, and stale packaging metadata; added offline test coverage for the pipeline
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
