# One-click run scripts for Windows

## run_gui.bat (launch the desktop app)

```bat
@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m osint_toolkit %*
) else (
  python -m osint_toolkit %*
)
endlocal
```

## run_cli.bat (CLI help)

```bat
@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m osint_toolkit list
) else (
  python -m osint_toolkit list
)
endlocal
```

## run_web.bat (optional loopback web view)

```bat
@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m osint_toolkit web --host 127.0.0.1 --port 8765
) else (
  python -m osint_toolkit web --host 127.0.0.1 --port 8765
)
endlocal
```

Put these in the repo root (the folder you cloned).
Users can double-click `run_gui.bat` to start the app on Windows.
