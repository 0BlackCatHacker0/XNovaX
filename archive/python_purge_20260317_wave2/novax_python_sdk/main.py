"""
NovaX Master Supervisor - Single Process Runtime
=================================================
One PID. One window. One killswitch.

The bridge lives IN this process (never restarts).
Everything else is a managed child process.
The extension connects here and NEVER disconnects.

(c) 2026 NovaX Project
"""
import os, sys, json, time, signal, subprocess, threading, logging
from pathlib import Path

# Ensure novax package is importable
NOVAX_ROOT = "C:/NovaX"
sys.path.insert(0, NOVAX_ROOT)

from novax.objects import Intent, Job, Status, Incident
from novax.events.bus import bus, SYSTEM_READY, SYSTEM_SHUTDOWN, SERVICE_STARTED, SERVICE_STOPPED, SERVICE_CRASHED
from novax.core.orchestrator import Orchestrator
from novax.core.scheduler import Scheduler
from novax.core.locks import LockManager
from novax.health.monitor import HealthMonitor
from novax.health.probes import probe_port, probe_http
from novax.policy.engine import PolicyEngine
from novax.snapshot.manager import SnapshotManager
from novax.memory.threads import ThreadManager
from novax.context.inference import ContextEngine
from novax.explain.translator import Explainer
from novax.discovery.scanner import Scanner
from novax.upc.controller import UniversalPromptController
from novax.godmode.orchestrator import GodModeController
from novax.verification.contract import VerificationRegistry
from novax.perception.vision import PerceptionEngine
from novax.gameplay.learning import GameplayLearner
from novax.tools.runner import ToolRunner
from novax.api.server import start_server, set_nova
from novax.transport.ws_server import start_ws_server, set_nova as ws_set_nova, broadcast_event

# ============================================================
#  LOGGING - one stream, not many windows
# ============================================================
LOG_DIR = "C:/NovaX/logs"
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(LOG_DIR, "master.log"), encoding="utf-8"),
    ]
)
log = logging.getLogger("NovaX")

# ============================================================
#  MANAGED SERVICE - child process wrapper
# ============================================================
class ManagedService:
    """A child process managed by the supervisor."""

    def __init__(self, name, command, port=None, health_url=None,
                 depends_on=None, cwd=None, max_restarts=5):
        self.name = name
        self.command = command
        self.port = port
        self.health_url = health_url
        self.depends_on = depends_on or []
        self.cwd = cwd
        self.max_restarts = max_restarts
        self.process = None
        self.status = "stopped"  # stopped, starting, running, degraded, locked
        self.restarts = []       # timestamps of recent restarts
        self.pid = None
        self.log_file = None
        self._lock = threading.Lock()

    def start(self):
        with self._lock:
            if self.status in ("running", "starting"):
                return True
            # Check restart budget (max N in 5 min)
            now = time.time()
            self.restarts = [t for t in self.restarts if now - t < 300]
            if len(self.restarts) >= self.max_restarts:
                self.status = "locked"
                log.error(f"[{self.name}] LOCKED - exceeded {self.max_restarts} restarts in 5min")
                return False

            self.status = "starting"
            log.info(f"[{self.name}] Starting: {self.command}")
            try:
                self.log_file = open(os.path.join(LOG_DIR, f"{self.name}.log"), "a", encoding="utf-8")
                self.process = subprocess.Popen(
                    self.command, shell=True,
                    stdout=self.log_file, stderr=subprocess.STDOUT,
                    cwd=self.cwd, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                )
                self.pid = self.process.pid
                self.restarts.append(time.time())
                bus.emit(SERVICE_STARTED, {"service": self.name, "pid": self.pid})
                # Give it a moment to start
                threading.Thread(target=self._wait_healthy, daemon=True).start()
                return True
            except Exception as e:
                self.status = "stopped"
                log.error(f"[{self.name}] Failed to start: {e}")
                return False

    def _wait_healthy(self):
        """Wait for service to become healthy (3 consecutive passes)."""
        passes = 0
        for attempt in range(30):  # 30 seconds max
            time.sleep(1)
            if self.process and self.process.poll() is not None:
                self.status = "stopped"
                log.warning(f"[{self.name}] Process exited during startup (code {self.process.returncode})")
                return
            if self.is_healthy():
                passes += 1
                if passes >= 2:  # 2 consecutive passes
                    self.status = "running"
                    log.info(f"[{self.name}] HEALTHY (pid {self.pid})")
                    return
            else:
                passes = 0
        self.status = "degraded"
        log.warning(f"[{self.name}] Started but not healthy after 30s")

    def stop(self, graceful_timeout=8):
        with self._lock:
            if not self.process or self.status == "stopped":
                self.status = "stopped"
                return True
            log.info(f"[{self.name}] Stopping (pid {self.pid})...")
            try:
                # Try graceful first (CTRL_BREAK on Windows)
                self.process.send_signal(signal.CTRL_BREAK_EVENT)
                try:
                    self.process.wait(timeout=graceful_timeout)
                except subprocess.TimeoutExpired:
                    log.warning(f"[{self.name}] Graceful timeout, force killing")
                    self.process.kill()
                    self.process.wait(timeout=3)
            except Exception as e:
                log.error(f"[{self.name}] Stop error: {e}")
                try: self.process.kill()
                except: pass
            self.status = "stopped"
            self.pid = None
            if self.log_file:
                self.log_file.close()
                self.log_file = None
            bus.emit(SERVICE_STOPPED, {"service": self.name})
            return True

    def restart(self):
        self.stop()
        time.sleep(1)
        return self.start()

    def is_healthy(self):
        if self.health_url:
            return probe_http(self.health_url, timeout=3)
        if self.port:
            return probe_port("localhost", self.port, timeout=2)
        if self.process:
            return self.process.poll() is None
        return False

    def is_alive(self):
        return self.process and self.process.poll() is None

    def info(self):
        return {
            "name": self.name, "status": self.status, "pid": self.pid,
            "port": self.port, "restarts_5min": len(self.restarts),
            "alive": self.is_alive(), "locked": self.status == "locked"
        }


