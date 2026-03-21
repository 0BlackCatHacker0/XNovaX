Get-NetTCPConnection -LocalPort 9880 -ErrorAction SilentlyContinue | ForEach-Object {
    $procId = $_.OwningProcess
    try {
        Stop-Process -Id $procId -Force -ErrorAction Stop
        Write-Host "Killed $procId"
    } catch {
        Write-Host "Cannot kill $procId (needs admin)"
    }
}
