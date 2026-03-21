# event_bus.py — Event Bus: pub/sub messaging with event history
# Orchestrator uses: emit(), on(), off(), recent()
# Events: STATUS, REPAIR_APPLIED, QUERY_START, QUERY_COMPLETE, etc.

import time
from collections import deque


class EventBus:
    """Event Bus with pub/sub handlers and event history."""

    def __init__(self, max_history=500):
        self._handlers = {}
        self._history = deque(maxlen=max_history)

    def on(self, event, handler):
        """Subscribe a handler to an event type."""
        self._handlers.setdefault(event, []).append(handler)

    def emit(self, event, data=None, source=None, **kwargs):
        """Emit an event to all subscribers and record in history."""
        entry = {
            "event": event,
            "data": data,
            "source": source or "unknown",
            "time": time.time(),
        }
        self._history.append(entry)

        for h in self._handlers.get(event, []):
            try:
                h(data)
            except Exception:
                pass
        # Also fire wildcard handlers
        for h in self._handlers.get("*", []):
            try:
                h(entry)
            except Exception:
                pass

    def off(self, event, handler=None):
        """Unsubscribe a handler or all handlers for an event."""
        if handler:
            handlers = self._handlers.get(event, [])
            if handler in handlers:
                handlers.remove(handler)
        else:
            self._handlers.pop(event, None)

    def recent(self, limit=50, event_type=None):
        """Get recent events from history, optionally filtered by type."""
        events = list(self._history)
        if event_type:
            events = [e for e in events if e.get("event") == event_type]
        return events[-limit:]

    def stats(self):
        """Get event bus statistics."""
        event_counts = {}
        for e in self._history:
            et = e.get("event", "?")
            event_counts[et] = event_counts.get(et, 0) + 1
        return {
            "total_events": len(self._history),
            "handlers": {k: len(v) for k, v in self._handlers.items()},
            "event_counts": event_counts,
        }


bus = EventBus()
