"""
NovaX Guardian Agent System
=============================
Two AI agents that watch and repair each other.

Agent Alpha (Brain Guardian):
  - Runs on Brain (port 9990)
  - Watches Ollama (port 11434)
  - If Ollama dies, Alpha diagnoses and repairs it

Agent Beta (Ollama Guardian):
  - Runs on Ollama (port 11434)
  - Watches Brain (port 9990)
  - If Brain dies, Beta diagnoses and repairs it

Result: At least one AI is always available.
"""
import time, socket, subprocess, os, threading, json, logging, shutil
from collections import deque
from enum import Enum

log = logging.getLogger("NovaX.Guardian")

class AgentState(Enum):
    ACTIVE = "active"
    WATCHING = "watching"
    REPAIRING = "repairing"
    OFFLINE = "offline"
    DEGRADED = "degraded"

class RepairResult:
    def __init__(self, action, success, detail="", ts=None):
        self.action = action
        self.success = success
        self.detail = detail
        self.ts = ts or time.time()
    def to_dict(self):
        return {"action": self.action, "success": self.success,
                "detail": self.detail, "ts": self.ts}

class GuardianAgent:
    """One guardian agent that watches a target service and repairs it."""
    def __init__(self, name, host_port, target_name, target_port,
                 target_health_url=None, target_start_cmd=None,
                 target_process_name=None):
        self.name = name
        self.host_port = host_port
        self.target_name = target_name
        self.target_port = target_port
        self.target_health_url = target_health_url
        self.target_start_cmd = target_start_cmd
        self.target_process_name = target_process_name
        self.state = AgentState.OFFLINE
        self.target_state = "unknown"
        self.consecutive_fails = 0
        self.total_checks = 0
        self.total_repairs = 0
        self.successful_repairs = 0
        self.repair_history = deque(maxlen=50)
        self.last_check = None
        self.last_repair = None
        self.repair_cooldown = 30
        self._last_repair_time = 0

    def check_self(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2)
            s.connect(("127.0.0.1", self.host_port))
            s.close()
            self.state = AgentState.ACTIVE
            return True
        except Exception:
            self.state = AgentState.OFFLINE
            return False

    def check_target(self):
        self.total_checks += 1
        self.last_check = time.time()
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(3)
            s.connect(("127.0.0.1", self.target_port))
            s.close()
        except Exception:
            self.consecutive_fails += 1
            self.target_state = "down"
            return False
        if self.target_health_url:
            try:
                import urllib.request
                r = urllib.request.urlopen(self.target_health_url, timeout=3)
                if r.getcode() != 200:
                    self.consecutive_fails += 1
                    self.target_state = "degraded"
                    return False
            except Exception:
                self.consecutive_fails += 1
                self.target_state = "degraded"
                return False
        self.consecutive_fails = 0
        self.target_state = "up"
        return True
    def diagnose(self):
        diag = {"target": self.target_name, "port": self.target_port,
                "issues": [], "ts": time.time()}
        try:
            cmd = "netstat -aon | findstr :" + str(self.target_port)
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
            if r.stdout.strip(): diag["issues"].append("port_occupied")
            else: diag["issues"].append("port_not_listening")
        except Exception: diag["issues"].append("netstat_failed")
        if self.target_process_name:
            try:
                cmd = 'tasklist /FI "IMAGENAME eq ' + self.target_process_name + '" /NH'
                r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
                if self.target_process_name.lower() in r.stdout.lower(): diag["issues"].append("process_hung")
                else: diag["issues"].append("process_missing")
            except Exception: diag["issues"].append("process_check_failed")
        try:
            usage = shutil.disk_usage("C:/")
            if usage.free / (1024**3) < 1: diag["issues"].append("disk_critical")
        except Exception: pass
        return diag

    def repair(self):
        now = time.time()
        if now - self._last_repair_time < self.repair_cooldown:
            return RepairResult("cooldown", False, "Waiting")
        self._last_repair_time = now
        self.state = AgentState.REPAIRING
        self.total_repairs += 1
        for fn in [self._repair_restart, self._repair_kill_restart, self._repair_free_port]:
            result = fn()
            self.repair_history.append(result)
            if result.success:
                self.successful_repairs += 1
                self.last_repair = time.time()
                self.state = AgentState.WATCHING
                return result
            time.sleep(2)
        self.state = AgentState.WATCHING
        fail = RepairResult("all_failed", False, "Exhausted")
        self.repair_history.append(fail)
        return fail

    def _repair_restart(self):
        if not self.target_start_cmd:
            return RepairResult("restart", False, "No cmd")
        try:
            subprocess.Popen(self.target_start_cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(3)
            if self.check_target(): return RepairResult("restart", True, "OK")
            return RepairResult("restart", False, "Unresponsive")
        except Exception as e: return RepairResult("restart", False, str(e))

    def _repair_kill_restart(self):
        if self.target_process_name:
            try: subprocess.run("taskkill /F /IM " + self.target_process_name, shell=True, capture_output=True, timeout=5)
            except Exception: pass
        return self._repair_restart()

    def _repair_free_port(self):
        try: subprocess.run("netstat -aon | findstr :" + str(self.target_port), shell=True, capture_output=True, timeout=5)
        except Exception: pass
        return self._repair_restart()

    def to_dict(self):
        return {"name": self.name, "state": self.state.value, "host_port": self.host_port,
                "target": self.target_name, "target_port": self.target_port,
                "target_state": self.target_state, "consecutive_fails": self.consecutive_fails,
                "total_checks": self.total_checks, "total_repairs": self.total_repairs,
                "successful_repairs": self.successful_repairs,
                "repair_rate": round(self.successful_repairs / max(self.total_repairs, 1), 2),
                "last_check": self.last_check, "last_repair": self.last_repair,
                "recent_repairs": [r.to_dict() for r in list(self.repair_history)[-10:]]}

class GuardianSystem:
    """Dual Guardian: Alpha watches Ollama, Beta watches Brain."""
    def __init__(self):
        self.alpha = GuardianAgent("Alpha", 9990, "Ollama", 11434,
            "http://127.0.0.1:11434/api/tags", "start /B ollama serve", "ollama.exe")
        self.beta = GuardianAgent("Beta", 11434, "Brain", 9990,
            "http://127.0.0.1:9990/health", None, "python.exe")
        self.running = False
        self._thread = None
        self.check_interval = 10
        self.repair_threshold = 3
        self.events = deque(maxlen=100)

    def _emit(self, msg):
        self.events.append({"msg": msg, "ts": time.time()})
        log.info("Guardian: " + msg)

    def check_cycle(self):
        a_up = self.alpha.check_self()
        b_up = self.beta.check_self()
        if a_up:
            self.alpha.state = AgentState.WATCHING
            ok = self.alpha.check_target()
            if not ok and self.alpha.consecutive_fails >= self.repair_threshold:
                self._emit("Alpha: Ollama down, repairing")
                r = self.alpha.repair()
                self._emit("Alpha: " + r.action + " -> " + ("OK" if r.success else "FAIL"))
        if b_up:
            self.beta.state = AgentState.WATCHING
            ok = self.beta.check_target()
            if not ok and self.beta.consecutive_fails >= self.repair_threshold:
                self._emit("Beta: Brain down, repairing")
                r = self.beta.repair()
                self._emit("Beta: " + r.action + " -> " + ("OK" if r.success else "FAIL"))
        if not a_up and not b_up:
            self._emit("CRITICAL: Both AI down. Cold starting Ollama...")
            try: subprocess.Popen("start /B ollama serve", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception: pass

    def start(self):
        if self.running: return
        self.running = True
        self._emit("Guardian System activated")
        def loop():
            while self.running:
                try: self.check_cycle()
                except Exception as e: log.error("Guardian error: " + str(e))
                time.sleep(self.check_interval)
        self._thread = threading.Thread(target=loop, daemon=True)
        self._thread.start()

    def stop(self):
        self.running = False
        self._emit("Guardian System stopped")

    def status(self):
        a = self.alpha.state != AgentState.OFFLINE
        b = self.beta.state != AgentState.OFFLINE
        h = "DUAL_ACTIVE" if a and b else "SINGLE_ACTIVE" if a or b else "CRITICAL"
        return {"health": h, "running": self.running,
                "alpha": self.alpha.to_dict(), "beta": self.beta.to_dict(),
                "total_repairs": self.alpha.total_repairs + self.beta.total_repairs,
                "successful_repairs": self.alpha.successful_repairs + self.beta.successful_repairs,
                "events": [e for e in list(self.events)[-20:]]}

    def force_check(self):
        self.check_cycle()
        return self.status()
