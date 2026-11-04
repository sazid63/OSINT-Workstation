@echo off
REM OSINT Toolkit — Web UI entry point (MCP + FastAPI)
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m osint_toolkit.web.server %*
) else (
  python -m osint_toolkit.web.server %*
)
endlocal