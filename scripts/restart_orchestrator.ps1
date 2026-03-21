# Restart the orchestrator
$orchPid = (Get-NetTCPConnection -LocalPort 9999 -State Listen -ErrorAction SilentlyContinue).OwningProcess | Select-Object -First 1
if ($orchPid) {
    Write-Host "Killing orchestrator PID $orchPid"
    Stop-Process -Id $orchPid -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 3
}

# Relaunch
$si = New-Object System.Diagnostics.ProcessStartInfo
$si.FileName = "C:\Users\Jupit\AppData\Local\Programs\Python\Python312\pythonw.exe"
$si.Arguments = "C:\NovaX\core\orchestrator.py"
$si.WorkingDirectory = "C:\NovaX"
$si.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden
$si.CreateNoWindow = $true
$proc = [System.Diagnostics.Process]::Start($si)
Write-Host "Launched orchestrator PID $($proc.Id)"
Start-Sleep -Seconds 5
Write-Host "Done"
