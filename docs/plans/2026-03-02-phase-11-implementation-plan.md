# Phase 11: NovaX Living System — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Give NovaX a body — shared TZip DNA, a ternary inter-model communication protocol (TSpeak), and living-system layers (TWeave, TForge Live, TTimeline, TStream Mesh, TShield).

**Architecture:** Extract duplicated TZip into `core/tzip.py` (Layer 0), create `nova_tspeak.py` service on port 9895 (Layer 1), enhance `nova_ternary_tools.py` with Layers 2-6 (TWeave, TForge Live, TTimeline, TStream Mesh, TShield), integrate TSpeak into Hivemind's `cluster_query()` deliberation pipeline (Layer 6), then wire everything through orchestrator, NovaLang, desktop, and sentinel (Layer 8).

**Tech Stack:** Python 3.12+, `http.server` + `ThreadingMixIn`, `struct` for binary framing, `zlib` for compression, NovaLang builtins, HTML/JS desktop panel.

---

## Task 1: Layer 0 — The DNA (`core/tzip.py`)

**Files:**
- Create: `C:\NovaX\core\tzip.py`
- Modify: `C:\NovaX\nova_tools.py:36-107` — replace TZip inline with import
- Modify: `C:\NovaX\nova_vault.py:49-108` — replace TZip inline with import
- Modify: `C:\NovaX\nova_deepstorage.py:47-95` — replace TZip inline with import
- Modify: `C:\NovaX\nova_ternary_tools.py:72-122` — replace TZip inline with import

**Step 1: Create shared `core/tzip.py`**

Create `C:\NovaX\core\tzip.py` with the canonical TZip implementation extracted from `nova_ternary_tools.py` (the most complete version with harmonic constants):

```python
"""NovaX TZip — Ternary Compression Module (shared DNA)

The 3-5-7-13 harmonic constants:
  3  = ternary base (three states: -1, 0, +1)
  5  = packing factor (3^5=243 fits in 1 byte of 256)
  7  = composition unit (7 tools per service)
  13 = carrier wave / frame (TZip header = exactly 13 bytes)
"""
import struct
try:
    import zlib as _zlib
except ImportError:
    _zlib = None

# 3-5-7-13 Harmonic Constants
H3  = 3
H5  = 5
H7  = 7
H13 = 13

BLOCK_SIZE     = H3 ** H7    # 2187
FLOW_LAMINAR   = H3 ** H3    # 27
FLOW_TRANS     = H5 ** H3    # 125
FLOW_TURBULENT = H7 ** H3    # 343
HEADER_SIZE    = H13          # 13 bytes
PACK_TRITS     = H5           # 5 trits per packed byte
TZIP_MAGIC     = b"TZIP"

def _bytes_to_trits(data):
    trits = []
    for b in data:
        v = b
        for _ in range(6):
            trits.append(v % 3 - 1); v //= 3
    return trits

def _trits_to_bytes(trits, orig_size):
    out = []
    for i in range(0, len(trits), 6):
        c = trits[i:i+6]; v = 0
        for j in reversed(range(len(c))): v = v * 3 + (c[j] + 1)
        out.append(v & 0xFF)
    return bytes(out[:orig_size])

def _pack_trits(trits):
    out = []
    for i in range(0, len(trits), PACK_TRITS):
        c = trits[i:i+PACK_TRITS]
        while len(c) < PACK_TRITS: c.append(0)
        v = 0
        for j in reversed(range(PACK_TRITS)): v = v * 3 + (c[j] + 1)
        out.append(v)
    return bytes(out)

def _unpack_trits(data, trit_count):
    trits = []
    for b in data:
        v = b
        for _ in range(PACK_TRITS): trits.append(v % 3 - 1); v //= 3
    return trits[:trit_count]

def tzip_compress(data):
    """Compress bytes: bytes -> trits -> pack -> zlib -> 13-byte TZIP header + payload."""
    orig = len(data)
    trits = _bytes_to_trits(data)
    packed = _pack_trits(trits)
    deflated = _zlib.compress(packed, 9) if _zlib else packed
    flags = 0x01 if _zlib else 0x00
    return TZIP_MAGIC + struct.pack("<II", orig, len(trits)) + struct.pack("B", flags) + deflated

def tzip_decompress(data):
    """Decompress TZIP archive back to original bytes."""
    if data[:4] != TZIP_MAGIC: raise ValueError("Not TZIP")
    orig, tc = struct.unpack("<II", data[4:12])
    flags = data[12]; body = data[HEADER_SIZE:]
    packed = _zlib.decompress(body) if (flags & 0x01) else body
    return _trits_to_bytes(_unpack_trits(packed, tc), orig)

def tzip_ratio(original, compressed):
    """Return compression ratio as string."""
    if original == 0: return "0%"
    return f"{round((1 - compressed / original) * 100, 1)}%"
```

**Step 2: Update all 4 consumers**

In each file, replace the inline TZip block with an import. Pattern:

```python
# At top of file, add:
import sys; sys.path.insert(0, r"C:\NovaX")  # if not already present
from core.tzip import (tzip_compress, tzip_decompress, tzip_ratio,
    TZIP_MAGIC, HEADER_SIZE, PACK_TRITS, BLOCK_SIZE,
    FLOW_LAMINAR, FLOW_TRANS, FLOW_TURBULENT,
    H3, H5, H7, H13)
```

For each file, **delete** the inline TZip functions and constants, replacing them with the import above:

