# OSINT Workstation
Local-first, free/open-source OSINT environment (Windows 11).

## Architecture
`TARGET → detect → plan → parallel collect → normalize → dedupe → correlate → confidence → graph → report`

| Layer | Choice | Why |
|---|---|---|
| Metasearch | SearXNG (native, :8888, `tools/searxng`) | self-hosted, multi-engine, no key |
| P2P index (optional) | YaCy (not installed, :8090) | independent index; OFF by default (heavy, low ROI) |
| Investigation engine | SpiderFoot (native, :5001, `tools/spiderfoot-src`) | complements native orchestrator |
| Native collectors | dnspython, python-whois, RDAP, crt.sh, HackerTarget, ip-api, GitHub API | free, no keys, unique sources |
| Username | Sherlock (pip) | 400+ sites — unique coverage |
| Email/subdomain agg | theHarvester (pip) | unique aggregation |
| Metadata | ExifTool (winget) | no Python equivalent |
| NOT installed | YaCy default, Holehe (dead 2023), Amass/Subfinder overlap (crt.sh+DNS covers), Censys/Shodan (key-gated, slots in sources.yaml) | avoid junk drawer |

**No Docker.** SearXNG and SpiderFoot run as native Windows processes from dedicated
venvs in `services/` (SearXNG: Python 3.12, SpiderFoot: Python 3.11). Service state
lives in `services/services.json`, logs in `services/logs/`, SpiderFoot scan DB in
`services/spiderfoot-data/`. Docker containers, images, compose file, and volumes
were removed 2026-10-11.

## Quick start
```bat
pip install -r requirements.txt
python osint.py services up      :: start SearXNG + SpiderFoot (native, no Docker)
python osint.py status
python osint.py investigate example.com
osint.bat   :: interactive terminal
python osint.py services down    :: stop services when done
```

## Config
- `config/sources.yaml` — add/remove sources without code changes
- `secrets/.env` (from `.env.example`) — optional keys only
