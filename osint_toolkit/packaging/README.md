# Installer scripts for Windows (standalone .exe → Inno Setup)

## Build standalone .exe with PyInstaller (one-folder recommended)

Recommended: one-folder build (fewer false-positive AV flags, easier to debug).

```bash
cd osint-toolkit
uv venv
.venv\Scripts\activate
uv pip install -e ".[mcp]" pyinstaller
pyinstaller --name "OSINT-Toolkit" --noconsole --windowed ^
  --add-data "osint_toolkit/catalog;osint_toolkit/catalog" ^
  --add-data "osint_toolkit/web;osint_toolkit/web" ^
  --hidden-import=phonenumbers ^
  --hidden-import=dnspython ^
  --hidden-import=whois ^
  --hidden-import=ipwhois ^
  --hidden-import=keyring.backends.Windows ^
  osint_toolkit\ui\app.py
```

Output: `dist/OSINT-Toolkit/` (folder containing the .exe and DLLs).

## Create installer with Inno Setup

Use Inno Setup (free/open-source) with this script. Save as
`packaging/OSINT-Toolkit.iss`.

```text
; OSINT Toolkit Inno Setup script (template)
; Edit AppVersion and SourceDir to match your build.
```

A ready-to-edit template is provided below; the installer creates Start Menu
entry, Desktop shortcut, and uninstaller. The app stores user data under
`%LOCALAPPDATA%\OSINT Toolkit` — never inside the install folder.

## SHA-256 checksums

After building, compute checksums for the installer and upload them to GitHub
Releases:

```powershell
Get-FileHash "dist\OSINT-Toolkit-Setup-*.exe" -Algorithm SHA256
```
