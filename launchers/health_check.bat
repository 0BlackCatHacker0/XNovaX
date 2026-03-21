@echo off
title NovaX Health Check
powershell -Command "$h=@{9877='Exec Server';9990='NovaX Brain';9999='Bridge';11434='Ollama';18789='OpenClaw'};foreach($p in $h.Keys){$t=Test-NetConnection 127.0.0.1 -Port $p -WA Silent;if($t.TcpTestSucceeded){Write-Host '[ON] ' $h[$p] $p -Fore Green}else{Write-Host '[OFF]' $h[$p] $p -Fore Red}}"
pause