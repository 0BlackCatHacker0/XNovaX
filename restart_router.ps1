$conn = Get-NetTCPConnection -LocalPort 9878 -ErrorAction SilentlyContinue
if ($conn) {
    $pid = $conn.OwningProcess | Select-Object -First 1
    Stop-Process -Id $pid -Force
    Write-Host "Killed process on port 9878 (PID: $pid)"
} else {
    Write-Host "No process on 9878"
}
Start-Sleep -Seconds 2
# Restart cloud router
Start-Process -FilePath "C:\NovaX\novalang.exe" -ArgumentList "C:\NovaX\nova_cloud_router_service.nova" -WindowStyle Hidden
Write-Host "Cloud router restarted"
