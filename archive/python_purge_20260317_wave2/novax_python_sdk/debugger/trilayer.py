"""
NovaX Tri-Layer Stability System
=================================
Layer 1: Thinkers (replaceable AI workers)
Layer 2: Guardians (Cognitive + Execution)
Layer 3: Arbiter (decides, prevents storms)

Guardian A = Cognitive: ensures reasoning exists
Guardian B = Execution: ensures infrastructure exists
All repairs go through Arbiter before executing.
"""
import time, socket, threading, logging, json
from collections import deque
from enum import Enum

log = logging.getLogger("NovaX.TriGuard")

class HealthGrade(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    DEAD = "dead"

class CognitiveGuardian:
    """
    Ensures reasoning exists somewhere.
    Checks ALL AI providers: local (Brain, Ollama) + cloud (10 providers via Cloud Router).
    Can prompts be answered? latency sane? tokens flowing?
    """
    def __init__(self):
        self.name = "CognitiveGuardian"
        self.thinkers = {
            "brain": {"port": 9990, "health_url": "http://127.0.0.1:9990/health",
                      "chat_url": "http://127.0.0.1:9990/v1/chat/completions",
                      "format": "openai", "model": "local"},
            "ollama": {"port": 11434, "health_url": "http://127.0.0.1:11434/api/tags",
                       "chat_url": "http://127.0.0.1:11434/api/chat",
                       "format": "ollama", "model": "llama3.2:latest"},
        }
        # Cloud providers routed through Cloud Router (port 9878)
        self.cloud_providers = {
            "anthropic": {"via": "cloud_router", "port": 9878},
            "openai": {"via": "cloud_router", "port": 9878},
            "google": {"via": "cloud_router", "port": 9878},
            "mistral": {"via": "cloud_router", "port": 9878},
            "groq": {"via": "cloud_router", "port": 9878},
            "deepseek": {"via": "cloud_router", "port": 9878},
            "cohere": {"via": "cloud_router", "port": 9878},
            "together": {"via": "cloud_router", "port": 9878},
            "openrouter": {"via": "cloud_router", "port": 9878},
        }
        self.cloud_grades = {}  # provider -> HealthGrade
        self.grades = {}     # name -> HealthGrade
        self.latencies = {}  # name -> deque
        self.primary = None
        self.last_check = None
        self.repair_requests = deque(maxlen=50)

    def assess(self):
        """Check all thinkers (local + cloud) and pick primary."""
        self.last_check = time.time()
        best = None
        best_score = -1
        for name, cfg in self.thinkers.items():
            grade = self._check_thinker(name, cfg)
            self.grades[name] = grade
            score = {"healthy": 4, "degraded": 2, "unhealthy": 1, "dead": 0}[grade.value]
            if score > best_score:
                best_score = score
                best = name
        # Also assess cloud providers via Cloud Router
        self._assess_cloud_providers()
        old_primary = self.primary
        self.primary = best if best_score > 0 else None
        if old_primary != self.primary:
            log.info("Cognitive: primary switched " + str(old_primary) + " -> " + str(self.primary))
        return self.primary

    def _assess_cloud_providers(self):
        """Check all cloud AI providers via Cloud Router /api/v1/providers."""
        try:
            import urllib.request
            r = urllib.request.urlopen("http://127.0.0.1:9878/api/v1/providers", timeout=5)
            providers = json.loads(r.read().decode())
            for pid, info in providers.items():
                if pid == "ollama":
                    continue  # Already checked as local thinker
                if info.get("on") and info.get("key"):
                    self.cloud_grades[pid] = HealthGrade.HEALTHY
                elif info.get("on") and not info.get("key"):
                    self.cloud_grades[pid] = HealthGrade.DEGRADED
                else:
                    self.cloud_grades[pid] = HealthGrade.DEAD
        except Exception:
            # Cloud Router itself is down
            for pid in self.cloud_providers:
                self.cloud_grades[pid] = HealthGrade.DEAD

    def _check_thinker(self, name, cfg):
        """Check if a thinker can actually reason."""
        # Step 1: Port check
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2)
            s.connect(("127.0.0.1", cfg["port"]))
            s.close()
        except Exception:
            return HealthGrade.DEAD
        # Step 2: Health endpoint
        try:
            import urllib.request
            urllib.request.urlopen(cfg["health_url"], timeout=3)
        except Exception:
            return HealthGrade.UNHEALTHY
        # Step 3: Quick cognition test (ping prompt)
        try:
            import urllib.request
            t0 = time.time()
            if cfg["format"] == "openai":
                body = json.dumps({"model": cfg["model"],
                    "messages": [{"role": "user", "content": "Say OK"}],
                    "max_tokens": 5}).encode()
            else:
                body = json.dumps({"model": cfg["model"],
                    "messages": [{"role": "user", "content": "Say OK"}],
                    "stream": False}).encode()
            req = urllib.request.Request(cfg["chat_url"],
                data=body, headers={"Content-Type": "application/json"})
            r = urllib.request.urlopen(req, timeout=10)
            data = json.loads(r.read())
            latency = int((time.time() - t0) * 1000)
            if name not in self.latencies:
                self.latencies[name] = deque(maxlen=30)
            self.latencies[name].append(latency)
            # Check response has content
            if cfg["format"] == "openai":
                text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            else:
                text = data.get("message", {}).get("content", "")
            if not text:
                return HealthGrade.UNHEALTHY
            if latency > 8000:
                return HealthGrade.DEGRADED
            return HealthGrade.HEALTHY
        except Exception:
            return HealthGrade.UNHEALTHY

    def needs_repair(self):
        """Return list of thinkers that need repair (local + cloud)."""
        repairs = []
        for name, grade in self.grades.items():
            if grade in (HealthGrade.DEAD, HealthGrade.UNHEALTHY):
                repairs.append({"target": name, "grade": grade.value,
                               "reason": name + " is " + grade.value})
        for name, grade in self.cloud_grades.items():
            if grade == HealthGrade.DEAD:
                repairs.append({"target": "cloud:" + name, "grade": grade.value,
                               "reason": name + " cloud API sealed (fallback active)"})
        return repairs

    def to_dict(self):
        return {"primary": self.primary,
                "grades": {k: v.value for k, v in self.grades.items()},
                "cloud_grades": {k: v.value for k, v in self.cloud_grades.items()},
                "latencies": {k: list(v)[-5:] for k, v in self.latencies.items()},
                "last_check": self.last_check}


