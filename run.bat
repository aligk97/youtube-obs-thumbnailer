@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" thumbnailer.py run --config config.json
) else (
  py thumbnailer.py run --config config.json
)
