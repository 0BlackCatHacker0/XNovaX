"""
NovaX Discovery Scanner
========================
Scans hardware, software, services, models, network, and filesystem.
Builds CapabilityNodes for the live graph.
"""
import subprocess
import os
import json
import time
import logging
import platform
import shutil
import socket
import threading

log = logging.getLogger("NovaX.Discovery")

# ============================================================
#  CAPABILITY NODE
# ============================================================
class CapabilityNode:
    """One detected resource / capability."""
    def __init__(self, id, type, name, status="active", **meta):
        self.id = id
        self.type = type          # hardware.gpu, software.python, service.ollama, etc.
        self.name = name
        self.status = status      # active, available, degraded, missing
        self.detected_at = time.time()
        self.last_seen = time.time()
        self.confidence = 1.0
        self.abilities = []       # list of dicts: {name, available, detail}
        self.dependencies = []    # list of node IDs this depends on
        self.dependents = []      # list of node IDs that depend on this
        self.health = {}          # arbitrary health metrics
        self.meta = meta          # extra data

    def to_dict(self):
        return {
            "id": self.id, "type": self.type, "name": self.name,
            "status": self.status, "confidence": self.confidence,
            "detected_at": self.detected_at, "last_seen": self.last_seen,
            "abilities": self.abilities, "health": self.health,
            "dependencies": self.dependencies, "dependents": self.dependents,
            "meta": self.meta,
        }

    def touch(self):
        self.last_seen = time.time()

