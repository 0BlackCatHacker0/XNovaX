# Nova Ternary Toolkit — Design Document
**Date:** 2026-03-02
**Port:** 9894
**File:** `C:\NovaX\nova_ternary_tools.py`

## The 3-5-7-13 Harmonic Constants

These four numbers define the natural resonance of a ternary computing system.
They are not arbitrary — they emerge from the mathematics of base-3 logic:

| Constant | Role | Mathematical Basis |
|----------|------|-------------------|
| **3** | Base frequency | Ternary base. Three states: -1, 0, +1 |
| **5** | First harmonic | 3^5 = 243 fits in 1 byte (256). TZip packing factor |
| **7** | Second harmonic | Tool composition unit. Tryte(6) + 1 dimension |
| **13** | Carrier wave | TZip header size. 3 + 5 + 5. The frame/envelope |

### Derived Constants (used throughout the toolkit)

```
BLOCK_SIZE    = 3^7     = 2187 bytes   (ternary-native block)
FLOW_LAMINAR  = 3^3     = 27           (Reynolds boundary)
FLOW_TRANS    = 5^3     = 125          (Reynolds boundary)
FLOW_TURB     = 7^3     = 343          (Reynolds boundary)
HEADER_SIZE   = 13      bytes          (all frame headers)
PACK_TRITS    = 5       trits/byte     (TZip packing)
MAX_PIPE      = 7       steps          (pipeline depth)
TIERS         = 3       levels         (hot/warm/cold)
HEARTBEAT     = 5       seconds        (cache/stream check interval)
TOOLS         = 7       per service    (tool count)
SERVICES      = 13      total          (microservice cap)
```

### Modulation Model

```
Signal = Frame(13) x [Ternary(3) + Pack(5) x compression + Compose(7) x pipeline]

Carrier(13)  = envelope wrapping all data (headers, framing)
Base(3)      = ternary substrate (trit states)
Harmonic1(5) = data transformation (compression, packing)
Harmonic2(7) = tool orchestration (composition, pipelines)
```

## Architecture

Single service on port 9894. Seven tools under `/ttools/*`.
Uses `http.server` pattern (same as all standalone NovaX services).

```
Port 9894: Nova Ternary Toolkit
  POST /ttools/diff         — TDiff: ternary 3-state diff
  POST /ttools/diff/apply   — Apply a ternary diff
  POST /ttools/cache/set    — TCache: store compressed value
  GET  /ttools/cache/get    — TCache: retrieve value
  GET  /ttools/cache/status — TCache: stats
  POST /ttools/sync         — TSync: ternary delta sync
  POST /ttools/index        — TIndex: index files by ternary fingerprint
  POST /ttools/search       — TIndex: three-state search
  POST /ttools/mesh         — TMesh: compressed service relay
  POST /ttools/stream/start — TStream: start compressed stream
  POST /ttools/stream/write — TStream: write to stream
  GET  /ttools/stream/read  — TStream: read compressed data
  POST /ttools/forge        — TForge: Reynolds code analysis
  GET  /ttools/status       — Full toolkit status
  GET  /health              — Health check
```

## Tool Specifications

### Tool 1: TDiff — Ternary Diff Engine

Three states map to trits: +1 (added), 0 (unchanged), -1 (removed).
Unchanged bytes produce zero trits, which compress to near-nothing in TZip.

**Input:** `{old: "path_or_data", new: "path_or_data"}`
**Output:** `{diff_tzip: <base64>, changed_pct, added, removed, unchanged, reynolds}`

**Apply:** `{diff_tzip: <base64>, target: "path_or_data"}` -> reconstructed data

Key insight: A 5% change produces a diff ~5% of file size.
100 versions of 100KB file = 100KB + 100 x 5KB diffs = 600KB (vs 10MB raw).

### Tool 2: TCache — Ternary In-Memory Cache

All values TZip-compressed in RAM. Three-tier eviction:
- +1 (hot): recently accessed, decompressed on read
- 0 (warm): not recent, still cached compressed
- -1 (cold): eviction candidate

**Params:**
- HEARTBEAT: 5 seconds (check interval)
- TIERS: 3 (hot/warm/cold)
- Block unit: 2187 bytes (3^7)

Shared across all services via orchestrator proxy.

### Tool 3: TSync — Ternary Delta Sync

Uses TDiff internally. Maintains file manifest (hash + timestamp).
Only transfers ternary deltas for changed files.

**Input:** `{source: "dir", target: "dir", mode: "push|pull|mirror"}`
**Output:** `{synced, skipped, delta_bytes, full_equivalent, ratio}`

### Tool 4: TIndex — Ternary Search Index

Three-state matching: +1 (exact), 0 (partial >50% trit alignment), -1 (miss).
Indexes files by ternary fingerprint (TZip first 2187 bytes, hash trit pattern).

**Index:** `{path: "dir"}` -> indexes all files
**Search:** `{query: "text", type: "content|structure"}` -> ranked results with ternary similarity score

### Tool 5: TMesh — Ternary Service Mesh

Transparent TZip compression for inter-service calls.
Route through TMesh instead of direct HTTP.

**Input:** `{service: "hivemind", port: 9881, path: "/endpoint", body: {}}`
**Output:** `{response, request_bytes, raw_bytes, savings_pct}`

### Tool 6: TStream — Ternary Streaming

Real-time TZip-compressed data streams with 5-second flush interval.

**Start:** `{name: "stream_id", buffer: 1000}`
**Write:** `{stream: "id", data: "..."}`
**Read:** `{stream: "id"}` -> compressed chunks

### Tool 7: TForge — Reynolds Code Analyzer

Applies N-S fluid dynamics to source code. Per-function Reynolds analysis.
Uses harmonic boundaries: laminar <27, transitional 27-125, turbulent 125-343, chaotic >343.

**Input:** `{path: "file.py"}`
**Output:** `{reynolds, flow, hotspots: [{line, re, issue}], compression_potential, hints}`

## Integration Points

1. **Orchestrator:** 15+ proxy routes under `/api/ttools/*`
2. **NovaLang:** 10 builtins (tdiff, tcache_set, tcache_get, tsync, tindex, tsearch, tmesh, tstream, tforge, ttools_status)
3. **Sentinel:** watchdog entry for port 9894
4. **launch.json:** service entry with nowindow.py wrapper
5. **Desktop:** "Ternary Tools" panel

## Efficiency Projections

| Metric | Before | After | Source |
|--------|--------|-------|--------|
| Storage (versioned) | 1x | 16x | TDiff: base + diffs vs full copies |
| Storage (whole drive) | 2.5x | 3-5x | DeepStorage + TDiff + dedup |
| Cache RAM usage | 100% | ~50% | TCache: compressed in memory |
| Inter-service bandwidth | 100% | ~50% | TMesh: all calls compressed |
| AI query latency (cached) | 500-2000ms | 0ms | TCache: instant hits |
| Search quality | binary (yes/no) | ternary (yes/partial/no) | TIndex: fuzzy native |
| Pipeline depth | unlimited | 7 max | Harmonic-aligned composition |
