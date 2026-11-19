@echo off
chcp 65001 >nul
cd /d "%~dp0"
python scripts\main.py scheduler --stop
timeout /t 1 >nul
python scripts\main.py scheduler --status
pause
