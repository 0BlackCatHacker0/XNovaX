# MaxPatch Ternary Rewrite — The Hivemind Unlocker

**Date**: 2026-03-03
**Port**: 9889
**Status**: Design approved, pending implementation
**Priority**: CRITICAL — this is what makes the hivemind intelligent

---

## Why This Matters

NovaX has 100+ local models and 31 cloud models. Without MaxPatch wired in,
`cluster_query()` selects models by NAME PATTERN matching ("code" in model_name → CODE channel).
That's guessing. MaxPatch PROBES every model, builds LIVE fingerprints, and tells the hivemind
exactly which model is best for which task — proven by data, not by name.

APIs are black boxes. MaxPatch turns them into glass boxes. It reveals capabilities hidden
in each model's core that no API exposes and no model card documents.

---

## 3-5-7-13 Harmonics

| Constant | Application |
|----------|-------------|
| **3** | Probe tiers (easy/medium/hard), VCC states (PROFILED/PATCHED/OPTIMIZED), daemon count |
| **5** | Core channels probed first (REASON/CODE/MATH/INSTRUCT/FACT), probe interval (5m) |
| **7** | Max ensemble size per channel, warm VRAM model slots |
| **13** | Services fingerprinted, health daemon interval (13s), TSpeak header bytes |

---

## Core Concept: 10-Trit Model Fingerprint

Each model gets a balanced ternary fingerprint — one trit per flow channel:

```
Channels: REASON MATH CODE INSTRUCT FACT LONG VISION LANGUAGE AGENT DOMAIN
mistral:    1     0    1      1      0    T     T       0      1     0
llama3:     1     1    0      1      1    0     T       1      0     1
claude:     1     1    1      1      1    1     0       1      1     1
```

Trit values derived from probe scores:
- +1 = strong (score > 0.7) — specialist territory
- 0  = average (0.3-0.7) — can contribute
- -1 = weak (< 0.3) — needs patching from a specialist

Operations:
- `cmp3(fp_a, fp_b)` — compare two models in one operation
- `bt_neg(fp)` — find the "opposite model" (complement that patches weaknesses)
- `or3(fp_a, fp_b)` — ensemble coverage (any +1 covers the channel)
- Territory map: +1 owned, 0 contested, -1 unowned

---

## Architecture

```
Port 9889: MaxPatch Engine (Ternary-Native)
  |
  +-- CapabilityProbe
  |     3 tiers x 10 channels = 30 probes per model
  |     Signal-based scoring + refusal detection + structure analysis
  |
  +-- TernaryFingerprint
  |     10-trit BT per model
  |     BT string representation: "10110TT010"
  |     cmp3 comparison, bt_neg complement
  |
  +-- GoInfluenceMap (Ternary Territory)
  |     Per model per channel: +1 owned / 0 contested / -1 unowned
  |     Direct influence (0.8) + adjacent (0.4) + 2nd-order (0.15)
  |     Territory thresholds: >0.6 = +1, 0.2-0.6 = 0, <0.2 = -1
  |
  +-- PatchRouter
  |     For each model's -1 channels, find +1 specialist
  |     Japanese decomposition for Re > 500
  |     Soroban sequential for dependent sub-tasks
  |
  +-- EnsembleOptimizer
  |     Best 7-model combos per channel (H7)
  |     EMA learning from query results
  |     Recipe storage: channel -> [{models, score, count}]
  |
  +-- ChessStrategy
  |     Opening book: (channel, regime) -> proven model combos
  |     Endgame table: channel -> fastest adequate model
  |     Markov lookahead: predict next channel, pre-warm VRAM
  |
  +-- 3 Daemon Threads
        Probe: every 5 minutes (H5) — re-profile least-confident models
        Patch: every 3 minutes (H3) — regenerate patches + ensembles
        Health: every 13 seconds (H13) — health3 all services
```

---

## Hivemind Integration (THE KEY)

