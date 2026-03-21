@echo off
echo ============================================ > C:\NovaX\config\servers\logs\install_all.log
echo NovaX Server Stack Installation >> C:\NovaX\config\servers\logs\install_all.log
echo Started: %date% %time% >> C:\NovaX\config\servers\logs\install_all.log
echo ============================================ >> C:\NovaX\config\servers\logs\install_all.log

echo [1/12] Installing PostgreSQL 17... >> C:\NovaX\config\servers\logs\install_all.log
winget install PostgreSQL.PostgreSQL.17 --accept-package-agreements --accept-source-agreements --silent 2>&1 >> C:\NovaX\config\servers\logs\install_all.log
echo [1/12] PostgreSQL DONE >> C:\NovaX\config\servers\logs\install_all.log

echo [2/12] Installing Redis (Memurai)... >> C:\NovaX\config\servers\logs\install_all.log
winget install Memurai.MemuraiDeveloper --accept-package-agreements --accept-source-agreements --silent 2>&1 >> C:\NovaX\config\servers\logs\install_all.log
echo [2/12] Redis DONE >> C:\NovaX\config\servers\logs\install_all.log

echo [3/12] Installing Caddy (reverse proxy)... >> C:\NovaX\config\servers\logs\install_all.log
winget install CaddyServer.Caddy --accept-package-agreements --accept-source-agreements --silent 2>&1 >> C:\NovaX\config\servers\logs\install_all.log
echo [3/12] Caddy DONE >> C:\NovaX\config\servers\logs\install_all.log

echo [4/12] Installing NATS (message queue)... >> C:\NovaX\config\servers\logs\install_all.log
winget install NATS.NATSServer --accept-package-agreements --accept-source-agreements --silent 2>&1 >> C:\NovaX\config\servers\logs\install_all.log
echo [4/12] NATS DONE >> C:\NovaX\config\servers\logs\install_all.log

echo [5/12] Installing Meilisearch... >> C:\NovaX\config\servers\logs\install_all.log
winget install Meilisearch.Meilisearch --accept-package-agreements --accept-source-agreements --silent 2>&1 >> C:\NovaX\config\servers\logs\install_all.log
echo [5/12] Meilisearch DONE >> C:\NovaX\config\servers\logs\install_all.log

echo [6/12] Installing Grafana... >> C:\NovaX\config\servers\logs\install_all.log
winget install Grafana.Grafana.OSS --accept-package-agreements --accept-source-agreements --silent 2>&1 >> C:\NovaX\config\servers\logs\install_all.log
echo [6/12] Grafana DONE >> C:\NovaX\config\servers\logs\install_all.log

echo [7/12] Installing Prometheus... >> C:\NovaX\config\servers\logs\install_all.log
winget install Prometheus.Prometheus --accept-package-agreements --accept-source-agreements --silent 2>&1 >> C:\NovaX\config\servers\logs\install_all.log
echo [7/12] Prometheus DONE >> C:\NovaX\config\servers\logs\install_all.log

echo [8/12] Installing MinIO... >> C:\NovaX\config\servers\logs\install_all.log
winget install MinIO.MinIO --accept-package-agreements --accept-source-agreements --silent 2>&1 >> C:\NovaX\config\servers\logs\install_all.log
echo [8/12] MinIO DONE >> C:\NovaX\config\servers\logs\install_all.log

echo [9/12] Installing Gitea... >> C:\NovaX\config\servers\logs\install_all.log
winget install Gitea.Gitea --accept-package-agreements --accept-source-agreements --silent 2>&1 >> C:\NovaX\config\servers\logs\install_all.log
echo [9/12] Gitea DONE >> C:\NovaX\config\servers\logs\install_all.log

echo [10/12] Installing Mosquitto (MQTT)... >> C:\NovaX\config\servers\logs\install_all.log
winget install EclipseFoundation.Mosquitto --accept-package-agreements --accept-source-agreements --silent 2>&1 >> C:\NovaX\config\servers\logs\install_all.log
echo [10/12] Mosquitto DONE >> C:\NovaX\config\servers\logs\install_all.log

echo [11/12] Installing PM2 (process manager)... >> C:\NovaX\config\servers\logs\install_all.log
npm install -g pm2 2>&1 >> C:\NovaX\config\servers\logs\install_all.log
echo [11/12] PM2 DONE >> C:\NovaX\config\servers\logs\install_all.log

echo [12/12] Installing Syncthing (backup/sync)... >> C:\NovaX\config\servers\logs\install_all.log
winget install Syncthing.Syncthing --accept-package-agreements --accept-source-agreements --silent 2>&1 >> C:\NovaX\config\servers\logs\install_all.log
echo [12/12] Syncthing DONE >> C:\NovaX\config\servers\logs\install_all.log

echo ============================================ >> C:\NovaX\config\servers\logs\install_all.log
echo ALL INSTALLATIONS COMPLETE: %date% %time% >> C:\NovaX\config\servers\logs\install_all.log
echo ============================================ >> C:\NovaX\config\servers\logs\install_all.log
