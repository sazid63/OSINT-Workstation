# OSINT Workstation

A local-first, open-source OSINT (Open Source Intelligence) workstation for Windows 11. Combines multiple data sources into a unified evidence pipeline with automated collection, normalization, and reporting.

**Version:** v0.1.3-security | **Last Updated:** 2026-11-02

---

## 🏗️ Architecture

```
TARGET → detect → plan → parallel collect → normalize → dedupe → correlate → confidence → graph → report
```

| Layer | Tool | Purpose |
|-------|------|---------|
| Metasearch | SearXNG (:8888) | Multi-engine aggregation, no API keys |
| Engine | SpiderFoot (:5001) | Automated reconnaissance framework |
| DNS/WHOIS | Native Python | Direct resolver queries, free tier APIs |
| Certificates | crt.sh + TLS handshake | Certificate transparency & live verification |
| IP Intelligence | ipinfo.io, RIPEstat | Geo-IP and ASN lookup |
| Username | Sherlock, GitLab/GitHub APIs | Cross-platform handle detection |
| Metadata | ExifTool + Pillow | File EXIF extraction (local only) |

---

## 🚀 Quick Start

```powershell
# Install dependencies
pip install -r requirements.txt

# Start services (SearXNG + SpiderFoot)
python osint.py services up

# Run investigation
python osint.py investigate example.com

# Check status
python osint.py status

# Interactive terminal
osint.bat
```

**Stop services when done:**
```powershell
python osint.py services down
```

---

## 📁 Project Structure

```
OSINT project/
├── core/               # Main application logic
│   ├── analyst.py      # Local AI analysis (Ollama)
│   ├── clients.py      # HTTP clients for SearXNG/SpiderFoot
│   ├── detect.py       # Target type detection & planning
│   ├── health.py       # Source health monitoring
│   ├── http.py         # Rate-limited HTTP with caching
│   ├── orchestrator.py # Investigation pipeline
│   ├── process.py      # Normalization & correlation
│   ├── report.py       # Report generation
│   ├── services.py     # Service manager (native, no Docker)
│   └── storage.py      # Investigation storage
├── modules/
│   └── collectors.py   # Individual data collectors
├── config/
│   ├── sources.yaml    # Source configuration
│   └── source_registry.yaml  # 50+ source registry
├── tools/
│   ├── searxng/        # Self-hosted SearXNG instance
│   ├── spiderfoot-src/ # SpiderFoot framework
│   └── theHarvester/   # Email/subdomain aggregation
├── secrets/
│   └── .env.example    # API key template
└── osint.py           # Main CLI entry point
```

---

## 🔧 Configuration

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

---

## 🔐 Security & Privacy

- **Local-first**: All investigations stored locally in `investigations/`
- **No cloud uploads**: Data never leaves your machine
- **Polite crawling**: Built-in rate limiting (1 req/s per host)
- **Keyless by design**: Works without API keys; optional keys for enhanced coverage
- **Authorization only**: Use only on targets you're authorized to investigate

---

## 🛡️ Security Hardening (v0.1.3-security)

This release hardens the frontend and backend against common web vulnerabilities:

- **XSS prevention** — All user-controlled data rendered in HTML reports is escaped with `html.escape()`. SpiderFoot's `sf.replace_sfurltag()` now sanitizes URLs before inserting them into links. D3 tooltip content in `viz.js` uses `.text()` instead of `.html()`.
- **CSRF mitigation** — State-changing operations (`sf.deleteScan`, `sf.stopScan`) switched from GET to POST with a JSON body.
- **Race-condition fix** — `$.inArray()` filter check now correctly uses `!== -1` instead of a truthy check.
- **Resource management** — Parallel collection tasks in `orchestrator.py` now have a 30-second timeout to prevent hangs.
- **Storage bug fix** — `core/storage.py` no longer references an undefined variable `p` when writing investigation metadata.
- **Python 3 syntax fix** — `tools/theHarvester/.../harvestview.py` corrected from Python 2 `except OSError, ValueError` syntax.

See [CHANGELOG.md](CHANGELOG.md) for the full release notes.

Check which sources are working:
```powershell
python osint.py health
```

View source registry:
```powershell
python osint.py sources
```

---

## 🛠️ CLI Commands

```powershell
# Investigation
python osint.py investigate <target>          # Standard investigation
python osint.py investigate --deep <target>   # Deep analysis (includes chaining)
python osint.py investigate --ai <target>     # With AI analysis (requires Ollama)

# Services
python osint.py services up|down|status       # Manage SearXNG/SpiderFoot
python osint.py services start <name>         # Start single service

# Tools
python osint.py dns|ip|email|username <target>  # Quick single-source checks
python osint.py search <query>               # SearXNG search
python osint.py metadata <file>              # Local file EXIF analysis
python osint.py harvester <domain>           # Passive email/host aggregation

# Reports
python osint.py graph <investigation-id>     # View investigation graph
python osint.py report <investigation-id>    # View report markdown
```

---

## 🔄 Version History

- **v0.1.3-security** (2026-11-02): Security hardening — XSS fixes, CSRF mitigation, timeout guards, storage bug fix, Python 3 syntax fixes
- **v0.1.2-fixes** (2026-11-02): Fixed file handle leaks, improved resource management
- **v0.1.1** (2026-11-01): Enhanced health monitoring, added RIPEstat source
- **v0.1.0** (2026-10-05): Initial release with core pipeline

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/new-collector`)
3. Commit changes (`git commit -am 'Add new OSINT collector'`)
4. Push to branch (`git push origin feature/new-collector`)
5. Open a Pull Request

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

**Built with**: Python 3.12, dnspython, requests, Jinja2, SearXNG, SpiderFoot, theHarvester  
**Platform**: Windows 11 (native processes, no Docker required)
