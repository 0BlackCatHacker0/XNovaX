"""NovaX Natural Language Service Creator v1.0
Port 9942: Takes natural language descriptions and generates working .nova services.

Uses the Cloud Router API (127.0.0.1:9878) for AI-assisted code generation,
with template-based fallback when AI is unavailable.

Manages user services in C:/NovaX/user_services/ with a JSON manifest.
Assigns ports from the 9940-9980 range, checking for conflicts via TCP connect.
"""
import http.server
import json
import os
import re
import socket
import subprocess
import threading
import time
import traceback
import urllib.request

PORT = 9942
HOST = "127.0.0.1"
NOVA_DIR = "C:\\NovaX"
USER_SERVICES_DIR = os.path.join(NOVA_DIR, "user_services")
TEMPLATES_DIR = os.path.join(NOVA_DIR, "service_templates")
MANIFEST_PATH = os.path.join(USER_SERVICES_DIR, "manifest.json")
NOVALANG_EXE = os.path.join(NOVA_DIR, "novalang.exe")
CLOUD_ROUTER_URL = "http://127.0.0.1:9878"

# Port range for user services (excluding 9942 which is this service)
PORT_RANGE_START = 9940
PORT_RANGE_END = 9980
RESERVED_PORTS = {9942}  # This service

SERVICE_NAME = "nova-service-creator"
VERSION = "1.0.0"

os.makedirs(USER_SERVICES_DIR, exist_ok=True)
os.makedirs(TEMPLATES_DIR, exist_ok=True)

start_time = time.time()
stat_created = 0
stat_started = 0
stat_stopped = 0
stat_ai_calls = 0
stat_ai_fails = 0

# Track running service processes: name -> subprocess.Popen
_running = {}
_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Manifest helpers
# ---------------------------------------------------------------------------

def _load_manifest():
    if os.path.exists(MANIFEST_PATH):
        try:
            with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"services": {}}


def _save_manifest(manifest):
    tmp = MANIFEST_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    os.replace(tmp, MANIFEST_PATH)


# ---------------------------------------------------------------------------
# Port helpers
# ---------------------------------------------------------------------------

def _is_port_in_use(port):
    """Check if a TCP port is currently listening (fast, 50ms timeout)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.05)
        result = s.connect_ex((HOST, port))
        s.close()
        return result == 0
    except Exception:
        return False


def _find_available_port(manifest):
    """Find the next available port in the user range."""
    used = set(RESERVED_PORTS)
    for svc in manifest.get("services", {}).values():
        used.add(svc.get("port", 0))
    for p in range(PORT_RANGE_START, PORT_RANGE_END + 1):
        if p not in used:
            return p
    return None


def _get_available_ports(manifest):
    """Return list of ports not assigned in manifest (fast, no TCP scan)."""
    used = set(RESERVED_PORTS)
    for svc in manifest.get("services", {}).values():
        used.add(svc.get("port", 0))
    available = []
    for p in range(PORT_RANGE_START, PORT_RANGE_END + 1):
        if p not in used:
            available.append(p)
    return available


# ---------------------------------------------------------------------------
# Template system
# ---------------------------------------------------------------------------

TEMPLATE_MAP = {
    "http_monitor": "http_monitor.nova.tpl",
    "data_transformer": "data_transformer.nova.tpl",
    "aggregator": "aggregator.nova.tpl",
    "webhook": "webhook.nova.tpl",
}

# Keywords that map descriptions to templates
TEMPLATE_KEYWORDS = {
    "http_monitor": [
        "monitor", "check", "watch", "poll", "health", "ping",
        "track", "alert", "temperature", "cpu", "memory", "disk",
        "uptime", "sensor", "periodic", "interval", "scrape",
    ],
    "data_transformer": [
        "transform", "convert", "translate", "parse", "format",
        "encode", "decode", "compress", "filter", "map", "process",
        "clean", "normalize", "validate", "sanitize",
    ],
    "aggregator": [
        "aggregate", "collect", "merge", "combine", "gather",
        "summarize", "report", "dashboard", "multi", "sources",
        "consolidate", "accumulate", "stats", "metrics",
    ],
    "webhook": [
        "webhook", "event", "trigger", "listen", "callback",
        "notify", "subscribe", "hook", "receive", "dispatch",
        "handler", "action", "react", "respond",
    ],
}


def _classify_template(description):
    """Pick the best template based on keyword matching."""
    desc_lower = description.lower()
    scores = {}
    for tpl_name, keywords in TEMPLATE_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in desc_lower)
        scores[tpl_name] = score
    best = max(scores, key=scores.get)
    if scores[best] == 0:
        return "http_monitor"  # default fallback
    return best


def _load_template(template_name):
    """Load a .nova.tpl template file."""
    filename = TEMPLATE_MAP.get(template_name)
    if not filename:
        filename = TEMPLATE_MAP["http_monitor"]
    path = os.path.join(TEMPLATES_DIR, filename)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _sanitize_name(name):
    """Convert a name to a safe service identifier."""
    name = re.sub(r"[^a-zA-Z0-9_-]", "-", name.strip().lower())
    name = re.sub(r"-+", "-", name).strip("-")
    if not name:
        name = "user-service"
    return name


def _make_title(name):
    """Convert service-name to Service Name."""
    return " ".join(w.capitalize() for w in name.replace("-", " ").replace("_", " ").split())


# ---------------------------------------------------------------------------
# AI code generation via Cloud Router
# ---------------------------------------------------------------------------

def _ask_cloud_router(prompt, timeout=30):
    """Send a prompt to Cloud Router and get a response."""
    global stat_ai_calls, stat_ai_fails
    stat_ai_calls += 1
    try:
        payload = json.dumps({
            "prompt": prompt,
            "channel": "CODE",
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{CLOUD_ROUTER_URL}/cloud-router/query",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("response", data.get("text", ""))
    except Exception as e:
        stat_ai_fails += 1
        return None


def _generate_custom_code(description, template_name):
    """Use AI to generate custom NovaLang code for template placeholders."""
    prompt = f"""You are a NovaLang code generator for the NovaX ternary AI OS.
