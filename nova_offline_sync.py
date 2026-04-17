"""NovaX Offline-First Sync Service
Port 9949 -- manages offline/online state transitions.
When offline, queries route to local Ollama models.
When online, queued items sync through cloud providers.
State: C:\\NovaX\\data\\sync_state.json
Queue: C:\\NovaX\\data\\offline_queue.jsonl
"""
import http.server
import json
import os
import sys
import time
import threading
import uuid
import urllib.request
import urllib.error
from collections import deque
from datetime import datetime

PORT = 9949
DATA_DIR = "C:\\NovaX\\data"
STATE_FILE = os.path.join(DATA_DIR, "sync_state.json")
QUEUE_FILE = os.path.join(DATA_DIR, "offline_queue.jsonl")
HISTORY_MAX = 50
PING_INTERVAL = 30  # seconds between connectivity checks
CLOUD_TIMEOUT = 5   # seconds for cloud reachability checks

os.makedirs(DATA_DIR, exist_ok=True)

# ---- Cloud provider endpoints to probe ----
CLOUD_ENDPOINTS = {
    "google":    "http://www.google.com",
    "openai":    "http://127.0.0.1:9878/health",   # cloud router
    "ollama":    "http://127.0.0.1:11434/api/tags",
    "hivemind":  "http://127.0.0.1:9881/health",
}

# ---- Sync State ----
class SyncState:
    """Thread-safe sync state manager."""

    def __init__(self):
        self.lock = threading.Lock()
        self.mode = "auto"         # "auto" | "offline"
        self.status = "unknown"    # "online" | "offline" | "degraded"
        self.last_check = None
        self.provider_status = {}  # provider_name -> True/False
        self.history = deque(maxlen=HISTORY_MAX)
        self.boot_time = datetime.utcnow().isoformat() + "Z"
        self._load()

    def _load(self):
        """Load persisted state from disk."""
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.mode = data.get("mode", "auto")
                self.status = data.get("status", "unknown")
                self.last_check = data.get("last_check")
                self.provider_status = data.get("provider_status", {})
                hist = data.get("history", [])
                self.history = deque(hist[-HISTORY_MAX:], maxlen=HISTORY_MAX)
            except Exception as e:
                print("[SYNC] Failed to load state: %s" % str(e))

    def _save(self):
        """Persist current state to disk."""
        data = {
            "mode": self.mode,
            "status": self.status,
            "last_check": self.last_check,
            "provider_status": self.provider_status,
            "history": list(self.history),
            "boot_time": self.boot_time,
        }
        try:
            tmp = STATE_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            # os.replace is ATOMIC on Windows NTFS — no gap where file is missing
            os.replace(tmp, STATE_FILE)
        except Exception as e:
            print("[SYNC] Failed to save state: %s" % str(e))

    def record_event(self, event_type, detail=""):
        """Add a sync history event."""
        entry = {
            "id": uuid.uuid4().hex[:12],
            "ts": datetime.utcnow().isoformat() + "Z",
            "type": event_type,
            "status": self.status,
            "detail": detail,
        }
        self.history.append(entry)

    def update(self, new_status, provider_results):
        """Update status and persist."""
        with self.lock:
            old_status = self.status
            self.status = new_status
            self.provider_status = provider_results
            self.last_check = datetime.utcnow().isoformat() + "Z"
            if old_status != new_status:
                self.record_event(
                    "transition",
                    "%s -> %s" % (old_status, new_status)
                )
                print("[SYNC] Status changed: %s -> %s" % (old_status, new_status))
            self._save()

    def set_mode(self, mode):
        with self.lock:
            self.mode = mode
            self.record_event("mode_change", "mode set to %s" % mode)
            if mode == "offline":
                self.status = "offline"
            self._save()

    def to_dict(self):
        with self.lock:
            return {
                "status": self.status,
                "mode": self.mode,
                "last_check": self.last_check,
                "provider_status": dict(self.provider_status),
                "boot_time": self.boot_time,
            }