class ExecutionGuardian:
    """
    Ensures ALL infrastructure exists.
    Monitors every service, API, and software connected to NovaX.
    """
    def __init__(self):
        self.name = "ExecutionGuardian"
        self.services = {
            # Core NovaX services
            "orchestrator": {"port": 9999, "critical": True},
            "websocket":    {"port": 9998, "critical": False},
            "brain":        {"port": 9990, "critical": True},
            "ollama":       {"port": 11434, "critical": True},
            "cloud_router": {"port": 9878, "critical": True},
            "hivemind":     {"port": 9881, "critical": True},
            "nexus":        {"port": 9882, "critical": False},
            "sentinel":     {"port": 9884, "critical": False},
            "ternary":      {"port": 9885, "critical": False},
            "exec_server":  {"port": 9877, "critical": False},
            "closed_loop":  {"port": 9888, "critical": False},
            "max_patch":    {"port": 9889, "critical": False},
            # External infrastructure
            "redis":        {"port": 6379, "critical": False},
            "meilisearch":  {"port": 7700, "critical": False},
            "caddy":        {"port": 8080, "critical": False},
        }
        self.statuses = {}
        self.last_check = None
        self.repair_requests = deque(maxlen=50)

    def assess(self):
        """Check all infrastructure services."""
        self.last_check = time.time()
        all_ok = True
        for name, cfg in self.services.items():
            up = self._check_port(cfg["port"])
            self.statuses[name] = "up" if up else "down"
            if not up and cfg["critical"]:
                all_ok = False
        return all_ok

    def _check_port(self, port):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2)
            s.connect(("127.0.0.1", port))
            s.close()
            return True
        except Exception:
            return False

    def needs_repair(self):
        repairs = []
        for name, status in self.statuses.items():
            if status == "down" and self.services[name]["critical"]:
                repairs.append({"target": name, "status": status,
                               "port": self.services[name]["port"]})
        return repairs

    def to_dict(self):
        return {"services": dict(self.statuses),
                "last_check": self.last_check}


