@echo off
title NovaX Orchestrator v6.0.0 - 100%% Ternary Native
echo ============================================
echo   NovaX Orchestrator v6.0.0
echo   100%% Ternary Native - Zero Python
echo   Runtime: novalang.exe (Rust VM)
echo ============================================
echo.

REM Start external infrastructure (Redis, Ollama)
echo [1/3] Starting Redis...
start /B C:\NovaX\servers\redis\redis-server.exe >nul 2>&1
timeout /t 1 >nul

echo [2/3] Starting Ollama...
start /B ollama serve >nul 2>&1
timeout /t 2 >nul

echo [3/3] Starting NovaX Orchestrator (90 services)...
echo     This will take ~60 seconds to boot all services.
echo.

C:\NovaX\novalang.exe C:\NovaX\nova_orchestrator.nova

pause