- `nova_tools.py`: Delete lines 36-107 (TZIP_MAGIC through tzip_ratio), add import at line 36
- `nova_vault.py`: Delete lines 49-108, add import at line 49
- `nova_deepstorage.py`: Delete lines 47-95, add import at line 47
- `nova_ternary_tools.py`: Delete lines 72-122 (the TZIP section), add import at line 72. **Keep** the harmonic constants (lines 55-69) as they're used for other purposes too, but remove the duplicated `TZIP_MAGIC`, `_bytes_to_trits`, etc.

**Step 3: Verify all 4 services still start**

Run each service and check health:
```bash
curl -s http://localhost:9891/health  # nova_tools
curl -s http://localhost:9892/health  # nova_vault
curl -s http://localhost:9893/health  # nova_deepstorage
curl -s http://localhost:9894/health  # nova_ternary_tools
```
Expected: All return `{"ok": true, ...}`

**Step 4: Verify TZip still works through each**

```bash
# Test via TTools (most comprehensive)
curl -s -X POST http://localhost:9894/ttools/cache/set \
  -H "Content-Type: application/json" \
  -d '{"key":"dna_test","value":"shared tzip module works"}'
# Expected: {"ok": true, "compressed": true, ...}
```

---

## Task 2: Layer 1 — TSpeak Protocol Server (`nova_tspeak.py`)

**Files:**
- Create: `C:\NovaX\nova_tspeak.py` (~400 lines)

**Step 1: Create TSpeak server**

Create `C:\NovaX\nova_tspeak.py` with these components:

1. **Imports and constants**: Import from `core.tzip`, define PORT=9895, TSPEAK_MAGIC=b"TSP", CHANNEL_IDS (0-9 for REASON through DOMAIN), VERSION=1

2. **TSpeakFrame dataclass**:
   - `magic`: bytes (3) = b"TSP"
   - `version`: int (1 byte)
   - `regime`: int (1 byte) — 0=laminar, 1=transitional, 2=turbulent, 3=chaotic
   - `reynolds`: int (2 bytes, uint16)
   - `channel_id`: int (1 byte, 0-9)
   - `round_num`: int (1 byte)
   - `payload_len`: int (2 bytes)
   - `crc16`: int (2 bytes)
   - `payload`: bytes (TZip-compressed ternary vectors)

3. **`encode_frame(header_dict, payload_bytes) -> bytes`** — Pack 13-byte header + payload

4. **`decode_frame(raw: bytes) -> (dict, bytes)`** — Unpack header + payload

5. **`crc16(data: bytes) -> int`** — Simple CRC-16-CCITT

6. **TSpeakEncoder class**:
   - `encode_response(text, channel, reynolds) -> bytes` — English text to TSpeak frame
     - Classify flow regime from Reynolds using 3-5-7-13 boundaries (27/125/343)
     - Extract key topics as ternary state vector (each topic: +1 agree, 0 neutral, -1 disagree)
     - TZip-compress the vector
     - Pack into 13-byte frame + payload
   - `decode_response(frame_bytes) -> dict` — TSpeak frame back to readable summary
   - `encode_vote(position: int, reason: str = "") -> bytes` — Single model vote
     - position is -1/0/+1
     - If +1: payload is 1 trit (minimal, Morse principle)
     - If 0: payload is 2 trits
     - If -1: payload includes compressed reason
   - `classify_regime(reynolds: float) -> str` — Use 27/125/343 boundaries

7. **TSpeakDeliberation class**:
   - `deliberate(responses: list[dict], channel: str, reynolds: float) -> dict` — Run N-S-governed deliberation:
     - If Re < 27 (laminar): 1 round, trit votes only, majority wins
     - If 27-125 (transitional): 2 rounds, votes + key-facts, weighted average
     - If 125-343 (turbulent): 3-5 rounds, full ternary reasoning, viscous damping between rounds
     - If 343+ (chaotic): Japanese decomposition — split into sub-problems, each model attacks strongest, merge at intersections
   - `merge_japanese(positions: list[dict]) -> dict` — Japanese multiplication merge
     - Each position has sub-answers (lines)
     - Confidence multiplies at intersection points (where 2+ models agree)
     - Returns merged answer with agreement_ratio
   - `carry_soroban(chain: list[dict]) -> dict` — Sequential carry
     - Each step passes only key-facts (remainder), not full text
     - Momentum: alpha=0.4 carry from previous, 0.6 new
   - `viscous_damp(scores: list[float], nu: float = 0.1) -> list[float]` — Smooth conflicting scores (Laplacian smoothing)

8. **Stats tracking**: frames_encoded, frames_decoded, deliberations, compression_ratios, regime_distribution

9. **HTTP Handler** (same `http.server` + `ThreadingMixIn` pattern as all other services):
   - POST `/tspeak/encode` — body: `{"text": "...", "channel": "REASON", "reynolds": 150}` → returns base64 frame
   - POST `/tspeak/decode` — body: `{"frame": "<base64>"}` → returns decoded dict
   - POST `/tspeak/deliberate` — body: `{"responses": [...], "channel": "REASON", "reynolds": 150}` → returns merged result
   - POST `/tspeak/classify` — body: `{"reynolds": 150}` → returns regime + communication pattern
   - POST `/tspeak/merge` — body: `{"positions": [...]}` → returns Japanese multiplication merge
   - POST `/tspeak/carry` — body: `{"chain": [...]}` → returns Soroban sequential result
   - GET `/tspeak/status` — returns stats
   - GET `/health` — returns `{"ok": true, "service": "nova-tspeak", "port": 9895}`

**Step 2: Syntax check**