class TriLayerSystem:
    """
    The complete Tri-Layer Stability Architecture.
    Cognitive + Execution guardians report to Arbiter.
    Arbiter authorizes repairs. No direct mutation.
    """
    def __init__(self, arbiter=None):
        self.cognitive = CognitiveGuardian()
        self.execution = ExecutionGuardian()
        self.arbiter = arbiter  # injected from novax.arbiter
        self.state = "GREEN"
        self.running = False
        self._thread = None
        self.check_interval = 12
        self.events = deque(maxlen=100)
        self.repairs_requested = 0
        self.repairs_approved = 0

    def _emit(self, msg):
        self.events.append({"msg": msg, "ts": time.time()})
        log.info("TriLayer: " + msg)

    def check_cycle(self):
        """Full check cycle: assess -> request repairs -> update state."""
        # Layer 2: Guardians assess
        primary = self.cognitive.assess()
        infra_ok = self.execution.assess()

        # Determine system state
        cog_repairs = self.cognitive.needs_repair()
        exec_repairs = self.execution.needs_repair()

        if not cog_repairs and not exec_repairs:
            self.state = "GREEN"
        elif primary and not exec_repairs:
            self.state = "YELLOW"
        elif exec_repairs and not cog_repairs:
            self.state = "ORANGE"
        elif exec_repairs and cog_repairs:
            self.state = "RED"
        if not primary and not infra_ok:
            self.state = "SAFE"

        # Request repairs through Arbiter
        all_repairs = cog_repairs + exec_repairs
        for repair in all_repairs:
            self.repairs_requested += 1
            self._emit("Repair needed: " + repair["target"])
            if self.arbiter:
                self._request_arbiter_repair(repair)

        # Update arbiter with primary thinker
        if self.arbiter and primary:
            self.arbiter.set_thinker(primary)
            self.arbiter.update_state(self.state)

    def _request_arbiter_repair(self, repair):
        """Ask Arbiter to approve and execute a repair."""
        target = repair["target"]
        # Cloud API failures are "sealed" — no restart, just log the seal
        if target.startswith("cloud:"):
            provider = target.split(":", 1)[1]
            self._emit("API sealed: " + provider + " — fallback cascade active via Cloud Router")
            return
        repair_cmds = {
            "ollama": r"start /B C:\Users\Jupit\AppData\Local\Programs\Ollama\ollama.exe serve",
            "orchestrator": r"cd /d C:\NovaX && start /B python core\orchestrator.py",
            "cloud_router": r"cd /d C:\NovaX && start /B python nova_cloud_router.py",
            "hivemind": r"cd /d C:\NovaX && start /B python nova_hivemind.py",
        }
        cmd = repair_cmds.get(target)
        if not cmd:
            return
        try:
            from novax.arbiter.arbiter import ActionProposal, RiskLevel
            proposal = ActionProposal(
                proposed_by=self.cognitive.name if target in ("brain", "ollama") else self.execution.name,
                action_type="restart",
                command=cmd,
                risk=RiskLevel.MEDIUM,
                reason=target + " is down"
            )
            result = self.arbiter.submit(proposal)
            if result["decision"] == "APPROVED":
                self.repairs_approved += 1
                self._emit("Arbiter approved repair: " + target)
            else:
                self._emit("Arbiter denied repair: " + target + " - " + result.get("reason", ""))
        except Exception as e:
            self._emit("Arbiter request failed: " + str(e))

    def start(self):
        if self.running: return
        self.running = True
        self._emit("Tri-Layer System activated")
        def loop():
            while self.running:
                try: self.check_cycle()
                except Exception as e:
                    log.error("TriLayer error: " + str(e))
                time.sleep(self.check_interval)
        self._thread = threading.Thread(target=loop, daemon=True)
        self._thread.start()

    def stop(self):
        self.running = False
        self._emit("Tri-Layer System stopped")

    def get_active_thinker(self):
        return self.cognitive.primary

    def status(self):
        return {"state": self.state, "running": self.running,
                "active_thinker": self.cognitive.primary,
                "cognitive": self.cognitive.to_dict(),
                "execution": self.execution.to_dict(),
                "repairs_requested": self.repairs_requested,
                "repairs_approved": self.repairs_approved,
                "events": [e for e in list(self.events)[-15:]]}

    def force_check(self):
        self.check_cycle()
        return self.status()