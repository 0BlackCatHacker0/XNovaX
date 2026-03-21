"""NovaX Event Bus - modules communicate through events, not direct calls."""
import threading
from collections import defaultdict
from typing import Callable, Any

class EventBus:
    def __init__(self):
        self._subs = defaultdict(list)
        self._lock = threading.Lock()
        self._history = []

    def emit(self, event: str, data: Any = None):
        entry = {"event": event, "data": data}
        with self._lock:
            self._history.append(entry)
            if len(self._history) > 500:
                self._history = self._history[-250:]
        for cb in self._subs.get(event, []):
            try:
                cb(data)
            except Exception as e:
                print(f"[EventBus] Handler error on {event}: {e}")

    def on(self, event: str, callback: Callable):
        with self._lock:
            self._subs[event].append(callback)

    def off(self, event: str, callback: Callable = None):
        with self._lock:
            if callback:
                self._subs[event] = [c for c in self._subs[event] if c != callback]
            else:
                self._subs[event] = []

    def recent(self, n: int = 20):
        return self._history[-n:]

    def stats(self):
        return {e: len(cbs) for e, cbs in self._subs.items()}

# Singleton
bus = EventBus()

# Event type constants
SERVICE_STARTED = "service.started"
SERVICE_STOPPED = "service.stopped"
SERVICE_CRASHED = "service.crashed"
JOB_CREATED = "job.created"
JOB_COMPLETED = "job.completed"
JOB_FAILED = "job.failed"
POLICY_DENIED = "policy.denied"
SNAPSHOT_CREATED = "snapshot.created"
INTENT_DETECTED = "intent.detected"
RECOVERY_PERFORMED = "recovery.performed"
SYSTEM_READY = "system.ready"
SYSTEM_SHUTDOWN = "system.shutdown"
