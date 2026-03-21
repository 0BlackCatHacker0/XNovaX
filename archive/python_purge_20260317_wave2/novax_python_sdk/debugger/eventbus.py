"""
NovaX Event Bus - Structured Worker Communication
===================================================
No freeform chat. Workers post typed events.
Types: SUGGESTION, BLOCKER, PATCH, DECISION, RISK, STATUS
Router logs all events. Arbiter can filter.
"""
import time, threading, logging, json
from collections import deque
from enum import Enum

log = logging.getLogger("NovaX.EventBus")

class EventType(Enum):
    SUGGESTION = "suggestion"
    BLOCKER = "blocker"
    PATCH = "patch"
    DECISION = "decision"
    RISK = "risk"
    STATUS = "status"
    REPAIR = "repair"
    REROUTE = "reroute"
    HEALTH = "health"

class BusEvent:
    def __init__(self, event_type, from_id, payload, to_id="all", task_id=None):
        self.id = str(int(time.time() * 10000))
        self.type = event_type if isinstance(event_type, EventType) else EventType(event_type)
        self.from_id = from_id
        self.to_id = to_id
        self.task_id = task_id
        self.payload = payload
        self.ts = time.time()
        self.consumed_by = []
    def to_dict(self):
        return {"id": self.id, "type": self.type.value, "from": self.from_id,
                "to": self.to_id, "task_id": self.task_id,
                "payload": self.payload, "ts": self.ts}

class EventBus:
    """Central structured communication bus for all NovaX workers."""
    def __init__(self, max_events=500):
        self.events = deque(maxlen=max_events)
        self.subscribers = {}    # channel -> [callback]
        self.lock = threading.Lock()
        self.total_published = 0
        self.total_consumed = 0

    def publish(self, event_type, from_id, payload, to_id="all", task_id=None):
        """Publish a structured event to the bus."""
        evt = BusEvent(event_type, from_id, payload, to_id, task_id)
        with self.lock:
            self.events.append(evt)
            self.total_published += 1
        # Notify subscribers
        self._notify(evt)
        log.debug("Event: " + evt.type.value + " from=" + from_id)
        return evt

    def subscribe(self, channel, callback):
        """Subscribe to events. Channel can be event type or worker id."""
        if channel not in self.subscribers:
            self.subscribers[channel] = []
        self.subscribers[channel].append(callback)

    def _notify(self, evt):
        """Notify matching subscribers."""
        targets = []
        # By event type
        type_subs = self.subscribers.get(evt.type.value, [])
        targets.extend(type_subs)
        # By recipient
        to_subs = self.subscribers.get(evt.to_id, [])
        targets.extend(to_subs)
        # Broadcast
        all_subs = self.subscribers.get("all", [])
        targets.extend(all_subs)
        for cb in targets:
            try:
                cb(evt)
                evt.consumed_by.append(str(cb))
                self.total_consumed += 1
            except Exception as e:
                log.error("Subscriber error: " + str(e))

    def query(self, event_type=None, from_id=None, task_id=None, limit=20):
        """Query recent events with filters."""
        results = []
        for evt in reversed(list(self.events)):
            if event_type and evt.type.value != event_type:
                continue
            if from_id and evt.from_id != from_id:
                continue
            if task_id and evt.task_id != task_id:
                continue
            results.append(evt.to_dict())
            if len(results) >= limit:
                break
        return results

    def blockers(self, task_id=None):
        """Get all active blockers."""
        return self.query(event_type="blocker", task_id=task_id, limit=50)

    def status(self):
        return {
            "total_published": self.total_published,
            "total_consumed": self.total_consumed,
            "queue_size": len(self.events),
            "subscribers": len(self.subscribers),
            "recent": [e.to_dict() for e in list(self.events)[-10:]],
        }
