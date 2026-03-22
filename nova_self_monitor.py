"""NovaX System Self-Monitoring AI Service
Port 9945 -- watches all NovaX services, predicts failures, tracks trends.
Metrics stored in C:\\NovaX\\data\\metrics\\metrics.jsonl (append-only).
"""
import http.server
import json
import os
import sys
import time
import threading
import subprocess
import statistics
import uuid
import urllib.request
import urllib.error
from collections import defaultdict, deque
from datetime import datetime, timedelta

PORT = 9945
METRICS_DIR = "C:\\NovaX\\data\\metrics"
METRICS_FILE = os.path.join(METRICS_DIR, "metrics.jsonl")
os.makedirs(METRICS_DIR, exist_ok=True)

try:
    import psutil
except ImportError:
    psutil = None

# ─── Service Registry ───────────────────────────────────────────────
# Services to monitor: name -> (port, is_stub)
# is_stub=True means we won't alert if it's down
SERVICES = {
    "orchestrator":       (9999, False),
    "hivemind":           (9881, False),
    "cloud_router":       (9878, False),
    "voice_server":       (9801, False),
    "mcp_server":         (9777, False),
    "model_selector":     (9876, False),
    "train_monitor":      (9873, False),
    "tripple_gateway":    (9872, False),
    "nexus":              (9871, False),
    "skill_engine":       (9870, False),
    "deep_storage":       (9869, False),
    "nova_vault":         (9868, False),
    "registry":           (9867, False),
    "nova_shield":        (9866, False),
    "desktop_server":     (9864, False),
    "cortex":             (9863, False),
    "chladni":            (9862, False),
    "nova_tbuffer":       (9861, False),
    "nova_swarm":         (9860, False),
    "nova_net":           (9859, False),
    "nova_db":            (9858, False),
    "self_monitor":       (9945, True),  # don't alert on ourselves
}

# ─── Configuration ──────────────────────────────────────────────────
POLL_INTERVAL = 30          # seconds between health checks
ANOMALY_STDDEV = 2.0        # flag if > 2 std devs from mean
TREND_SAMPLES = 10          # consecutive samples for trend detection
ROLLING_WINDOW = 3600       # 1 hour of metrics in memory
METRICS_FLUSH_INTERVAL = 10 # seconds between disk flushes

# ─── In-Memory State ────────────────────────────────────────────────
# metrics_buffer: service_name -> metric_name -> deque of (timestamp, value)
metrics_buffer = defaultdict(lambda: defaultdict(lambda: deque(maxlen=7200)))
# alerts: alert_id -> alert dict
alerts = {}
alerts_lock = threading.Lock()
# acknowledged alerts
acknowledged = set()
# metrics pending disk write
pending_metrics = []
pending_lock = threading.Lock()
# service status cache
service_status = {}
status_lock = threading.Lock()
# gpu cache
gpu_cache = {"ts": 0, "data": None}
# system cache
sys_cache = {"ts": 0, "data": None}

start_time = time.time()
poll_count = 0


# ─── Utility ────────────────────────────────────────────────────────
def ts_now():
    return time.time()

def iso_now():
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

def make_alert_id():
    return uuid.uuid4().hex[:12]

def record_metric(service, metric, value):
    """Store a metric in the rolling window and queue for disk."""
    t = ts_now()
    metrics_buffer[service][metric].append((t, value))
    entry = {
        "ts": t,
        "iso": iso_now(),
        "service": service,
        "metric": metric,
        "value": value,
    }
    with pending_lock:
        pending_metrics.append(json.dumps(entry, separators=(",", ":")))

def get_metric_values(service, metric, last_seconds=None):
    """Get values for a metric, optionally filtered by time window."""
    buf = metrics_buffer.get(service, {}).get(metric, deque())
    if last_seconds is None:
        return [v for _, v in buf]
    cutoff = ts_now() - last_seconds
    return [v for t, v in buf if t >= cutoff]

def get_metric_entries(service, metric, last_seconds=None):
    """Get (timestamp, value) pairs."""
    buf = metrics_buffer.get(service, {}).get(metric, deque())
    if last_seconds is None:
        return list(buf)
    cutoff = ts_now() - last_seconds
    return [(t, v) for t, v in buf if t >= cutoff]


