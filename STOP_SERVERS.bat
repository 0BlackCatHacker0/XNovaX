@echo off
echo Stopping all NovaX services...
taskkill /F /IM novalang.exe 2>nul
taskkill /F /IM redis-server.exe 2>nul
taskkill /F /IM ollama.exe 2>nul
echo All services stopped.
pause
