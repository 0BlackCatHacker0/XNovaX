"""
NovaX Time-Travel Debugging Service
Port: 9943

Append-only event log with replay, search, and root-cause analysis.
Every significant decision in the NovaX pipeline is captured as an event,
linked by correlation_id for end-to-end tracing.

Event types:
  QUERY_RECEIVED, ROUTE_DECISION, MODEL_SELECTED, MODEL_RESPONSE,
  CONFIDENCE_SCORE, ESCALATION, ERROR, TOOL_CALL, CACHE_HIT, USER_FEEDBACK

Integration (other services call POST /events/log):
  - Orchestrator: log on every /think request with correlation_id
  - Cloud Router: log model selection (MODEL_SELECTED) and response (MODEL_RESPONSE)
  - Hivemind: log deliberation phases (ROUTE_DECISION, CONFIDENCE_SCORE)

Usage:
  python nova_time_travel.py
"""

import json
import os
import sys
import time
import uuid
import threading
import re
from datetime import datetime, timedelta, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
HOST = "127.0.0.1"
PORT = 9943
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
LOG_FILE = os.path.join(DATA_DIR, "event_log.jsonl")
MAX_LOG_SIZE = 100 * 1024 * 1024  # 100 MB

VALID_EVENT_TYPES = {
    "QUERY_RECEIVED", "ROUTE_DECISION", "MODEL_SELECTED", "MODEL_RESPONSE",
    "CONFIDENCE_SCORE", "ESCALATION", "ERROR", "TOOL_CALL", "CACHE_HIT",
    "USER_FEEDBACK",
}

# ---------------------------------------------------------------------------
# Thread-safe append-only log writer
# ---------------------------------------------------------------------------
_log_lock = threading.Lock()


def _ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def _rotate_if_needed():
    """Rotate log file when it exceeds MAX_LOG_SIZE."""
    try:
        if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > MAX_LOG_SIZE:
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            rotated = os.path.join(DATA_DIR, f"event_log_{stamp}.jsonl")
            os.rename(LOG_FILE, rotated)
    except OSError:
        pass  # race-safe: if rename fails, next write creates fresh file


def append_event(event):
    """Append a single event dict as one JSON line. Crash-safe via flush+fsync."""
    _ensure_data_dir()
    with _log_lock:
        _rotate_if_needed()
        line = json.dumps(event, ensure_ascii=True, separators=(",", ":")) + "\n"
        with open(LOG_FILE, "a", encoding="ascii") as f:
            f.write(line)
            f.flush()
            os.fsync(f.fileno())


# ---------------------------------------------------------------------------
# Log scanning helpers (line-by-line, never full load)
# ---------------------------------------------------------------------------
def _iter_events(path=None):
    """Yield parsed event dicts from the log file, one line at a time."""
    target = path or LOG_FILE
    if not os.path.exists(target):
        return
    with open(target, "r", encoding="ascii") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def _parse_ts(ts_str):
    """Parse ISO timestamp string to epoch float."""
    try:
        # Handle both Z suffix and +00:00
        ts_str = ts_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(ts_str)
        return dt.timestamp()
    except (ValueError, AttributeError):
        return 0.0


def _parse_duration(spec):
    """Parse duration like '24h', '7d', '30m' to seconds."""
    m = re.match(r"^(\d+)([hdms])$", spec)
    if not m:
        return 86400  # default 24h
    val, unit = int(m.group(1)), m.group(2)
    mult = {"h": 3600, "d": 86400, "m": 60, "s": 1}
    return val * mult.get(unit, 3600)


# ---------------------------------------------------------------------------
# Query functions
# ---------------------------------------------------------------------------
def replay_correlation(correlation_id):
    """Return all events for a correlation_id, ordered by timestamp."""
    events = []
    for ev in _iter_events():
        if ev.get("correlation_id") == correlation_id:
            events.append(ev)
    events.sort(key=lambda e: e.get("timestamp", ""))
    # Calculate end-to-end latency
    latency_ms = None
    if len(events) >= 2:
        t_start = _parse_ts(events[0].get("timestamp", ""))
        t_end = _parse_ts(events[-1].get("timestamp", ""))
        if t_start and t_end:
            latency_ms = round((t_end - t_start) * 1000, 2)
    return {
        "correlation_id": correlation_id,
        "event_count": len(events),
        "latency_ms": latency_ms,
        "events": events,
    }


def search_events(query=None, from_ts=None, to_ts=None, limit=500):
    """Search events by text and/or time range."""
    from_epoch = _parse_ts(from_ts) if from_ts else 0
    to_epoch = _parse_ts(to_ts) if to_ts else float("inf")
    results = []
    for ev in _iter_events():
        ts = _parse_ts(ev.get("timestamp", ""))
        if ts < from_epoch or ts > to_epoch:
            continue
        if query:
            blob = json.dumps(ev, ensure_ascii=True).lower()
            if query.lower() not in blob:
                continue
        results.append(ev)
        if len(results) >= limit:
            break
    return results


