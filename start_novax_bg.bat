@echo off
REM NovaX Background Launcher - starts orchestrator without visible window
REM External infra
start /B C:\NovaX\servers\redis\redis-server.exe >nul 2>&1
start /B ollama serve >nul 2>&1
timeout /t 2 >nul
REM Main orchestrator
start /B C:\NovaX\novalang.exe C:\NovaX\nova_orchestrator.nova >C:\NovaX\nova_boot.log 2>&1
