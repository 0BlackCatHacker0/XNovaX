"""
NovaX Nervous System - Master Startup
=======================================
Starts: Arbiter, EventBus, Router, Guardians, Watchdog, DebugEngine
All running as daemon threads with continuous monitoring.
"""
import sys, time, json, logging, threading
sys.path.insert(0, "C:/NovaX")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
log = logging.getLogger("NovaX.Startup")

print("=" * 50)
print("  NovaX Nervous System - Starting Up")
print("=" * 50)

# 1. Arbiter
from novax.debugger.arbiter import Arbiter
arbiter = Arbiter()
log.info("[1/6] Arbiter online - state: " + arbiter.state.value)

# 2. EventBus
from novax.debugger.eventbus import EventBus
bus = EventBus()
bus.publish("status", "system", "NovaX nervous system starting")
log.info("[2/6] EventBus online - subscribers ready")

# 3. Router
from novax.debugger.router import Router
router = Router(arbiter, bus)
router.check_all_health()
router.start_health_loop(interval=12)
active = router.active_endpoint
eps = {n: e.alive for n, e in router.endpoints.items()}
log.info("[3/6] Router online - endpoints: " + str(eps))

# 4. Guardians
from novax.debugger.guardians import GuardianSystem
guardians = GuardianSystem()
guardians.start()
log.info("[4/6] Guardians online - Alpha watches Ollama, Beta watches Brain")

# 5. Watchdog
from novax.debugger.watchdog import Watchdog
watchdog = Watchdog()
watchdog.start(interval=20)
log.info("[5/6] Watchdog online - probes active")

# 6. DebugEngine
from novax.debugger.engine import DebugEngine
engine = DebugEngine()
engine.start(interval=25)
log.info("[6/6] DebugEngine online - contracts loaded")

# Initial diagnosis
bus.publish("status", "system", "All 6 subsystems online")
diag = engine.full_diagnosis()
health = diag.get("health", "UNKNOWN")
services_up = sum(1 for s in diag.get("services", {}).values() if s.get("status") == "up")
services_total = len(diag.get("services", {}))

print()
print("=" * 50)
print("  SYSTEM HEALTH: " + health)
print("  Services: " + str(services_up) + "/" + str(services_total) + " up")
print("  Router endpoints: " + str(eps))
print("  Guardians: running")
print("  Watchdog: running")
print("  Arbiter state: " + arbiter.state.value)
print("=" * 50)
print()
print("Nervous system active. Monitoring every 10-25s.")
print("Press Ctrl+C to stop.")
print()

# Write PID file so other tools know we're running
import os
pid_path = "C:/NovaX/memory/nervous_system.pid"
os.makedirs(os.path.dirname(pid_path), exist_ok=True)
with open(pid_path, "w") as f:
    f.write(str(os.getpid()))

# Status endpoint - write JSON every 10s for the UI to read
def status_loop():
    while True:
        try:
            status = {
                "ts": time.time(),
                "arbiter": arbiter.status(),
                "router": router.status(),
                "guardians": guardians.status(),
                "engine": {"health": health, "running": engine.running},
                "watchdog": watchdog.summary(),
            }
            status_path = "C:/NovaX/memory/nervous_status.json"
            with open(status_path, "w") as f:
                json.dump(status, f)
        except Exception as e:
            log.error("Status write error: " + str(e))
        time.sleep(10)

t = threading.Thread(target=status_loop, daemon=True)
t.start()

# Keep alive
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\nShutting down nervous system...")
    guardians.stop()
    watchdog.stop()
    engine.stop()
    router.stop()
    if os.path.exists(pid_path):
        os.remove(pid_path)
    print("Stopped.")
