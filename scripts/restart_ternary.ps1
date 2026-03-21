# Kill ternary server and restart it
$ternPid = (Get-NetTCPConnection -LocalPort 9885 -State Listen -ErrorAction SilentlyContinue).OwningProcess | Select-Object -First 1
if ($ternPid) {
    Write-Host "Killing ternary server PID $ternPid"
    Stop-Process -Id $ternPid -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
}

# Relaunch with CREATE_NO_WINDOW
$si = New-Object System.Diagnostics.ProcessStartInfo
$si.FileName = "C:\Users\Jupit\AppData\Local\Programs\Python\Python312\pythonw.exe"
$si.Arguments = "C:\NovaX\nova_ternary_server.py"
$si.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden
$si.CreateNoWindow = $true
$proc = [System.Diagnostics.Process]::Start($si)
Write-Host "Launched ternary server PID $($proc.Id)"
Start-Sleep -Seconds 5
Write-Host "Done"