# ─── Anomaly Detection ──────────────────────────────────────────────
def check_anomaly(service, metric, current_value):
    """Check if current value is anomalous (>2 stddev from 1h mean)."""
    values = get_metric_values(service, metric, ROLLING_WINDOW)
    if len(values) < 5:
        return None  # not enough data
    mean = statistics.mean(values)
    if mean == 0 and current_value == 0:
        return None
    try:
        stdev = statistics.stdev(values)
    except statistics.StatisticsError:
        return None
    if stdev == 0:
        return None
    z_score = abs(current_value - mean) / stdev
    if z_score > ANOMALY_STDDEV:
        return {
            "type": "anomaly",
            "service": service,
            "metric": metric,
            "value": current_value,
            "mean": round(mean, 4),
            "stdev": round(stdev, 4),
            "z_score": round(z_score, 2),
        }
    return None

def check_trend(service, metric):
    """Check if metric has a consistent increasing/decreasing trend."""
    values = get_metric_values(service, metric, ROLLING_WINDOW)
    if len(values) < TREND_SAMPLES:
        return None
    recent = values[-TREND_SAMPLES:]
    increasing = all(recent[i] < recent[i + 1] for i in range(len(recent) - 1))
    decreasing = all(recent[i] > recent[i + 1] for i in range(len(recent) - 1))
    if increasing:
        return {
            "type": "trend",
            "direction": "increasing",
            "service": service,
            "metric": metric,
            "samples": TREND_SAMPLES,
            "start_value": round(recent[0], 4),
            "end_value": round(recent[-1], 4),
        }
    if decreasing:
        return {
            "type": "trend",
            "direction": "decreasing",
            "service": service,
            "metric": metric,
            "samples": TREND_SAMPLES,
            "start_value": round(recent[0], 4),
            "end_value": round(recent[-1], 4),
        }
    return None


# ─── Alert Management ───────────────────────────────────────────────
def raise_alert(level, title, detail, source="system"):
    """Create or update an alert."""
    # Deduplicate: same title within 5 minutes
    with alerts_lock:
        for aid, a in alerts.items():
            if a["title"] == title and a["level"] == level:
                if ts_now() - a["raised_at"] < 300:
                    a["count"] = a.get("count", 1) + 1
                    a["last_seen"] = iso_now()
                    return aid
        aid = make_alert_id()
        alerts[aid] = {
            "id": aid,
            "level": level,
            "title": title,
            "detail": detail,
            "source": source,
            "raised_at": ts_now(),
            "raised_iso": iso_now(),
            "last_seen": iso_now(),
            "count": 1,
            "acknowledged": False,
        }
        return aid

def get_active_alerts():
    """Get all unacknowledged alerts from the last hour."""
    cutoff = ts_now() - ROLLING_WINDOW
    with alerts_lock:
        return [
            a for a in alerts.values()
            if a["raised_at"] >= cutoff and not a["acknowledged"]
        ]

def acknowledge_alert(alert_id):
    with alerts_lock:
        if alert_id in alerts:
            alerts[alert_id]["acknowledged"] = True
            return True
    return False


# ─── Service Health Polling ──────────────────────────────────────────
def poll_service(name, port):
    """Poll a single service's /health endpoint. Returns (up, latency_ms, detail)."""
    url = "http://127.0.0.1:%d/health" % port
    t0 = time.time()
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            latency = (time.time() - t0) * 1000
            body = resp.read().decode("utf-8", errors="replace")
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                data = {"raw": body[:200]}
            return True, round(latency, 2), data
    except urllib.error.URLError:
        latency = (time.time() - t0) * 1000
        return False, round(latency, 2), None
    except Exception:
        latency = (time.time() - t0) * 1000
        return False, round(latency, 2), None

def poll_all_services():
    """Poll all registered services and record metrics."""
    global poll_count
    poll_count += 1
    results = {}
    for name, (port, is_stub) in SERVICES.items():
        up, latency, detail = poll_service(name, port)
        results[name] = {
            "up": up,
            "latency_ms": latency,
            "detail": detail,
            "is_stub": is_stub,
        }
        # Record metrics
        record_metric(name, "up", 1 if up else 0)
        record_metric(name, "latency_ms", latency)
        # Check for errors in detail
        if detail and isinstance(detail, dict):
            error_count = detail.get("errors", detail.get("error_count", 0))
            if isinstance(error_count, (int, float)):
                record_metric(name, "error_count", error_count)
        # Anomaly checks
        if up:
            anomaly = check_anomaly(name, "latency_ms", latency)
            if anomaly:
                raise_alert(
                    "WARNING",
                    "%s latency anomaly" % name,
                    anomaly,
                    source=name,
                )
        # Service down alert (only for non-stubs)
        if not up and not is_stub:
            raise_alert(
                "CRITICAL",
                "%s is DOWN" % name,
                {"port": port, "latency_ms": latency},
                source=name,
            )
        # Trend checks
        trend = check_trend(name, "latency_ms")
        if trend and trend["direction"] == "increasing":
            raise_alert(
                "INFO",
                "latency increasing on %s" % name,
                trend,
                source=name,
            )
    with status_lock:
        service_status.update(results)
    return results