def timeline(last_n=100):
    """Return last N events chronologically (tail of file)."""
    # Collect from end efficiently using a deque-like approach
    buf = []
    for ev in _iter_events():
        buf.append(ev)
        if len(buf) > last_n * 2:
            buf = buf[-last_n:]
    return buf[-last_n:]


def errors_in_window(duration_spec="24h"):
    """Return all ERROR events within the given time window."""
    secs = _parse_duration(duration_spec)
    cutoff = time.time() - secs
    results = []
    for ev in _iter_events():
        if ev.get("event_type") != "ERROR":
            continue
        ts = _parse_ts(ev.get("timestamp", ""))
        if ts >= cutoff:
            results.append(ev)
    return results


def compute_stats():
    """Compute event counts by type, error rate, average latency."""
    type_counts = {}
    total = 0
    error_count = 0
    # Track latencies per correlation_id
    corr_start = {}
    corr_end = {}

    for ev in _iter_events():
        total += 1
        et = ev.get("event_type", "UNKNOWN")
        type_counts[et] = type_counts.get(et, 0) + 1
        if et == "ERROR":
            error_count += 1
        cid = ev.get("correlation_id")
        if cid:
            ts = _parse_ts(ev.get("timestamp", ""))
            if cid not in corr_start:
                corr_start[cid] = ts
            corr_end[cid] = ts

    # Calculate average latency
    latencies = []
    for cid in corr_start:
        if cid in corr_end and corr_end[cid] > corr_start[cid]:
            latencies.append((corr_end[cid] - corr_start[cid]) * 1000)

    avg_latency_ms = round(sum(latencies) / len(latencies), 2) if latencies else None
    p95_latency_ms = None
    if latencies:
        latencies.sort()
        idx = int(len(latencies) * 0.95)
        p95_latency_ms = round(latencies[min(idx, len(latencies) - 1)], 2)

    return {
        "total_events": total,
        "event_counts": type_counts,
        "error_count": error_count,
        "error_rate": round(error_count / total, 4) if total else 0,
        "unique_queries": len(corr_start),
        "avg_latency_ms": avg_latency_ms,
        "p95_latency_ms": p95_latency_ms,
    }


def slow_queries(threshold_ms=5000):
    """Find queries that took longer than threshold_ms end-to-end."""
    corr_start = {}
    corr_end = {}
    corr_events = {}

    for ev in _iter_events():
        cid = ev.get("correlation_id")
        if not cid:
            continue
        ts = _parse_ts(ev.get("timestamp", ""))
        if cid not in corr_start:
            corr_start[cid] = ts
            corr_events[cid] = []
        corr_end[cid] = ts
        corr_events[cid].append(ev.get("event_type", "UNKNOWN"))

    results = []
    for cid in corr_start:
        if cid in corr_end:
            latency = (corr_end[cid] - corr_start[cid]) * 1000
            if latency >= threshold_ms:
                results.append({
                    "correlation_id": cid,
                    "latency_ms": round(latency, 2),
                    "event_types": corr_events.get(cid, []),
                })
    results.sort(key=lambda r: r["latency_ms"], reverse=True)
    return results


def model_events(model_name):
    """Return all events involving a specific model."""
    results = []
    for ev in _iter_events():
        blob = json.dumps(ev.get("data", {}), ensure_ascii=True).lower()
        src = (ev.get("source_service") or "").lower()
        if model_name.lower() in blob or model_name.lower() in src:
            results.append(ev)
        elif model_name.lower() in (ev.get("event_type", "")).lower():
            results.append(ev)
    return results


def prune_before(timestamp_str):
    """Delete events before the given timestamp. Rewrites the log file."""
    cutoff = _parse_ts(timestamp_str)
    if cutoff == 0:
        return {"error": "Invalid timestamp", "deleted": 0}

    kept = 0
    deleted = 0
    tmp_path = LOG_FILE + ".tmp"

    with _log_lock:
        with open(tmp_path, "w", encoding="ascii") as out:
            for ev in _iter_events():
                ts = _parse_ts(ev.get("timestamp", ""))
                if ts >= cutoff:
                    out.write(json.dumps(ev, ensure_ascii=True, separators=(",", ":")) + "\n")
                    kept += 1
                else:
                    deleted += 1
            out.flush()
            os.fsync(out.fileno())
        # Atomic-ish replace
        if os.path.exists(LOG_FILE):
            os.remove(LOG_FILE)
        os.rename(tmp_path, LOG_FILE)

    return {"deleted": deleted, "kept": kept}