# ============================================================
#  SCANNER
# ============================================================
class Scanner:
    """Scans the entire machine and builds CapabilityNodes."""

    def __init__(self):
        self.nodes = {}   # id -> CapabilityNode
        self._lock = threading.Lock()

    def add(self, node):
        with self._lock:
            self.nodes[node.id] = node

    def get(self, id):
        return self.nodes.get(id)

    def remove(self, id):
        with self._lock:
            self.nodes.pop(id, None)

    def by_type(self, prefix):
        return [n for n in self.nodes.values() if n.type.startswith(prefix)]

    def all_nodes(self):
        return list(self.nodes.values())

    def to_dict(self):
        return {id: n.to_dict() for id, n in self.nodes.items()}

    # ---------- UTILITIES ----------
    def _run(self, cmd, timeout=10):
        """Run a command and return stdout."""
        try:
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                             timeout=timeout, encoding="utf-8", errors="replace")
            return r.stdout.strip() if r.returncode == 0 else ""
        except Exception:
            return ""

    def _wmi(self, cls, fields):
        """Query WMI class and return list of dicts."""
        cols = ",".join(fields)
        cmd = f'powershell -NoProfile -Command "Get-WmiObject -Class {cls} | Select-Object {cols} | ConvertTo-Json -Compress"'
        raw = self._run(cmd, timeout=15)
        if not raw:
            return []
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                data = [data]
            return data
        except Exception:
            return []

    # ============================================================
    #  LAYER 1: HARDWARE
    # ============================================================
    def scan_hardware(self):
        log.info("Scanning hardware...")
        self._scan_cpu()
        self._scan_gpu()
        self._scan_ram()
        self._scan_drives()
        self._scan_usb()
        self._scan_network_adapters()
        self._scan_audio()
        self._scan_displays()

    def _scan_cpu(self):
        items = self._wmi("Win32_Processor", ["Name","NumberOfCores","NumberOfLogicalProcessors","MaxClockSpeed","Architecture"])
        for i, cpu in enumerate(items):
            n = CapabilityNode(
                id=f"cpu-{i}", type="hardware.cpu",
                name=cpu.get("Name", "Unknown CPU").strip(),
                cores=cpu.get("NumberOfCores", 0),
                threads=cpu.get("NumberOfLogicalProcessors", 0),
                clock_mhz=cpu.get("MaxClockSpeed", 0),
                arch=cpu.get("Architecture", 0)
            )
            n.abilities = [
                {"name": "compute", "available": True, "cores": n.meta.get("cores", 0)},
                {"name": "multithreading", "available": n.meta.get("threads", 0) > n.meta.get("cores", 0)},
            ]
            self.add(n)

    def _scan_gpu(self):
        items = self._wmi("Win32_VideoController", ["Name","AdapterRAM","DriverVersion","Status"])
        for i, gpu in enumerate(items):
            vram_bytes = gpu.get("AdapterRAM", 0) or 0
            vram_gb = round(vram_bytes / (1024**3), 1)
            name = gpu.get("Name", "Unknown GPU").strip()
            is_nvidia = "nvidia" in name.lower()
            is_amd = "amd" in name.lower() or "radeon" in name.lower()

            n = CapabilityNode(
                id=f"gpu-{i}", type="hardware.gpu", name=name,
                vram_gb=vram_gb, driver=gpu.get("DriverVersion", ""),
                vendor="nvidia" if is_nvidia else "amd" if is_amd else "other"
            )

            # NVIDIA-specific: get CUDA info
            if is_nvidia:
                smi = self._run("nvidia-smi --query-gpu=memory.total,memory.used,memory.free,temperature.gpu,utilization.gpu --format=csv,noheader,nounits", timeout=5)
                if smi:
                    parts = [p.strip() for p in smi.split(",")]
                    if len(parts) >= 5:
                        n.health = {
                            "vram_total_mb": int(parts[0]),
                            "vram_used_mb": int(parts[1]),
                            "vram_free_mb": int(parts[2]),
                            "temperature": int(parts[3]),
                            "utilization": int(parts[4]),
                        }
                        vram_gb = round(int(parts[0]) / 1024, 1)
                        n.meta["vram_gb"] = vram_gb

            can_inference = vram_gb >= 4
            n.abilities = [
                {"name": "display", "available": True},
                {"name": "cuda_compute", "available": is_nvidia},
                {"name": "model_inference", "available": can_inference,
                 "max_params": "7B-q4" if vram_gb >= 6 else "3B-q4" if vram_gb >= 4 else "none"},
                {"name": "video_encode", "available": is_nvidia, "codec": "NVENC"},
            ]
            self.add(n)

    def _scan_ram(self):
        items = self._wmi("Win32_PhysicalMemory", ["Capacity","Speed","Manufacturer"])
        total = 0
        for m in items:
            total += int(m.get("Capacity", 0) or 0)
        total_gb = round(total / (1024**3), 1)
        n = CapabilityNode(
            id="ram", type="hardware.ram",
            name=f"{total_gb} GB RAM",
            total_gb=total_gb, sticks=len(items),
            speed=items[0].get("Speed", 0) if items else 0
        )
        n.abilities = [
            {"name": "memory", "available": True, "total_gb": total_gb},
            {"name": "large_models", "available": total_gb >= 16},
        ]
        self.add(n)

    def _scan_drives(self):
        items = self._wmi("Win32_LogicalDisk", ["DeviceID","Size","FreeSpace","DriveType","VolumeName"])
        for d in items:
            dtype = d.get("DriveType", 0)
            if dtype not in [2, 3]:  # 2=removable, 3=local
                continue
            size = int(d.get("Size", 0) or 0)
            free = int(d.get("FreeSpace", 0) or 0)
            letter = d.get("DeviceID", "?")
            n = CapabilityNode(
                id=f"drive-{letter.replace(':', '')}", type="hardware.storage",
                name=f"{letter} {d.get('VolumeName', '')}".strip(),
                size_gb=round(size/(1024**3), 1),
                free_gb=round(free/(1024**3), 1),
                drive_type="removable" if dtype == 2 else "local"
            )
            n.health = {"free_gb": n.meta["free_gb"], "pct_free": round(free/size*100, 1) if size > 0 else 0}
            n.abilities = [{"name": "storage", "available": True, "free_gb": n.meta["free_gb"]}]
            self.add(n)

    def _scan_usb(self):
        items = self._wmi("Win32_USBHub", ["DeviceID","Name","Status"])
        for i, u in enumerate(items):
            n = CapabilityNode(
                id=f"usb-{i}", type="hardware.usb",
                name=u.get("Name", "USB Device"),
                device_id=u.get("DeviceID", ""),
                status="active" if u.get("Status") == "OK" else "degraded"
            )
            self.add(n)

    def _scan_network_adapters(self):
        items = self._wmi("Win32_NetworkAdapter", ["Name","MACAddress","Speed","NetConnectionStatus"])
        for i, a in enumerate(items):
            status_code = a.get("NetConnectionStatus")
            if status_code is None:
                continue
            connected = status_code == 2
            name = a.get("Name", "Adapter")
            is_vpn = any(v in name.lower() for v in ["vpn", "tap", "tun", "wireguard", "nordlynx"])
            n = CapabilityNode(
                id=f"net-{i}", type="hardware.network",
                name=name, status="active" if connected else "available",
                mac=a.get("MACAddress", ""),
                speed=a.get("Speed", 0),
                is_vpn=is_vpn
            )
            self.add(n)

    def _scan_audio(self):
        items = self._wmi("Win32_SoundDevice", ["Name","Status"])
        for i, a in enumerate(items):
            n = CapabilityNode(
                id=f"audio-{i}", type="hardware.audio",
                name=a.get("Name", "Audio"),
                status="active" if a.get("Status") == "OK" else "degraded"
            )
            self.add(n)

    def _scan_displays(self):
        out = self._run('powershell -NoProfile -Command "Get-WmiObject Win32_DesktopMonitor | Select-Object Name,ScreenWidth,ScreenHeight | ConvertTo-Json -Compress"')
        if not out:
            return
        try:
            items = json.loads(out)
            if isinstance(items, dict):
                items = [items]
            for i, m in enumerate(items):
                n = CapabilityNode(
                    id=f"display-{i}", type="hardware.display",
                    name=m.get("Name", "Monitor"),
                    width=m.get("ScreenWidth", 0),
                    height=m.get("ScreenHeight", 0)
                )
                self.add(n)
        except Exception:
            pass

    # ============================================================
    #  LAYER 2: SOFTWARE
    # ============================================================
    def scan_software(self):
        log.info("Scanning software...")
        checks = [
            ("python",    "python --version",    "software.runtime"),
            ("node",      "node --version",      "software.runtime"),
            ("npm",       "npm --version",       "software.tool"),
            ("git",       "git --version",       "software.tool"),
            ("rustc",     "rustc --version",     "software.runtime"),
            ("go",        "go version",          "software.runtime"),
            ("java",      "java --version",      "software.runtime"),
            ("dotnet",    "dotnet --version",    "software.runtime"),
            ("docker",    "docker --version",    "software.tool"),
            ("cargo",     "cargo --version",     "software.tool"),
            ("pip",       "pip --version",       "software.tool"),
            ("code",      "code --version",      "software.editor"),
            ("ollama",    "ollama --version",    "software.ai"),
            ("ffmpeg",    "ffmpeg -version",     "software.media"),
            ("winget",    "winget --version",    "software.tool"),
        ]
        for name, cmd, stype in checks:
            ver = self._run(cmd, timeout=8)
            if ver:
                first_line = ver.split("\n")[0].strip()
                n = CapabilityNode(
                    id=f"sw-{name}", type=stype,
                    name=name, version=first_line
                )
                n.abilities = [{"name": name, "available": True, "version": first_line}]
                self.add(n)

        # Check for Kodi
        kodi_paths = ["C:/Program Files/Kodi/kodi.exe", "C:/Program Files (x86)/Kodi/kodi.exe"]
        for p in kodi_paths:
            if os.path.isfile(p):
                n = CapabilityNode(id="sw-kodi", type="software.media", name="Kodi", path=p)
                n.abilities = [{"name": "media_playback", "available": True}]
                self.add(n)
                break

        # Check for qBittorrent
        qb_paths = ["C:/Program Files/qBittorrent/qbittorrent.exe"]
        for p in qb_paths:
            if os.path.isfile(p):
                n = CapabilityNode(id="sw-qbittorrent", type="software.download", name="qBittorrent", path=p)
                n.abilities = [{"name": "torrent", "available": True}]
                self.add(n)
                break

    # ============================================================
    #  LAYER 3: SERVICES (ports + processes)
    # ============================================================
    def scan_services(self):
        log.info("Scanning services...")
        # Check known ports
        known = [
            (9999, "NovaX Bridge", "service.novax"),
            (9998, "NovaX WebSocket", "service.novax"),
            (9990, "NovaX Brain", "service.ai"),
            (11434, "Ollama", "service.ai"),
            (8080, "qBittorrent Web UI", "service.download"),
            (8081, "Kodi JSON-RPC", "service.media"),
            (5432, "PostgreSQL", "service.database"),
            (3306, "MySQL", "service.database"),
            (6379, "Redis", "service.database"),
            (27017, "MongoDB", "service.database"),
            (8888, "Jupyter", "service.dev"),
            (3000, "Dev Server", "service.dev"),
            (5173, "Vite Dev", "service.dev"),
        ]
        for port, name, stype in known:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(0.5)
                result = s.connect_ex(("127.0.0.1", port))
                s.close()
                if result == 0:
                    n = CapabilityNode(
                        id=f"svc-{port}", type=stype,
                        name=name, port=port, status="active"
                    )
                    n.abilities = [{"name": name.lower().replace(" ", "_"), "available": True, "port": port}]
                    self.add(n)
            except Exception:
                pass

    # ============================================================
    #  LAYER 4: AI MODELS
    # ============================================================
    def scan_models(self):
        log.info("Scanning AI models...")
        out = self._run("ollama list", timeout=10)
        if not out:
            return
        lines = out.strip().split("\n")
        for line in lines[1:]:  # skip header
            parts = line.split()
            if len(parts) >= 3:
                model_name = parts[0]
                model_id = parts[1] if len(parts) > 1 else ""
                size = parts[2] if len(parts) > 2 else ""
                n = CapabilityNode(
                    id=f"model-{model_name.replace(':', '-')}",
                    type="model.local", name=model_name,
                    model_id=model_id, size=size
                )
                n.abilities = [
                    {"name": "text_generation", "available": True},
                    {"name": "inference", "available": True, "model": model_name},
                ]
                self.add(n)

    # ============================================================
    #  LAYER 5: NETWORK
    # ============================================================
    def scan_network(self):
        log.info("Scanning network...")
        # Internet check
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(3)
            s.connect(("8.8.8.8", 53))
            s.close()
            n = CapabilityNode(id="net-internet", type="network.internet", name="Internet", status="active")
            n.abilities = [{"name": "internet", "available": True}]
            self.add(n)
        except Exception:
            n = CapabilityNode(id="net-internet", type="network.internet", name="Internet", status="missing")
            n.abilities = [{"name": "internet", "available": False}]
            self.add(n)

    # ============================================================
    #  LAYER 6: FILESYSTEM
    # ============================================================
    def scan_filesystem(self):
        log.info("Scanning filesystem...")
        # NovaX workspace
        novax_root = "C:/NovaX"
        if os.path.isdir(novax_root):
            dirs = [d for d in os.listdir(novax_root) if os.path.isdir(os.path.join(novax_root, d))]
            n = CapabilityNode(
                id="fs-novax", type="filesystem.workspace",
                name="NovaX Root", path=novax_root,
                subdirs=dirs
            )
            self.add(n)

        # Media library
        media = "C:/NovaX/media"
        if os.path.isdir(media):
            total_size = 0
            file_count = 0
            for root, dirs, files in os.walk(media):
                for f in files:
                    fp = os.path.join(root, f)
                    try:
                        total_size += os.path.getsize(fp)
                        file_count += 1
                    except Exception:
                        pass
            n = CapabilityNode(
                id="fs-media", type="filesystem.media",
                name="Media Library", path=media,
                files=file_count, size_mb=round(total_size / (1024**2), 1)
            )
            self.add(n)

    # ============================================================
    #  FULL SCAN
    # ============================================================
    def full_scan(self):
        """Run all detection layers. Returns elapsed time."""
        start = time.time()
        log.info("=== Full Discovery Scan Starting ===")
        self.scan_hardware()
        self.scan_software()
        self.scan_services()
        self.scan_models()
        self.scan_network()
        self.scan_filesystem()
        elapsed = round(time.time() - start, 2)
        log.info(f"=== Discovery Complete: {len(self.nodes)} nodes in {elapsed}s ===")
        return elapsed

    # ============================================================
    #  ABILITY SCORING
    # ============================================================
    def can(self, ability_name):
        """Check if a specific ability is possible. Returns dict with confidence."""
        for node in self.nodes.values():
            for ab in node.abilities:
                if ab.get("name") == ability_name and ab.get("available"):
                    conf = node.confidence
                    if node.status == "degraded":
                        conf *= 0.5
                    return {"possible": True, "confidence": conf,
                            "provider": node.id, "detail": ab}
        return {"possible": False, "confidence": 0.0, "missing": ability_name}

    def abilities_summary(self):
        """Return all available abilities with scores."""
        result = {}
        for node in self.nodes.values():
            for ab in node.abilities:
                name = ab.get("name", "")
                if name and ab.get("available"):
                    if name not in result or node.confidence > result[name]["confidence"]:
                        result[name] = {
                            "available": True,
                            "confidence": node.confidence,
                            "provider": node.id,
                            "detail": ab,
                        }
        return result

    def health_summary(self):
        """Return health of all nodes that have health data."""
        return {n.id: n.health for n in self.nodes.values() if n.health}
