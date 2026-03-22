"""
NovaX Skill Marketplace Service
Port 9948 - Install, share, manage, and run .nova skills
"""

import os
import sys
import json
import time
import shutil
import hashlib
import subprocess
import urllib.request
import urllib.error
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timezone

PORT = 9948
SKILLS_DIR = os.path.join("C:\\NovaX", "skills")
REGISTRY_FILE = os.path.join(SKILLS_DIR, "registry.json")
NOVALANG_EXE = os.path.join("C:\\NovaX", "novalang.exe")

VALID_CATEGORIES = [
    "utility", "monitor", "transformer",
    "aggregator", "integration", "analysis"
]

# ---------------------------------------------------------------------------
# Registry helpers
# ---------------------------------------------------------------------------

def ensure_dirs():
    os.makedirs(SKILLS_DIR, exist_ok=True)


def load_registry():
    ensure_dirs()
    if os.path.exists(REGISTRY_FILE):
        try:
            with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {"skills": {}, "version": 1}
    return {"skills": {}, "version": 1}


def save_registry(reg):
    ensure_dirs()
    tmp = REGISTRY_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(reg, f, indent=2)
    shutil.move(tmp, REGISTRY_FILE)


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def make_metadata(name, version="1.0.0", author="unknown",
                  description="", category="utility", port=None,
                  dependencies=None):
    return {
        "name": name,
        "version": version,
        "author": author,
        "description": description,
        "category": category if category in VALID_CATEGORIES else "utility",
        "port": port,
        "dependencies": dependencies or [],
        "created": now_iso(),
        "updated": now_iso(),
    }


def skill_path(name):
    safe = name.replace("..", "").replace("/", "").replace("\\", "")
    return os.path.join(SKILLS_DIR, safe + ".nova")


def sidecar_path(name):
    safe = name.replace("..", "").replace("/", "").replace("\\", "")
    return os.path.join(SKILLS_DIR, safe + ".meta.json")


def read_sidecar(name):
    p = sidecar_path(name)
    if os.path.exists(p):
        try:
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    return None


def write_sidecar(name, meta):
    p = sidecar_path(name)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)


def read_skill_source(name):
    p = skill_path(name)
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            return f.read()
    return None


# ---------------------------------------------------------------------------
# Request handler
# ---------------------------------------------------------------------------

