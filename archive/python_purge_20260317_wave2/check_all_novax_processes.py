"""Find all NovaX-related Python processes and their resource usage."""
import subprocess, json

r = subprocess.run(
    ["powershell", "-Command",
     "Get-CimInstance Win32_Process -Filter \"Name='python.exe' or Name='pythonw.exe'\" | Select ProcessId,CommandLine,WorkingSet64 | ConvertTo-Json"],
    capture_output=True, text=True, timeout=10,
    creationflags=0x08000000
)
if not r.stdout.strip():
    print("No Python processes found")
    exit()

data = json.loads(r.stdout)
if isinstance(data, dict):
    data = [data]

total_ram = 0
nova_count = 0
for p in data:
    cmd = p.get("CommandLine") or ""
    ram = (p.get("WorkingSet64") or 0) // 1024 // 1024
    pid = p.get("ProcessId", "?")
    total_ram += ram
    if "nova" in cmd.lower() or "NovaX" in cmd:
        nova_count += 1
        # Extract script name
        parts = cmd.split()
        script = parts[-1] if parts else "?"
        script = script.split("\\")[-1].split("/")[-1]
        print(f"PID={pid:>6} RAM={ram:>4}MB  {script}")

print(f"--- NovaX Python processes: {nova_count}, Total RAM: {total_ram}MB")
print(f"--- All Python processes: {len(data)}")