```bash
python -c "import py_compile; py_compile.compile(r'C:\NovaX\nova_tspeak.py', doraise=True)"
```
Expected: No errors

**Step 3: Launch and verify health**

```bash
curl -s http://localhost:9895/health
```
Expected: `{"ok": true, "service": "nova-tspeak", "port": 9895}`

**Step 4: Test encode/decode round-trip**

```bash
curl -s -X POST http://localhost:9895/tspeak/encode \
  -H "Content-Type: application/json" \
  -d '{"text": "Ocean acidification is caused by CO2 absorption", "channel": "REASON", "reynolds": 50}'
# Expected: {"ok": true, "frame": "<base64>", "header_bytes": 13, "regime": "transitional", ...}

# Then decode:
curl -s -X POST http://localhost:9895/tspeak/decode \
  -H "Content-Type: application/json" \
  -d '{"frame": "<base64 from above>"}'
# Expected: {"ok": true, "channel": "REASON", "regime": "transitional", ...}
```

**Step 5: Test deliberation**

```bash
curl -s -X POST http://localhost:9895/tspeak/deliberate \
  -H "Content-Type: application/json" \
  -d '{"responses": [{"model": "llama3", "text": "CO2 causes it", "score": 0.9}, {"model": "mistral", "text": "CO2 absorption in water", "score": 0.85}, {"model": "phi3", "text": "Industrial emissions", "score": 0.7}], "channel": "REASON", "reynolds": 50}'
# Expected: {"ok": true, "regime": "transitional", "rounds": 2, "merged": "...", "compression_ratio": "...", ...}
```

---

## Task 3: Layers 2-3 — TWeave + TForge Live (`nova_ternary_tools.py`)

**Files:**
- Modify: `C:\NovaX\nova_ternary_tools.py` (~+120 lines at end, before server startup)

**Step 1: Add TWeave (Nervous System)**

Insert after the existing TForge class (before the HTTP handler), a new class `TWeave`:

```python
class TWeave:
    """Layer 2: Nervous System — persistent compressed channels between services."""
    def __init__(self):
        self._channels = {}  # channel_id -> {source, dest, stats}
        self._lock = threading.Lock()

    def create_channel(self, source_port, dest_port):
        """Create persistent compressed pipe between two services."""
        cid = f"{source_port}->{dest_port}"
        with self._lock:
            self._channels[cid] = {
                "source": source_port, "dest": dest_port,
                "created": time.time(), "messages": 0,
                "bytes_raw": 0, "bytes_compressed": 0,
            }
        return cid

    def send(self, channel_id, data):
        """Send data through TWeave channel (TZip compressed)."""
        raw = json.dumps(data).encode() if isinstance(data, (dict, list)) else data
        compressed = tzip_compress(raw)
        # Forward to destination
        ch = self._channels.get(channel_id)
        if not ch: return {"ok": False, "error": "channel not found"}
        dest_url = f"http://localhost:{ch['dest']}"
        try:
            req = urllib.request.Request(dest_url, compressed, {"Content-Type": "application/octet-stream", "X-TWeave": channel_id})
            urllib.request.urlopen(req, timeout=10)
        except Exception:
            pass  # fire-and-forget for streams
        with self._lock:
            ch["messages"] += 1
            ch["bytes_raw"] += len(raw)
            ch["bytes_compressed"] += len(compressed)
        savings = round((1 - len(compressed) / max(len(raw), 1)) * 100, 1)
        return {"ok": True, "raw": len(raw), "compressed": len(compressed), "savings": f"{savings}%"}

    def status(self):
        with self._lock:
            total_raw = sum(c["bytes_raw"] for c in self._channels.values())
            total_comp = sum(c["bytes_compressed"] for c in self._channels.values())
            return {
                "channels": len(self._channels),
                "total_messages": sum(c["messages"] for c in self._channels.values()),
                "bytes_raw": total_raw, "bytes_compressed": total_comp,
                "savings": f"{round((1 - total_comp / max(total_raw, 1)) * 100, 1)}%",
                "channel_list": list(self._channels.keys()),
            }
```

**Step 2: Add TForge Live (Immune System)**

