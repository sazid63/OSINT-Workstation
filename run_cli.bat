@echo off
REM OSINT Workstation — CLI entry point
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" osint.py %*
) else (
  python osint.py %*
)
endlocal