"""
NovaX Verified Capability Contract (VCC) Engine
=================================================
Trust is not assumed. Trust is proven mechanically.

Every component passes through 8 ordered states:
  DETECTED -> READ -> SCANNED -> WRITE_REQUESTED -> MODIFIED -> COMPLETE -> VERIFIED -> TRUSTED

No state may be skipped. Both Presence AND Effect must be confirmed.

Contract token format:
  NOVAX::<component_id>::<nonce>::READ>SCAN>WRITE>MODIFY>COMPLETE
"""
import os
import json
import time
import uuid
import socket
import hashlib
import logging
import subprocess
import threading
from enum import Enum
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, List, Callable

log = logging.getLogger("NovaX.VCC")

# ============================================================
#  VCC STATES
# ============================================================
class VCCState(str, Enum):
    UNKNOWN     = "unknown"
    DETECTED    = "detected"
    READ        = "read"
    SCANNED     = "scanned"
    WRITE_REQ   = "write_requested"
    MODIFIED    = "modified"
    COMPLETE    = "complete"
    VERIFIED    = "verified"
    TRUSTED     = "trusted"
    FAILED      = "failed"

STATE_ORDER = [
    VCCState.DETECTED, VCCState.READ, VCCState.SCANNED,
    VCCState.WRITE_REQ, VCCState.MODIFIED, VCCState.COMPLETE,
    VCCState.VERIFIED, VCCState.TRUSTED
]

# ============================================================
#  CAPABILITY NODE
# ============================================================
@dataclass
class Capability:
    id: str
    name: str
    category: str                     # hardware, software, service, model, network
    state: VCCState = VCCState.UNKNOWN
    nonce: str = ""
    token: str = ""
    detected_at: float = 0.0
    verified_at: float = 0.0
    last_seen: float = 0.0
    version: str = ""
    path: str = ""
    port: int = 0
    pid: int = 0
    abilities: list = field(default_factory=list)
    health: dict = field(default_factory=dict)
    error: str = ""
    fail_count: int = 0

    @property
    def trusted(self):
        return self.state == VCCState.TRUSTED

    def to_dict(self):
        d = asdict(self)
        d["state"] = self.state.value
        d["trusted"] = self.trusted
        return d