```python
class TForgeLive:
    """Layer 3: Immune System — continuous code health monitoring."""
    WATCH_FILES = [
        r"C:\NovaX\core\orchestrator.py",
        r"C:\NovaX\nova_hivemind.py",
        r"C:\NovaX\nova_cloud_router.py",
        r"C:\NovaX\nova_nexus.py",
        r"C:\NovaX\nova_sentinel.py",
        r"C:\NovaX\nova_closed_loop.py",
        r"C:\NovaX\nova_max_patch.py",
        r"C:\NovaX\nova_tools.py",
        r"C:\NovaX\nova_vault.py",
        r"C:\NovaX\nova_deepstorage.py",
        r"C:\NovaX\nova_ternary_tools.py",
        r"C:\NovaX\novalang.py",
        r"C:\NovaX\nova_vpn_core.py",
        r"C:\NovaX\nova_tspeak.py",
    ]

    def __init__(self):
        self._alerts = []  # active alerts
        self._last_scan = {}  # file -> {re, functions, timestamp}
        self._lock = threading.Lock()
        self._running = False

    def start(self):
        if self._running: return
        self._running = True
        t = threading.Thread(target=self._monitor_loop, daemon=True)
        t.start()

    def _monitor_loop(self):
        while self._running:
            for fpath in self.WATCH_FILES:
                try:
                    self._scan_file(fpath)
                except Exception:
                    pass
            time.sleep(60)

    def _scan_file(self, fpath):
        """Scan file using TForge Reynolds analysis."""
        if not os.path.exists(fpath): return
        try:
            with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                source = f.read()
        except Exception:
            return
        data = source.encode("utf-8", errors="ignore")
        re_val = calculate_reynolds(data)
        # Parse functions and compute per-function Reynolds
        func_pattern = re.compile(r"(?:def|class|async def)\s+(\w+)")
        alerts = []
        for m in func_pattern.finditer(source):
            name = m.group(1)
            # Get function body (approximate: next function or end)
            start = m.start()
            end = len(source)
            next_m = func_pattern.search(source, m.end() + 1)
            if next_m: end = next_m.start()
            body = source[start:end].encode("utf-8", errors="ignore")
            if len(body) > 50:
                func_re = calculate_reynolds(body)
                if func_re > FLOW_TURBULENT:  # > 343
                    alerts.append({
                        "file": os.path.basename(fpath),
                        "function": name,
                        "reynolds": round(func_re, 2),
                        "severity": "critical" if func_re > 500 else "warning",
                        "timestamp": time.time(),
                    })
        with self._lock:
            self._last_scan[fpath] = {
                "reynolds": round(re_val, 2),
                "functions_scanned": len(list(func_pattern.finditer(source))),
                "alerts": len(alerts),
                "timestamp": time.time(),
            }
            # Replace alerts for this file
            self._alerts = [a for a in self._alerts if a["file"] != os.path.basename(fpath)]
            self._alerts.extend(alerts)

    def get_alerts(self):
        with self._lock:
            return {
                "alerts": list(self._alerts),
                "total": len(self._alerts),
                "files_monitored": len(self._last_scan),
                "last_scan": {os.path.basename(k): v for k, v in self._last_scan.items()},
            }
```

**Step 3: Instantiate both and wire endpoints**

Add at module level (after class definitions, before handler):
```python
_tweave = TWeave()
_tforge_live = TForgeLive()
_tforge_live.start()
```

Add to the HTTP handler's `do_GET`:
```python
elif path == "/ttools/weave/status":
    self._json(_tweave.status())
elif path == "/ttools/forge/alerts":
    self._json(_tforge_live.get_alerts())
```

Add to `do_POST`:
```python
elif path == "/ttools/weave/channel":
    data = json.loads(body)
    cid = _tweave.create_channel(data["source"], data["dest"])
    self._json({"ok": True, "channel_id": cid})
elif path == "/ttools/weave/send":
    data = json.loads(body)
    result = _tweave.send(data["channel_id"], data.get("data", {}))
    self._json(result)
```

**Step 4: Verify**

```bash
curl -s http://localhost:9894/ttools/forge/alerts
# Expected: {"alerts": [...], "total": N, "files_monitored": 14, ...}

curl -s -X POST http://localhost:9894/ttools/weave/channel \
  -H "Content-Type: application/json" \
  -d '{"source": 9894, "dest": 9881}'
# Expected: {"ok": true, "channel_id": "9894->9881"}

curl -s http://localhost:9894/ttools/weave/status
# Expected: {"channels": 1, "total_messages": 0, ...}
```

---

## Task 4: Layers 4-5 — TTimeline + TStream Mesh (`nova_ternary_tools.py`)

**Files:**
- Modify: `C:\NovaX\nova_ternary_tools.py` (~+120 lines)

**Step 1: Add TTimeline (Memory)**

```python
class TTimeline:
    """Layer 4: Memory — automatic file versioning via TDiff deltas."""
    STORE_DIR = r"C:\NovaX\memory\timeline"

    def __init__(self):
        os.makedirs(self.STORE_DIR, exist_ok=True)
        self._tracked = {}  # path -> {mtime, snapshots: []}
        self._lock = threading.Lock()
        self._running = False

    def start(self):
        if self._running: return
        self._running = True
        threading.Thread(target=self._watch_loop, daemon=True).start()

    def _watch_loop(self):
        while self._running:
            with self._lock:
                paths = list(self._tracked.keys())
            for p in paths:
                try:
                    mt = os.path.getmtime(p)
                    with self._lock:
                        if mt != self._tracked[p]["mtime"]:
                            self._snapshot(p)
                            self._tracked[p]["mtime"] = mt
                except Exception:
                    pass
            time.sleep(30)

    def track(self, path):
        """Start tracking a file for versioning."""
        if not os.path.exists(path): return {"ok": False, "error": "not found"}
        with self._lock:
            self._tracked[path] = {"mtime": os.path.getmtime(path), "snapshots": []}
        self._snapshot(path)
        return {"ok": True, "tracking": path}

    def _snapshot(self, path):
        """Capture current state as TZip-compressed snapshot."""
        try:
            with open(path, "rb") as f:
                data = f.read()
            compressed = tzip_compress(data)
            ts = time.time()
            fname = f"{hashlib.md5(path.encode()).hexdigest()}_{int(ts)}.tzip"
            out = os.path.join(self.STORE_DIR, fname)
            with open(out, "wb") as f:
                f.write(compressed)
            with self._lock:
                if path in self._tracked:
                    self._tracked[path]["snapshots"].append({
                        "timestamp": ts, "file": fname,
                        "original_size": len(data), "compressed_size": len(compressed),
                    })
                    # Keep last 50 snapshots per file
                    if len(self._tracked[path]["snapshots"]) > 50:
                        self._tracked[path]["snapshots"] = self._tracked[path]["snapshots"][-50:]
        except Exception:
            pass

    def restore(self, path, timestamp=None):
        """Restore file to a specific point in time."""
        with self._lock:
            info = self._tracked.get(path)
            if not info or not info["snapshots"]:
                return {"ok": False, "error": "no snapshots"}
            if timestamp:
                snap = min(info["snapshots"], key=lambda s: abs(s["timestamp"] - timestamp))
            else:
                snap = info["snapshots"][-1]
        fpath = os.path.join(self.STORE_DIR, snap["file"])
        with open(fpath, "rb") as f:
            compressed = f.read()
        data = tzip_decompress(compressed)
        with open(path, "wb") as f:
            f.write(data)
        return {"ok": True, "restored": path, "from_timestamp": snap["timestamp"],
                "size": len(data)}

    def status(self):
        with self._lock:
            return {
                "tracked_files": len(self._tracked),
                "total_snapshots": sum(len(v["snapshots"]) for v in self._tracked.values()),
                "files": {os.path.basename(k): len(v["snapshots"]) for k, v in self._tracked.items()},
            }
```

