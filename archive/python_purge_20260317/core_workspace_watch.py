# workspace_watch.py — Workspace monitor for query tracking and model health
# Records query starts/completions, model health, activity feed, throughput

import time
from collections import deque


class WorkspaceWatch:
    """Tracks AI query activity, model health, and workspace changes."""

    def __init__(self):
        self.watching = True
        self.activity_feed = deque(maxlen=500)
        self.model_health = {}
        self._active_queries = {}
        self._throughput = deque(maxlen=1000)

    def start(self, **kwargs):
        self.watching = True
        return True

    def stop(self):
        self.watching = False
        return True

    def record_query_start(self, query_id, model, text_preview=""):
        """Record the start of an AI query."""
        self._active_queries[query_id] = {
            "model": model,
            "text": text_preview[:100],
            "start": time.time(),
        }
        self.activity_feed.append({
            "type": "query_start",
            "model": model,
            "text": text_preview[:100],
            "time": time.time(),
        })

    def record_query_complete(self, query_id, model, success, duration_ms, reply_preview=""):
        """Record completion of an AI query."""
        self._active_queries.pop(query_id, None)
        # Update model health
        if model not in self.model_health:
            self.model_health[model] = {"success": 0, "fail": 0, "total_ms": 0}
        if success:
            self.model_health[model]["success"] += 1
        else:
            self.model_health[model]["fail"] += 1
        self.model_health[model]["total_ms"] += duration_ms
        self.activity_feed.append({
            "type": "query_complete",
            "model": model,
            "success": success,
            "duration_ms": duration_ms,
            "reply": reply_preview[:100],
            "time": time.time(),
        })
        self._throughput.append({
            "model": model,
            "ok": success,
            "ms": duration_ms,
            "time": time.time(),
        })

    def record_event(self, event_type, model, data=None):
        """Record a generic event."""
        self.activity_feed.append({
            "type": event_type,
            "model": model,
            "data": data,
            "time": time.time(),
        })

    def record_handoff(self, from_model, to_model, reason=""):
        """Record a model handoff."""
        self.activity_feed.append({
            "type": "handoff",
            "from": from_model,
            "to": to_model,
            "reason": reason,
            "time": time.time(),
        })

    def status(self):
        return {
            "watching": self.watching,
            "active_queries": len(self._active_queries),
            "total_events": len(self.activity_feed),
            "models_tracked": len(self.model_health),
        }

    def get_active(self):
        return list(self._active_queries.values())

    def get_feed(self, limit=50, event_type=None):
        feed = list(self.activity_feed)
        if event_type:
            feed = [e for e in feed if e.get("type") == event_type]
        return feed[-limit:]

    def get_health(self):
        return self.model_health

    def get_throughput(self, window=300):
        """Get throughput stats for the last N seconds."""
        cutoff = time.time() - window
        recent = [t for t in self._throughput if t["time"] > cutoff]
        total = len(recent)
        success = sum(1 for t in recent if t["ok"])
        avg_ms = sum(t["ms"] for t in recent) / max(total, 1)
        return {
            "window_seconds": window,
            "total": total,
            "success": success,
            "fail": total - success,
            "avg_ms": round(avg_ms, 1),
        }

    def get_changes(self, **kwargs):
        return []


workspace_watch = WorkspaceWatch()
