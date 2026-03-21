@echo off
echo === NovaX Server Startup ===
echo Starting all services...

echo [1/8] Redis...
start /B C:\NovaX\servers\redis\redis-server.exe
timeout /t 1 >nul

echo [2/8] Meilisearch...
start /B C:\NovaX\servers\meilisearch\meilisearch.exe --db-path C:\NovaX\servers\meilisearch\data
timeout /t 1 >nul

echo [3/8] Caddy...
start /B C:\NovaX\servers\caddy\caddy.exe run --config C:\NovaX\servers\caddy\Caddyfile
timeout /t 1 >nul

echo [4/8] Nova Relay...
start /B node C:\NovaX\nova_relay.js
timeout /t 1 >nul

echo [5/8] Cloud Router...
start /B C:\Users\Jupit\AppData\Local\Programs\Python\Python312\python.exe C:\NovaX\nova_cloud_router.py
timeout /t 1 >nul

echo [6/8] Ollama...
start /B ollama serve
timeout /t 2 >nul

echo [7/8] Nova Bridge...
start /B C:\Users\Jupit\AppData\Local\Programs\Python\Python312\python.exe C:\NovaX\novax\main.py
timeout /t 2 >nul

echo [8/8] STT Server...
start /B C:\Users\Jupit\AppData\Local\Programs\Python\Python312\python.exe C:\NovaX\whisper_stt_server.py
timeout /t 1 >nul

echo === All servers started ===
echo Servers: Redis:6379 Meili:7700 Caddy:8080 Relay:9877 Router:9878 Ollama:11434 Bridge:9999 STT:9876
echo UI: http://localhost:9999/static/index.html
echo Super Archive: http://localhost:9999/static/super_archive.html
pause
