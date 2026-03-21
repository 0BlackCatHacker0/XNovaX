"""Health monitor - watches services, detects failures, triggers recovery."""
import time
from ..objects import Incident
from ..events.bus import bus, SERVICE_CRASHED, RECOVERY_PERFORMED

class HealthMonitor:
    def __init__(self):
        self.services = {}
        self.incidents = []

    def register(self, name, probe_fn, recover_fn=None):
        self.services[name] = {"probe": probe_fn, "recover": recover_fn,
            "status": "unknown", "last_check": 0, "failures": 0}

    def check_all(self):
        results = {}
        for name, svc in self.services.items():
            try:
                ok = svc["probe"]()
                svc["status"] = "healthy" if ok else "degraded"
                svc["failures"] = 0 if ok else svc["failures"] + 1
            except Exception as e:
                svc["status"] = "down"
                svc["failures"] += 1
                inc = Incident(service=name, error=str(e))
                self.incidents.append(inc)
                bus.emit(SERVICE_CRASHED, {"service": name, "error": str(e)})
                if svc["recover"] and svc["failures"] >= 2:
                    try:
                        svc["recover"]()
                        inc.recovered = True
                        bus.emit(RECOVERY_PERFORMED, {"service": name})
                    except: pass
            svc["last_check"] = time.time()
            results[name] = svc["status"]
        return results

    def status(self): return {n: s["status"] for n, s in self.services.items()}
    def recent_incidents(self, n=20): return self.incidents[-n:]