# ============================================================
#  NOVA - the supervisor singleton
# ============================================================
class Nova:
    """The NovaX master supervisor. One instance. One process."""

    # Master states: OFF, STARTING, ON, DEGRADED, STOPPING, PANIC
    STATES = ("OFF", "STARTING", "ON", "DEGRADED", "STOPPING", "PANIC")

    def __init__(self):
        self.state = "OFF"
        self.boot_time = time.time()
        self.services = {}

        # Core modules
        self.orchestrator = Orchestrator()
        self.scheduler = Scheduler()
        self.locks = LockManager()
        self.health = HealthMonitor()
        self.policy = PolicyEngine()
        self.snapshots = SnapshotManager()
        self.threads = ThreadManager()
        self.context = ContextEngine()
        self.explainer = Explainer()
        self.scanner = Scanner()
        self.upc = UniversalPromptController()
        self.godmode = GodModeController()
        self.verifier = VerificationRegistry()
        self.perception = PerceptionEngine()
        self.gameplay = GameplayLearner()
        self.tools = ToolRunner()

        # Register managed services
        self._register_services()

    def _register_services(self):
        """Register all child services the supervisor manages."""
        # Brain server (port 9990)
        self.register_service(ManagedService(
            name="brain", port=9990,
            command='python "C:/NovaX/core/server.py"',
            health_url="http://127.0.0.1:9990/health",
            cwd=NOVAX_ROOT
        ))

        # Ollama (port 11434) - external, just monitor
        self.register_service(ManagedService(
            name="ollama", port=11434,
            command="ollama serve",
            health_url="http://127.0.0.1:11434/api/tags"
        ))

        # OpenClaw gateway (if exists)
        gw_path = "C:/NovaX/core/openclaw_client.py"
        if os.path.isfile(gw_path):
            self.register_service(ManagedService(
                name="openclaw_gw",
                command=f'python "{gw_path}"',
                depends_on=["brain"],
                cwd=NOVAX_ROOT
            ))

        # Register probes with health monitor
        for name, svc in self.services.items():
            self.health.register(
                name, svc.is_healthy,
                recover_fn=lambda s=svc: s.restart()
            )

    def register_service(self, svc):
        self.services[svc.name] = svc

    # -------- Master Control --------
    def start_all(self):
        """Boot sequence - start children in dependency order."""
        self.state = "STARTING"
        log.info("=" * 50)
        log.info("  NovaX Master - Starting all services")
        log.info("=" * 50)

        # Sort by dependencies (simple topological)
        started = set()
        order = []
        remaining = list(self.services.values())
        rounds = 0
        while remaining and rounds < 10:
            rounds += 1
            still_waiting = []
            for svc in remaining:
                if all(d in started for d in svc.depends_on):
                    order.append(svc)
                    started.add(svc.name)
                else:
                    still_waiting.append(svc)
            remaining = still_waiting

        for svc in order:
            log.info(f"  Starting {svc.name}...")
            svc.start()
            # Wait a bit for dependent services
            if svc.port:
                for _ in range(10):
                    if svc.is_healthy():
                        break
                    time.sleep(1)

        # Check overall health
        self._update_state()
        log.info(f"  Master state: {self.state}")
        bus.emit(SYSTEM_READY, {"state": self.state})

    def stop_all(self, panic=False):
        """Graceful or panic shutdown of all children."""
        self.state = "PANIC" if panic else "STOPPING"
        log.info(f"  NovaX Master - {'PANIC' if panic else 'Graceful'} shutdown")

        # Stop in reverse dependency order
        order = list(self.services.values())
        order.reverse()
        for svc in order:
            svc.stop(graceful_timeout=2 if panic else 8)

        self.state = "OFF"
        bus.emit(SYSTEM_SHUTDOWN, {"panic": panic})

    def stop_service(self, name):
        if name == "all":
            self.stop_all()
            return "all stopped"
        svc = self.services.get(name)
        if svc:
            svc.stop()
            self._update_state()
            return f"{name} stopped"
        return f"unknown service: {name}"

    def start_service(self, name):
        if name == "all":
            self.start_all()
            return "all started"
        svc = self.services.get(name)
        if svc:
            svc.start()
            self._update_state()
            return f"{name} starting"
        return f"unknown service: {name}"

    def restart_service(self, name):
        svc = self.services.get(name)
        if svc:
            svc.restart()
            self._update_state()
            return f"{name} restarting"
        return f"unknown service: {name}"

    def _update_state(self):
        """Recalculate master state based on child health."""
        statuses = [s.status for s in self.services.values()]
        if all(s == "stopped" for s in statuses):
            self.state = "OFF"
        elif all(s == "running" for s in statuses):
            self.state = "ON"
        elif any(s in ("running", "starting") for s in statuses):
            self.state = "DEGRADED"

    def managed_services(self):
        return {name: svc.info() for name, svc in self.services.items()}

    # -------- Boot --------
    def boot(self):
        """Full boot sequence per the spec."""
        log.info("")
        log.info("  â–ˆâ–ˆâ–ˆâ•—   â–ˆâ–ˆâ•— â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ•— â–ˆâ–ˆâ•—   â–ˆâ–ˆâ•— â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ•— â–ˆâ–ˆâ•—  â–ˆâ–ˆâ•—")
        log.info("  â–ˆâ–ˆâ–ˆâ–ˆâ•—  â–ˆâ–ˆâ•‘â–ˆâ–ˆâ•”â•â•â•â–ˆâ–ˆâ•—â–ˆâ–ˆâ•‘   â–ˆâ–ˆâ•‘â–ˆâ–ˆâ•”â•â•â–ˆâ–ˆâ•—â•šâ–ˆâ–ˆâ•—â–ˆâ–ˆâ•”â•")
        log.info("  â–ˆâ–ˆâ•”â–ˆâ–ˆâ•— â–ˆâ–ˆâ•‘â–ˆâ–ˆâ•‘   â–ˆâ–ˆâ•‘â–ˆâ–ˆâ•‘   â–ˆâ–ˆâ•‘â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ•‘ â•šâ–ˆâ–ˆâ–ˆâ•”â• ")
        log.info("  â–ˆâ–ˆâ•‘â•šâ–ˆâ–ˆâ•—â–ˆâ–ˆâ•‘â–ˆâ–ˆâ•‘   â–ˆâ–ˆâ•‘â•šâ–ˆâ–ˆâ•— â–ˆâ–ˆâ•”â•â–ˆâ–ˆâ•”â•â•â–ˆâ–ˆâ•‘ â–ˆâ–ˆâ•”â–ˆâ–ˆâ•— ")
        log.info("  â–ˆâ–ˆâ•‘ â•šâ–ˆâ–ˆâ–ˆâ–ˆâ•‘â•šâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ•”â• â•šâ–ˆâ–ˆâ–ˆâ–ˆâ•”â• â–ˆâ–ˆâ•‘  â–ˆâ–ˆâ•‘â–ˆâ–ˆâ•”â• â–ˆâ–ˆâ•—")
        log.info("  â•šâ•â•  â•šâ•â•â•â• â•šâ•â•â•â•â•â•   â•šâ•â•â•â•  â•šâ•â•  â•šâ•â•â•šâ•â•  â•šâ•â•")
        log.info("  Master Supervisor v1.0")
        log.info("")

        # 1) Load persistent memory
        log.info("[Boot 1/8] Loading persistent memory...")
        # threads auto-load from disk

        # 2) Restore unfinished threads
        uf = self.threads.unfinished()
        log.info(f"[Boot 2/8] Unfinished threads: {len(uf)}")

        # 3) Start health probes
        log.info("[Boot 3/8] Health probe system ready")

        # 4) Rebuild job queue
        log.info("[Boot 4/8] Job orchestrator ready")

        # 5) Check last crash
        crash_log = os.path.join(LOG_DIR, "last_crash.json")
        if os.path.isfile(crash_log):
            with open(crash_log) as f:
                crash = json.load(f)
            log.info(f"[Boot 5/8] Last crash: {crash.get('reason','unknown')}")
        else:
            log.info("[Boot 5/8] No crash history")

        # 6) Start scheduler for periodic health checks
        self.scheduler.every("health_check", 15, self.health.check_all)
        self.scheduler.start()
        log.info("[Boot 6/8] Scheduler started (health every 15s)")

        # 7) Discovery scan
        log.info("[Boot 7/10] Running discovery scan...")
        elapsed = self.scanner.full_scan()
        log.info(f"         Found {len(self.scanner.nodes)} nodes in {elapsed}s")

        # 8) Start child services
        log.info("[Boot 7/8] Starting managed services...")
        self.start_all()

        # 8) Start WebSocket transport (persistent channel)
        log.info("[Boot 9/10] Starting WebSocket on :9998...")
        ws_set_nova(self)
        start_ws_server(9998)

        # Wire event bus -> WebSocket broadcast
        from novax.events.bus import bus as _bus
        _bus.on("service.started", broadcast_event)
        _bus.on("service.stopped", broadcast_event)
        _bus.on("service.crashed", broadcast_event)
        _bus.on("job.created", broadcast_event)
        _bus.on("job.completed", broadcast_event)
        _bus.on("job.failed", broadcast_event)
        _bus.on("recovery.performed", broadcast_event)
        _bus.on("system.ready", broadcast_event)
        log.info("         Event bus -> WS broadcast wired")

        # 9) Start the API bridge (IN-PROCESS - never dies)
        log.info("[Boot 10/10] Starting API bridge on :9999...")
        set_nova(self)
        server = start_server(9999)
        self.state = "ON" if self.state != "DEGRADED" else "DEGRADED"

        log.info("")
        log.info("  ==============================")
        log.info(f"  NovaX is {self.state}")
        log.info(f"  Bridge: http://127.0.0.1:9999")
        log.info(f"  WebSocket: ws://localhost:9998")
        log.info(f"  Killswitch: http://127.0.0.1:9999/static/killswitch.html")
        log.info(f"  Services: {len(self.services)}")
        for name, svc in self.services.items():
            log.info(f"    {name}: {svc.status} (pid {svc.pid})")
        log.info("  ==============================")
        log.info("")

        # Serve forever (bridge is in-process, never dies)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            log.info("Ctrl+C received - shutting down...")
            self.stop_all()
            server.shutdown()
            log.info("NovaX stopped.")


# ============================================================
#  ENTRY POINT
# ============================================================
if __name__ == "__main__":
    nova = Nova()
    nova.boot()

