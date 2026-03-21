"""
NovaX Conversation Router
==========================
Air traffic control for prompts, tasks, memory, and model routing.
All prompt bars submit standardized packets.
Router selects model, creates task graphs, fans out subtasks.
"""
import time, threading, json, logging, uuid, socket
from collections import deque
from enum import Enum

log = logging.getLogger("NovaX.Router")

class RouteMode(Enum):
    SINGLE = "single"
    MULTI = "multi"
    AUTO = "auto"

class ModelEndpoint:
    """One AI model endpoint the router can send work to."""
    def __init__(self, name, url, chat_path, model_name,
                 port=None, response_format="openai"):
        self.name = name
        self.url = url
        self.chat_path = chat_path
        self.model_name = model_name
        self.port = port
        self.response_format = response_format  # openai or ollama
        self.alive = False
        self.latency_ms = 0
        self.success_count = 0
        self.fail_count = 0
        self.last_check = None
        self.last_success = None
        self.quality_score = 1.0 / 3  # H3 harmonic default (MAYBE zone)

    def check_health(self):
        self.last_check = time.time()
        if not self.port:
            self.alive = False
            return False
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2)
            t0 = time.time()
            s.connect(("127.0.0.1", self.port))
            s.close()
            self.latency_ms = round((time.time() - t0) * 1000)
            self.alive = True
            return True
        except Exception:
            self.alive = False
            return False

    def record_success(self, latency_ms=0):
        self.success_count += 1
        self.last_success = time.time()
        if latency_ms > 0:
            self.latency_ms = latency_ms
        self.quality_score = min(1.0, self.quality_score + 1.0 / 13)  # H13 success increment

    def record_failure(self):
        self.fail_count += 1
        self.quality_score = max(0.0, self.quality_score - 1.0 / 7)  # H7 failure penalty

    def score(self):
        if not self.alive: return 0
        latency_factor = max(0, 1 - self.latency_ms / 5000)
        # 3-5-7-13 harmonic: 2/H3 quality + 1/H3 latency
        return round(self.quality_score * (2.0 / 3) + latency_factor * (1.0 / 3), 3)

    def to_dict(self):
        return {"name": self.name, "url": self.url, "port": self.port,
                "alive": self.alive, "latency_ms": self.latency_ms,
                "success": self.success_count, "fail": self.fail_count,
                "quality": self.quality_score, "score": self.score()}

class PromptPacket:
    """Standardized prompt packet - all inputs become this."""
    def __init__(self, user_text, mode=RouteMode.AUTO, god_mode=False,
                 task_id=None, attachments=None, memory_refs=None,
                 system_prompt=None):
        self.packet_id = str(uuid.uuid4())[:12]
        self.user_text = user_text
        self.mode = mode
        self.god_mode = god_mode
        self.task_id = task_id
        self.attachments = attachments or []
        self.memory_refs = memory_refs or []
        self.system_prompt = system_prompt
        self.ts = time.time()
        self.routed_to = None
        self.response = None
        self.latency_ms = 0
    def to_dict(self):
        return {"packet_id": self.packet_id, "text": self.user_text[:100],
                "mode": self.mode.value, "god_mode": self.god_mode,
                "routed_to": self.routed_to, "latency_ms": self.latency_ms,
                "ts": self.ts}

