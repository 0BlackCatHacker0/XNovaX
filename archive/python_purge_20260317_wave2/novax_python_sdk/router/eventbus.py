"""NovaX Event Bus - Structured communication between all components."""
import time, threading, json, logging, os
from collections import deque
from enum import Enum

log = logging.getLogger("NovaX.EventBus")

class EventType(Enum):
    SUGGESTION = "SUGGESTION"
    BLOCKER = "BLOCKER"
    PATCH = "PATCH"
    DECISION = "DECISION"
    RISK = "RISK"
    STATUS = "STATUS"
    HEALTH = "HEALTH"
    REPAIR_REQUEST = "REPAIR_REQUEST"
    REPAIR_RESULT = "REPAIR_RESULT"
    ROUTE_CHANGE = "ROUTE_CHANGE"
    TASK_UPDATE = "TASK_UPDATE"
    ARBITER_ORDER = "ARBITER_ORDER"
    GUARDIAN_ALERT = "GUARDIAN_ALERT"
    MODEL_SWAP = "MODEL_SWAP"
    PROMPT_ROUTED = "PROMPT_ROUTED"
    PROOF_RESULT = "PROOF_RESULT"

class Event:
    def __init__(self, etype, source, target="all", task_id=None, payload=None):
        self.id = str(int(time.time() * 1000000))
        self.type = etype if isinstance(etype, EventType) else EventType(etype)
        self.source = source
        self.target = target
        self.task_id = task_id
        self.payload = payload or {}
        self.ts = time.time()
    def to_dict(self):
        return {"id": self.id, "type": self.type.value, "source": self.source,
                "target": self.target, "task_id": self.task_id,
                "payload": self.payload, "ts": self.ts}

class EventBus:
    """Central event bus for all NovaX inter-component communication."""
    def __init__(self, max_history=500):
        self.history = deque(maxlen=max_history)
        self.subscribers = {}  # event_type -> [callback]
        self.filters = {}      # subscriber_id -> [event_types]
        self._lock = threading.Lock()
        self.total_events = 0
        self.total_dropped = 0

    def subscribe(self, subscriber_id, event_types, callback):
        with self._lock:
            for et in event_types:
                key = et.value if isinstance(et, EventType) else et
                if key not in self.subscribers:
                    self.subscribers[key] = []
                self.subscribers[key].append({"id": subscriber_id, "cb": callback})
            self.filters[subscriber_id] = event_types

    def unsubscribe(self, subscriber_id):
        with self._lock:
            for key in list(self.subscribers.keys()):
                self.subscribers[key] = [s for s in self.subscribers[key] if s["id"] != subscriber_id]
            self.filters.pop(subscriber_id, None)

    def emit(self, event):
        with self._lock:
            self.history.append(event)
            self.total_events += 1
            key = event.type.value if isinstance(event.type, EventType) else event.type
            subs = self.subscribers.get(key, [])
        for sub in subs:
            try:
                if event.target == "all" or event.target == sub["id"]:
                    sub["cb"](event)
            except Exception as e:
                log.error("EventBus delivery failed to " + sub["id"] + ": " + str(e))
                self.total_dropped += 1

    def post(self, etype, source, target="all", task_id=None, payload=None):
        e = Event(etype, source, target, task_id, payload)
        self.emit(e)
        return e

    def query(self, event_type=None, source=None, limit=20):
        results = []
        for e in reversed(self.history):
            if event_type and e.type != event_type:
                continue
            if source and e.source != source:
                continue
            results.append(e.to_dict())
            if len(results) >= limit:
                break
        return results

    def status(self):
        return {"total_events": self.total_events,
                "total_dropped": self.total_dropped,
                "subscribers": list(self.filters.keys()),
                "history_size": len(self.history),
                "recent": [e.to_dict() for e in list(self.history)[-10:]]}

# Global singleton
_bus = None
def get_bus():
    global _bus
    if _bus is None:
        _bus = EventBus()
    return _bus