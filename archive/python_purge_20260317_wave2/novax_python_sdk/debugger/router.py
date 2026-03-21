"""
NovaX Conversation Router
==========================
Air traffic control for prompts, tasks, memory, tools, merges.
All prompt bars submit standardized packets.
Router selects best AI, handles failover, never drops.
"""
import time, threading, logging, json, uuid
from collections import deque

log = logging.getLogger("NovaX.Router")

class PromptPacket:
    """Standardized prompt - no raw chat messages routed directly."""
    def __init__(self, user_text, mode="auto", god_mode=False,
                 permissions="normal", task_id=None, attachments=None,
                 workspace_root="C:/NovaX", memory_refs=None):
        self.packet_id = str(uuid.uuid4())[:12]
        self.user_text = user_text
        self.mode = mode           # single, multi, auto
        self.god_mode = god_mode
        self.permissions = permissions
        self.task_id = task_id
        self.attachments = attachments or []
        self.workspace_root = workspace_root
        self.memory_refs = memory_refs or []
        self.ts = time.time()
        self.routed_to = None
        self.response = None
        self.latency = None
        self.success = None
    def to_dict(self):
        return {"packet_id": self.packet_id, "user_text": self.user_text[:80],
                "mode": self.mode, "god_mode": self.god_mode,
                "routed_to": self.routed_to, "success": self.success,
                "latency": self.latency, "ts": self.ts}

class ModelEndpoint:
    """One AI model endpoint the router can use."""
    def __init__(self, name, chat_url, health_url=None, model_id=None, priority=1):
        self.name = name
        self.chat_url = chat_url
        self.health_url = health_url
        self.model_id = model_id or name
        self.priority = priority
        self.alive = False
        self.latency_avg = 0
        self.success_count = 0
        self.fail_count = 0
        self.last_check = None
        self.consecutive_fails = 0
    def success_rate(self):
        total = self.success_count + self.fail_count
        if total == 0: return 0.0
        return round(self.success_count / total, 3)
    def check_health(self):
        self.last_check = time.time()
        if not self.health_url:
            self.alive = True
            return True
        try:
            import urllib.request
            r = urllib.request.urlopen(self.health_url, timeout=3)
            self.alive = r.getcode() == 200
            self.consecutive_fails = 0 if self.alive else self.consecutive_fails + 1
            return self.alive
        except Exception:
            self.alive = False
            self.consecutive_fails += 1
            return False
    def to_dict(self):
        return {"name": self.name, "alive": self.alive, "priority": self.priority,
                "success_rate": self.success_rate(), "latency_avg": self.latency_avg,
                "consecutive_fails": self.consecutive_fails}