Generate ONLY the custom function bodies and routes for a .nova service.

CRITICAL NovaLang rules:
- Use dict_get(d, "key", default) for dict access
- dict_set(d, "key", val) returns NEW dict - must reassign: d = dict_set(d, k, v)
- append(list, item) returns NEW list - must reassign: list = append(list, item)
- POST handlers must parse body: let body = try3 {{ json_decode(req["body"]) }} {{ {{}} }}
- Return dicts from handlers (auto-serialized to JSON)
- Use try3 {{ expr }} {{ fallback }} for error handling (NO fail3 keyword)
- shell(cmd) returns dict with stdout field: dict_get(result, "stdout", "")
- Use 127.0.0.1 not localhost
- ASCII only in comments and strings
- No f-strings, no || or && chains
- Comments use backslash: \\ comment text
- Avoid keywords (for, while, if, fn, let, return) inside comments

Service description: {description}
Template type: {template_name}

Return ONLY valid NovaLang code snippets. No markdown, no explanation.
Format:
FUNCTIONS:
<function definitions here>

ROUTES:
<troute calls here>

LOGIC:
<any inline logic for template placeholders>
"""
    return _ask_cloud_router(prompt)


def _parse_ai_response(ai_text):
    """Parse AI response into functions, routes, and logic sections."""
    result = {"functions": "", "routes": "", "logic": ""}
    if not ai_text:
        return result
    current = None
    lines = ai_text.split("\n")
    for line in lines:
        stripped = line.strip().upper()
        if stripped.startswith("FUNCTIONS:"):
            current = "functions"
            continue
        elif stripped.startswith("ROUTES:"):
            current = "routes"
            continue
        elif stripped.startswith("LOGIC:"):
            current = "logic"
            continue
        if current and not stripped.startswith("```"):
            result[current] += line + "\n"
    return result


# ---------------------------------------------------------------------------
# Service generation
# ---------------------------------------------------------------------------

def _generate_service(name, description, port):
    """Generate a complete .nova service file."""
    template_name = _classify_template(description)
    template = _load_template(template_name)

    if not template:
        return None, "Template not found"

    title = _make_title(name)

    # Try AI generation for custom code
    ai_code = _generate_custom_code(description, template_name)
    parsed = _parse_ai_response(ai_code)

    # Apply template substitutions
    code = template
    code = code.replace("{{PORT}}", str(port))
    code = code.replace("{{SERVICE_NAME}}", name)
    code = code.replace("{{SERVICE_TITLE}}", title)
    code = code.replace("{{DESCRIPTION}}", description)

    # Fill custom sections from AI or leave empty
    custom_fn = parsed.get("functions", "").strip()
    custom_routes = parsed.get("routes", "").strip()
    custom_logic = parsed.get("logic", "").strip()

    code = code.replace("{{CUSTOM_FUNCTIONS}}", custom_fn if custom_fn else "")
    code = code.replace("{{CUSTOM_ROUTES}}", custom_routes if custom_routes else "")

    # Template-specific placeholders
    code = code.replace("{{TRANSFORM_LOGIC}}", custom_logic if custom_logic else
                         "\\ Default: pass-through transform\n")
    code = code.replace("{{AGGREGATE_LOGIC}}", custom_logic if custom_logic else
                         "\\ Default: return empty results\n")
    code = code.replace("{{WEBHOOK_LOGIC}}", custom_logic if custom_logic else
                         "\\ Default: log event and return ok\n")

    return code, template_name


# ---------------------------------------------------------------------------
# Process management
# ---------------------------------------------------------------------------

def _start_service(name):
    """Start a .nova service via novalang.exe."""
    manifest = _load_manifest()
    svc = manifest["services"].get(name)
    if not svc:
        return False, "Service not found in manifest"

    nova_file = svc.get("file")
    if not nova_file or not os.path.exists(nova_file):
        return False, f"Nova file not found: {nova_file}"

    svc_port = svc.get("port", 0)
    if _is_port_in_use(svc_port):
        with _lock:
            if name not in _running:
                _running[name] = None  # mark as externally running
        return True, f"Port {svc_port} already in use (service may already be running)"

    if not os.path.exists(NOVALANG_EXE):
        return False, f"novalang.exe not found at {NOVALANG_EXE}"

    try:
        proc = subprocess.Popen(
            [NOVALANG_EXE, nova_file],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=0x08000000,  # CREATE_NO_WINDOW
        )
        with _lock:
            _running[name] = proc

        # Update manifest
        svc["status"] = "running"
        svc["pid"] = proc.pid
        svc["started_at"] = time.time()
        _save_manifest(manifest)

        return True, f"Started {name} (PID {proc.pid}) on port {svc_port}"
    except Exception as e:
        return False, f"Failed to start: {e}"


def _stop_service(name):
    """Stop a running user service."""
    with _lock:
        proc = _running.get(name)

    manifest = _load_manifest()
    svc = manifest["services"].get(name)
    if not svc:
        return False, "Service not found"

    stopped = False
    if proc and proc.poll() is None:
        try:
            proc.terminate()
            proc.wait(timeout=5)
            stopped = True
        except Exception:
            try:
                proc.kill()
                stopped = True
            except Exception:
                pass
    elif svc.get("pid"):
        # Try killing by stored PID
        try:
            os.kill(svc["pid"], 9)
            stopped = True
        except Exception:
            pass

    with _lock:
        _running.pop(name, None)

    svc["status"] = "stopped"
    svc.pop("pid", None)
    svc.pop("started_at", None)
    _save_manifest(manifest)

    if stopped:
        return True, f"Stopped {name}"
    return True, f"Marked {name} as stopped (process may have already exited)"


# ---------------------------------------------------------------------------
# HTTP Handler
# ---------------------------------------------------------------------------

class ServiceCreatorHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json_response(self, code, data):
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(code)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
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
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_GET(self):
        if self.path == "/health":
            self._handle_health()
        elif self.path == "/list":
            self._handle_list()
        elif self.path == "/ports":
            self._handle_ports()
        elif self.path.startswith("/source/"):
            name = self.path.split("/source/", 1)[1].strip("/")
            self._handle_source(name)
        else:
            self._json_response(404, {"error": "Not found"})

    def do_POST(self):
        if self.path == "/create":
            self._handle_create()
        elif self.path.startswith("/start/"):
            name = self.path.split("/start/", 1)[1].strip("/")
            self._handle_start(name)
        elif self.path.startswith("/stop/"):
            name = self.path.split("/stop/", 1)[1].strip("/")
            self._handle_stop(name)
        else:
            self._json_response(404, {"error": "Not found"})

    # -- Endpoint handlers --

    def _handle_health(self):
        global stat_created, stat_started, stat_stopped
        uptime = time.time() - start_time
        manifest = _load_manifest()
        total = len(manifest.get("services", {}))
        running = sum(1 for n in _running if _running[n] is not None)
        self._json_response(200, {
            "status": "ok",
            "trit": 1,
            "service": SERVICE_NAME,
            "version": VERSION,
            "port": PORT,
            "uptime": int(uptime),
            "total_services": total,
            "running_services": running,
            "stats": {
                "created": stat_created,
                "started": stat_started,
                "stopped": stat_stopped,
                "ai_calls": stat_ai_calls,
                "ai_fails": stat_ai_fails,
            },
        })

    def _handle_list(self):
        manifest = _load_manifest()
        services = {}
        for name, svc in manifest.get("services", {}).items():
            port = svc.get("port", 0)
            is_up = _is_port_in_use(port) if port else False
            services[name] = {
                "port": port,
                "template": svc.get("template", ""),
                "description": svc.get("description", ""),
                "file": svc.get("file", ""),
                "created_at": svc.get("created_at", ""),
                "status": "running" if is_up else "stopped",
            }
        self._json_response(200, {
            "ok": 1,
            "count": len(services),
            "services": services,
        })

    def _handle_ports(self):
        manifest = _load_manifest()
        available = _get_available_ports(manifest)
        used = {}
        for name, svc in manifest.get("services", {}).items():
            used[name] = svc.get("port", 0)
        self._json_response(200, {
            "ok": 1,
            "range": f"{PORT_RANGE_START}-{PORT_RANGE_END}",
            "available": available,
            "available_count": len(available),
            "used": used,
        })

    def _handle_source(self, name):
        manifest = _load_manifest()
        svc = manifest.get("services", {}).get(name)
        if not svc:
            self._json_response(404, {"error": f"Service '{name}' not found"})
            return
        fpath = svc.get("file", "")
        if not fpath or not os.path.exists(fpath):
            self._json_response(404, {"error": "Source file not found"})
            return
        with open(fpath, "r", encoding="utf-8") as f:
            source = f.read()
        self._json_response(200, {
            "ok": 1,
            "name": name,
            "port": svc.get("port", 0),
            "template": svc.get("template", ""),
            "source": source,
        })

    def _handle_create(self):
        global stat_created
        body = self._read_body()
        description = body.get("description", "").strip()
        name = body.get("name", "").strip()

        if not description:
            self._json_response(400, {"error": "Missing 'description' field"})
            return

        if not name:
            # Auto-generate name from description
            words = re.sub(r"[^a-zA-Z0-9\s]", "", description).split()[:4]
            name = "-".join(w.lower() for w in words if w)
            if not name:
                name = f"service-{int(time.time()) % 10000}"

        name = _sanitize_name(name)

        manifest = _load_manifest()

        # Check if name already exists
        if name in manifest.get("services", {}):
            self._json_response(409, {
                "error": f"Service '{name}' already exists. Choose a different name.",
            })
            return

        # Find available port
        port = _find_available_port(manifest)
        if port is None:
            self._json_response(503, {
                "error": "No available ports in range "
                         f"{PORT_RANGE_START}-{PORT_RANGE_END}",
            })
            return

        # Generate the .nova file
        code, template_name = _generate_service(name, description, port)
        if code is None:
            self._json_response(500, {"error": f"Generation failed: {template_name}"})
            return

        # Save the file
        nova_file = os.path.join(USER_SERVICES_DIR, f"{name}.nova")
        with open(nova_file, "w", encoding="utf-8") as f:
            f.write(code)

        # Update manifest
        if "services" not in manifest:
            manifest["services"] = {}
        manifest["services"][name] = {
            "port": port,
            "template": template_name,
            "description": description,
            "file": nova_file,
            "created_at": time.time(),
            "status": "stopped",
        }
        _save_manifest(manifest)

        stat_created += 1

        self._json_response(201, {
            "ok": 1,
            "name": name,
            "port": port,
            "template": template_name,
            "file": nova_file,
            "description": description,
            "message": f"Service '{name}' created on port {port}",
        })

    def _handle_start(self, name):
        global stat_started
        ok, msg = _start_service(name)
        if ok:
            stat_started += 1
        self._json_response(200 if ok else 500, {
            "ok": 1 if ok else -1,
            "name": name,
            "message": msg,
        })

    def _handle_stop(self, name):
        global stat_stopped
        ok, msg = _stop_service(name)
        if ok:
            stat_stopped += 1
        self._json_response(200 if ok else 500, {
            "ok": 1 if ok else -1,
            "name": name,
            "message": msg,
        })


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    # Initialize manifest if it doesn't exist
    if not os.path.exists(MANIFEST_PATH):
        _save_manifest({"services": {}})

    server = http.server.HTTPServer((HOST, PORT), ServiceCreatorHandler)
    print(f"[ServiceCreator] v{VERSION} listening on {HOST}:{PORT}")
    print(f"[ServiceCreator] Templates: {TEMPLATES_DIR}")
    print(f"[ServiceCreator] User services: {USER_SERVICES_DIR}")
    print(f"[ServiceCreator] Port range: {PORT_RANGE_START}-{PORT_RANGE_END}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("[ServiceCreator] Shutting down...")
        # Stop all running services
        with _lock:
            for name, proc in list(_running.items()):
                if proc and proc.poll() is None:
                    proc.terminate()
        server.server_close()


if __name__ == "__main__":
    main()
