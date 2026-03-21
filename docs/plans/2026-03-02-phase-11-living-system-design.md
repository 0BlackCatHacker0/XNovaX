# Phase 11: NovaX Becomes a Living System

**Date:** 2026-03-02
**Status:** Approved
**Scope:** 7-layer living system architecture + TSpeak ternary inter-model communication protocol + N-S flow-governed model deliberation

---

## Problem

NovaX has 19 services, 100+ local models, 10 cloud providers, and a full physics engine (N-S, Go influence, Chess lookahead, Japanese decomposition, 4-phase deliberation). But:

1. **TZip is duplicated** in 4 files (~500 lines of copy-paste)
2. **Models communicate in English** — 348 bytes per response, 102KB for 100-model deliberation
3. **Services don't breathe together** — no persistent health streams, no continuous code monitoring
4. **11 of 19 services are binary-only** — no ternary compression, no Reynolds, no channels
5. **No traffic analysis** — Reynolds classifies queries but not network patterns

## Solution

Give NovaX a body. 7 layers + a ternary communication protocol (TSpeak) where Navier-Stokes fluid dynamics govern how models talk to each other.

---

## TSpeak Protocol (centerpiece)

### Core Concept

Models don't need English to communicate. A ternary state vector captures agreement/neutrality/disagreement per topic dimension:

```
+1 = agree    (1 trit, like Morse 'E' — most common, shortest)
 0 = neutral  (2 trits)
-1 = disagree (variable length — carries compressed reason)
```

### N-S Flow Dynamics Govern Communication

| Reynolds Range | Regime | Pattern | Rounds | Size/Model |
|---|---|---|---|---|
| Re < 27 (3^3) | Laminar | Whisper: single trit vector | 1 | ~2 bytes |
| 27-125 (5^3) | Transitional | Discuss: vectors + key-facts | 2 | ~8 bytes |
| 125-343 (7^3) | Turbulent | Debate: full ternary reasoning, viscous damping | 3-5 | ~40 bytes |
| 343+ | Chaotic | Storm: Japanese decomposition, merge at intersections | variable | ~17 bytes |

### Compression

- 100-model deliberation: 102KB English -> 5KB TSpeak -> 1.7KB TZip'd (61x)
- ~24,825 context window tokens saved per deliberation

### Message Frame (13 bytes, harmonic)

```
Bytes 0-2:   "TSP" magic
Byte 3:      Version
Byte 4:      Flow regime
Bytes 5-6:   Reynolds (uint16)
Byte 7:      Channel ID (0-9)
Byte 8:      Round number
Bytes 9-10:  Payload length
Bytes 11-12: CRC-16
Payload:     TZip-compressed ternary vectors
```

### N-S Integration

- **Energy conservation:** tokens_in ~ useful_tokens_out (discard duplicates)
- **Momentum:** Previous round context alpha=0.4, new round 0.6 (context carries forward)
- **Backpressure:** Ollama overloaded -> shorter ternary bursts, fewer debate rounds
- **Viscous damping:** Smooth conflicting vote scores between rounds

### Merging Strategies

- **Japanese Multiplication:** Disagreements decomposed into independent sub-problems (lines). Models attack strongest sub-problem. Confidence multiplies at intersection points (where answers agree).
- **Soroban Carry:** Sequential chains pass only remainder (key facts, not full text). Compact, lossless, sequential.
- **Morse Principle:** Most frequent signals shortest. Agreement (80%+ of votes) = 1 trit.

---

## 7 Layers

### Layer 0: The DNA — `core/tzip.py`

Extract shared TZip module from 4 duplicated implementations. Single source of truth.

- `tzip_compress(data) -> bytes`
- `tzip_decompress(data) -> bytes`
- `TERNARY_BASE=3, PACK_FACTOR=5, COMPOSE_UNIT=7, CARRIER_FRAME=13`
- `BLOCK_SIZE=2187, BOUNDARIES=[27, 125, 343]`
- ~80 lines replacing ~500 lines of duplication

### Layer 1: TSpeak — `nova_tspeak.py` (port 9895)

New service. Ternary inter-model communication server.

Endpoints:
- POST `/tspeak/encode` — English -> TSpeak frame
- POST `/tspeak/decode` — TSpeak frame -> readable summary
- POST `/tspeak/deliberate` — N-S-governed multi-model deliberation
- POST `/tspeak/classify` — Reynolds classification for communication regime
- POST `/tspeak/merge` — Japanese multiplication merge
- POST `/tspeak/carry` — Soroban sequential carry
- GET `/tspeak/status` — Protocol stats
- GET `/health` — Standard health

