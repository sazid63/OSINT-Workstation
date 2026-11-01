@echo off
REM OSINT Terminal launcher
set "PATH=%APPDATA%\Python\Python314\Scripts;%PATH%"
cd /d "%~dp0"
python osint.py %*