class SkillMarketplaceHandler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        print("[SkillMarketplace] %s - %s" % (self.address_string(), fmt % args))

    # -- response helpers --------------------------------------------------

    def _json_response(self, data, status=200):
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "http://localhost:9999")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def _error(self, msg, status=400):
        self._json_response({"ok": False, "error": msg}, status)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return {}

    # -- routing -----------------------------------------------------------

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "http://localhost:9999")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        qs = parse_qs(parsed.query)

        if path == "/health":
            return self._handle_health()
        if path == "/skills/list":
            return self._handle_list()
        if path == "/skills/categories":
            return self._handle_categories()
        if path == "/skills/search":
            q = qs.get("q", [""])[0]
            return self._handle_search(q)
        if path.startswith("/skills/"):
            name = path.split("/skills/", 1)[1]
            if name:
                return self._handle_get_skill(name)

        self._error("Not found", 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path == "/skills/install":
            return self._handle_install()
        if path == "/skills/create":
            return self._handle_create()
        if path.startswith("/skills/run/"):
            name = path.split("/skills/run/", 1)[1]
            if name:
                return self._handle_run(name)

        self._error("Not found", 404)

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path.startswith("/skills/"):
            name = path.split("/skills/", 1)[1]
            if name:
                return self._handle_delete(name)

        self._error("Not found", 404)

    # -- handlers ----------------------------------------------------------

    def _handle_health(self):
        reg = load_registry()
        self._json_response({
            "ok": True,
            "service": "NovaX Skill Marketplace",
            "port": PORT,
            "skills_installed": len(reg.get("skills", {})),
            "skills_dir": SKILLS_DIR,
            "uptime_s": int(time.time() - _start_time),
        })

    def _handle_list(self):
        reg = load_registry()
        skills = []
        for name, entry in reg.get("skills", {}).items():
            meta = read_sidecar(name) or entry.get("meta", {})
            skills.append({
                "name": name,
                "meta": meta,
                "has_source": os.path.exists(skill_path(name)),
            })
        self._json_response({"ok": True, "count": len(skills), "skills": skills})

    def _handle_get_skill(self, name):
        reg = load_registry()
        if name not in reg.get("skills", {}):
            return self._error("Skill not found: %s" % name, 404)
        meta = read_sidecar(name) or reg["skills"][name].get("meta", {})
        source = read_skill_source(name)
        self._json_response({
            "ok": True,
            "name": name,
            "meta": meta,
            "source": source,
        })

    def _handle_categories(self):
        reg = load_registry()
        counts = {c: 0 for c in VALID_CATEGORIES}
        for _name, entry in reg.get("skills", {}).items():
            cat = entry.get("meta", {}).get("category", "utility")
            if cat in counts:
                counts[cat] += 1
            else:
                counts["utility"] += 1
        self._json_response({
            "ok": True,
            "categories": VALID_CATEGORIES,
            "counts": counts,
        })

    def _handle_search(self, query):
        if not query:
            return self._error("Missing query parameter ?q=")
        reg = load_registry()
        query_lower = query.lower()
        results = []
        for name, entry in reg.get("skills", {}).items():
            meta = read_sidecar(name) or entry.get("meta", {})
            searchable = " ".join([
                name,
                meta.get("description", ""),
                meta.get("category", ""),
                meta.get("author", ""),
            ]).lower()
            if query_lower in searchable:
                results.append({"name": name, "meta": meta})
        self._json_response({"ok": True, "query": query, "count": len(results), "results": results})

    def _handle_install(self):
        body = self._read_body()
        url = body.get("url", "")
        local_path = body.get("path", "")
        name = body.get("name", "")

        if not url and not local_path:
            return self._error("Provide 'url' or 'path' to install from")

        # Determine source
        source_code = None
        if local_path:
            local_path = os.path.abspath(local_path)
            if not os.path.exists(local_path):
                return self._error("Local path not found: %s" % local_path)
            with open(local_path, "r", encoding="utf-8") as f:
                source_code = f.read()
            if not name:
                name = os.path.splitext(os.path.basename(local_path))[0]
        elif url:
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "NovaX-SkillMarketplace/1.0"})
                with urllib.request.urlopen(req, timeout=15) as resp:
                    source_code = resp.read().decode("utf-8")
            except Exception as e:
                return self._error("Failed to fetch URL: %s" % str(e))
            if not name:
                name = os.path.splitext(os.path.basename(urlparse(url).path))[0] or "unnamed_skill"

        # Sanitize name
        name = name.replace(" ", "_").replace("..", "").replace("/", "").replace("\\", "")
        if not name:
            return self._error("Could not determine skill name")

        # Write .nova file
        dest = skill_path(name)
        with open(dest, "w", encoding="utf-8") as f:
            f.write(source_code)

        # Build metadata
        meta = make_metadata(
            name=name,
            version=body.get("version", "1.0.0"),
            author=body.get("author", "community"),
            description=body.get("description", "Installed skill"),
            category=body.get("category", "utility"),
            port=body.get("port"),
            dependencies=body.get("dependencies", []),
        )
        write_sidecar(name, meta)

        # Update registry
        reg = load_registry()
        reg.setdefault("skills", {})[name] = {
            "installed": now_iso(),
            "source": url or local_path,
            "meta": meta,
            "checksum": hashlib.sha256(source_code.encode("utf-8")).hexdigest(),
        }
        save_registry(reg)

        print("[SkillMarketplace] Installed skill: %s" % name)
        self._json_response({"ok": True, "name": name, "meta": meta}, 201)

    def _handle_create(self):
        body = self._read_body()
        name = body.get("name", "")
        code = body.get("code", "")
        description = body.get("description", "")

        if not name:
            return self._error("Missing 'name'")
        if not code:
            return self._error("Missing 'code'")

        name = name.replace(" ", "_").replace("..", "").replace("/", "").replace("\\", "")
        dest = skill_path(name)

        if os.path.exists(dest) and not body.get("overwrite", False):
            return self._error("Skill '%s' already exists. Set overwrite=true to replace." % name)

        with open(dest, "w", encoding="utf-8") as f:
            f.write(code)

        meta = make_metadata(
            name=name,
            version=body.get("version", "1.0.0"),
            author=body.get("author", "user"),
            description=description,
            category=body.get("category", "utility"),
            port=body.get("port"),
            dependencies=body.get("dependencies", []),
        )
        write_sidecar(name, meta)

        reg = load_registry()
        reg.setdefault("skills", {})[name] = {
            "installed": now_iso(),
            "source": "created",
            "meta": meta,
            "checksum": hashlib.sha256(code.encode("utf-8")).hexdigest(),
        }
        save_registry(reg)

        print("[SkillMarketplace] Created skill: %s" % name)
        self._json_response({"ok": True, "name": name, "meta": meta}, 201)

    def _handle_delete(self, name):
        reg = load_registry()
        if name not in reg.get("skills", {}):
            return self._error("Skill not found: %s" % name, 404)

        # Remove files
        sp = skill_path(name)
        sc = sidecar_path(name)
        if os.path.exists(sp):
            os.remove(sp)
        if os.path.exists(sc):
            os.remove(sc)

        del reg["skills"][name]
        save_registry(reg)

        print("[SkillMarketplace] Deleted skill: %s" % name)
        self._json_response({"ok": True, "deleted": name})

    def _handle_run(self, name):
        reg = load_registry()
        if name not in reg.get("skills", {}):
            return self._error("Skill not found: %s" % name, 404)

        sp = skill_path(name)
        if not os.path.exists(sp):
            return self._error("Skill file missing: %s" % sp, 404)

        body = self._read_body()
        args = body.get("args", [])
        timeout = body.get("timeout", 30)

        # Determine executor
        exe = NOVALANG_EXE
        if not os.path.exists(exe):
            # Fallback: try novalang.py
            py_fallback = os.path.join("C:\\NovaX", "novalang.py")
            if os.path.exists(py_fallback):
                exe = None
                cmd = [sys.executable, py_fallback, sp] + [str(a) for a in args]
            else:
                return self._error("novalang executor not found (checked .exe and .py)")
        else:
            cmd = [exe, sp] + [str(a) for a in args]

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=SKILLS_DIR,
            )
            self._json_response({
                "ok": proc.returncode == 0,
                "name": name,
                "exit_code": proc.returncode,
                "stdout": proc.stdout[-4096:] if proc.stdout else "",
                "stderr": proc.stderr[-2048:] if proc.stderr else "",
            })
        except subprocess.TimeoutExpired:
            self._error("Skill execution timed out after %ds" % timeout, 504)
        except Exception as e:
            self._error("Execution error: %s" % str(e), 500)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

_start_time = time.time()


def main():
    ensure_dirs()

    # Initialize registry if missing
    if not os.path.exists(REGISTRY_FILE):
        save_registry({"skills": {}, "version": 1})
        print("[SkillMarketplace] Initialized empty registry at %s" % REGISTRY_FILE)

    server = HTTPServer(("127.0.0.1", PORT), SkillMarketplaceHandler)
    print("[SkillMarketplace] NovaX Skill Marketplace running on http://127.0.0.1:%d" % PORT)
    print("[SkillMarketplace] Skills directory: %s" % SKILLS_DIR)
    print("[SkillMarketplace] Registry: %s" % REGISTRY_FILE)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[SkillMarketplace] Shutting down.")
        server.server_close()


if __name__ == "__main__":
    main()
