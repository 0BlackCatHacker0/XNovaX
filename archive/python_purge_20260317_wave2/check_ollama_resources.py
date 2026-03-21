"""Check Ollama resource usage."""
import subprocess, json

r = subprocess.run(
    ["powershell", "-Command",
     "Get-Process -Name ollama*,ollama_runners* -EA SilentlyContinue | Select Id,Name,WorkingSet64,CPU | ConvertTo-Json"],
    capture_output=True, text=True, timeout=10,
    creationflags=0x08000000
)
if r.stdout.strip():
    data = json.loads(r.stdout)
    if isinstance(data, dict):
        data = [data]
    total_ram = 0
    for p in data:
        ram = p.get("WorkingSet64", 0) // 1024 // 1024
        cpu = p.get("CPU") or 0
        total_ram += ram
        print(f"PID={p['Id']} {p['Name']} RAM={ram}MB CPU={cpu:.0f}s")
    print(f"--- Total Ollama RAM: {total_ram}MB")
else:
    print("No Ollama processes found")

# Check GPU usage
r2 = subprocess.run(
    ["powershell", "-Command",
     "nvidia-smi --query-gpu=utilization.gpu,utilization.memory,memory.used,memory.total --format=csv,noheader,nounits 2>$null"],
    capture_output=True, text=True, timeout=5,
    creationflags=0x08000000
)
if r2.stdout.strip():
    parts = r2.stdout.strip().split(", ")
    if len(parts) >= 4:
        print(f"GPU: {parts[0]}% util, VRAM: {parts[2]}MB/{parts[3]}MB ({parts[1]}% util)")

# Check loaded models
import urllib.request
try:
    resp = urllib.request.urlopen("http://127.0.0.1:11434/api/ps", timeout=3)
    data = json.loads(resp.read())
    models = data.get("models", [])
    print(f"Models in VRAM: {len(models)}")
    for m in models:
        name = m.get("name", "?")
        vram = m.get("size_vram", 0) // 1024 // 1024
        size = m.get("size", 0) // 1024 // 1024
        print(f"  {name}: {vram}MB VRAM, {size}MB total")
except:
    print("Ollama API not responding")
