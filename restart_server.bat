@echo off
timeout /t 2 /nobreak >nul
taskkill /PID 65544 /F >nul 2>&1
timeout /t 1 /nobreak >nul
cd /d C:\ProgramData\NovaX\app\shell\static
start "" "C:\Python314\python.exe" novax_core.py --root C:\ProgramData\NovaX\app\shell\static --port 9999
