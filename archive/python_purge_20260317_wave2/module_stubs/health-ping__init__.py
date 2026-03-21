"""health-ping -- Periodic health check for all NovaX services"""
import urllib.request, urllib.error, json, threading, time, os

_timer = None
_running = False
_log_path = os.path.join(os.path.dirname(__file__), "health.log")
_config = {}


def setup():
    global _config
    manifest_path = os.path.join(os.path.dirname(__file__), "manifest.json")
    with open(manifest_path) as f:
        _config = json.load(f).get("config", {})
    print(f"[health-ping] Loaded — monitoring {len(_config.get('services', {}))} services")
    start()


def teardown():
    stop()
    print("[health-ping] Stopped.")


def start():
    global _running
    _running = True
    _tick()


def stop():
    global _running, _timer
    _running = False
    if _timer:
        _timer.cancel()
        _timer = None


def _tick():
    global _timer
    if not _running:
        return
    results = ping_all()
    down = [name for name, info in results.items() if not info["ok"]]
    if down:
        print(f"[health-ping] DOWN: {', '.join(down)}")
    _log(results)
    interval = _config.get("interval_seconds", 60)
    _timer = threading.Timer(interval, _tick)
    _timer.daemon = True
    _timer.start()


def ping_all():
    services = _config.get("services", {})
    results = {}
    for name, url in services.items():
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                results[name] = {"ok": resp.status < 400, "status": resp.status, "ms": 0}
        except Exception as e:
            results[name] = {"ok": False, "status": 0, "error": str(e)[:80]}
    return results


def _log(results):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    up = sum(1 for r in results.values() if r["ok"])
    line = f"{ts} | {up}/{len(results)} services up"
    down = [n for n, r in results.items() if not r["ok"]]
    if down:
        line += f" | DOWN: {','.join(down)}"
    with open(_log_path, "a") as f:
        f.write(line + "\n")


def run(params=None):
    return ping_all()
