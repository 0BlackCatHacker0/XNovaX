# MaxPatch Ternary Rewrite — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rewrite MaxPatch with ternary-native model fingerprints and wire it as the hivemind's primary model selector.

**Architecture:** MaxPatch (port 9889) probes models across 10 flow channels with 3-tier difficulty,
builds 10-trit balanced ternary fingerprints, and provides live-ranked model lists to cluster_query()
via a new /patch/rank endpoint. BenchmarkCluster becomes the fallback.

**Tech Stack:** Python 3 (http.server, ThreadPoolExecutor), balanced ternary arithmetic,
NovaLang builtins, Flask orchestrator proxy routes, cyberpunk desktop JS panel.

---

### Task 1: Rewrite nova_max_patch.py — Constants & TernaryFingerprint

**Files:**
- Rewrite: `C:\NovaX\nova_max_patch.py` (keep port 9889, replace lines 1-99)

**Step 1: Replace constants section with 3-5-7-13 harmonics and 10 channels**

Replace lines 1-42 with:
```python
#!/usr/bin/env python3
"""NovaX Ternary MaxPatch — Port 9889
Probes every model across 10 flow channels, builds 10-trit balanced ternary
fingerprints, routes queries to proven specialists. The hivemind's eyes.
"""

import json, time, threading, uuid, urllib.request, urllib.error, math, statistics, socket
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from collections import deque, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── 3-5-7-13 Harmonic Constants ──────────────────────────────────────
PORT = 9889
H3, H5, H7, H13 = 3, 5, 7, 13
BLOCK_SIZE = 3 ** 7  # 2187

# Reynolds flow boundaries (cubes of harmonics)
RE_LAMINAR   = H3 ** 3   # 27
RE_TRANSIT   = H5 ** 3   # 125
RE_TURBULENT = H7 ** 3   # 343

# Daemon intervals (harmonics in seconds)
PROBE_INTERVAL  = H5 * 60   # 300s = 5 minutes
PATCH_INTERVAL  = H3 * 60   # 180s = 3 minutes
HEALTH_INTERVAL = H13       # 13 seconds

# Upstream service URLs
HIVE_URL    = "http://localhost:9881"
OLLAMA_URL  = "http://localhost:11434"
CLOUD_URL   = "http://localhost:9878"

# 10 flow channels — aligned with hivemind FLOW_CHANNELS
CHANNELS = [
    "REASON", "MATH", "CODE", "INSTRUCT", "FACT",
    "LONG", "VISION", "LANGUAGE", "AGENT", "DOMAIN",
]

# 13 NovaX services (H13)
SERVICE_PORTS = {
    "orchestrator":  9999, "cloud_router": 9878, "hivemind":      9881,
    "wifi_bridge":   9880, "nova_tools":   9891, "nova_vault":    9892,
    "deepstorage":   9893, "ternary_tools":9894, "tspeak":        9895,
    "cortex":        9896, "tfetch":       9897, "sentinel":      9884,
    "ollama":       11434,
}

CONFIDENCE_WORDS = {
    "because", "therefore", "specifically", "evidence", "step",
    "first", "second", "third", "proof", "thus", "result",
    "conclude", "demonstrate", "verify", "analysis", "hence",
}

REFUSAL_SIGNALS = [
    "i cannot", "i can't", "i'm unable", "as an ai", "i don't have",
    "not able to", "sorry, but", "i apologize",
]
```

**Step 2: Replace ModelFingerprint with TernaryFingerprint**

