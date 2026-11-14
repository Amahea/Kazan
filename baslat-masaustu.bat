@echo off
title Kazan - Masaustu
cd /d "%~dp0"
python masaustu.py
if errorlevel 1 (
    echo.
    echo Program baslatilamadi.
    echo Python kurulu degilse: python.org adresinden indirip kurun.
    echo Masaustu penceresi icin:  pip install pywebview
    echo.
    pause
)
