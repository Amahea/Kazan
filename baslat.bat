@echo off
title Dukkan Takip Programi
cd /d "%~dp0"
python uygulama.py
if errorlevel 1 (
    echo.
    echo Program baslatilamadi.
    echo Python kurulu degilse: python.org adresinden indirip kurun.
    echo.
    pause
)