Replace lines 44-98 (ModelFingerprint class) with:
```python
# ── TernaryFingerprint ─────────────────────────────────────────────────

def _score_to_trit(score):
    """Convert 0.0-1.0 float score to balanced ternary trit."""
    if score >= 0.7: return 1    # strong — specialist
    if score >= 0.3: return 0    # average — can contribute
    return -1                     # weak — needs patching

def _trit_to_char(t):
    """Trit to display char: 1='+', 0='0', -1='T'"""
    if t == 1: return '1'
    if t == 0: return '0'
    return 'T'

def _bt_string(trits):
    """List of trits to balanced ternary string."""
    return ''.join(_trit_to_char(t) for t in trits)

def _bt_neg(bt_str):
    """Negate BT string — flip all trits (free in balanced ternary)."""
    m = {'1': 'T', '0': '0', 'T': '1'}
    return ''.join(m.get(c, c) for c in bt_str)

def _bt_cmp3(a_str, b_str):
    """Compare two BT fingerprints: +1 if a stronger, 0 if equal, -1 if b stronger."""
    a_val = sum(({'1':1,'0':0,'T':-1}.get(c,0)) * (3**i) for i,c in enumerate(reversed(a_str)))
    b_val = sum(({'1':1,'0':0,'T':-1}.get(c,0)) * (3**i) for i,c in enumerate(reversed(b_str)))
    if a_val > b_val: return 1
    if a_val < b_val: return -1
    return 0


@dataclass
class TernaryFingerprint:
    """10-trit balanced ternary model fingerprint — one trit per flow channel."""
    model_id: str
    is_cloud: bool = False
    # Raw float scores (from probing) — kept for ranking precision
    channel_scores: Dict[str, float] = field(default_factory=lambda: {ch: 0.0 for ch in CHANNELS})
    channel_confidence: Dict[str, int] = field(default_factory=lambda: {ch: 0 for ch in CHANNELS})
    # Balanced ternary fingerprint (derived from scores)
    bt_fingerprint: str = "0000000000"  # 10 trits, one per channel
    # Ternary territory: +1 owned, 0 contested, -1 unowned
    territory: Dict[str, int] = field(default_factory=lambda: {ch: 0 for ch in CHANNELS})
    strengths: List[str] = field(default_factory=list)     # channels with +1
    weaknesses: List[str] = field(default_factory=list)    # channels with -1
    limits: Dict = field(default_factory=lambda: {
        "max_context_tokens": 0, "avg_tokens_per_sec": 0.0,
        "failure_modes": [], "reasoning_depth": 0, "instruction_complexity": 0,
    })
    ensemble_partners: Dict[str, List[str]] = field(default_factory=dict)
    probed_at: float = 0.0
    probe_count: int = 0
    vcc_state: str = "DETECTED"  # DETECTED -> PROFILED -> PATCHED -> OPTIMIZED

    def update_bt(self):
        """Recompute balanced ternary fingerprint from float scores."""
        trits = [_score_to_trit(self.channel_scores.get(ch, 0.0)) for ch in CHANNELS]
        self.bt_fingerprint = _bt_string(trits)
        self.strengths = [ch for ch, t in zip(CHANNELS, trits) if t == 1]
        self.weaknesses = [ch for ch, t in zip(CHANNELS, trits) if t == -1
                          and self.channel_confidence.get(ch, 0) > 0]

    def trit_for(self, channel: str) -> int:
        """Get trit value for a specific channel."""
        idx = CHANNELS.index(channel) if channel in CHANNELS else -1
        if idx < 0 or idx >= len(self.bt_fingerprint): return 0
        return {'1': 1, '0': 0, 'T': -1}.get(self.bt_fingerprint[idx], 0)

    def overall_score(self) -> float:
        scores = [v for v in self.channel_scores.values() if v > 0]
        return round(sum(scores) / max(len(scores), 1), 3)

    def complement(self) -> str:
        """Negated fingerprint — the ideal patching partner."""
        return _bt_neg(self.bt_fingerprint)

    def to_dict(self) -> dict:
        return {
            "model_id": self.model_id, "is_cloud": self.is_cloud,
            "bt_fingerprint": self.bt_fingerprint,
            "overall_score": self.overall_score(),
            "channel_scores": {k: round(v, 3) for k, v in self.channel_scores.items()},
            "channel_confidence": self.channel_confidence,
            "territory": self.territory,
            "strengths": self.strengths, "weaknesses": self.weaknesses,
            "limits": self.limits, "ensemble_partners": self.ensemble_partners,
            "probed_at": self.probed_at, "probe_count": self.probe_count,
            "vcc_state": self.vcc_state,
        }

    def summary(self) -> dict:
        return {
            "model_id": self.model_id, "is_cloud": self.is_cloud,
            "bt": self.bt_fingerprint, "overall": self.overall_score(),
            "strengths": self.strengths, "weaknesses": self.weaknesses,
            "vcc_state": self.vcc_state, "probe_count": self.probe_count,
        }
```

---

### Task 2: Rewrite CapabilityProbe — 10 Channels Only

**Files:**
- Rewrite: `C:\NovaX\nova_max_patch.py` (replace CapabilityProbe class, lines 100-390)