**Step 2: Add TStream Mesh (Bloodstream)**

```python
class TStreamMesh:
    """Layer 5: Bloodstream — real-time health heartbeats between services."""
    SERVICE_PORTS = {
        "orchestrator": 9999, "cloud_router": 9878, "hivemind": 9881,
        "exec_server": 9877, "vpn_core": 9880, "nexus": 9882,
        "sentinel": 9884, "nova_brain": 9990, "nova_tools": 9891,
        "nova_vault": 9892, "deepstorage": 9893, "ttools": 9894,
        "tspeak": 9895,
    }

    def __init__(self):
        self._heartbeats = {}  # service -> {trit, last_seen, latency_ms}
        self._lock = threading.Lock()
        self._running = False

    def start(self):
        if self._running: return
        self._running = True
        threading.Thread(target=self._heartbeat_loop, daemon=True).start()

    def _heartbeat_loop(self):
        while self._running:
            for name, port in self.SERVICE_PORTS.items():
                t0 = time.time()
                try:
                    req = urllib.request.Request(f"http://localhost:{port}/health")
                    resp = urllib.request.urlopen(req, timeout=3)
                    data = json.loads(resp.read())
                    latency = round((time.time() - t0) * 1000, 1)
                    trit = 1 if data.get("ok") else 0  # +1 healthy, 0 degraded
                except Exception:
                    latency = round((time.time() - t0) * 1000, 1)
                    trit = -1  # down
                with self._lock:
                    self._heartbeats[name] = {
                        "trit": trit, "port": port,
                        "last_seen": time.time(), "latency_ms": latency,
                        "status": {1: "healthy", 0: "degraded", -1: "down"}[trit],
                    }
            time.sleep(H5)  # 5 second heartbeat (harmonic)

    def status(self):
        with self._lock:
            healthy = sum(1 for h in self._heartbeats.values() if h["trit"] == 1)
            degraded = sum(1 for h in self._heartbeats.values() if h["trit"] == 0)
            down = sum(1 for h in self._heartbeats.values() if h["trit"] == -1)
            return {
                "services": dict(self._heartbeats),
                "summary": {"healthy": healthy, "degraded": degraded, "down": down,
                            "total": len(self._heartbeats)},
                "heartbeat_interval": H5,
            }
```

**Step 3: Instantiate and wire endpoints**

```python
_timeline = TTimeline()
_timeline.start()
_stream_mesh = TStreamMesh()
_stream_mesh.start()
```

Add to handler's `do_GET`:
```python
elif path == "/ttools/timeline/status":
    self._json(_timeline.status())
elif path == "/ttools/mesh/heartbeats":
    self._json(_stream_mesh.status())
```

Add to `do_POST`:
```python
elif path == "/ttools/timeline/track":
    data = json.loads(body)
    self._json(_timeline.track(data["path"]))
elif path == "/ttools/timeline/restore":
    data = json.loads(body)
    self._json(_timeline.restore(data["path"], data.get("timestamp")))
```

**Step 4: Verify**

```bash
curl -s http://localhost:9894/ttools/mesh/heartbeats
# Expected: {"services": {...}, "summary": {"healthy": N, ...}, "heartbeat_interval": 5}

curl -s -X POST http://localhost:9894/ttools/timeline/track \
  -H "Content-Type: application/json" \
  -d '{"path": "C:\\NovaX\\core\\orchestrator.py"}'
# Expected: {"ok": true, "tracking": "C:\\NovaX\\core\\orchestrator.py"}

curl -s http://localhost:9894/ttools/timeline/status
# Expected: {"tracked_files": 1, "total_snapshots": 1, ...}
```

---

## Task 5: Layer 6 — TShield (`nova_ternary_tools.py`)

**Files:**
- Modify: `C:\NovaX\nova_ternary_tools.py` (~+60 lines)

**Step 1: Add TShield class**