class Router:
    """Central conversation router - directs prompts to best available AI."""
    def __init__(self):
        self.models = {}  # name -> ModelEndpoint
        self.packet_history = deque(maxlen=200)
        self.total_routed = 0
        self.total_failed = 0
        self._lock = threading.Lock()
        self._health_thread = None
        self.running = False
        self.health_interval = 8
        self._register_defaults()

    def _register_defaults(self):
        self.add_model(ModelEndpoint("brain", "http://127.0.0.1:9990",
            "/v1/chat/completions", "local", port=9990, response_format="openai"))
        self.add_model(ModelEndpoint("ollama", "http://127.0.0.1:11434",
            "/api/chat", "llama3.2:latest", port=11434, response_format="ollama"))

    def add_model(self, endpoint):
        self.models[endpoint.name] = endpoint

    def select_model(self, packet):
        """Choose best model for this packet."""
        if packet.mode == RouteMode.SINGLE:
            # Use first alive model
            for m in self.models.values():
                if m.alive:
                    return m
        # Auto/multi: pick highest scoring alive model
        alive = [(m.score(), m) for m in self.models.values() if m.alive]
        if alive:
            alive.sort(key=lambda x: -x[0])
            return alive[0][1]
        return None

    def route(self, packet):
        """Route a prompt packet to the best model and get response."""
        import urllib.request
        self.total_routed += 1
        model = self.select_model(packet)
        if not model:
            self.total_failed += 1
            packet.response = "All AI services offline."
            packet.routed_to = "none"
            self.packet_history.append(packet)
            return packet

        packet.routed_to = model.name
        sys_prompt = packet.system_prompt or "You are Nova, a helpful AI assistant. Be concise."
        t0 = time.time()

        try:
            if model.response_format == "openai":
                body = json.dumps({"model": model.model_name,
                    "messages": [{"role": "system", "content": sys_prompt},
                                 {"role": "user", "content": packet.user_text}],
                    "max_tokens": 200}).encode()
                req = urllib.request.Request(model.url + model.chat_path,
                    data=body, headers={"Content-Type": "application/json"})
                r = urllib.request.urlopen(req, timeout=15)
                d = json.loads(r.read())
                text = d["choices"][0]["message"]["content"]
            else:  # ollama format
                body = json.dumps({"model": model.model_name,
                    "messages": [{"role": "system", "content": sys_prompt},
                                 {"role": "user", "content": packet.user_text}],
                    "stream": False}).encode()
                req = urllib.request.Request(model.url + model.chat_path,
                    data=body, headers={"Content-Type": "application/json"})
                r = urllib.request.urlopen(req, timeout=30)
                d = json.loads(r.read())
                text = d["message"]["content"]

            packet.response = text
            packet.latency_ms = int((time.time() - t0) * 1000)
            model.record_success(packet.latency_ms)

        except Exception as e:
            log.error("Route to " + model.name + " failed: " + str(e))
            model.record_failure()
            # Try fallback
            for fb in self.models.values():
                if fb.name != model.name and fb.alive:
                    packet.routed_to = fb.name + " (fallback)"
                    try:
                        if fb.response_format == "openai":
                            body = json.dumps({"model": fb.model_name,
                                "messages": [{"role": "system", "content": sys_prompt},
                                             {"role": "user", "content": packet.user_text}],
                                "max_tokens": 200}).encode()
                            req = urllib.request.Request(fb.url + fb.chat_path,
                                data=body, headers={"Content-Type": "application/json"})
                        else:
                            body = json.dumps({"model": fb.model_name,
                                "messages": [{"role": "system", "content": sys_prompt},
                                             {"role": "user", "content": packet.user_text}],
                                "stream": False}).encode()
                            req = urllib.request.Request(fb.url + fb.chat_path,
                                data=body, headers={"Content-Type": "application/json"})
                        r = urllib.request.urlopen(req, timeout=30)
                        d = json.loads(r.read())
                        if fb.response_format == "openai":
                            packet.response = d["choices"][0]["message"]["content"]
                        else:
                            packet.response = d["message"]["content"]
                        fb.record_success()
                        break
                    except Exception:
                        fb.record_failure()
            if not packet.response:
                packet.response = "All AI endpoints failed."
                self.total_failed += 1

        self.packet_history.append(packet)
        return packet

    def check_all_health(self):
        for m in self.models.values():
            m.check_health()

    def start(self):
        if self.running: return
        self.running = True
        def hloop():
            while self.running:
                self.check_all_health()
                time.sleep(self.health_interval)
        self._health_thread = threading.Thread(target=hloop, daemon=True)
        self._health_thread.start()
        log.info("Router started with " + str(len(self.models)) + " models")

    def stop(self):
        self.running = False

    def status(self):
        return {"running": self.running,
                "total_routed": self.total_routed,
                "total_failed": self.total_failed,
                "models": {n: m.to_dict() for n, m in self.models.items()},
                "recent": [p.to_dict() for p in list(self.packet_history)[-10:]]}

# Singleton
_router = None
def get_router():
    global _router
    if _router is None:
        _router = Router()
    return _router