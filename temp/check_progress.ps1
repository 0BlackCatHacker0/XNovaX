Write-Host "=== INSTALL PROGRESS ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "--- PIP (django, fastapi, langchain, etc) ---" -ForegroundColor Yellow
if(Test-Path C:\NovaX\temp\pip2_log.txt){Get-Content C:\NovaX\temp\pip2_log.txt | Select-String "done|DONE|error|ERROR" | Select-Object -Last 5}else{Write-Host "Not started"}
Write-Host ""
Write-Host "--- NPM (pnpm, yarn) ---" -ForegroundColor Yellow
if(Test-Path C:\NovaX\temp\npm2_log.txt){Get-Content C:\NovaX\temp\npm2_log.txt | Select-String "done|DONE|error|ERROR" | Select-Object -Last 3}else{Write-Host "Not started"}
Write-Host ""
Write-Host "--- CHOCO (godot, gimp, inkscape, wireshark, etc) ---" -ForegroundColor Yellow
if(Test-Path C:\NovaX\temp\choco2_log.txt){Get-Content C:\NovaX\temp\choco2_log.txt | Select-String "done|DONE|error|ERROR|installed" | Select-Object -Last 5}else{Write-Host "Not started"}
Write-Host ""
Write-Host "--- BIG (CUDA, PyTorch, TF) ---" -ForegroundColor Yellow
if(Test-Path C:\NovaX\temp\big_log.txt){Get-Content C:\NovaX\temp\big_log.txt | Select-String "done|DONE|error|ERROR|installed" | Select-Object -Last 5}else{Write-Host "Not started"}