# ---- Offline Queue ----
class OfflineQueue:
    """Append-only JSONL queue for items to sync when online."""

    def __init__(self):
        self.lock = threading.Lock()

    def add(self, item):
        """Add an item to the queue. Returns the item with id/ts."""
        entry = {
            "id": uuid.uuid4().hex[:12],
            "ts": datetime.utcnow().isoformat() + "Z",
            "status": "pending",
            "payload": item,
        }
        with self.lock:
            with open(QUEUE_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        return entry

    def get_all(self):
        """Read all queued items."""
        items = []
        if not os.path.exists(QUEUE_FILE):
            return items
        with self.lock:
            with open(QUEUE_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            items.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass
        return items

    def get_pending(self):
        """Return only pending items."""
        return [i for i in self.get_all() if i.get("status") == "pending"]

    def mark_done(self, item_ids, result="synced"):
        """Mark items as synced by rewriting the queue file."""
        done_set = set(item_ids)
        if not os.path.exists(QUEUE_FILE):
            return
        with self.lock:
            items = []
            with open(QUEUE_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        if entry.get("id") in done_set:
                            entry["status"] = result
                            entry["synced_at"] = datetime.utcnow().isoformat() + "Z"
                        items.append(entry)
                    except json.JSONDecodeError:
                        pass
            with open(QUEUE_FILE, "w", encoding="utf-8") as f:
                for entry in items:
                    f.write(json.dumps(entry) + "\n")

    def count(self):
        pending = self.get_pending()
        return {"total": len(self.get_all()), "pending": len(pending)}


# ---- Connectivity Checker ----
def check_endpoint(url, timeout=CLOUD_TIMEOUT):
    """Check if an endpoint is reachable. Returns True/False."""
    try:
        req = urllib.request.Request(url, method="GET")
        resp = urllib.request.urlopen(req, timeout=timeout)
        return resp.status < 500
    except Exception:
        return False


def check_connectivity(state):
    """
    Probe all cloud endpoints and determine overall status.
    Returns (status_string, provider_results_dict).
    """
    if state.mode == "offline":
        # Forced offline -- skip probes
        return "offline", {name: False for name in CLOUD_ENDPOINTS}

    results = {}
    for name, url in CLOUD_ENDPOINTS.items():
        results[name] = check_endpoint(url)

    online_count = sum(1 for v in results.values() if v)
    total = len(results)

    if online_count == 0:
        return "offline", results
    elif online_count == total:
        return "online", results
    else:
        return "degraded", results


# ---- Flush Logic ----
def flush_queue(state, queue):
    """
    Process all pending queue items through the cloud router.
    Returns (processed_count, failed_count).
    """
    pending = queue.get_pending()
    if not pending:
        return 0, 0

    processed = []
    failed = 0

    for item in pending:
        payload = item.get("payload", {})
        try:
            # Forward to cloud router for re-evaluation
            body = json.dumps({
                "prompt": payload.get("prompt", ""),
                "context": payload.get("context", ""),
                "source": "offline_sync",
                "original_id": item.get("id"),
            }).encode("utf-8")

            req = urllib.request.Request(
                "http://127.0.0.1:9878/v1/chat/completions",
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            resp = urllib.request.urlopen(req, timeout=30)
            if resp.status < 400:
                processed.append(item["id"])
            else:
                failed += 1
        except Exception as e:
            print("[SYNC] Flush failed for %s: %s" % (item.get("id", "?"), str(e)))
            failed += 1

    if processed:
        queue.mark_done(processed, result="synced")

    state.record_event(
        "flush",
        "processed=%d failed=%d" % (len(processed), failed)
    )
    return len(processed), failed


# ---- Background Monitor Thread ----
def connectivity_monitor(state, queue):
    """Background thread that checks connectivity every PING_INTERVAL seconds."""
    print("[SYNC] Connectivity monitor started (interval=%ds)" % PING_INTERVAL)
    while True:
        try:
            new_status, results = check_connectivity(state)
            old_status = state.status
            state.update(new_status, results)

            # Auto-flush when transitioning from offline/degraded to online
            if old_status in ("offline", "degraded", "unknown") and new_status == "online":
                pending_count = len(queue.get_pending())
                if pending_count > 0:
                    print("[SYNC] Back online -- flushing %d queued items" % pending_count)
                    flush_queue(state, queue)

        except Exception as e:
            print("[SYNC] Monitor error: %s" % str(e))

        time.sleep(PING_INTERVAL)


# ---- HTTP Handler ----
class SyncHandler(http.server.BaseHTTPRequestHandler):

    state = None   # set at startup
    queue = None   # set at startup

    def log_message(self, fmt, *args):
        # Quieter logging
        pass

    def _send_json(self, data, status=200):
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return {}

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?")[0].rstrip("/")

        if path == "/health":
            self._send_json({
                "service": "nova_offline_sync",
                "port": PORT,
                "status": "running",
                "sync_status": self.state.status,
                "mode": self.state.mode,
                "uptime_since": self.state.boot_time,
                "queue": self.queue.count(),
            })

        elif path == "/sync/status":
            self._send_json(self.state.to_dict())

        elif path == "/sync/queue":
            items = self.queue.get_all()
            self._send_json({
                "total": len(items),
                "pending": len([i for i in items if i.get("status") == "pending"]),
                "items": items[-100:],  # cap at last 100
            })

        elif path == "/sync/history":
            with self.state.lock:
                history = list(self.state.history)
            self._send_json({
                "count": len(history),
                "events": history,
            })

        else:
            self._send_json({"error": "not found", "path": path}, 404)

    def do_POST(self):
        path = self.path.split("?")[0].rstrip("/")

        if path == "/sync/check":
            new_status, results = check_connectivity(self.state)
            self.state.update(new_status, results)
            self._send_json({
                "status": new_status,
                "providers": results,
                "checked_at": self.state.last_check,
            })

        elif path == "/sync/queue/add":
            body = self._read_body()
            if not body:
                self._send_json({"error": "empty body"}, 400)
                return
            entry = self.queue.add(body)
            self.state.record_event("queue_add", "id=%s" % entry["id"])
            self._send_json({
                "queued": True,
                "item": entry,
                "queue_size": self.queue.count(),
            })

        elif path == "/sync/flush":
            if self.state.status == "offline":
                self._send_json({
                    "error": "cannot flush while offline",
                    "status": self.state.status,
                }, 409)
                return
            processed, failed = flush_queue(self.state, self.queue)
            self._send_json({
                "processed": processed,
                "failed": failed,
                "remaining": self.queue.count(),
            })

        elif path == "/sync/mode/offline":
            self.state.set_mode("offline")
            self._send_json({
                "mode": "offline",
                "status": self.state.status,
                "message": "Forced offline mode. All queries route to local models.",
            })

        elif path == "/sync/mode/auto":
            self.state.set_mode("auto")
            # Immediately re-check connectivity
            new_status, results = check_connectivity(self.state)
            self.state.update(new_status, results)
            self._send_json({
                "mode": "auto",
                "status": new_status,
                "providers": results,
                "message": "Auto-detect mode restored.",
            })

        else:
            self._send_json({"error": "not found", "path": path}, 404)


# ---- Main ----
def main():
    state = SyncState()
    queue = OfflineQueue()

    # Wire into handler class
    SyncHandler.state = state
    SyncHandler.queue = queue

    # Initial connectivity check
    print("[SYNC] Running initial connectivity check...")
    new_status, results = check_connectivity(state)
    state.update(new_status, results)
    print("[SYNC] Initial status: %s" % new_status)
    for name, ok in results.items():
        print("[SYNC]   %s: %s" % (name, "UP" if ok else "DOWN"))

    # Start background monitor
    monitor = threading.Thread(
        target=connectivity_monitor,
        args=(state, queue),
        daemon=True,
    )
    monitor.start()

    # Start HTTP server
    server = http.server.HTTPServer(("127.0.0.1", PORT), SyncHandler)
    print("[SYNC] Offline-First Sync Service running on 127.0.0.1:%d" % PORT)
    print("[SYNC] State file: %s" % STATE_FILE)
    print("[SYNC] Queue file: %s" % QUEUE_FILE)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("[SYNC] Shutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
