@echo off
chcp 65001 >nul
title News Analyzer — Live Sniping Console
cd /d "%~dp0"
python scripts\main.py scheduler --daemon
pause
