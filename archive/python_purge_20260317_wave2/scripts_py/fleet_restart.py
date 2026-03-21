"""
Rolling fleet restart — stops and restarts all NovaX services.
Preserves orchestrator (9999), restarts everything else.
Uses CREATE_NO_WINDOW to avoid blue shells.
"""
import json
import os
import socket
import subprocess
import time
import urllib.request

CREATE_NO_WINDOW = 0x08000000
NOVA_DIR = r"C:\NovaX"

# Services to NOT restart (orchestrator must stay alive)
SKIP_RESTART = {9999}

# External services we can't restart
EXTERNAL = {6379, 7700, 11434}  # redis, meili, ollama


def find_service_file(service_name, port):
    """Find the Python file for a service."""
    # Try common patterns
    candidates = [
        os.path.join(NOVA_DIR, "nova_%s.py" % service_name.replace("nova-", "").replace("-", "_")),
        os.path.join(NOVA_DIR, "nova_%s.py" % service_name.replace("-", "_")),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None


def discover_services():
    """Find all live services."""
    live = []
    for port in range(9870, 10000):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.2)
            if s.connect_ex(("127.0.0.1", port)) == 0:
                s.close()
                try:
                    resp = urllib.request.urlopen(
                        "http://127.0.0.1:%d/health" % port, timeout=1
                    )
                    data = json.loads(resp.read())
                    name = data.get("service", "unknown")
                    live.append((port, name))
                except Exception:
                    live.append((port, "unknown"))
            else:
                s.close()
        except Exception:
            pass
    return live


def kill_port(port):
    """Kill the process on a port."""
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-NetTCPConnection -LocalPort %d -ErrorAction SilentlyContinue | "
             "ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }" % port],
            capture_output=True, timeout=5, creationflags=CREATE_NO_WINDOW
        )
        return True
    except Exception:
        return False


def start_service(filepath, port):
    """Start a service headlessly."""
    try:
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 0
        proc = subprocess.Popen(
            ["python", filepath],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            creationflags=CREATE_NO_WINDOW, startupinfo=si, close_fds=True
        )
        return proc.pid
    except Exception as e:
        return None


def main():
    print("[FleetRestart] Discovering live services...")
    services = discover_services()
    print("[FleetRestart] Found %d services" % len(services))

    # Find restartable services
    restartable = []
    for port, name in services:
        if port in SKIP_RESTART:
            print("  SKIP: %s:%d (orchestrator)" % (name, port))
            continue
        if port in EXTERNAL:
            print("  SKIP: %s:%d (external)" % (name, port))
            continue
        filepath = find_service_file(name, port)
        if filepath:
            restartable.append((port, name, filepath))
        else:
            print("  SKIP: %s:%d (no file found)" % (name, port))

    print("\n[FleetRestart] Restarting %d services in waves of 7..." % len(restartable))

    restarted = 0
    failed = 0
    wave_size = 7
    wave_pause = 1.0

    for i in range(0, len(restartable), wave_size):
        wave = restartable[i:i + wave_size]
        wave_num = (i // wave_size) + 1
        print("\n  Wave %d: %s" % (wave_num, ", ".join("%s:%d" % (n, p) for p, n, _ in wave)))

        # Kill all in this wave
        for port, name, filepath in wave:
            kill_port(port)

        time.sleep(0.5)  # let ports release

        # Start all in this wave
        for port, name, filepath in wave:
            pid = start_service(filepath, port)
            if pid:
                restarted += 1
            else:
                failed += 1
                print("    FAIL: %s:%d" % (name, port))

        time.sleep(wave_pause)

    # Wait for services to come up
    print("\n[FleetRestart] Waiting 5s for services to initialize...")
    time.sleep(5)

    # Verify
    print("[FleetRestart] Verifying...")
    alive = 0
    dead = []
    for port, name, filepath in restartable:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            if s.connect_ex(("127.0.0.1", port)) == 0:
                alive += 1
            else:
                dead.append("%s:%d" % (name, port))
            s.close()
        except Exception:
            dead.append("%s:%d" % (name, port))

    print("\n[FleetRestart] Complete:")
    print("  Restarted: %d" % restarted)
    print("  Alive: %d" % alive)
    print("  Failed: %d" % failed)
    if dead:
        print("  Dead: %s" % ", ".join(dead))

    print("\n[FleetRestart] Done. Run fleet_audit.py to check health times.")


if __name__ == "__main__":
    main()
