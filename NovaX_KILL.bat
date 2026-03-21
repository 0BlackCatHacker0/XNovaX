@echo off
title NovaX Emergency Kill Switch
color 4F
echo.
echo  ╔══════════════════════════════════════════════╗
echo  ║     NovaX EMERGENCY KILL SWITCH              ║
echo  ║     Terminating all NovaX processes...        ║
echo  ╚══════════════════════════════════════════════╝
echo.

REM Kill all known NovaX service ports
for %%p in (9999 9990 9881 9882 9883 9884 9880 9878 9877 9875 9998 9885 9886 9887 9888 9889 9890) do (
    for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":%%p " ^| findstr "LISTENING"') do (
        echo Killing PID %%a (port %%p)
        taskkill /PID %%a /F >nul 2>&1
    )
)

REM Kill by process name patterns
taskkill /IM ollama.exe /F >nul 2>&1
taskkill /IM redis-server.exe /F >nul 2>&1
taskkill /IM meilisearch.exe /F >nul 2>&1
taskkill /IM caddy.exe /F >nul 2>&1

REM Kill NovaX python processes (match command line)
wmic process where "commandline like '%%NovaX%%' and name='python.exe'" call terminate >nul 2>&1
wmic process where "commandline like '%%nova_%%' and name='python.exe'" call terminate >nul 2>&1
wmic process where "commandline like '%%novax%%' and name='pythonw.exe'" call terminate >nul 2>&1

REM Restore explorer if needed
tasklist /FI "IMAGENAME eq explorer.exe" | find /I "explorer.exe" >nul
if errorlevel 1 (
    echo.
    echo  Explorer.exe was not running - restarting it now...
    start explorer.exe
)

echo.
echo  ╔══════════════════════════════════════════════╗
echo  ║     All NovaX processes terminated.           ║
echo  ║     Windows desktop restored.                 ║
echo  ╚══════════════════════════════════════════════╝
echo.
pause
