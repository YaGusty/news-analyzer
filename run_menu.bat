@echo off
chcp 65001 >nul
title News Analyzer — Macro Intelligence Command Center
cd /d "%~dp0"
python scripts\main.py menu
pause
