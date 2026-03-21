"""Check what sihost.exe is spawning."""
import subprocess, json

r = subprocess.run(
    ["powershell", "-Command",
     "Get-CimInstance Win32_Process -Filter 'ParentProcessId=15768' | Select ProcessId,Name,CommandLine | ConvertTo-Json"],
    capture_output=True, text=True, timeout=10,
    creationflags=0x08000000
)
if r.stdout.strip():
    data = json.loads(r.stdout)
    if isinstance(data, dict):
        data = [data]
    for p in data:
        print(f"PID={p['ProcessId']} Name={p['Name']}")
        cmd = (p.get('CommandLine') or '')[:200]
        if cmd:
            print(f"  CMD: {cmd}")
else:
    print("No child processes of sihost (PID 15768)")
    if r.stderr:
        print(f"Error: {r.stderr[:300]}")