### Layer 2: The Nervous System — TWeave (nova_ternary_tools.py)

TMesh upgrade: persistent compressed channels between services. Proxy calls use TWeave pipes instead of raw HTTP. ~40% bandwidth reduction.

- `weave_channel(source_port, dest_port)` — persistent compressed pipe
- `weave_send(channel_id, data)` — send through pipe
- `weave_recv(channel_id)` — receive from pipe

### Layer 3: The Immune System — TForge Live (nova_ternary_tools.py)

Continuous code health monitoring. Background thread scans 19 service files every 60s.

- `_live_monitor_loop()` — background scanner
- `/ttools/forge/alerts` — active alerts endpoint
- Sentinel consumption: alert when function Re > 343

### Layer 4: The Memory — TTimeline (nova_ternary_tools.py)

Automatic file versioning using TDiff deltas. Time-travel to any previous state.

- `timeline_snapshot(path)` — capture current state
- `timeline_restore(path, timestamp)` — restore to point in time
- Watcher thread: mtime polling every 30s
- Storage: `C:\NovaX\memory\timeline/`

### Layer 5: The Bloodstream — TStream Mesh (nova_ternary_tools.py)

All 13 services push compressed health heartbeats every 5s through TStream channels.

- `mesh_heartbeat()` — broadcast health trit
- TSpeak format: +1 healthy, 0 degraded, -1 down
- Sentinel and desktop consume the stream

### Layer 6: The Shield — TShield (nova_ternary_tools.py)

Reynolds on HTTP traffic patterns. Request rate, payload sizes, route diversity.

- POST `/ttools/shield/analyze` — classify traffic source
- Laminar = normal user, Turbulent = potential abuse, Chaotic = attack
- Sentinel feeds request logs for analysis

### Layer 7: The Evolution — Ternary-Native Services

Upgrade 3 most impactful binary-only services:
1. Cloud Router (:9878) — TZip on API payloads
2. Orchestrator (:9999) — TWeave on 158 proxy routes
3. Nexus (:9882) — TSpeak for skill chain communication

Remaining 8 get `core/tzip.py` import only.

---

## Hivemind Integration

`cluster_query()` deliberation phases with TSpeak:

1. **Scatter** — English to models (unchanged)
2. **Encode** — NEW: responses -> TSpeak ternary state vectors
3. **Pressure Gradient** — operate on TSpeak vectors (faster sorting)
4. **Deliberation Vortex** — models exchange TSpeak frames, not English
5. **Laminar Output** — decode final response back to English

Vortex phase gets 61x compression. Judge models receive TSpeak frames. Each judge votes with trit vector. Viscous damping smooths votes.

---

## Implementation Order

```
Step 1: core/tzip.py              — Shared TZip module         (~80 lines)
Step 2: nova_tspeak.py            — TSpeak protocol server     (~400 lines)
Step 3: TWeave + TForge Live      — Nervous + immune system    (~120 lines)
Step 4: TTimeline + TStream Mesh  — Memory + bloodstream       (~120 lines)
Step 5: TShield                   — Security flow analysis     (~60 lines)
Step 6: Hivemind integration      — cluster_query uses TSpeak  (~100 lines)
Step 7: Service evolution          — Cloud Router + Orch TZip   (~80 lines)
Step 8: Wiring                     — Orch, NovaLang, Desktop   (~150 lines)
```

Steps 3/4 independent. Step 6 needs Step 2. Step 7 needs Step 1.

## File Impact

| File | Action | Lines |
|---|---|---|
| `core/tzip.py` | create | ~80 |
| `nova_tspeak.py` | create | ~400 |
| `nova_ternary_tools.py` | modify | +200 |
| `nova_hivemind.py` | modify | +100 |
| `nova_cloud_router.py` | modify | +30 |
| `core/orchestrator.py` | modify | +80 |
| `novalang.py` | modify | +70 |
| `web/nova_desktop.html` | modify | +100 |
| `nova_sentinel.py` | modify | +30 |
| **Total** | | **~1,090** |

## Verification

1. `curl localhost:9895/health` — TSpeak alive
2. POST `/tspeak/encode` -> 13-byte header + payload
3. POST `/tspeak/decode` round-trip
4. POST `/tspeak/deliberate` with 5 responses -> N-S regime + merged output
5. POST `/tspeak/merge` -> Japanese multiplication intersection
6. GET `/ttools/forge/alerts` — continuous monitoring
7. GET `/ttools/timeline` — file versioning
8. POST `/ttools/shield/analyze` — traffic Reynolds
9. Hivemind cluster_query with TSpeak — verify compression
10. Desktop TSpeak panel — live flow visualization
