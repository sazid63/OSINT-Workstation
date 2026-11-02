@echo off
REM OSINT Terminal launcher - uses system PATH
cd /d "%~dp0"
python osint.py %*