**Step 1: Replace CapabilityProbe with 10-channel version**

Keep the existing PROBE_PROMPTS for the 10 real channels (REASON, MATH, CODE, INSTRUCT, FACT, CREATIVE->LONG, SCIENCE->VISION, LANGUAGE, AGENT, DOMAIN).

Remove the 15 aliased channels (SAFETY, RETRIEVAL, ROBUST, etc.) and the CHANNEL_ALIASES dict.

Keep score_response(), _query_model_direct(), probe_model(), probe_all() methods as-is BUT:
- probe_model() returns TernaryFingerprint instead of ModelFingerprint
- After scoring, call fp.update_bt() to compute the BT fingerprint
- Reduce PROBE_PROMPTS to only the 10 CHANNELS entries

---

### Task 3: Rewrite PatchRouter with Ternary Territory

**Files:**
- Rewrite: `C:\NovaX\nova_max_patch.py` (replace PatchRouter, lines 449-626)

**Step 1: Replace Go influence with ternary territory map**

`_compute_influence()` stays but the OUTPUT is quantized to trits:
- influence > 0.6 → +1 (owned territory)
- influence 0.2-0.6 → 0 (contested)
- influence < 0.2 → -1 (unowned — needs patch)

Store territory trits in each TernaryFingerprint.territory dict.

**Step 2: Patching uses trit comparison**

`generate_patches()`: for each model's -1 channels, find a model with +1 on that channel.
This is `bt_neg(weakness_model)` → find model whose fingerprint has +1 where we have T.

---

### Task 4: Add /patch/rank Endpoint — THE KEY

**Files:**
- Modify: `C:\NovaX\nova_max_patch.py` (add to PatchHandler.do_GET)

**Step 1: Add rank endpoint**

```python
elif path.startswith("/patch/rank"):
    qs = self.path.split("?")[1] if "?" in self.path else ""
    params = dict(p.split("=") for p in qs.split("&") if "=" in p)
    channel = params.get("channel", "REASON").upper()
    reynolds = float(params.get("reynolds", "0"))

    with _engine._lock:
        fps = dict(_engine.fingerprints)

    # Rank models by channel score (descending) — only profiled models
    ranked = []
    for mid, fp in fps.items():
        if fp.probe_count == 0:
            continue
        score = fp.channel_scores.get(channel, 0.0)
        trit = fp.trit_for(channel)
        ranked.append((mid, score, trit, fp.is_cloud))

    ranked.sort(key=lambda x: x[1], reverse=True)

    local_ranked = [r[0] for r in ranked if not r[3]]
    cloud_ranked = [r[0] for r in ranked if r[3]]

    # Ensemble recipe for this channel
    recipe = _engine.ensemble.get_best_ensemble(channel, H7)

    # Chess shortcut
    regime = "laminar" if reynolds < 100 else ("transitional" if reynolds < 500 else "turbulent")
    opening = _engine.chess.check_opening_book(channel, regime)

    self._json({
        "ok": True if ranked else False,
        "channel": channel,
        "reynolds": reynolds,
        "local": local_ranked[:H7],
        "cloud": cloud_ranked[:H5],
        "fingerprints": {
            mid: {"bt": fps[mid].bt_fingerprint, "channel_score": round(score, 3), "trit": trit}
            for mid, score, trit, _ in ranked[:13]
        },
        "ensemble_recipe": recipe,
        "chess_opening": opening,
        "strategy": "ternary_fingerprint_ranked",
        "total_profiled": len(ranked),
    })
```

---

### Task 5: Rewrite MaxPatchEngine with 3-5-7-13 Daemons

**Files:**
- Rewrite: `C:\NovaX\nova_max_patch.py` (replace MaxPatchEngine class)

**Step 1: Update daemon intervals to harmonic constants**

```python
threads = [
    ("probe-loop", self._probe_loop, PROBE_INTERVAL),   # 5 minutes (H5)
    ("patch-loop", self._patch_loop, PATCH_INTERVAL),    # 3 minutes (H3)
    ("health-loop", self._health_loop, HEALTH_INTERVAL), # 13 seconds (H13)
]
```

**Step 2: Replace ServiceFingerprint with health3 probing**

