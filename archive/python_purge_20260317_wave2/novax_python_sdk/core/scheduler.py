"""Scheduler - time-based job triggering."""
import threading, time

class Scheduler:
    def __init__(self):
        self.timers = {}
        self._running = False

    def every(self, name, seconds, callback):
        self.timers[name] = {"interval": seconds, "fn": callback, "last": 0}

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self): self._running = False

    def _loop(self):
        while self._running:
            now = time.time()
            for name, t in self.timers.items():
                if now - t["last"] >= t["interval"]:
                    try: t["fn"]()
                    except Exception as e: print(f"[Scheduler] {name}: {e}")
                    t["last"] = now
            time.sleep(1)