# ─── GPU Monitoring ──────────────────────────────────────────────────
def get_gpu_stats():
    """Get GPU stats via nvidia-smi XML output."""
    now = ts_now()
    if now - gpu_cache["ts"] < 10 and gpu_cache["data"] is not None:
        return gpu_cache["data"]
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,name,temperature.gpu,"
             "utilization.gpu,memory.used,memory.total,power.draw",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10,
            creationflags=0x08000000,  # CREATE_NO_WINDOW
        )
        if result.returncode != 0:
            gpu_cache["ts"] = now
            gpu_cache["data"] = {"available": False, "error": "nvidia-smi failed"}
            return gpu_cache["data"]
        gpus = []
        for line in result.stdout.strip().split("\n"):
            if not line.strip():
                continue
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 7:
                gpu = {
                    "index": int(parts[0]),
                    "name": parts[1],
                    "temp_c": float(parts[2]) if parts[2] != "N/A" else None,
                    "util_pct": float(parts[3]) if parts[3] != "N/A" else None,
                    "vram_used_mb": float(parts[4]) if parts[4] != "N/A" else None,
                    "vram_total_mb": float(parts[5]) if parts[5] != "N/A" else None,
                    "power_w": float(parts[6]) if parts[6] != "N/A" else None,
                }
                if gpu["vram_total_mb"] and gpu["vram_used_mb"]:
                    gpu["vram_pct"] = round(
                        gpu["vram_used_mb"] / gpu["vram_total_mb"] * 100, 1
                    )
                else:
                    gpu["vram_pct"] = None
                gpus.append(gpu)
                # Record GPU metrics
                gname = "gpu_%d" % gpu["index"]
                if gpu["temp_c"] is not None:
                    record_metric(gname, "temp_c", gpu["temp_c"])
                if gpu["util_pct"] is not None:
                    record_metric(gname, "util_pct", gpu["util_pct"])
                if gpu["vram_pct"] is not None:
                    record_metric(gname, "vram_pct", gpu["vram_pct"])
                if gpu["power_w"] is not None:
                    record_metric(gname, "power_w", gpu["power_w"])
                # VRAM alert
                if gpu["vram_pct"] is not None and gpu["vram_pct"] > 95:
                    raise_alert(
                        "CRITICAL",
                        "GPU %d VRAM nearly full (%.1f%%)" % (gpu["index"], gpu["vram_pct"]),
                        gpu,
                        source=gname,
                    )
                elif gpu["vram_pct"] is not None and gpu["vram_pct"] > 85:
                    raise_alert(
                        "WARNING",
                        "GPU %d VRAM high (%.1f%%)" % (gpu["index"], gpu["vram_pct"]),
                        gpu,
                        source=gname,
                    )
                # Temperature alert
                if gpu["temp_c"] is not None and gpu["temp_c"] > 85:
                    raise_alert(
                        "CRITICAL",
                        "GPU %d overheating (%d C)" % (gpu["index"], gpu["temp_c"]),
                        gpu,
                        source=gname,
                    )
        data = {"available": True, "gpus": gpus, "ts": iso_now()}
        gpu_cache["ts"] = now
        gpu_cache["data"] = data
        return data
    except FileNotFoundError:
        gpu_cache["ts"] = now
        gpu_cache["data"] = {"available": False, "error": "nvidia-smi not found"}
        return gpu_cache["data"]
    except Exception as e:
        gpu_cache["ts"] = now
        gpu_cache["data"] = {"available": False, "error": str(e)}
        return gpu_cache["data"]


