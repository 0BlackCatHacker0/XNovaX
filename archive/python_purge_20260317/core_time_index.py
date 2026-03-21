# time_index.py — Stub for orchestrator startup
# Original encrypted (.enc). Provides minimal no-op implementations.

_events = []

def record_event(event_type=None, data=None, **kwargs):
    """Record a timestamped event. Stub appends to in-memory list."""
    import time
    _events.append({"type": event_type, "data": data, "ts": time.time(), **kwargs})
    return True

def search(query=None, start=None, end=None, **kwargs):
    """Search events by query/time range. Stub returns empty list."""
    return []