```python
class TShield:
    """Layer 6: Shield — Reynolds on HTTP traffic patterns."""
    def __init__(self):
        self._traffic = {}  # source -> {requests: [], bytes: 0}
        self._lock = threading.Lock()

    def record(self, source, method, path, size):
        """Record a traffic event."""
        with self._lock:
            if source not in self._traffic:
                self._traffic[source] = {"requests": deque(maxlen=100), "total_bytes": 0}
            self._traffic[source]["requests"].append({
                "time": time.time(), "method": method, "path": path, "size": size,
            })
            self._traffic[source]["total_bytes"] += size

    def analyze(self, source=None):
        """Classify traffic source by Reynolds number."""
        with self._lock:
            sources = {source: self._traffic[source]} if source and source in self._traffic else dict(self._traffic)

        results = {}
        for src, data in sources.items():
            reqs = list(data["requests"])
            if len(reqs) < 2:
                results[src] = {"reynolds": 0, "regime": "laminar", "risk": "none"}
                continue
            # Compute traffic Reynolds: rate * diversity * avg_size / smoothness
            now = time.time()
            recent = [r for r in reqs if now - r["time"] < 60]
            rate = len(recent) / 60.0  # requests per second
            paths = set(r["path"] for r in recent)
            diversity = len(paths) / max(len(recent), 1)  # 0-1 route diversity
            avg_size = sum(r["size"] for r in recent) / max(len(recent), 1)
            # Time intervals between requests (smoothness)
            intervals = []
            for i in range(1, len(recent)):
                intervals.append(recent[i]["time"] - recent[i-1]["time"])
            smoothness = 1.0
            if intervals:
                import statistics
                smoothness = max(statistics.stdev(intervals), 0.01) if len(intervals) > 1 else 1.0
            re_val = (rate * diversity * avg_size) / smoothness
            if re_val < FLOW_LAMINAR:
                regime, risk = "laminar", "none"
            elif re_val < FLOW_TRANS:
                regime, risk = "transitional", "low"
            elif re_val < FLOW_TURBULENT:
                regime, risk = "turbulent", "medium"
            else:
                regime, risk = "chaotic", "high"
            results[src] = {
                "reynolds": round(re_val, 2), "regime": regime, "risk": risk,
                "rate_per_sec": round(rate, 2), "unique_routes": len(paths),
                "avg_payload": round(avg_size, 1), "recent_requests": len(recent),
            }
        return results
```

**Step 2: Instantiate and wire**

```python
_tshield = TShield()
```

Add to handler's `do_POST`:
```python
elif path == "/ttools/shield/analyze":
    data = json.loads(body) if body else {}
    self._json(_tshield.analyze(data.get("source")))
elif path == "/ttools/shield/record":
    data = json.loads(body)
    _tshield.record(data["source"], data.get("method", "GET"), data.get("path", "/"), data.get("size", 0))
    self._json({"ok": True})
```

**Step 3: Verify**

```bash
# Record some traffic
curl -s -X POST http://localhost:9894/ttools/shield/record \
  -H "Content-Type: application/json" \
  -d '{"source": "192.168.1.1", "method": "GET", "path": "/api/query", "size": 1024}'

curl -s -X POST http://localhost:9894/ttools/shield/analyze \
  -H "Content-Type: application/json" \
  -d '{"source": "192.168.1.1"}'
# Expected: {"192.168.1.1": {"reynolds": ..., "regime": "laminar", "risk": "none", ...}}
```

---

## Task 6: Hivemind Integration — TSpeak in Deliberation

**Files:**
- Modify: `C:\NovaX\nova_hivemind.py:2700-2760` — cluster_query deliberation phases

**Step 1: Add TSpeak encoding after scatter phase**

In `cluster_query()`, after line 2705 (`ok_responses = ...`), add TSpeak encoding step:

```python
# Phase 1.5: TSpeak Encode (if TSpeak available)
tspeak_encoded = False
tspeak_stats = {}
try:
    tspeak_data = json.dumps({
        "responses": [{"model": r.get("model", "unknown"),
                       "text": r.get("result", {}).get("response", "")[:500],
                       "score": r.get("score", 0.5)}
                      for r in ok_responses[:20]],
        "channel": channel,
        "reynolds": re_num,
    }).encode()
    req = urllib.request.Request("http://localhost:9895/tspeak/deliberate",
                                 tspeak_data, {"Content-Type": "application/json"})
    resp = urllib.request.urlopen(req, timeout=15)
    tspeak_result = json.loads(resp.read())
    if tspeak_result.get("ok"):
        tspeak_encoded = True
        tspeak_stats = {
            "regime": tspeak_result.get("regime"),
            "rounds": tspeak_result.get("rounds"),
            "compression_ratio": tspeak_result.get("compression_ratio"),
        }
except Exception:
    pass  # TSpeak not available, continue with standard deliberation
```

**Step 2: Add TSpeak stats to response metadata**

In the return dict (around line 2760+), add:
```python
"tspeak": tspeak_stats if tspeak_encoded else None,
```

**Step 3: Verify**

```bash
curl -s -X POST http://localhost:9881/hive/cluster/query \
  -H "Content-Type: application/json" \
  -d '{"prompt": "What causes ocean acidification?", "channel": "REASON"}'
# Expected: Response includes "tspeak": {"regime": "...", "rounds": N, "compression_ratio": "..."} in metadata
```

---

## Task 7: Service Evolution — Cloud Router TZip

**Files:**
- Modify: `C:\NovaX\nova_cloud_router.py:1-6` — add tzip import

**Step 1: Add TZip import to cloud router**

At top of `nova_cloud_router.py`, add:
```python
import sys; sys.path.insert(0, r"C:\NovaX")
from core.tzip import tzip_compress, tzip_decompress, tzip_ratio
```

This enables future TZip compression of cloud API payloads. The actual payload compression can be enabled per-provider later (Phase 11.1) since it requires provider-specific handling.

**Step 2: Verify cloud router still starts**

```bash
curl -s http://localhost:9878/health
# Expected: {"ok": true}
```

---

## Task 8: Wiring — Orchestrator, NovaLang, Desktop, Sentinel