# ─── System Monitoring ───────────────────────────────────────────────
def get_system_stats():
    """Get CPU, RAM, disk stats via psutil."""
    now = ts_now()
    if now - sys_cache["ts"] < 5 and sys_cache["data"] is not None:
        return sys_cache["data"]
    if psutil is None:
        return {"error": "psutil not installed", "ts": iso_now()}
    try:
        cpu_pct = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("C:\\")
        data = {
            "cpu_pct": cpu_pct,
            "cpu_count": psutil.cpu_count(),
            "ram_total_gb": round(mem.total / (1024**3), 2),
            "ram_used_gb": round(mem.used / (1024**3), 2),
            "ram_pct": mem.percent,
            "disk_total_gb": round(disk.total / (1024**3), 2),
            "disk_used_gb": round(disk.used / (1024**3), 2),
            "disk_free_gb": round(disk.free / (1024**3), 2),
            "disk_pct": round(disk.percent, 1),
            "ts": iso_now(),
        }
        # Record system metrics
        record_metric("_system", "cpu_pct", cpu_pct)
        record_metric("_system", "ram_pct", mem.percent)
        record_metric("_system", "disk_pct", disk.percent)
        # Alerts
        if mem.percent > 95:
            raise_alert("CRITICAL", "RAM nearly full (%.1f%%)" % mem.percent,
                        data, source="_system")
        elif mem.percent > 85:
            raise_alert("WARNING", "RAM high (%.1f%%)" % mem.percent,
                        data, source="_system")
        if disk.percent > 95:
            raise_alert("CRITICAL", "Disk nearly full (%.1f%%)" % disk.percent,
                        data, source="_system")
        elif disk.percent > 85:
            raise_alert("WARNING", "Disk space high (%.1f%%)" % disk.percent,
                        data, source="_system")
        sys_cache["ts"] = now
        sys_cache["data"] = data
        return data
    except Exception as e:
        return {"error": str(e), "ts": iso_now()}


# ─── Predictions ─────────────────────────────────────────────────────
def get_predictions():
    """Predict future issues based on trends."""
    predictions = []
    # Disk prediction
    disk_values = get_metric_entries("_system", "disk_pct", ROLLING_WINDOW)
    if len(disk_values) >= 3:
        first_t, first_v = disk_values[0]
        last_t, last_v = disk_values[-1]
        dt = last_t - first_t
        if dt > 0 and last_v > first_v:
            rate_per_sec = (last_v - first_v) / dt
            if rate_per_sec > 0:
                remaining_pct = 100.0 - last_v
                seconds_left = remaining_pct / rate_per_sec
                days_left = seconds_left / 86400
                if days_left < 30:
                    predictions.append({
                        "type": "disk_full",
                        "message": "Disk will be full in %.1f days at current rate" % days_left,
                        "days_left": round(days_left, 1),
                        "current_pct": round(last_v, 1),
                        "rate_pct_per_hour": round(rate_per_sec * 3600, 4),
                        "level": "CRITICAL" if days_left < 3 else "WARNING",
                    })
    # RAM trend prediction
    ram_values = get_metric_entries("_system", "ram_pct", ROLLING_WINDOW)
    if len(ram_values) >= 3:
        first_t, first_v = ram_values[0]
        last_t, last_v = ram_values[-1]
        dt = last_t - first_t
        if dt > 0 and last_v > first_v:
            rate_per_sec = (last_v - first_v) / dt
            if rate_per_sec > 0:
                remaining_pct = 100.0 - last_v
                seconds_left = remaining_pct / rate_per_sec
                hours_left = seconds_left / 3600
                if hours_left < 24:
                    predictions.append({
                        "type": "ram_exhaustion",
                        "message": "RAM may be exhausted in %.1f hours at current rate" % hours_left,
                        "hours_left": round(hours_left, 1),
                        "current_pct": round(last_v, 1),
                        "rate_pct_per_hour": round(rate_per_sec * 3600, 4),
                        "level": "WARNING",
                    })
    # VRAM trend prediction
    vram_values = get_metric_entries("gpu_0", "vram_pct", ROLLING_WINDOW)
    if len(vram_values) >= 3:
        first_t, first_v = vram_values[0]
        last_t, last_v = vram_values[-1]
        dt = last_t - first_t
        if dt > 0 and last_v > first_v:
            rate_per_sec = (last_v - first_v) / dt
            if rate_per_sec > 0:
                remaining_pct = 100.0 - last_v
                seconds_left = remaining_pct / rate_per_sec
                hours_left = seconds_left / 3600
                if hours_left < 12:
                    predictions.append({
                        "type": "vram_exhaustion",
                        "message": "GPU VRAM may fill in %.1f hours" % hours_left,
                        "hours_left": round(hours_left, 1),
                        "current_pct": round(last_v, 1),
                        "level": "WARNING",
                    })
    # Service degradation prediction (latency trending up)
    for name in SERVICES:
        lat_values = get_metric_values(name, "latency_ms", ROLLING_WINDOW)
        if len(lat_values) >= TREND_SAMPLES:
            recent = lat_values[-TREND_SAMPLES:]
            if all(recent[i] < recent[i + 1] for i in range(len(recent) - 1)):
                rate = (recent[-1] - recent[0]) / len(recent)
                if rate > 5:  # >5ms increase per sample
                    predictions.append({
                        "type": "service_degradation",
                        "service": name,
                        "message": "%s latency increasing by %.1f ms/sample" % (name, rate),
                        "current_latency": round(recent[-1], 2),
                        "rate_ms_per_sample": round(rate, 2),
                        "level": "INFO",
                    })
    return predictions


