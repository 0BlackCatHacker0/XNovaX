"""Kill old service creator, start new one, run tests."""
import subprocess
import socket
import time
import os
import signal

HOST = "127.0.0.1"
PORT = 9942

def kill_port(port):
    """Kill whatever is listening on this port."""
    try:
        result = subprocess.run(
            ["netstat", "-ano"], capture_output=True, text=True
        )
        for line in result.stdout.splitlines():
            if f":{port}" in line and "LISTENING" in line:
                parts = line.split()
                pid = int(parts[-1])
                try:
                    os.kill(pid, signal.SIGTERM)
                    time.sleep(0.5)
                except Exception:
                    pass
                try:
                    subprocess.run(["taskkill", "/F", "/PID", str(pid)],
                                   capture_output=True)
                except Exception:
                    pass
    except Exception as e:
        print(f"kill_port error: {e}")

def wait_for_port(port, timeout=10):
    start = time.time()
    while time.time() - start < timeout:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.2)
            s.connect((HOST, port))
            s.close()
            return True
        except Exception:
            time.sleep(0.3)
    return False

# Step 1: Kill old
print("[1] Killing old service on port 9942...")
kill_port(PORT)
time.sleep(1)

# Step 2: Start new
print("[2] Starting nova_service_creator.py...")
proc = subprocess.Popen(
    [r"C:\Python314\pythonw.exe", r"C:\NovaX\nova_service_creator.py"],
    creationflags=0x08000000,
)
print(f"    PID: {proc.pid}")

# Step 3: Wait for it
print("[3] Waiting for port 9942...")
if not wait_for_port(PORT):
    print("    FAILED - service did not start!")
    exit(1)
print("    Service is UP!")

# Step 4: Run tests
print("[4] Running tests...\n")
subprocess.run([r"C:\Python314\python.exe", r"C:\NovaX\test_service_creator.py"])
