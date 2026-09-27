@echo off
chcp 65001 >nul
title HMS setup

if not exist "%~dp0setup.ps1" (
    echo setup.ps1 not found next to this file.
    pause
    exit /b 1
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1"

if errorlevel 1 (
    echo.
    echo Script exited with an error.
)
pause