New `_health_loop()` method:
```python
def _health_loop(self):
    """Health3: probe 13 services, classify by response time against 343ms boundary."""
    for name, port in SERVICE_PORTS.items():
        try:
            t0 = time.time()
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2)
            s.connect(("127.0.0.1", port))
            s.close()
            ms = (time.time() - t0) * 1000
            # Ternary classification: 343ms = H7^3 boundary
            trit = 1 if ms < RE_TURBULENT else 0
        except Exception:
            trit = -1
        self._service_health[name] = trit
    bt = ''.join(_trit_to_char(self._service_health.get(n, -1))
                 for n in SERVICE_PORTS)
    self._health_bt = bt
```

**Step 3: Add ThreadingMixIn to HTTP server**

```python
class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
```

---

### Task 6: Wire Hivemind Integration

**Files:**
- Modify: `C:\NovaX\nova_hivemind.py` (~lines 2855-2910)

**Step 1: Add _get_patch_rankings() function**

After the imports / near the cluster_query method:
```python
def _get_patch_rankings(channel, reynolds):
    """Ask MaxPatch for live-ranked models for this channel.
    Returns {"local": [...], "cloud": [...]} or None for fallback."""
    try:
        url = f"http://localhost:9889/patch/rank?channel={channel}&reynolds={reynolds}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read())
        if data.get("ok") and (data.get("local") or data.get("cloud")):
            return data
    except Exception:
        pass
    return None  # fallback to BenchmarkCluster
```

**Step 2: Modify cluster_query() model selection (~line 2860)**

Replace:
```python
ch_data = _cluster.channels.get(channel, {"local": [], "cloud": []})
local_pool = list(ch_data["local"])
cloud_pool = list(ch_data["cloud"])
```

With:
```python
# Ask MaxPatch for LIVE fingerprint-ranked models (primary)
_patch_data = _get_patch_rankings(channel, re_num)
if _patch_data:
    local_pool = list(_patch_data["local"])
    cloud_pool = list(_patch_data["cloud"])
    _selection_strategy = "maxpatch_fingerprint"
else:
    # Fallback to static BenchmarkCluster (blind)
    ch_data = _cluster.channels.get(channel, {"local": [], "cloud": []})
    local_pool = list(ch_data["local"])
    cloud_pool = list(ch_data["cloud"])
    _selection_strategy = "benchmark_cluster_fallback"
```

**Step 3: Include strategy in cluster_query response**

At the return dict (~line 3027+), add:
```python
"selection_strategy": _selection_strategy,
```

---

### Task 7: Add NovaLang Builtins (7 = H7)

**Files:**
- Modify: `C:\NovaX\novalang.py`

**Step 1: Register 7 builtins (after tfetch builtins, ~line 737)**

```python
# -- MaxPatch Builtins (port 9889) -----------------------
g.set('patch_status', self._patch_status)
g.set('patch_probe', self._patch_probe)
g.set('patch_all', self._patch_all)
g.set('patch_route', self._patch_route)
g.set('patch_matrix', self._patch_matrix)
g.set('patch_fp', self._patch_fp)
g.set('patch_influence', self._patch_influence)
```

**Step 2: Implement methods (after tfetch methods, ~line 1897)**

```python
# -- MaxPatch Builtins (port 9889) -------------------------
MAXPATCH_URL = "http://localhost:9889"

def _patch_request(self, path, data=None):
    try:
        if data:
            body = json.dumps(data).encode()
            req = urllib.request.Request(f"{MAXPATCH_URL}{path}", body,
                                         {"Content-Type": "application/json"})
        else:
            req = urllib.request.Request(f"{MAXPATCH_URL}{path}")
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}

def _patch_status(self):
    return self._patch_request("/patch/status")

def _patch_probe(self, model_id, channels=None):
    d = {"model_id": str(model_id)}
    if channels: d["channels"] = channels
    return self._patch_request("/patch/probe", d)

def _patch_all(self):
    return self._patch_request("/patch/probe-all", {})

def _patch_route(self, prompt, channel="REASON"):
    return self._patch_request("/patch/route", {"prompt": str(prompt), "channel": str(channel)})

def _patch_matrix(self):
    return self._patch_request("/patch/matrix")

def _patch_fp(self, model_id):
    mid = str(model_id).replace("/", "%2F").replace(":", "%3A")
    return self._patch_request(f"/patch/fingerprint/{mid}")

def _patch_influence(self):
    return self._patch_request("/patch/influence")
```

