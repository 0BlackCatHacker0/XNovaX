Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'nova_tspin' } | ForEach-Object {
    Write-Host "Killing PID $($_.ProcessId)"
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
}
Write-Host "Done"
