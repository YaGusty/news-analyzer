@echo off
chcp 65001 >nul
cd /d "%~dp0"
python scripts\main.py scheduler --start-bg
timeout /t 2 >nul
python scripts\main.py scheduler --status
pause
