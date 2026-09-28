@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_autostart.ps1"
echo.
pause