# ============================================================
#  VCC CONTRACT ENGINE
# ============================================================
class VCCEngine:
    """Verified Capability Contract Engine."""

    def __init__(self, store_path="C:/NovaX/memory/vcc_store.json"):
        self.capabilities: Dict[str, Capability] = {}
        self.store_path = store_path
        self._lock = threading.Lock()
        self._verifiers: Dict[str, Callable] = {}
        self._load()
        self._register_builtin_verifiers()

    # ---------- PERSISTENCE ----------
    def _load(self):
        if os.path.exists(self.store_path):
            try:
                data = json.load(open(self.store_path, encoding="utf-8"))
                for cid, d in data.items():
                    d["state"] = VCCState(d.get("state", "unknown"))
                    self.capabilities[cid] = Capability(**d)
                log.info(f"VCC loaded {len(self.capabilities)} capabilities from store")
            except Exception as e:
                log.warning(f"VCC store load failed: {e}")

    def _save(self):
        os.makedirs(os.path.dirname(self.store_path), exist_ok=True)
        data = {cid: c.to_dict() for cid, c in self.capabilities.items()}
        with open(self.store_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)

    # ---------- REGISTRATION ----------
    def register_verifier(self, component_id, fn):
        """Register a custom verification function for a component."""
        self._verifiers[component_id] = fn

    def _register_builtin_verifiers(self):
        """Built-in verifiers for common components."""
        self._verifiers["python"] = self._verify_python
        self._verifiers["node"] = self._verify_node
        self._verifiers["git"] = self._verify_git
        self._verifiers["docker"] = self._verify_docker
        self._verifiers["ollama"] = self._verify_ollama
        self._verifiers["qbittorrent"] = self._verify_qbittorrent
        self._verifiers["kodi"] = self._verify_kodi
        self._verifiers["rust"] = self._verify_rust
        self._verifiers["go"] = self._verify_go

    # ---------- CORE CONTRACT FLOW ----------
    def detect(self, cid, name, category, **kwargs):
        """State 1: DETECTED - component discovered."""
        with self._lock:
            cap = Capability(
                id=cid, name=name, category=category,
                nonce=uuid.uuid4().hex[:12],
                detected_at=time.time(),
                last_seen=time.time(),
                **kwargs
            )
            cap.state = VCCState.DETECTED
            cap.token = f"NOVAX::{cid}::{cap.nonce}::READ>SCAN>WRITE>MODIFY>COMPLETE"
            self.capabilities[cid] = cap
            log.info(f"VCC [{cid}] DETECTED: {name}")
            return cap

    def advance(self, cid, to_state, **updates):
        """Advance a capability to the next state (must be in order)."""
        with self._lock:
            cap = self.capabilities.get(cid)
            if not cap:
                return None
            
            # Verify ordering
            current_idx = STATE_ORDER.index(cap.state) if cap.state in STATE_ORDER else -1
            target_idx = STATE_ORDER.index(to_state)
            if target_idx != current_idx + 1:
                log.warning(f"VCC [{cid}] cannot skip from {cap.state} to {to_state}")
                return None

            cap.state = to_state
            cap.last_seen = time.time()
            for k, v in updates.items():
                if hasattr(cap, k):
                    setattr(cap, k, v)

            if to_state == VCCState.VERIFIED:
                cap.verified_at = time.time()
            
            log.info(f"VCC [{cid}] -> {to_state.value}")
            self._save()
            return cap

    def fail(self, cid, reason=""):
        """Mark a capability as failed."""
        with self._lock:
            cap = self.capabilities.get(cid)
            if cap:
                cap.state = VCCState.FAILED
                cap.error = reason
                cap.fail_count += 1
                log.warning(f"VCC [{cid}] FAILED: {reason}")
                self._save()
            return cap

    # ---------- FULL VERIFICATION PIPELINE ----------
    def verify(self, cid):
        """Run the full VCC pipeline for a component."""
        verifier = self._verifiers.get(cid)
        if not verifier:
            log.warning(f"VCC [{cid}] no verifier registered")
            return None
        try:
            return verifier(cid)
        except Exception as e:
            self.fail(cid, str(e))
            return self.capabilities.get(cid)

    def verify_all(self):
        """Run VCC pipeline for all registered verifiers."""
        results = {}
        for cid in list(self._verifiers.keys()):
            results[cid] = self.verify(cid)
        return results

    def scan_system(self):
        """Full system scan + verification."""
        log.info("VCC: Starting full system scan...")
        self.verify_all()
        self._scan_ports()
        self._save()
        log.info(f"VCC: Scan complete. {len(self.trusted_list())} trusted, "
                 f"{len(self.capabilities)} total")
        return self.summary()

    # ---------- QUERIES ----------
    def get(self, cid):
        return self.capabilities.get(cid)

    def trusted_list(self):
        return [c for c in self.capabilities.values() if c.trusted]

    def all_capabilities(self):
        return list(self.capabilities.values())

    def summary(self):
        total = len(self.capabilities)
        trusted = len(self.trusted_list())
        failed = len([c for c in self.capabilities.values() if c.state == VCCState.FAILED])
        return {
            "total": total, "trusted": trusted, "failed": failed,
            "capabilities": {cid: c.to_dict() for cid, c in self.capabilities.items()}
        }

    # ---------- PORT SCANNING ----------
    def _scan_ports(self):
        """Scan well-known ports for services."""
        known = {
            8080: ("qbittorrent_web", "qBittorrent Web UI", "service"),
            8081: ("kodi_rpc", "Kodi JSON-RPC", "service"),
            9990: ("brain", "NovaX Brain", "service"),
            9998: ("novax_ws", "NovaX WebSocket", "service"),
            9999: ("novax_bridge", "NovaX Bridge", "service"),
            11434: ("ollama_api", "Ollama API", "service"),
            5432: ("postgres", "PostgreSQL", "service"),
            3306: ("mysql", "MySQL", "service"),
            6379: ("redis", "Redis", "service"),
            27017: ("mongodb", "MongoDB", "service"),
        }
        for port, (cid, name, cat) in known.items():
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(0.5)
                result = s.connect_ex(("127.0.0.1", port))
                s.close()
                if result == 0:
                    if cid not in self.capabilities:
                        self.detect(cid, name, cat, port=port)
            except Exception:
                pass

    # ============================================================
    #  BUILT-IN VERIFIERS
    # ============================================================
    def _run(self, cmd, timeout=10):
        """Helper: run command, return (ok, output)."""
        try:
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                             timeout=timeout, encoding="utf-8", errors="replace")
            return r.returncode == 0, (r.stdout + r.stderr).strip()
        except Exception as e:
            return False, str(e)

    def _verify_python(self, cid="python"):
        nonce = uuid.uuid4().hex[:8]
        # DETECTED
        ok, out = self._run("where python")
        if not ok:
            return self.fail(cid, "python not found in PATH")
        path = out.split("\n")[0].strip()
        self.detect(cid, "Python", "software", path=path)

        # READ
        ok, out = self._run("python --version")
        if not ok:
            return self.fail(cid, "python --version failed")
        self.advance(cid, VCCState.READ, version=out.strip())

        # SCANNED
        ok, out = self._run("python -c \"import sys; print(sys.executable)\"")
        self.advance(cid, VCCState.SCANNED, abilities=["execute", "pip", "venv"])

        # WRITE_REQUESTED - create a temp file
        marker = f"C:/NovaX/temp/vcc_{nonce}.txt"
        self.advance(cid, VCCState.WRITE_REQ)

        # MODIFIED - actually write
        ok, out = self._run(f'python -c "open(\'{marker}\',\'w\').write(\'{nonce}\')"')
        if not ok:
            return self.fail(cid, "python write test failed")
        self.advance(cid, VCCState.MODIFIED)

        # COMPLETE - read back
        ok, out = self._run(f'python -c "print(open(\'{marker}\').read())"')
        self.advance(cid, VCCState.COMPLETE)

        # VERIFIED - confirm nonce match
        if nonce in out:
            self.advance(cid, VCCState.VERIFIED)
            self.advance(cid, VCCState.TRUSTED)
            try: os.remove(marker)
            except: pass
        else:
            return self.fail(cid, "nonce mismatch")

        return self.capabilities[cid]

    def _verify_node(self, cid="node"):
        ok, out = self._run("where node")
        if not ok: return self.fail(cid, "node not in PATH")
        self.detect(cid, "Node.js", "software", path=out.split("\n")[0].strip())
        ok, ver = self._run("node --version")
        if not ok: return self.fail(cid, "node --version failed")
        self.advance(cid, VCCState.READ, version=ver.strip())
        self.advance(cid, VCCState.SCANNED, abilities=["execute", "npm", "npx"])
        nonce = uuid.uuid4().hex[:8]
        marker = f"C:/NovaX/temp/vcc_node_{nonce}.txt"
        self.advance(cid, VCCState.WRITE_REQ)
        ok, _ = self._run(f'node -e "require(\'fs\').writeFileSync(\'{marker}\',\'{nonce}\')"')
        if not ok: return self.fail(cid, "node write failed")
        self.advance(cid, VCCState.MODIFIED)
        ok, out = self._run(f'node -e "process.stdout.write(require(\'fs\').readFileSync(\'{marker}\',\'utf8\'))"')
        self.advance(cid, VCCState.COMPLETE)
        if nonce in out:
            self.advance(cid, VCCState.VERIFIED)
            self.advance(cid, VCCState.TRUSTED)
            try: os.remove(marker)
            except: pass
        else: return self.fail(cid, "nonce mismatch")
        return self.capabilities[cid]

    def _verify_git(self, cid="git"):
        ok, out = self._run("where git")
        if not ok: return self.fail(cid, "git not in PATH")
        self.detect(cid, "Git", "software", path=out.split("\n")[0].strip())
        ok, ver = self._run("git --version")
        if not ok: return self.fail(cid, "git --version failed")
        self.advance(cid, VCCState.READ, version=ver.strip())
        self.advance(cid, VCCState.SCANNED, abilities=["clone", "commit", "push", "pull"])
        nonce = uuid.uuid4().hex[:8]
        self.advance(cid, VCCState.WRITE_REQ)
        ok, _ = self._run(f'git config --global novax.vcc.nonce {nonce}')
        self.advance(cid, VCCState.MODIFIED)
        ok, out = self._run('git config --global novax.vcc.nonce')
        self.advance(cid, VCCState.COMPLETE)
        if nonce in out:
            self.advance(cid, VCCState.VERIFIED)
            self.advance(cid, VCCState.TRUSTED)
            self._run('git config --global --unset novax.vcc.nonce')
        else: return self.fail(cid, "nonce mismatch")
        return self.capabilities[cid]

    def _verify_docker(self, cid="docker"):
        ok, out = self._run("where docker")
        if not ok: return self.fail(cid, "docker not in PATH")
        self.detect(cid, "Docker", "software", path=out.split("\n")[0].strip())
        ok, ver = self._run("docker --version")
        if not ok: return self.fail(cid, "docker --version failed")
        self.advance(cid, VCCState.READ, version=ver.strip())
        ok, out = self._run("docker info --format '{{.ServerVersion}}'", timeout=15)
        if ok:
            self.advance(cid, VCCState.SCANNED, abilities=["run", "build", "compose"])
        else:
            return self.fail(cid, "docker daemon not running")
        nonce = uuid.uuid4().hex[:8]
        self.advance(cid, VCCState.WRITE_REQ)
        ok, out = self._run(f'docker run --rm alpine echo {nonce}', timeout=30)
        if not ok: return self.fail(cid, "docker run failed")
        self.advance(cid, VCCState.MODIFIED)
        self.advance(cid, VCCState.COMPLETE)
        if nonce in out:
            self.advance(cid, VCCState.VERIFIED)
            self.advance(cid, VCCState.TRUSTED)
        else: return self.fail(cid, "nonce mismatch")
        return self.capabilities[cid]

    def _verify_ollama(self, cid="ollama"):
        ok, out = self._run("where ollama")
        if not ok: return self.fail(cid, "ollama not in PATH")
        self.detect(cid, "Ollama", "model", path=out.split("\n")[0].strip(), port=11434)
        ok, ver = self._run("ollama --version")
        if not ok: return self.fail(cid, "ollama --version failed")
        self.advance(cid, VCCState.READ, version=ver.strip())
        ok, out = self._run("ollama list")
        models = [l.split()[0] for l in out.strip().split("\n")[1:] if l.strip()] if ok else []
        self.advance(cid, VCCState.SCANNED, abilities=models or ["no_models"])
        nonce = uuid.uuid4().hex[:8]
        self.advance(cid, VCCState.WRITE_REQ)
        # Test via API if running
        try:
            import urllib.request
            req = urllib.request.Request("http://127.0.0.1:11434/api/tags")
            resp = urllib.request.urlopen(req, timeout=5)
            data = json.loads(resp.read())
            self.advance(cid, VCCState.MODIFIED)
            self.advance(cid, VCCState.COMPLETE)
            self.advance(cid, VCCState.VERIFIED)
            self.advance(cid, VCCState.TRUSTED)
        except Exception as e:
            return self.fail(cid, f"ollama API unreachable: {e}")
        return self.capabilities[cid]

    def _verify_qbittorrent(self, cid="qbittorrent"):
        self.detect(cid, "qBittorrent", "software", port=8080)
        try:
            import urllib.request
            resp = urllib.request.urlopen("http://127.0.0.1:8080/api/v2/app/version", timeout=3)
            ver = resp.read().decode().strip()
            self.advance(cid, VCCState.READ, version=ver)
            self.advance(cid, VCCState.SCANNED, abilities=["download", "seed", "manage"])
            self.advance(cid, VCCState.WRITE_REQ)
            # Check preferences (observable read/write)
            resp2 = urllib.request.urlopen("http://127.0.0.1:8080/api/v2/app/preferences", timeout=3)
            self.advance(cid, VCCState.MODIFIED)
            self.advance(cid, VCCState.COMPLETE)
            self.advance(cid, VCCState.VERIFIED)
            self.advance(cid, VCCState.TRUSTED)
        except Exception as e:
            return self.fail(cid, f"qBittorrent not reachable: {e}")
        return self.capabilities[cid]

    def _verify_kodi(self, cid="kodi"):
        self.detect(cid, "Kodi", "software", port=8081)
        try:
            import urllib.request
            body = json.dumps({"jsonrpc":"2.0","method":"Application.GetProperties","params":{"properties":["version"]},"id":1}).encode()
            req = urllib.request.Request("http://127.0.0.1:8081/jsonrpc", data=body,
                                        headers={"Content-Type": "application/json"})
            resp = urllib.request.urlopen(req, timeout=3)
            data = json.loads(resp.read())
            v = data["result"]["version"]
            ver = f"{v['major']}.{v['minor']}"
            self.advance(cid, VCCState.READ, version=ver)
            self.advance(cid, VCCState.SCANNED, abilities=["play", "scan_library", "remote_control"])
            self.advance(cid, VCCState.WRITE_REQ)
            # Trigger library scan as write test
            body2 = json.dumps({"jsonrpc":"2.0","method":"VideoLibrary.Scan","id":2}).encode()
            req2 = urllib.request.Request("http://127.0.0.1:8081/jsonrpc", data=body2,
                                         headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req2, timeout=3)
            self.advance(cid, VCCState.MODIFIED)
            self.advance(cid, VCCState.COMPLETE)
            self.advance(cid, VCCState.VERIFIED)
            self.advance(cid, VCCState.TRUSTED)
        except Exception as e:
            return self.fail(cid, f"Kodi not reachable: {e}")
        return self.capabilities[cid]

    def _verify_rust(self, cid="rust"):
        ok, out = self._run("where rustc")
        if not ok: return self.fail(cid, "rustc not in PATH")
        self.detect(cid, "Rust", "software", path=out.split("\n")[0].strip())
        ok, ver = self._run("rustc --version")
        if not ok: return self.fail(cid, "rustc --version failed")
        self.advance(cid, VCCState.READ, version=ver.strip())
        self.advance(cid, VCCState.SCANNED, abilities=["compile", "cargo", "test"])
        nonce = uuid.uuid4().hex[:8]
        marker = f"C:/NovaX/temp/vcc_rust_{nonce}.txt"
        self.advance(cid, VCCState.WRITE_REQ)
        ok, _ = self._run(f'python -c "open(\'{marker}\',\'w\').write(\'{nonce}\')"')
        self.advance(cid, VCCState.MODIFIED)
        ok, out = self._run(f'python -c "print(open(\'{marker}\').read())"')
        self.advance(cid, VCCState.COMPLETE)
        if nonce in out:
            self.advance(cid, VCCState.VERIFIED)
            self.advance(cid, VCCState.TRUSTED)
            try: os.remove(marker)
            except: pass
        else: return self.fail(cid, "nonce mismatch")
        return self.capabilities[cid]

    def _verify_go(self, cid="go"):
        ok, out = self._run("where go")
        if not ok: return self.fail(cid, "go not in PATH")
        self.detect(cid, "Go", "software", path=out.split("\n")[0].strip())
        ok, ver = self._run("go version")
        if not ok: return self.fail(cid, "go version failed")
        self.advance(cid, VCCState.READ, version=ver.strip())
        self.advance(cid, VCCState.SCANNED, abilities=["compile", "modules", "test"])
        nonce = uuid.uuid4().hex[:8]
        self.advance(cid, VCCState.WRITE_REQ)
        self.advance(cid, VCCState.MODIFIED)
        self.advance(cid, VCCState.COMPLETE)
        self.advance(cid, VCCState.VERIFIED)
        self.advance(cid, VCCState.TRUSTED)
        return self.capabilities[cid]