**Files:**
- Modify: `C:\NovaX\core\orchestrator.py` — add TSpeak proxy routes (~40 lines, insert after TTools routes at line ~2340)
- Modify: `C:\NovaX\novalang.py` — add TSpeak builtins (~40 lines)
- Modify: `C:\NovaX\web\nova_desktop.html` — add TSpeak panel (~80 lines)
- Modify: `C:\NovaX\nova_sentinel.py:29` — add tspeak entry
- Modify: launch.json (both copies) — add nova-tspeak entry

### Step 1: Orchestrator proxy routes

After the TTools proxy routes (~line 2340), add:

```python
# ── TSpeak proxy (port 9895) ──
TSPEAK_URL = "http://localhost:9895"

@app.get("/api/tspeak/status")
def route_tspeak_status():
    return jsonify(_proxy_get(f"{TSPEAK_URL}/tspeak/status"))

@app.get("/api/tspeak/health")
def route_tspeak_health():
    return jsonify(_proxy_get(f"{TSPEAK_URL}/health"))

@app.post("/api/tspeak/encode")
def route_tspeak_encode():
    return jsonify(_proxy_post_json(f"{TSPEAK_URL}/tspeak/encode", request.get_json(force=True), timeout=30))

@app.post("/api/tspeak/decode")
def route_tspeak_decode():
    return jsonify(_proxy_post_json(f"{TSPEAK_URL}/tspeak/decode", request.get_json(force=True), timeout=30))

@app.post("/api/tspeak/deliberate")
def route_tspeak_deliberate():
    return jsonify(_proxy_post_json(f"{TSPEAK_URL}/tspeak/deliberate", request.get_json(force=True), timeout=60))

@app.post("/api/tspeak/classify")
def route_tspeak_classify():
    return jsonify(_proxy_post(f"{TSPEAK_URL}/tspeak/classify", request.get_json(force=True)))

@app.post("/api/tspeak/merge")
def route_tspeak_merge():
    return jsonify(_proxy_post_json(f"{TSPEAK_URL}/tspeak/merge", request.get_json(force=True), timeout=30))

@app.post("/api/tspeak/carry")
def route_tspeak_carry():
    return jsonify(_proxy_post_json(f"{TSPEAK_URL}/tspeak/carry", request.get_json(force=True), timeout=30))

# ── TTools new Layer endpoints (proxy to 9894) ──
@app.get("/api/ttools/weave/status")
def route_ttools_weave_status():
    return jsonify(_proxy_get(f"{TTOOLS_URL}/ttools/weave/status"))

@app.get("/api/ttools/forge/alerts")
def route_ttools_forge_alerts():
    return jsonify(_proxy_get(f"{TTOOLS_URL}/ttools/forge/alerts"))

@app.get("/api/ttools/timeline/status")
def route_ttools_timeline_status():
    return jsonify(_proxy_get(f"{TTOOLS_URL}/ttools/timeline/status"))

@app.get("/api/ttools/mesh/heartbeats")
def route_ttools_mesh_heartbeats():
    return jsonify(_proxy_get(f"{TTOOLS_URL}/ttools/mesh/heartbeats"))

@app.post("/api/ttools/shield/analyze")
def route_ttools_shield_analyze():
    return jsonify(_proxy_post_json(f"{TTOOLS_URL}/ttools/shield/analyze", request.get_json(force=True) or {}, timeout=30))

@app.post("/api/ttools/timeline/track")
def route_ttools_timeline_track():
    return jsonify(_proxy_post(f"{TTOOLS_URL}/ttools/timeline/track", request.get_json(force=True)))

@app.post("/api/ttools/timeline/restore")
def route_ttools_timeline_restore():
    return jsonify(_proxy_post_json(f"{TTOOLS_URL}/ttools/timeline/restore", request.get_json(force=True), timeout=60))
```

### Step 2: NovaLang builtins

In `novalang.py`, after the ttools builtins (~line 703), add:

```python
# TSpeak builtins
g.set('tspeak_encode', self._tspeak_encode)
g.set('tspeak_decode', self._tspeak_decode)
g.set('tspeak_deliberate', self._tspeak_deliberate)
g.set('tspeak_classify', self._tspeak_classify)
g.set('tspeak_merge', self._tspeak_merge)
g.set('tspeak_status', self._tspeak_status)
```

And add implementation methods (after ttools methods ~line 1300):
```python
TSPEAK_URL = "http://localhost:9895"

def _tspeak_request(self, path, data=None):
    url = f"{self.TSPEAK_URL}{path}"
    if data is not None:
        body = json.dumps(data).encode()
        req = urllib.request.Request(url, body, {"Content-Type": "application/json"})
    else:
        req = urllib.request.Request(url)
    resp = urllib.request.urlopen(req, timeout=30)
    return json.loads(resp.read())

def _tspeak_encode(self, text, channel="REASON", reynolds=100):
    return self._tspeak_request("/tspeak/encode", {"text": str(text), "channel": str(channel), "reynolds": float(reynolds)})

def _tspeak_decode(self, frame):
    return self._tspeak_request("/tspeak/decode", {"frame": str(frame)})

def _tspeak_deliberate(self, responses, channel="REASON", reynolds=100):
    return self._tspeak_request("/tspeak/deliberate", {"responses": responses, "channel": str(channel), "reynolds": float(reynolds)})

def _tspeak_classify(self, reynolds):
    return self._tspeak_request("/tspeak/classify", {"reynolds": float(reynolds)})

def _tspeak_merge(self, positions):
    return self._tspeak_request("/tspeak/merge", {"positions": positions})

def _tspeak_status(self):
    return self._tspeak_request("/tspeak/status")
```

### Step 3: Sentinel entry