class Router:
    """
    Routes prompts to the best available AI.
    Handles failover automatically. User never loses interaction.
    """
    def __init__(self, arbiter=None, eventbus=None):
        self.arbiter = arbiter
        self.eventbus = eventbus
        self.endpoints = {}
        self.history = deque(maxlen=200)
        self.active_endpoint = None
        self.running = False
        self._thread = None
        self._lock = threading.Lock()
        self._register_defaults()

    def _register_defaults(self):
        # ── Local AI endpoints ──
        self.add_endpoint(ModelEndpoint(
            "brain", "http://127.0.0.1:9990/v1/chat/completions",
            "http://127.0.0.1:9990/health", "local", priority=1))
        self.add_endpoint(ModelEndpoint(
            "ollama", "http://127.0.0.1:11434/api/chat",
            "http://127.0.0.1:11434/api/tags", "llama3:latest", priority=2))
        # ── Cloud Router (all 10 providers behind one gateway) ──
        self.add_endpoint(ModelEndpoint(
            "cloud_router", "http://127.0.0.1:9878/api/v1/chat",
            "http://127.0.0.1:9878/health", "cloud", priority=3))
        # ── Hivemind cluster (parallel local model swarm) ──
        self.add_endpoint(ModelEndpoint(
            "hivemind", "http://127.0.0.1:9881/hive/query",
            "http://127.0.0.1:9881/health", "swarm", priority=4))
        # ── Max Patch (intelligent routing through specialist models) ──
        self.add_endpoint(ModelEndpoint(
            "max_patch", "http://127.0.0.1:9889/patch/route",
            "http://127.0.0.1:9889/health", "patch", priority=5))

    def add_endpoint(self, endpoint):
        self.endpoints[endpoint.name] = endpoint

    def select_best(self):
        """Select best alive endpoint by priority then success rate."""
        alive = [e for e in self.endpoints.values() if e.alive]
        if not alive:
            # Recheck all
            for e in self.endpoints.values():
                e.check_health()
            alive = [e for e in self.endpoints.values() if e.alive]
        if not alive:
            return None
        alive.sort(key=lambda e: (-e.priority, -e.success_rate()))
        return alive[0] if alive else None

    def route(self, packet):
        """Route a prompt packet to the best AI and get response."""
        best = self.select_best()
        if not best:
            packet.routed_to = "none"
            packet.success = False
            packet.response = "All AI services offline. Attempting recovery..."
            self.history.append(packet)
            if self.eventbus:
                self.eventbus.publish("reroute", "router", "All endpoints down")
            return packet

        packet.routed_to = best.name
        t0 = time.time()
        try:
            response = self._call_endpoint(best, packet.user_text)
            packet.latency = round((time.time() - t0) * 1000)
            packet.response = response
            packet.success = True
            best.success_count += 1
            best.latency_avg = (best.latency_avg * 0.8) + (packet.latency * 0.2)
            self.active_endpoint = best.name
        except Exception as e:
            packet.latency = round((time.time() - t0) * 1000)
            packet.success = False
            packet.response = str(e)
            best.fail_count += 1
            best.alive = False
            # Failover: try next best
            fallback = self.select_best()
            if fallback and fallback.name != best.name:
                try:
                    response = self._call_endpoint(fallback, packet.user_text)
                    packet.routed_to = fallback.name + " (failover)"
                    packet.response = response
                    packet.success = True
                    fallback.success_count += 1
                    self.active_endpoint = fallback.name
                    if self.eventbus:
                        self.eventbus.publish("reroute", "router",
                            best.name + " down, rerouted to " + fallback.name)
                except Exception:
                    packet.response = "All AI endpoints failed."

        self.history.append(packet)
        return packet

    def _call_endpoint(self, endpoint, text):
        """Call an AI endpoint and return text response."""
        import urllib.request
        sys_prompt = "You are Nova, a helpful AI assistant. Keep responses concise. Max 2-3 sentences."

        if endpoint.name == "brain":
            body = json.dumps({"model": "local", "messages": [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": text}], "max_tokens": 200})
            req = urllib.request.Request(endpoint.chat_url, data=body.encode(),
                headers={"Content-Type": "application/json"}, method="POST")
            r = urllib.request.urlopen(req, timeout=15)
            data = json.loads(r.read().decode())
            return data["choices"][0]["message"]["content"]

        elif endpoint.name == "ollama":
            body = json.dumps({"model": endpoint.model_id, "messages": [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": text}], "stream": False})
            req = urllib.request.Request(endpoint.chat_url, data=body.encode(),
                headers={"Content-Type": "application/json"}, method="POST")
            r = urllib.request.urlopen(req, timeout=30)
            data = json.loads(r.read().decode())
            return data["message"]["content"]

        elif endpoint.name == "cloud_router":
            # Cloud Router: OpenAI-compatible chat endpoint → routes to best provider
            body = json.dumps({"prompt": text, "provider": "auto"})
            req = urllib.request.Request(endpoint.chat_url, data=body.encode(),
                headers={"Content-Type": "application/json"}, method="POST")
            r = urllib.request.urlopen(req, timeout=30)
            raw = r.read()
            if r.headers.get("Content-Encoding") == "gzip":
                import gzip
                raw = gzip.decompress(raw)
            data = json.loads(raw)
            return data.get("text", data.get("response", str(data)))

        elif endpoint.name == "hivemind":
            # Hivemind cluster query — parallel model swarm
            body = json.dumps({"prompt": text, "channel": "REASON", "top_k": 3})
            req = urllib.request.Request(endpoint.chat_url, data=body.encode(),
                headers={"Content-Type": "application/json"}, method="POST")
            r = urllib.request.urlopen(req, timeout=60)
            data = json.loads(r.read().decode())
            return data.get("merged", data.get("response", str(data)))

        elif endpoint.name == "max_patch":
            # Max Patch: smart-routed through specialist models
            body = json.dumps({"prompt": text, "channel": "REASON"})
            req = urllib.request.Request(endpoint.chat_url, data=body.encode(),
                headers={"Content-Type": "application/json"}, method="POST")
            r = urllib.request.urlopen(req, timeout=60)
            data = json.loads(r.read().decode())
            return data.get("response", data.get("text", str(data)))

        raise Exception("Unknown endpoint: " + endpoint.name)

    def route_text(self, text):
        """Shortcut: create packet from text and route."""
        pkt = PromptPacket(text, mode="auto")
        return self.route(pkt)

    def check_all_health(self):
        """Check health of all endpoints."""
        results = {}
        for name, ep in self.endpoints.items():
            ep.check_health()
            results[name] = ep.alive
        return results

    def start_health_loop(self, interval=10):
        """Continuous health monitoring."""
        if self.running: return
        self.running = True
        def loop():
            while self.running:
                self.check_all_health()
                time.sleep(interval)
        self._thread = threading.Thread(target=loop, daemon=True)
        self._thread.start()

    def stop(self):
        self.running = False

    def status(self):
        return {
            "active_endpoint": self.active_endpoint,
            "endpoints": {n: e.to_dict() for n, e in self.endpoints.items()},
            "total_routed": len(self.history),
            "recent": [p.to_dict() for p in list(self.history)[-10:]],
            "running": self.running,
        }
