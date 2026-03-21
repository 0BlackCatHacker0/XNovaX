"""NovaX Zombie Killer — find and kill ALL duplicate NovaX processes.
Keeps exactly 1 instance of each service. Kills watchdog FIRST to stop respawning."""
import subprocess, json, os, time

CREATE_NO_WINDOW = 0x08000000

def get_all_python_procs():
    """Get all Python processes with their command lines."""
    r = subprocess.run(
        ["powershell", "-Command",
         "Get-CimInstance Win32_Process -Filter \"Name='python.exe' or Name='pythonw.exe'\" "
         "| Select ProcessId,CommandLine | ConvertTo-Json"],
        capture_output=True, text=True, timeout=10,
        creationflags=CREATE_NO_WINDOW
    )
    if not r.stdout.strip():
        return []
    data = json.loads(r.stdout)
    return [data] if isinstance(data, dict) else data

def kill_pid(pid):
    """Kill a process by PID."""
    try:
        subprocess.run(["taskkill", "/F", "/PID", str(pid)],
                       capture_output=True, timeout=5, creationflags=CREATE_NO_WINDOW)
        return True
    except:
        return False

def main():
    my_pid = os.getpid()
    procs = get_all_python_procs()

    # Group by script name
    by_script = {}
    for p in procs:
        pid = p.get("ProcessId", 0)
        cmd = p.get("CommandLine") or ""
        if pid == my_pid:
            continue
        # Extract script name
        parts = cmd.split()
        script = None
        for part in parts:
            if part.endswith(".py") or part.endswith(".pyw"):
                script = part.split("\\")[-1].split("/")[-1]
                break
        if not script:
            continue
        by_script.setdefault(script, []).append(pid)

    # PHASE 1: Kill ALL watchdog instances FIRST (stop the respawner)
    killed = 0
    if "novax_watchdog.py" in by_script:
        pids = by_script.pop("novax_watchdog.py")
        print(f"[PHASE 1] Killing ALL watchdog instances: {len(pids)} PIDs")
        for pid in pids:
            if kill_pid(pid):
                killed += 1
                print(f"  Killed watchdog PID {pid}")
        time.sleep(1)

    # PHASE 2: Kill ALL duplicate instances (keep lowest PID = oldest = likely original)
    for script, pids in sorted(by_script.items()):
        if len(pids) <= 1:
            continue
        pids.sort()  # Keep lowest PID
        keep = pids[0]
        dupes = pids[1:]
        print(f"[PHASE 2] {script}: keeping PID {keep}, killing {len(dupes)} duplicates")
        for pid in dupes:
            if kill_pid(pid):
                killed += 1
                print(f"  Killed PID {pid}")

    print(f"\n=== Killed {killed} zombie processes ===")

    # Verify
    time.sleep(2)
    remaining = get_all_python_procs()
    nova = [p for p in remaining if "nova" in (p.get("CommandLine") or "").lower()
            and p.get("ProcessId") != my_pid]
    print(f"Remaining NovaX processes: {len(nova)}")
    for p in nova:
        cmd = p.get("CommandLine") or ""
        parts = cmd.split()
        script = "?"
        for part in parts:
            if part.endswith(".py") or part.endswith(".pyw"):
                script = part.split("\\")[-1]
                break
        print(f"  PID={p['ProcessId']} {script}")

if __name__ == "__main__":
    main()