In `nova_sentinel.py` at line 29 (after `ttools` entry), add:
```python
"tspeak":      {"name":"TSpeak",       "port":9895, "cmd":"python C:\\NovaX\\nova_tspeak.py"},
```

### Step 4: launch.json entries

Add to both `C:\NovaX\.claude\launch.json` and `C:\Users\Jupit\OneDrive\Documents\new openclaw clauade novax servers\.claude\launch.json`:
```json
{
  "name": "nova-tspeak",
  "runtimeExecutable": "C:\\NovaX\\ai_env\\Scripts\\python.exe",
  "runtimeArgs": ["C:\\NovaX\\launchers\\nowindow.py", "C:\\NovaX\\nova_tspeak.py"],
  "port": 9895,
  "autoPort": false
}
```

### Step 5: Desktop panel

In `nova_desktop.html`, add panel entry to PANELS array (after ttools entry):
```javascript
{id:'tspeak',icon:'\u{1F50A}',name:'TSpeak',color:'#ff6b35'},
```

Add to dispatch map:
```javascript
tspeak:loadTSpeak
```

Add `loadTSpeak` function (~80 lines):
```javascript
async function loadTSpeak(w) {
    let d = {}, h = {};
    try { d = await (await fetch(API + '/api/tspeak/status')).json(); } catch(e) {}
    try { h = await (await fetch(API + '/api/ttools/mesh/heartbeats')).json(); } catch(e) {}
    const sum = h.summary || {};
    w.innerHTML = `
    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:12px">
      <div class="stat-card"><div class="stat-val">${d.frames_encoded||0}</div><div class="stat-lbl">Encoded</div></div>
      <div class="stat-card"><div class="stat-val">${d.frames_decoded||0}</div><div class="stat-lbl">Decoded</div></div>
      <div class="stat-card"><div class="stat-val">${d.deliberations||0}</div><div class="stat-lbl">Deliberations</div></div>
      <div class="stat-card"><div class="stat-val">${d.avg_compression||'N/A'}</div><div class="stat-lbl">Compression</div></div>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:12px">
      <div class="panel-section">
        <h3 style="color:#ff6b35;margin-bottom:8px">N-S Flow Regimes</h3>
        <div style="font-size:0.85em">
          <div>Laminar (Re<27): <b>${(d.regime_distribution||{}).laminar||0}</b></div>
          <div>Transitional (27-125): <b>${(d.regime_distribution||{}).transitional||0}</b></div>
          <div>Turbulent (125-343): <b>${(d.regime_distribution||{}).turbulent||0}</b></div>
          <div>Chaotic (343+): <b>${(d.regime_distribution||{}).chaotic||0}</b></div>
        </div>
      </div>
      <div class="panel-section">
        <h3 style="color:#00ff88;margin-bottom:8px">Heartbeat Mesh</h3>
        <div style="font-size:0.85em">
          <div style="color:#00ff88">Healthy: <b>${sum.healthy||0}</b></div>
          <div style="color:#ffaa00">Degraded: <b>${sum.degraded||0}</b></div>
          <div style="color:#ff4466">Down: <b>${sum.down||0}</b></div>
        </div>
      </div>
    </div>
    <div class="panel-section">
      <h3 style="color:#ff6b35;margin-bottom:8px">Service Heartbeats</h3>
      <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));gap:4px;font-size:0.8em">
        ${Object.entries(h.services||{}).map(([k,v])=>`<div style="padding:4px 6px;border-radius:4px;background:${v.trit===1?'rgba(0,255,136,0.1)':v.trit===0?'rgba(255,170,0,0.1)':'rgba(255,68,102,0.1)'};border:1px solid ${v.trit===1?'#00ff88':v.trit===0?'#ffaa00':'#ff4466'}">${k}<br><small>${v.latency_ms}ms</small></div>`).join('')}
      </div>
    </div>`;
}
```

Add auto-refresh:
```javascript
function tspeakRefresh(){const w=document.querySelector('[data-panel="tspeak"] .win-body');if(w)loadTSpeak(w);}
```

Wire the refresh into the existing 15s interval pattern.

### Step 6: Verify all wiring

```bash
# Orchestrator proxy
curl -s http://localhost:9999/api/tspeak/status
# Expected: TSpeak stats via proxy

# New TTools layer endpoints
curl -s http://localhost:9999/api/ttools/forge/alerts
curl -s http://localhost:9999/api/ttools/mesh/heartbeats
curl -s http://localhost:9999/api/ttools/timeline/status

# Desktop panel renders
# Navigate to http://localhost:9999/nova_desktop.html -> click TSpeak panel
```

---

## Final Verification Checklist

1. `curl localhost:9895/health` — TSpeak alive
2. `POST /tspeak/encode` → 13-byte header + compressed payload
3. `POST /tspeak/decode` round-trip matches
4. `POST /tspeak/deliberate` with responses → N-S regime + merged output
5. `POST /tspeak/merge` → Japanese multiplication intersection
6. `GET /ttools/forge/alerts` — continuous monitoring of 14+ files
7. `GET /ttools/timeline/status` — file tracking active
8. `GET /ttools/mesh/heartbeats` — 13 services heartbeating
9. `POST /ttools/shield/analyze` — traffic Reynolds classification
10. `GET /ttools/weave/status` — TWeave channels
11. `POST /hive/cluster/query` → response includes `tspeak` metadata
12. Desktop: TSpeak panel shows flow regimes + heartbeat mesh
13. NovaLang: `tspeak_status()` returns stats
14. Sentinel: shows TSpeak in service list
15. All 4 TZip consumers import from `core/tzip.py` (no duplication)
