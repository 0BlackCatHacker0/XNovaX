"""Rebuild tool_registry.json by scanning live services and their source files."""
import json, os, re, socket, urllib.request, time
from concurrent.futures import ThreadPoolExecutor

NOVA_DIR = r"C:\NovaX"
PORT_RANGE = range(9870, 10000)
SKIP_PORTS = {6379, 7700, 11434}

def check_port(port):
    """Check if port is alive and get health info."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(1)
    try:
        s.connect(("127.0.0.1", port))
        s.close()
    except:
        s.close()
        return None

    try:
        req = urllib.request.Request(f"http://127.0.0.1:{port}/health")
        resp = urllib.request.urlopen(req, timeout=3)
        data = json.loads(resp.read().decode())
        name = data.get("service", f"port-{port}")
        return {"port": port, "name": name, "health": data}
    except:
        return {"port": port, "name": f"port-{port}", "health": {}}

def find_service_file(port):
    """Find the Python/Nova file that serves on this port."""
    for fname in os.listdir(NOVA_DIR):
        if not (fname.endswith(".py") or fname.endswith(".nova")):
            continue
        fpath = os.path.join(NOVA_DIR, fname)
        try:
            with open(fpath, encoding="utf-8", errors="replace") as f:
                content = f.read(5000)  # first 5KB
            # Look for PORT = NNNN
            m = re.search(r'\bPORT\s*=\s*(\d+)', content)
            if m and int(m.group(1)) == port:
                return fpath
        except:
            continue
    return None

def extract_routes_from_file(fpath):
    """Extract HTTP routes from a service file."""
    with open(fpath, encoding="utf-8", errors="replace") as f:
        content = f.read()

    routes = {}
    in_get = in_post = False

    for line in content.split("\n"):
        if "def do_GET" in line:
            in_get = True; in_post = False
        elif "def do_POST" in line:
            in_get = False; in_post = True
        elif re.match(r'\s+def \w+', line) and "do_" not in line:
            pass  # other method, keep current state

        # Match path == "/something"
        m = re.search(r'path\s*==\s*["\'](/[^"\'\s]+)["\']', line)
        if m:
            path = m.group(1)
            method = "GET" if in_get else "POST" if in_post else "GET"
            key = path.split("/")[-1] or path.split("/")[-2]
            key = re.sub(r'[^a-z0-9_]', '_', key.lower())
            if path != "/health":
                routes[key] = {"method": method, "path": path, "desc": f"{method} {path}"}

        # Match path.startswith("/something")
        m2 = re.search(r'path\.startswith\(["\'](/[^"\'\s]+)["\']\)', line)
        if m2:
            path = m2.group(1)
            method = "GET" if in_get else "POST" if in_post else "GET"
            key = path.split("/")[-1] or path.split("/")[-2]
            key = re.sub(r'[^a-z0-9_]', '_', key.lower())
            routes[key] = {"method": method, "path": path, "desc": f"{method} {path}"}

    # Always add health
    routes["health"] = {"method": "GET", "path": "/health", "desc": "Health check"}

    return routes

# Known service descriptions (from memory)
DESCRIPTIONS = {
    "hivemind": "Model Swarm - 848-slot hivemind with deliberation",
    "cloud_router": "Cloud AI Router - 10 providers (Ollama, OpenAI, Anthropic, Google, etc.)",
    "nova-tools": "NovaX MCP Tool Server",
    "nova-ternary-server": "Ternary Computation Server",
    "nova-sentinel": "Fleet Sentinel - service watchdog",
    "nova-cortex": "Desktop AI Bridge - Claude/ChatGPT UI automation",
    "nova-tkill": "Process Killer - port/PID management",
    "nova-tshield": "Security Shield - threat detection",
    "nova-tscale": "Auto-Scaler - service scaling",
    "nova-ttimeout": "Fleet Timeout Hardening Engine - audit + stress test",
    "nova-tmapper": "Mapping Debugger - port scanner, VCC/registry differ",
    "nova-tspin": "Process Spinner - service lifecycle management",
    "nova-tdebug": "Universal Debugger - syntax check, compare, probe",
    "nova-tpacman": "Python-to-Nova Converter",
    "nova-thttp": "HTTP Client",
    "nova-tmarkdown": "Markdown Processor",
    "nova-tnet": "Network Tools",
    "nova-tgit": "Git Operations",
    "nova-tshell": "Shell Executor",
    "nova-tconfig": "Configuration Manager",
    "nova-tcron": "Cron Scheduler",
    "nova-tquery": "Query Engine",
    "nova-tredis": "Redis Client",
    "nova-tsqlite": "SQLite Database",
    "nova-timage": "Image Processing",
    "nova-tmedia": "Media Processing",
    "nova-tfetch": "URL Fetcher",
    "nova-tbuffer": "TBuffer - Ternary Response Membrane",
    "nova-talchemy": "Data Alchemy - type conversion",
    "nova-tsession": "Session Manager",
    "nova-tsecurity": "Security Scanner",
    "nova-tsysmon": "System Monitor",
    "nova-tci": "CI/CD Pipeline",
    "nova-tbuild": "Build System",
    "nova-tterraform": "Infrastructure as Code",
    "nova-tdocker": "Docker Manager",
    "nova-tdocs": "Documentation Generator",
    "nova-ttest": "Test Runner",
    "nova-tbenchmark": "Benchmark Suite",
    "nova-tspeak": "Text-to-Speech",
    "nova-skiptrace": "Error Tracer",
    "nova-max-patch": "Max Patcher",
    "nova-fleet": "Fleet Manager",
    "nova-closed-loop": "Closed Loop Controller",
    "nova-ternary-tools": "Ternary Toolkit - 7 tools on 3-5-7-13 harmonics",
    "nova-thunter": "Process Hunter",
    "novacore": "NovaXCore - N-S Reynolds routing",
    "nova-tyaml": "YAML Processor",
}

print("Scanning fleet...")
with ThreadPoolExecutor(max_workers=13) as pool:
    results = list(pool.map(check_port, PORT_RANGE))

services = {}
alive = [r for r in results if r is not None]
print(f"Found {len(alive)} live services")

for svc in alive:
    port = svc["port"]
    name = svc["name"]

    # Normalize name to registry key
    key = name.replace("nova-", "").replace("nova_", "").replace("-", "_")
    if key.startswith("t") and len(key) > 1 and not key.startswith("ternary"):
        pass  # keep tXxx names

    # Find source file and extract routes
    fpath = find_service_file(port)
    if fpath:
        routes = extract_routes_from_file(fpath)
    else:
        routes = {"health": {"method": "GET", "path": "/health", "desc": "Health check"}}

    desc = DESCRIPTIONS.get(name, DESCRIPTIONS.get(f"nova-{key}", f"Service on port {port}"))

    services[key] = {
        "port": port,
        "description": desc,
        "routes": routes
    }

# Build registry
registry = {
    "_meta": {
        "version": "2.0.0",
        "description": "NovaX Tool Bridge Registry v2 - ALL services, ALL routes",
        "harmonic": "3-5-7-13: 3 trit states per call, 5 core params, 7 error contexts, 13-byte envelope",
        "auto_prefix": True,
        "note": "Add a new service here -> NovaLang instantly gains new builtins",
        "total_services": len(services),
        "generated": "Session 62 - auto-rebuilt from live fleet scan"
    },
    "services": dict(sorted(services.items()))
}

# Write with atomic temp file pattern
tmp_path = os.path.join(NOVA_DIR, "tool_registry.json.tmp")
final_path = os.path.join(NOVA_DIR, "tool_registry.json")

with open(tmp_path, "w", encoding="utf-8") as f:
    json.dump(registry, f, indent=2, ensure_ascii=True)

# Verify the tmp file is valid JSON
with open(tmp_path, encoding="utf-8") as f:
    verify = json.load(f)
    assert len(verify["services"]) > 30, f"Only {len(verify['services'])} services - too few"

# Atomic replace
os.replace(tmp_path, final_path)

print(f"\nRegistry rebuilt: {len(services)} services")
print(f"File: {final_path}")
for key in sorted(services.keys()):
    s = services[key]
    print(f"  {key:20s} :{s['port']}  ({len(s['routes'])} routes)")