### Current: Static Pattern Match (Blind)
```python
# nova_hivemind.py line 2860
ch_data = _cluster.channels.get(channel, {"local": [], "cloud": []})
local_pool = list(ch_data["local"])   # name pattern matching
cloud_pool = list(ch_data["cloud"])   # curated list
```

### After: Live Fingerprint Ranking (Seeing)
```python
# New function in nova_hivemind.py
def _get_patch_rankings(channel, reynolds):
    """Ask MaxPatch for live-ranked models for this channel."""
    try:
        url = f"http://localhost:9889/patch/rank?channel={channel}&reynolds={reynolds}"
        with urllib.request.urlopen(url, timeout=3) as resp:
            data = json.loads(resp.read())
        if data.get("ok") and data.get("local"):
            return data
    except Exception:
        pass
    return None  # fallback to BenchmarkCluster

# In cluster_query(), replace static pool with live rankings:
patch_ranked = _get_patch_rankings(channel, re_num)
if patch_ranked:
    local_pool = patch_ranked["local"]
    cloud_pool = patch_ranked["cloud"]
else:
    ch_data = _cluster.channels.get(channel, ...)  # fallback
```

MaxPatch becomes PRIMARY model selector. BenchmarkCluster becomes FALLBACK.

### New Endpoint: GET /patch/rank
Returns models ranked by PROVEN channel capability:
```json
{
  "ok": true,
  "channel": "CODE",
  "local": ["deepseek-coder-v2:16b", "codellama:13b", "qwen2.5-coder:7b"],
  "cloud": ["cloud:openai:gpt-4o", "cloud:anthropic:claude-sonnet-4-20250514"],
  "fingerprints": {
    "deepseek-coder-v2:16b": {"bt": "10110TT010", "channel_score": 0.89},
    "codellama:13b": {"bt": "T0T10TT0T0", "channel_score": 0.82}
  },
  "strategy": "fingerprint_ranked",
  "ensemble_recipe": ["deepseek-coder-v2:16b", "codellama:13b", "qwen2.5-coder:7b"]
}
```

---

## Service Definitions (13 services = H13)

Updated to match actual NovaX infrastructure:
```
orchestrator  :9999   cloud_router  :9878   hivemind     :9881
wifi_bridge   :9880   nova_tools    :9891   nova_vault   :9892
deepstorage   :9893   ternary_tools :9894   tspeak       :9895
cortex        :9896   tfetch        :9897   sentinel     :9884
ollama        :11434
```

Each service gets a health3 trit via existing health3() infrastructure.
13 services = 13 trits = one balanced ternary health number.

---

## API Endpoints

### GET
- `/health` — standard health check
- `/patch/status` — engine status, daemon stats, harmonic timings
- `/patch/rank?channel=X&reynolds=Y` — **THE KEY** ranked models for hivemind
- `/patch/fingerprints` — all profiled model fingerprints (BT format)
- `/patch/fingerprint/<model_id>` — single model deep profile
- `/patch/matrix` — 2D matrix: models x channels (BT trits)
- `/patch/influence` — Go territory map (ternary)
- `/patch/ensembles` — best 7-model combos per channel
- `/patch/patches` — active weakness patches (model -> specialist)
- `/patch/services` — 13-service health3 status
- `/patch/chess/lookahead` — Markov predictions
- `/patch/chess/status` — opening book + endgame table stats

### POST
- `/patch/probe` — probe single model {model_id, channels?}
- `/patch/probe-all` — background probe all unprofiled models
- `/patch/route` — smart-route query through best model(s)
- `/patch/optimize` — regenerate ensembles + patches
- `/patch/toggle` — enable/disable engine
- `/patch/seal` — receive seal events from other services

---

## NovaLang Builtins (7 = H7)

