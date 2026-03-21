@echo off
echo ========================================
echo  NovaX Server Infrastructure Launcher
echo  Dependency Order (Section 7)
echo ========================================

echo [1/6] DATABASE LAYER...
echo   PostgreSQL: Windows service (auto)
echo   Redis...
start /B C:\NovaX\servers\redis\redis-server.exe --port 6379 --bind 127.0.0.1
timeout /t 3 >nul

echo [2/6] CACHE + SEARCH...
start /B C:\NovaX\servers\meilisearch\meilisearch.exe --http-addr 127.0.0.1:7700 --db-path C:\NovaX\servers\meilisearch\data.ms
timeout /t 3 >nul

echo [3/6] MESSAGING...
start /B C:\NovaX\servers\nats\nats-server-v2.10.24-windows-amd64\nats-server.exe -a 127.0.0.1 -p 4222
echo   Mosquitto: Windows service (auto)
timeout /t 3 >nul

echo [4/6] APP SERVICES...
start /B C:\NovaX\servers\gitea\gitea.exe --port 3001
start /B npx node-red -p 1880
set MINIO_ROOT_USER=novax
set MINIO_ROOT_PASSWORD=novax_s3cure
start /B C:\NovaX\servers\minio\minio.exe server C:\NovaX\servers\minio\data --address :9000 --console-address :9001
timeout /t 5 >nul

echo [5/6] REVERSE PROXY...
start /B C:\NovaX\servers\caddy\caddy.exe run --config C:\NovaX\config\servers\caddy\Caddyfile
timeout /t 3 >nul

echo [6/6] MONITORING...
start /B C:\NovaX\servers\prometheus\prometheus.exe --config.file=C:\NovaX\config\servers\prometheus\prometheus.yml --web.listen-address=:9090
start /B C:\NovaX\servers\grafana\bin\grafana.exe server --homepath C:\NovaX\servers\grafana
timeout /t 5 >nul

echo ========================================
echo  Running health check...
echo ========================================
C:\Users\Jupit\AppData\Local\Programs\Python\Python312\python.exe C:\NovaX\config\servers\health\novax_supervisor.py
pause