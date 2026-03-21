Set WshShell = CreateObject("WScript.Shell") 
WshShell.Run "cmd /c openclaw gateway --port 18789 > C:\NovaX\openclaw_gateway.log 2>&1", 0, False