# ─── Latency Percentiles ────────────────────────────────────────────
def get_percentiles(values):
    """Calculate p50, p95, p99 from a list of values."""
    if not values:
        return {"p50": None, "p95": None, "p99": None}
    s = sorted(values)
    n = len(s)
    return {
        "p50": round(s[int(n * 0.50)], 2),
        "p95": round(s[min(int(n * 0.95), n - 1)], 2),
        "p99": round(s[min(int(n * 0.99), n - 1)], 2),
    }


# ─── Metrics Flusher ────────────────────────────────────────────────
def flush_metrics():
    """Periodically flush pending metrics to disk."""
    while True:
        time.sleep(METRICS_FLUSH_INTERVAL)
        with pending_lock:
            if not pending_metrics:
                continue
            batch = pending_metrics[:]
            pending_metrics.clear()
        try:
            with open(METRICS_FILE, "a", encoding="utf-8") as f:
                for line in batch:
                    f.write(line + "\n")
        except Exception:
            pass  # silently drop if disk write fails


# ─── Polling Loop ───────────────────────────────────────────────────
def poll_loop():
    """Main monitoring loop."""
    while True:
        try:
            poll_all_services()
            get_gpu_stats()
            get_system_stats()
        except Exception:
            pass
        time.sleep(POLL_INTERVAL)


# ─── Expired Alert Cleanup ──────────────────────────────────────────
def cleanup_loop():
    """Remove alerts older than 2 hours."""
    while True:
        time.sleep(300)
        cutoff = ts_now() - 7200
        with alerts_lock:
            expired = [k for k, v in alerts.items() if v["raised_at"] < cutoff]
            for k in expired:
                del alerts[k]


# ─── HTTP Handler ───────────────────────────────────────────────────
def parse_qs(query):
    """Minimal query string parser."""
    params = {}
    if not query:
        return params
    for part in query.split("&"):
        if "=" in part:
            k, v = part.split("=", 1)
            params[k] = v
    return params

def parse_duration(s):
    """Parse duration string like '1h', '30m', '2h' to seconds."""
    s = s.strip().lower()
    if s.endswith("h"):
        return int(s[:-1]) * 3600
    if s.endswith("m"):
        return int(s[:-1]) * 60
    if s.endswith("s"):
        return int(s[:-1])
    return int(s)


class MonitorHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json_response(self, code, data):
        body = json.dumps(data, indent=2, default=str).encode("utf-8")
        self.send_response(code)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?")[0]
        query = self.path.split("?")[1] if "?" in self.path else ""
        params = parse_qs(query)

        # /health
        if path == "/health":
            active_alerts = get_active_alerts()
            critical = sum(1 for a in active_alerts if a["level"] == "CRITICAL")
            self._json_response(200, {
                "status": "degraded" if critical > 0 else "ok",
                "trit": -1 if critical > 0 else 1,
                "service": "self_monitor",
                "port": PORT,
                "uptime": int(ts_now() - start_time),
                "poll_count": poll_count,
                "active_alerts": len(active_alerts),
                "critical_alerts": critical,
            })

        # /monitor/status
        elif path == "/monitor/status":
            with status_lock:
                svc = dict(service_status)
            # Build summary
            up_count = sum(1 for v in svc.values() if v.get("up"))
            total = len(svc)
            down = [k for k, v in svc.items()
                    if not v.get("up") and not v.get("is_stub")]
            # Latency percentiles per service
            latencies = {}
            for name in SERVICES:
                vals = get_metric_values(name, "latency_ms", ROLLING_WINDOW)
                if vals:
                    latencies[name] = get_percentiles(vals)
            self._json_response(200, {
                "ts": iso_now(),
                "services_up": up_count,
                "services_total": total,
                "services_down": down,
                "service_status": svc,
                "latency_percentiles": latencies,
                "gpu": get_gpu_stats(),
                "system": get_system_stats(),
                "active_alerts": len(get_active_alerts()),
                "poll_count": poll_count,
                "uptime": int(ts_now() - start_time),
            })

        # /monitor/alerts
        elif path == "/monitor/alerts":
            active = get_active_alerts()
            active.sort(key=lambda a: (
                {"CRITICAL": 0, "WARNING": 1, "INFO": 2}.get(a["level"], 3),
                -a["raised_at"],
            ))
            self._json_response(200, {
                "ts": iso_now(),
                "count": len(active),
                "alerts": active,
            })

        # /monitor/metrics?service=X&last=1h
        elif path == "/monitor/metrics":
            svc_name = params.get("service", "")
            last_str = params.get("last", "1h")
            try:
                last_sec = parse_duration(last_str)
            except (ValueError, TypeError):
                last_sec = 3600
            if not svc_name:
                # Return all available service/metric combos
                available = {}
                for s in metrics_buffer:
                    available[s] = list(metrics_buffer[s].keys())
                self._json_response(200, {
                    "ts": iso_now(),
                    "available": available,
                })
            else:
                result = {}
                if svc_name in metrics_buffer:
                    for metric_name in metrics_buffer[svc_name]:
                        entries = get_metric_entries(svc_name, metric_name, last_sec)
                        vals = [v for _, v in entries]
                        result[metric_name] = {
                            "count": len(entries),
                            "values": vals[-100:],  # last 100 points
                            "percentiles": get_percentiles(vals) if vals else {},
                            "mean": round(statistics.mean(vals), 4) if vals else None,
                        }
                self._json_response(200, {
                    "ts": iso_now(),
                    "service": svc_name,
                    "window": last_str,
                    "metrics": result,
                })

        # /monitor/gpu
        elif path == "/monitor/gpu":
            self._json_response(200, get_gpu_stats())

        # /monitor/system
        elif path == "/monitor/system":
            self._json_response(200, get_system_stats())

        # /monitor/predictions
        elif path == "/monitor/predictions":
            preds = get_predictions()
            self._json_response(200, {
                "ts": iso_now(),
                "predictions": preds,
                "count": len(preds),
            })

        else:
            self._json_response(404, {"error": "not found", "path": path})

    def do_POST(self):
        path = self.path.split("?")[0]

        # POST /monitor/acknowledge/<alert_id>
        if path.startswith("/monitor/acknowledge/"):
            alert_id = path.split("/")[-1]
            if acknowledge_alert(alert_id):
                self._json_response(200, {
                    "acknowledged": True,
                    "alert_id": alert_id,
                })
            else:
                self._json_response(404, {
                    "error": "alert not found",
                    "alert_id": alert_id,
                })
        else:
            self._json_response(404, {"error": "not found", "path": path})


# ─── Main ────────────────────────────────────────────────────────────
def main():
    print("NovaX Self-Monitor starting on port %d..." % PORT)

    if psutil is None:
        print("[WARN] psutil not installed -- system metrics will be limited")
        print("       Install with: pip install psutil")

    # Start background threads (all daemon so they die with main)
    threads = [
        ("poll", poll_loop),
        ("flush", flush_metrics),
        ("cleanup", cleanup_loop),
    ]
    for name, target in threads:
        t = threading.Thread(target=target, daemon=True, name="monitor_%s" % name)
        t.start()
        print("  [+] %s thread started" % name)

    # Do an initial poll immediately
    try:
        poll_all_services()
        get_gpu_stats()
        get_system_stats()
    except Exception as e:
        print("[WARN] Initial poll error: %s" % e)

    server = http.server.HTTPServer(("127.0.0.1", PORT), MonitorHandler)
    print("Self-Monitor ready at http://127.0.0.1:%d" % PORT)
    print("  /health            - Service health check")
    print("  /monitor/status    - Full system status")
    print("  /monitor/alerts    - Active alerts")
    print("  /monitor/metrics   - Service metrics")
    print("  /monitor/gpu       - GPU stats")
    print("  /monitor/system    - CPU/RAM/Disk")
    print("  /monitor/predictions - Predicted issues")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down Self-Monitor...")
        server.shutdown()


if __name__ == "__main__":
    main()
