@echo off
cd /d "%~dp0"
python scripts\trigger_github_worker.py
pause
