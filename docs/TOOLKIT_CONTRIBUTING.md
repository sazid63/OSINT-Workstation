# Contributing to the OSINT Toolkit

Thanks for helping improve the Toolkit. It is an open-source (MIT) desktop app
for lawful, educational OSINT work.

## Ground rules

- **Lawful, ethical use only.** Contributions that add authentication bypass,
  CAPTCHA/paywall circumvention, credential attacks, or private-data scraping
  will be rejected.
- **Free and open-source only.** New tools must be free and open-source. No
  proprietary or paid services as required dependencies. Optional connectors to
  free, public data sources are acceptable if they need no payment.
- **No personal data in the repo.** Never commit real people's data, real
  investigation output, API keys, or machine-specific paths.

## Adding a tool

Every tool is a **manifest** (`tools/<category>/<id>.yaml`) plus an optional
**adapter** (`tools/<category>/<id>.py`). See `docs/adding-tools.md` for the full
schema. A manifest looks like:

```yaml
id: example
name: Example Tool
category: domain
description: One line on what it does.
how_to_use: |
  Plain-English steps for a non-technical user.
what_to_connect: []           # e.g. [api_key: VIRUSTOTAL_API_KEY] or [binary: nmap]
safety: passive               # passive | active
license: MIT
homepage: https://example.org
install: { method: pip, package: example-tool }   # or { method: binary, ... }
```

## Development

```bash
git clone https://github.com/sazid63/OSINT-Toolkit
cd osint-toolkit
uv venv
uv pip install -e ".[dev]"
python -m osint_toolkit
```

## Before you open a PR

- `python -m pytest` passes.
- `gitleaks detect` reports nothing.
- No absolute paths, secrets, or personal data.

By contributing you agree your work is licensed under the repository's MIT
License and you accept the project [Disclaimer](DISCLAIMER.md).
