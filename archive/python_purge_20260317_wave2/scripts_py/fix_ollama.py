"""Configure Ollama for minimal resource usage and restart it."""
import subprocess, os, time, json, urllib.request

CREATE_NO_WINDOW = 0x08000000

# Set Ollama environment variables (persist across reboots)
env_vars = {
    "OLLAMA_MAX_LOADED_MODELS": "1",    # Only 1 model in VRAM at a time
    "OLLAMA_NUM_PARALLEL": "1",          # No parallel inference (saves VRAM)
    "OLLAMA_KEEP_ALIVE": "5m",           # Unload after 5 min idle
    "OLLAMA_FLASH_ATTENTION": "1",       # Enable flash attention (less VRAM)
}

print("Setting Ollama environment variables...")
for key, val in env_vars.items():
    subprocess.run(
        ["powershell", "-Command",
         f"[Environment]::SetEnvironmentVariable('{key}','{val}','User')"],
        capture_output=True, creationflags=CREATE_NO_WINDOW
    )
    os.environ[key] = val
    print(f"  {key}={val}")

# Kill existing Ollama processes
print("\nKilling existing Ollama processes...")
subprocess.run(["taskkill", "/F", "/IM", "ollama.exe"],
               capture_output=True, creationflags=CREATE_NO_WINDOW)
subprocess.run(["taskkill", "/F", "/IM", "ollama_runners.exe"],
               capture_output=True, creationflags=CREATE_NO_WINDOW)
time.sleep(3)

# Restart Ollama with env vars applied
print("Starting Ollama serve...")
env = os.environ.copy()
for key, val in env_vars.items():
    env[key] = val

subprocess.Popen(
    [r"C:\Users\Jupit\AppData\Local\Programs\Ollama\ollama.exe", "serve"],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    creationflags=CREATE_NO_WINDOW, env=env
)

# Wait for API
print("Waiting for Ollama API...")
for i in range(20):
    time.sleep(2)
    try:
        resp = urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=3)
        data = json.loads(resp.read())
        models = data.get("models", [])
        print(f"Ollama UP: {len(models)} models available")
        break
    except:
        if i % 3 == 0:
            print(f"  ...waiting ({i*2}s)")
else:
    print("Ollama failed to start within 40s")
    exit(1)

# Verify low resource state
print("\nVerifying resource state:")
try:
    resp = urllib.request.urlopen("http://127.0.0.1:11434/api/ps", timeout=3)
    data = json.loads(resp.read())
    loaded = data.get("models", [])
    if loaded:
        for m in loaded:
            print(f"  Loaded: {m['name']} ({m.get('size_vram',0)//1024//1024}MB VRAM)")
    else:
        print("  No models loaded (VRAM free)")
except:
    print("  Could not check loaded models")

print("\nOllama configured for minimal resource usage:")
print("  - Max 1 model in VRAM at any time")
print("  - No parallel inference")
print("  - Auto-unload after 5 min idle")
print("  - Flash attention enabled")
