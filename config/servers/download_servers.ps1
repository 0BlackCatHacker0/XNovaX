$ErrorActionPreference = "Continue"
$base = "C:\NovaX\servers"
New-Item -ItemType Directory -Force -Path $base | Out-Null
$log = "C:\NovaX\config\servers\logs\download_ps.log"
Add-Content $log "=== Download Session $(Get-Date) ==="

function DL($Name, $Url, $Out) {
  Write-Host "[DL] $Name..."
  try {
    $ProgressPreference = "SilentlyContinue"
    Invoke-WebRequest -Uri $Url -OutFile $Out -UseBasicParsing
    $s = (Get-Item $Out).Length
    Write-Host "[OK] $Name - $([math]::Round($s/1MB,1)) MB" -ForegroundColor Green
    Add-Content $log "OK: $Name ($s bytes)"
  } catch {
    Write-Host "[FAIL] $Name - $_" -ForegroundColor Red
    Add-Content $log "FAIL: $Name - $_"
  }
}

# Redis
New-Item -ItemType Directory -Force -Path "$base\redis" | Out-Null
DL "Redis" "https://github.com/tporadowski/redis/releases/download/v5.0.14.1/Redis-x64-5.0.14.1.zip" "$base\redis\redis.zip"

# NATS
New-Item -ItemType Directory -Force -Path "$base\nats" | Out-Null
DL "NATS" "https://github.com/nats-io/nats-server/releases/download/v2.10.24/nats-server-v2.10.24-windows-amd64.zip" "$base\nats\nats.zip"

# Meilisearch
New-Item -ItemType Directory -Force -Path "$base\meilisearch" | Out-Null
DL "Meilisearch" "https://github.com/meilisearch/meilisearch/releases/download/v1.12.8/meilisearch-windows-amd64.exe" "$base\meilisearch\meilisearch.exe"

# Grafana
New-Item -ItemType Directory -Force -Path "$base\grafana" | Out-Null
DL "Grafana" "https://dl.grafana.com/oss/release/grafana-11.5.2.windows-amd64.zip" "$base\grafana\grafana.zip"

# Prometheus
New-Item -ItemType Directory -Force -Path "$base\prometheus" | Out-Null
DL "Prometheus" "https://github.com/prometheus/prometheus/releases/download/v3.2.1/prometheus-3.2.1.windows-amd64.zip" "$base\prometheus\prometheus.zip"

# MinIO
New-Item -ItemType Directory -Force -Path "$base\minio" | Out-Null
DL "MinIO" "https://dl.min.io/server/minio/release/windows-amd64/minio.exe" "$base\minio\minio.exe"

# Gitea
New-Item -ItemType Directory -Force -Path "$base\gitea" | Out-Null
DL "Gitea" "https://github.com/go-gitea/gitea/releases/download/v1.23.4/gitea-1.23.4-gogit-windows-4.0-amd64.exe" "$base\gitea\gitea.exe"

# Node-RED
Write-Host "[NPM] Node-RED..."
npm install -g --unsafe-perm node-red 2>&1 | Select-Object -Last 5
Add-Content $log "Node-RED npm done"

Write-Host "[COMPLETE] All downloads finished." -ForegroundColor Green
Add-Content $log "Session complete $(Get-Date)"