# ---------------------------------------------------------------------------
# HTTP Handler
# ---------------------------------------------------------------------------
class TimeTravelHandler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        """Suppress default stderr logging."""
        pass

    def _send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=True, indent=2).encode("ascii")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "localhost")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8"))

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "localhost")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        params = parse_qs(parsed.query)

        # GET /health
        if path == "/health":
            log_size = 0
            if os.path.exists(LOG_FILE):
                log_size = os.path.getsize(LOG_FILE)
            self._send_json({
                "status": "ok",
                "service": "nova_time_travel",
                "port": PORT,
                "log_file": LOG_FILE,
                "log_size_bytes": log_size,
                "uptime_seconds": round(time.time() - _start_time, 1),
            })
            return

        # GET /events/replay/<correlation_id>
        if path.startswith("/events/replay/"):
            cid = path[len("/events/replay/"):]
            if not cid:
                self._send_json({"error": "Missing correlation_id"}, 400)
                return
            self._send_json(replay_correlation(cid))
            return

        # GET /events/search?q=...&from=...&to=...
        if path == "/events/search":
            q = params.get("q", [None])[0]
            fr = params.get("from", [None])[0]
            to = params.get("to", [None])[0]
            lim = int(params.get("limit", [500])[0])
            self._send_json({"results": search_events(q, fr, to, lim)})
            return

        # GET /events/timeline?last=100
        if path == "/events/timeline":
            n = int(params.get("last", [100])[0])
            self._send_json({"events": timeline(n)})
            return

        # GET /events/errors?last=24h
        if path == "/events/errors":
            window = params.get("last", ["24h"])[0]
            errs = errors_in_window(window)
            self._send_json({"error_count": len(errs), "errors": errs})
            return

        # GET /events/stats
        if path == "/events/stats":
            self._send_json(compute_stats())
            return

        # GET /events/slow?threshold=5000
        if path == "/events/slow":
            thresh = int(params.get("threshold", [5000])[0])
            self._send_json({"threshold_ms": thresh, "slow_queries": slow_queries(thresh)})
            return

        # GET /events/model/<model_name>
        if path.startswith("/events/model/"):
            name = path[len("/events/model/"):]
            if not name:
                self._send_json({"error": "Missing model name"}, 400)
                return
            evts = model_events(name)
            self._send_json({"model": name, "event_count": len(evts), "events": evts})
            return

        self._send_json({"error": "Not found", "endpoints": [
            "GET /health",
            "POST /events/log",
            "GET /events/replay/<correlation_id>",
            "GET /events/search?q=&from=&to=",
            "GET /events/timeline?last=100",
            "GET /events/errors?last=24h",
            "GET /events/stats",
            "GET /events/slow?threshold=5000",
            "GET /events/model/<model_name>",
            "DELETE /events/before/<timestamp>",
        ]}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        # POST /events/log
        if path == "/events/log":
            try:
                body = self._read_body()
            except (json.JSONDecodeError, ValueError):
                self._send_json({"error": "Invalid JSON body"}, 400)
                return

            event_type = body.get("event_type", "")
            if event_type not in VALID_EVENT_TYPES:
                self._send_json({
                    "error": f"Invalid event_type: {event_type}",
                    "valid_types": sorted(VALID_EVENT_TYPES),
                }, 400)
                return

            # Build canonical event
            event = {
                "timestamp": body.get("timestamp") or datetime.now(timezone.utc).isoformat(),
                "event_type": event_type,
                "source_service": body.get("source_service", "unknown"),
                "correlation_id": body.get("correlation_id") or str(uuid.uuid4()),
                "data": body.get("data", {}),
            }

            append_event(event)
            self._send_json({
                "status": "logged",
                "correlation_id": event["correlation_id"],
            }, 201)
            return

        self._send_json({"error": "Not found"}, 404)

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        # DELETE /events/before/<timestamp>
        if path.startswith("/events/before/"):
            ts = path[len("/events/before/"):]
            if not ts:
                self._send_json({"error": "Missing timestamp"}, 400)
                return
            result = prune_before(ts)
            self._send_json(result)
            return

        self._send_json({"error": "Not found"}, 404)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
_start_time = time.time()


def main():
    _ensure_data_dir()
    server = HTTPServer((HOST, PORT), TimeTravelHandler)
    server.timeout = 1
    print(f"[NovaX Time-Travel Debug] Listening on {HOST}:{PORT}")
    print(f"[NovaX Time-Travel Debug] Log file: {LOG_FILE}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[NovaX Time-Travel Debug] Shutting down.")
        server.server_close()


if __name__ == "__main__":
    main()
