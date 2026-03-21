@echo off
title NovaX - STOP ALL
powershell -Command "9877,9990,9999,9998,18789|ForEach{try{Stop-Process -Id (Get-NetTCPConnection -LocalPort $_ -EA Stop).OwningProcess -Force -EA Stop;Write-Host Killed $_}catch{Write-Host $_ clean}}"
pause