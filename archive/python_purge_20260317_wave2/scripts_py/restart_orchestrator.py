"""
Restart the NovaX orchestrator.
Spawned detached — kills old process, waits, starts new one.
"""
import subprocess
import time
import os

ORCHESTRATOR_PID = 13120
PYTHON = r"C:\Users\Jupit\AppData\Local\Programs\Python\Python312\python.exe"
SCRIPT = r"C:\NovaX\core\orchestrator.py"
LOG = r"C:\NovaX\logs\orchestrator_restart.log"
CREATE_NO_WINDOW = 0x08000000

print(f"[restart] Killing PID {ORCHESTRATOR_PID}...")
result = subprocess.run(
    ["taskkill", "/PID", str(ORCHESTRATOR_PID), "/F", "/T"],
    capture_output=True, text=True,
    creationflags=CREATE_NO_WINDOW
)
print(f"[restart] Kill result: {result.stdout} {result.stderr}")

print("[restart] Waiting 3 seconds for port release...")
time.sleep(3)

print("[restart] Starting new orchestrator...")
os.makedirs(os.path.dirname(LOG), exist_ok=True)
proc = subprocess.Popen(
    [PYTHON, SCRIPT],
    stdout=open(LOG, "w"),
    stderr=subprocess.STDOUT,
    creationflags=CREATE_NO_WINDOW
)
print(f"[restart] New orchestrator PID: {proc.pid}")

# Wait and verify
time.sleep(5)
import urllib.request
try:
    resp = urllib.request.urlopen("http://127.0.0.1:9999/health", timeout=5)
    data = resp.read().decode()
    print(f"[restart] Health check: {data[:200]}")
except Exception as e:
    print(f"[restart] Health check failed: {e}")