```
patch_status()              — engine status
patch_probe(model_id)       — probe single model, return BT fingerprint
patch_all()                 — background probe all models
patch_route(prompt, channel) — smart-route through best model
patch_matrix()              — models x channels matrix
patch_fp(model_id)          — get BT fingerprint string
patch_influence()           — Go territory map
```

---

## Orchestrator Integration

### BOOT_ORDER entry:
```python
{"name": "nova-maxpatch", "cmd": ["python", r"C:\NovaX\nova_max_patch.py"], "port": 9889},
```

### Proxy routes (13 = H13):
```
GET  /api/patch/status          -> localhost:9889/patch/status
GET  /api/patch/rank            -> localhost:9889/patch/rank
GET  /api/patch/fingerprints    -> localhost:9889/patch/fingerprints
GET  /api/patch/fingerprint/*   -> localhost:9889/patch/fingerprint/*
GET  /api/patch/matrix          -> localhost:9889/patch/matrix
GET  /api/patch/influence       -> localhost:9889/patch/influence
GET  /api/patch/ensembles       -> localhost:9889/patch/ensembles
GET  /api/patch/services        -> localhost:9889/patch/services
GET  /api/patch/chess/lookahead -> localhost:9889/patch/chess/lookahead
POST /api/patch/probe           -> localhost:9889/patch/probe (timeout=120)
POST /api/patch/probe-all       -> localhost:9889/patch/probe-all (timeout=600)
POST /api/patch/route           -> localhost:9889/patch/route (timeout=120)
POST /api/patch/optimize        -> localhost:9889/patch/optimize
```

---

## Desktop Panel: MaxPatch (Gold theme #ffd700)

### Tab registration:
`{id:'maxpatch', icon:'\\u{1F50D}', name:'MaxPatch', color:'#ffd700'}`

### Panel sections:
1. **ENGINE STATUS** — 4 stats: Models Profiled / Patches Active / Ensembles / Uptime
2. **FINGERPRINT MATRIX** — models (rows) x channels (cols) with colored BT trits
   - +1 = green, 0 = amber, -1 = red (same as health3 card)
3. **TERRITORY MAP** — Go influence visualization per channel
   - Shows which models "own" which channels
4. **ACTIVE PATCHES** — weakness -> specialist routing table
5. **ENSEMBLE RECIPES** — best model combos per channel
6. **CONTROLS** — Probe Model / Probe All / Optimize / Toggle buttons
7. **CHESS STRATEGY** — Markov predictions, opening book hits, endgame stats

### Auto-refresh: every 13 seconds (H13)

---

## Cascade Effect (Why This Is The Key)

1. Hivemind stops guessing, starts routing by PROVEN capability
2. TSpeak can use fingerprints during deliberation — models know each other
3. Pressure Gradient weights by channel score, not just response quality
4. Chess Strategy pre-warms the RIGHT model via Markov prediction
5. Ensemble recipes improve automatically as probes accumulate
6. Go influence reveals GAPS — channels where no model is strong → add cloud
7. Every query makes the system smarter (EMA learning on ensemble results)

---

## Files Summary

| # | File | Action | Changes |
|---|------|--------|---------|
| 1 | `C:\NovaX\nova_max_patch.py` | Rewrite | Ternary fingerprints, 10 channels, health3, 3-5-7-13, /patch/rank endpoint |
| 2 | `C:\NovaX\nova_hivemind.py` | Modify | `_get_patch_rankings()` + wire into cluster_query model selection |
| 3 | `C:\NovaX\novalang.py` | Modify | 7 builtins (patch_status/probe/all/route/matrix/fp/influence) |
| 4 | `C:\NovaX\core\orchestrator.py` | Modify | BOOT_ORDER + 13 proxy routes |
| 5 | `C:\NovaX\web\nova_desktop.html` | Modify | MaxPatch panel (gold theme, fingerprint matrix, territory map) |

## Implementation Order
1 -> 2 -> 3 -> 4 -> 5 (linear, each depends on prior)