---

### Task 8: Add Orchestrator Proxy Routes

**Files:**
- Modify: `C:\NovaX\core\orchestrator.py` (after existing /api/patch routes, ~line 3895)

**Step 1: Add missing routes for rank, influence, chess**

```python
@app.get("/api/patch/rank")
def route_patch_rank():
    qs = request.query_string.decode()
    return jsonify(_proxy_get(f"http://localhost:9889/patch/rank?{qs}"))

@app.get("/api/patch/influence")
def route_patch_influence():
    return jsonify(_proxy_get("http://localhost:9889/patch/influence"))

@app.get("/api/patch/chess/lookahead")
def route_patch_chess_lookahead():
    return jsonify(_proxy_get("http://localhost:9889/patch/chess/lookahead"))

@app.get("/api/patch/chess/status")
def route_patch_chess_status():
    return jsonify(_proxy_get("http://localhost:9889/patch/chess/status"))
```

---

### Task 9: Upgrade Desktop Panel — Ternary BT Display

**Files:**
- Modify: `C:\NovaX\web\nova_desktop.html` (loadMaxPatch function, ~line 1802-1908)

**Step 1: Replace float percentage matrix with BT trit display**

In the matrix table cell rendering (line ~1828), replace float percentage with colored trit char:
```javascript
// Old: percentage display
// New: balanced ternary trit display
const v = cs[c] || 0;
const trit = v >= 0.7 ? '+1' : (v >= 0.3 ? '0' : 'T');
const color = v >= 0.7 ? '#00ff41' : (v >= 0.3 ? '#ffcc00' : '#ff4444');
return `<td style="padding:1px;text-align:center;color:${color};font-size:9px;font-weight:bold;
  text-shadow:0 0 4px ${color};min-width:14px" title="${c}: ${trit}">${trit}</td>`;
```

**Step 2: Replace 25 channels with 10**

Replace the `chans` array (line 1817) with:
```javascript
const chans = ['REASON','MATH','CODE','INSTRUCT','FACT','LONG','VISION','LANGUAGE','AGENT','DOMAIN'];
```

**Step 3: Add BT fingerprint column to matrix**

After the Model column header, add a BT column showing the full 10-trit fingerprint string.

**Step 4: Add TERRITORY MAP section and CHESS STRATEGY section**

After the ENSEMBLES div, add:
- Territory map: fetch /api/patch/influence, display per-channel ownership
- Chess strategy: fetch /api/patch/chess/status, show opening book hits, endgame table, Markov predictions

**Step 5: Change auto-refresh to 13 seconds (H13)**

Replace `setInterval(..., 10000)` with `setInterval(..., 13000)` (line 1903).

---

### Task 10: Verify End-to-End

**Step 1: Verify MaxPatch service starts**
```
GET http://localhost:9889/health
Expected: {"status": "ok", "service": "max-patch", "port": 9889}
```

**Step 2: Verify /patch/rank returns data**
```
GET http://localhost:9889/patch/rank?channel=CODE&reynolds=150
Expected: {"ok": true, "channel": "CODE", "local": [...], "strategy": "ternary_fingerprint_ranked"}
```

**Step 3: Verify hivemind uses MaxPatch**
```
POST http://localhost:9881/hive/cluster/query {"prompt": "Write a hello world in Python"}
Response should include: "selection_strategy": "maxpatch_fingerprint"
```

**Step 4: Verify NovaLang**
```
patch_status()
Expected: returns engine status with ternary fields
```

**Step 5: Verify desktop panel shows BT trits**
Open desktop, navigate to MaxPatch panel, verify matrix shows +1/0/T instead of percentages.

---

## Implementation Order

1. Task 1+2: Constants + TernaryFingerprint + CapabilityProbe (core data model)
2. Task 3: PatchRouter with ternary territory
3. Task 4: /patch/rank endpoint (hivemind API)
4. Task 5: MaxPatchEngine with harmonic daemons
5. Task 6: Hivemind cluster_query integration (THE UNLOCK)
6. Task 7: NovaLang builtins
7. Task 8: Orchestrator routes
8. Task 9: Desktop panel upgrade
9. Task 10: End-to-end verification

Tasks 1-5 are all in nova_max_patch.py (single file rewrite).
Task 6 is the critical integration point.
Tasks 7-9 are wiring (following established patterns).
