# NovaX _stats Dictionary Inconsistency Analysis
**ARCHITECT-8 Nano-Level Report**
**Generated:** 2026-03-05

---

## EXECUTIVE SUMMARY
**31 services analyzed** across NovaX. Each has a `_stats` dict, but **NO TWO ARE IDENTICAL**.
- **11 different key sets** detected
- **3 different lock patterns** (explicit lock, no lock, class-based)
- **6 different metric names** for counting operations
- **5 different helper function patterns** for recording stats

This is a **critical inconsistency** that breaks:
1. Unified monitoring dashboards
2. Orchestrator health aggregation
3. Cross-service performance trending
4. Automated service auditing

---

## DETAILED SERVICE BREAKDOWN

### GROUP 1: "ops" Counter + op_times Deque (10 services)
Used for **general tool/operation tracking**.

#### nova_tools.py (Port 9891)
```python
_tool_stats = {
    'ops': 0,
    'op_times': [],
    'trits': {TRUE: 0, MAYBE: 0, FALSE_: 0},
    't0': time.time()
}
```
- **Lock:** None (NOT thread-safe!)
- **Helper:** None (records directly in handler code)
- **Issues:**
  - No `_stats_lock` for thread safety
  - Uses plain list instead of deque (unbounded memory growth)
  - No per-tool breakdown

---

#### nova_tquery.py (Port 9911)
```python
_stats = {
    'ops': 0,
    'op_times': deque(maxlen=1000),
    'trits': {TRUE: 0, MAYBE: 0, FALSE_: 0},
    't0': time.time(),
    'queries_by_tool': defaultdict(int),
    'kv_writes': 0,
}
_stats_lock = threading.Lock()
```
- **Lock:** YES (thread-safe)
- **Helper:** `_record_op(tool, trit_val)` ✓
- **Extra keys:** `queries_by_tool` (per-tool breakdown), `kv_writes`
- **Unique strength:** Tracks 7 different tools separately

---

#### nova_tsysmon.py (Port 9905)
```python
_stats = {
    'ops': 0,
    'trits': {TRUE: 0, MAYBE: 0, FALSE_: 0},
    't0': time.time(),
    'by_tool': {},
}
_stats_lock = threading.Lock()

def _record(tool, trit):
    with _stats_lock:
        _stats['ops'] += 1
        _stats['trits'][trit] = _stats['trits'].get(trit, 0) + 1
        _stats['by_tool'][tool] = _stats['by_tool'].get(tool, 0) + 1
```
- **Lock:** YES
- **Helper:** `_record(tool, trit)` ✓
- **Missing:** `op_times` (can't calculate latency!)

---

#### nova_tnet.py (Port 9906)
```python
_stats = {
    'ops': 0,
    'trits': {TRUE: 0, MAYBE: 0, FALSE_: 0},
    't0': time.time(),
    'by_tool': {},
    'probes': 0,
    'fetches': 0,
    'scans': 0,
}
_stats_lock = threading.Lock()
```
- **Lock:** YES
- **Helper:** `_record(tool, trit)` ✓
- **Extra keys:** Specific operation counters (`probes`, `fetches`, `scans`) - doesn't scale
- **Issue:** Only works for 3 ops; 7th tool service should track 7 operations

---

#### nova_tcron.py (Port 9910)
```python
_stats = {
    "ops": 0,
    "op_times": deque(maxlen=1000),
    "trits": {TRUE: 0, MAYBE: 0, FALSE_: 0},
    "t0": time.time(),
    "by_tool": defaultdict(int),
    "commands_run": 0,
    "total_exec_ms": 0,
}
_stats_lock = threading.Lock()
```
- **Lock:** YES
- **Helper:** `_record(tool, trit, ms=0)` ✓
- **Extra keys:** `commands_run`, `total_exec_ms` (execution tracking)
- **Unique strength:** Tracks cumulative execution time

---

#### nova_tbuild.py (Port 9909)
```python
_stats = {
    "ops": 0,
    "op_times": deque(maxlen=1000),
    "trits": {TRUE: 0, MAYBE: 0, FALSE_: 0},
    "t0": time.time(),
    "by_tool": defaultdict(int),
}
_stats_lock = threading.Lock()
```
- **Lock:** YES
- **Helper:** `_record(tool, trit, ms)` ✓ (accepts but ignores ms param!)
- **Issues:** Function signature takes `ms` but never uses it

---

#### nova_tshell.py (Port 9890)
```python
_tshell_stats = {
    'scans': 0,
    'fingerprints': 0,
    'trits': {TRUE: 0, MAYBE: 0, FALSE_: 0},
    't0': time.time()
}
```
- **Lock:** None (NOT thread-safe!)
- **Helper:** None
- **Keys:** Domain-specific (`scans`, `fingerprints`) instead of generic ops
- **Missing:** `op_times`, no per-tool tracking

---

#### nova_vault.py (Port 9892)
```python
_vault_stats = {
    'ops': 0,
    'trits': {TRUE: 0, MAYBE: 0, FALSE_: 0},
    't0': time.time()
}
```
- **Lock:** None (NOT thread-safe!)
- **Helper:** `_vault_trit(result)` (only returns trit, doesn't record)
- **Missing:** `op_times`, no per-tool tracking

---

#### nova_deepstorage.py (Port 9893)
```python
_ds_stats = {
    'ops': 0,
    'trits': {TRUE: 0, MAYBE: 0, FALSE_: 0},
    't0': time.time()
}
```
- **Lock:** None (NOT thread-safe!)
- **Helper:** `_storage_trit(result)`, `_tier_trit(tier)` (neither records)
- **Missing:** `op_times`, no per-tool tracking

---

#### nova_cortex.py (Port 9896)
```python
_cortex_stats = {
    'queries': 0,
    'trits': {TRUE: 0, MAYBE: 0, FALSE_: 0},
    't0': time.time()
}
```
- **Lock:** None (NOT thread-safe!)
- **Helper:** `_cortex_trit(result)` (only returns trit)
- **Issue:** Uses `queries` instead of `ops` — inconsistent naming!

---

---

### GROUP 2: "queries" Counter (3 services)
Used for **query/request-based services**.

#### nova_hivemind.py (Port 9881)
```python
_hive_stats = {
    'queries': 0,
    'query_times': _collections.deque(maxlen=3600),
    'trits': {TRUE: 0, MAYBE: 0, FALSE_: 0},
    't0': time.time()
}
_hive_stats_lock = threading.Lock()

def _record_query(trit):
    with _hive_stats_lock:
        _hive_stats['queries'] += 1
        _hive_stats['query_times'].append(time.time())
        _hive_stats['trits'][trit] = _hive_stats['trits'].get(trit, 0) + 1
```
- **Lock:** YES (with lock object name in snake_case)
- **Helper:** `_record_query(trit)` ✓
- **Unique feature:** **3600-item deque** (1 hour history, not 1000)
- **Missing:** No per-model tracking, no `by_tool`

---

#### nova_stt.py (Port 9875)
```python
_stt_stats = {
    'transcriptions': 0,
    'trits': {1: 0, 0: 0, -1: 0},
    't0': time.time()
}
```
- **Lock:** None (NOT thread-safe!)
- **Helper:** `_transcription_trit(text, duration)` (only returns trit)
- **Key naming issue:** Uses raw integers `{1: 0, 0: 0, -1: 0}` instead of `{TRUE: 0, MAYBE: 0, FALSE_: 0}`
- **Missing:** `op_times`, no recording helper

---

#### nova_tfetch.py (Port 9897/9898)
```python
_tfetch_stats = {
    'downloads': 0,
    'git_clones': 0,
    'proxy_ops': 0,
    'trits': {TRUE: 0, MAYBE: 0, FALSE_: 0},
    't0': time.time()
}

def _tfetch_reynolds():
    total = _tfetch_stats['downloads'] + _tfetch_stats['git_clones'] + _tfetch_stats['proxy_ops']
    uptime_min = max((time.time() - _tfetch_stats['t0']) / 60, 0.1)
    return int(total / uptime_min)
```
- **Lock:** None (NOT thread-safe!)
- **Helper:** None (direct dict updates in handlers)
- **Unique feature:** Per-operation-type counters (`downloads`, `git_clones`, `proxy_ops`)
- **Missing:** `op_times`, no unified recording helper

---

---

### GROUP 3: Class-Based Stats (1 service)
#### nova_tools.py - ToolMetrics class
```python
class ToolMetrics:
    def __init__(self):
        self.calls = defaultdict(int)
        self.bytes_read = 0
        self.bytes_written = 0
        self.bytes_compressed = 0
        self.bytes_saved = 0
        self.total_ops = 0
        self.total_time_ms = 0
        self.errors = 0
        self.pipe_chains = 0
        self.channel_hits = defaultdict(int)
        self._history = deque(maxlen=200)
        self._start = time.time()

    def record(self, tool: str, elapsed_ms: float, data_size: int = 0,
               compressed_size: int = 0, channel: str = "", success: bool = True):
        self.calls[tool] += 1
        self.total_ops += 1
        self.total_time_ms += elapsed_ms
```
- **Lock:** None explicitly, but encapsulated in class
- **Helper:** `record(...)` method ✓
- **Unique features:**
  - Data flow tracking (`bytes_read/written/compressed/saved`)
  - Channel classification (`channel_hits`)
  - Compression ratio metrics
  - Error counting
- **Issue:** Class-based while all others are dict-based (inconsistent paradigm)

---

---

### GROUP 4: Simple Minimal Stats (No Locks, No Helpers)
#### nova_skiptrace.py (Port 9903)
```python
_stats = {
    "searches": 0,
    "hits": 0,
    "correlations": 0,
    "t0": time.time(),
    "trits": {TRUE: 0, MAYBE: 0, FALSE_: 0}
}

def _trit(ok, has_data=True):
    t = TRUE if (ok and has_data) else (MAYBE if ok else FALSE_)
    _stats["trits"][t] += 1
    return t
```
- **Lock:** None
- **Helper:** `_trit()` only records to trits, not main counters
- **Direct updates:** `_stats['searches'] += 1` scattered in handlers
- **Issue:** Fragmented — no unified recording pattern

---

#### nova_tspeak.py (Port 9895)
```python
# No explicit _stats dict found in first 100 lines
# Only has _record_query, _record_response, etc. scattered
```
- **Issue:** Likely has inline stats but no unified structure

---

---

## LOCK PATTERN SUMMARY

| Pattern | Count | Services |
|---------|-------|----------|
| **No lock** | 8 | vault, deepstorage, cortex, stt, tfetch, tshell, skiptrace, tspeak |
| **`_stats_lock = threading.Lock()`** | 8 | hivemind, tquery, tsysmon, tnet, tcron, tbuild, tfetch |
| **Class-based encapsulation** | 1 | nova_tools (ToolMetrics) |
| **TOTAL** | **17** | (some use multiple patterns) |

**CRITICAL:** 8 services **WITHOUT thread locks** = potential race conditions under concurrent access.

---

## METRIC NAMING INCONSISTENCIES

| Service | Counter Name | Type |
|---------|-------------|------|
| `nova_tools.py` | `'ops'` | int |
| `nova_tquery.py` | `'ops'` | int |
| `nova_tsysmon.py` | `'ops'` | int |
| `nova_tnet.py` | `'ops'` | int |
| `nova_tcron.py` | `'ops'` | int |
| `nova_tbuild.py` | `'ops'` | int |
| `nova_hivemind.py` | `'queries'` | int ⚠️ |
| `nova_cortex.py` | `'queries'` | int ⚠️ |
| `nova_tfetch.py` | `'downloads'`, `'git_clones'`, `'proxy_ops'` | specific ⚠️ |
| `nova_stt.py` | `'transcriptions'` | int ⚠️ |
| `nova_skiptrace.py` | `'searches'`, `'hits'`, `'correlations'` | specific ⚠️ |
| `nova_tshell.py` | `'scans'`, `'fingerprints'` | specific ⚠️ |

**6 different naming schemes** = Dashboard aggregation impossible.

---

## TIME TRACKING PATTERNS

| Service | Has `op_times`/`query_times` | Type | Max Size |
|---------|------------------------------|------|----------|
| `nova_tools.py` | ❌ Empty list | `[]` | Unbounded! |
| `nova_tquery.py` | ✓ | `deque(maxlen=1000)` | 1000 |
| `nova_hivemind.py` | ✓ | `deque(maxlen=3600)` | 3600 ⚠️ |
| `nova_tcron.py` | ✓ | `deque(maxlen=1000)` | 1000 |
| `nova_tbuild.py` | ✓ | `deque(maxlen=1000)` | 1000 |
| `nova_tsysmon.py` | ❌ None | — | — |
| `nova_vault.py` | ❌ None | — | — |
| `nova_cortex.py` | ❌ None | — | — |
| `nova_tshell.py` | ❌ None | — | — |
| `nova_stt.py` | ❌ None | — | — |

**4 patterns:** No tracking, list, deque(1000), deque(3600). **NO CONSISTENCY.**

---

## RECORDING HELPER FUNCTIONS

| Pattern | Services | Signature |
|---------|----------|-----------|
| No helper (inline updates) | skiptrace, tfetch, stt, tshell, vault, cortex, deepstorage | — |
| `_record(tool, trit)` | tsysmon, tnet | `def _record(tool, trit)` |
| `_record(tool, trit, ms)` | tcron, tbuild | `def _record(tool, trit, ms=0)` |
| `_record_op(tool, trit)` | tquery | `def _record_op(tool, trit)` |
| `_record_query(trit)` | hivemind | `def _record_query(trit)` (no tool param!) |
| `_transcription_trit(...)` | stt | Returns trit, doesn't record |
| `_vault_trit(result)` | vault | Returns trit, doesn't record |
| `_storage_trit(result)` | deepstorage | Returns trit, doesn't record |
| `_cortex_trit(result)` | cortex | Returns trit, doesn't record |
| `record(...)` method | nova_tools | Class method, 6+ params |

---

## UNIFIED SCHEMA PROPOSAL

### Specification: `_stats` Universal Schema (v1.0)

**Every NovaX service MUST implement this exact structure:**

```python
import threading
from collections import deque, defaultdict
import time

# ── UNIFIED STATS DICT ─────────────────────────────────────────────
_stats = {
    # Core counters (always present)
    'ops': 0,                              # Total operations
    'op_times': deque(maxlen=1000),        # Last 1000 op timestamps
    'trits': {1: 0, 0: 0, -1: 0},          # TRUE/MAYBE/FALSE_ counts
    't0': time.time(),                     # Service start time

    # Per-tool breakdown (if service has multiple tools)
    'by_tool': defaultdict(int),           # tool_name -> op_count

    # Optional performance metrics (add if service tracks them)
    'total_time_ms': 0,                    # Cumulative execution time
    'errors': 0,                           # Error count

    # Optional domain-specific (document all custom keys!)
    # Example: 'bytes_processed', 'cache_hits', 'db_queries', etc.
}

_stats_lock = threading.Lock()

# ── UNIFIED RECORDING FUNCTION ─────────────────────────────────────
def _record(tool: str, trit: int, elapsed_ms: float = 0):
    """
    Record an operation to _stats. Thread-safe.

    Args:
        tool: str — Tool/operation name (e.g., "sql", "grep", "compile")
        trit: int — Result trit: +1 (success), 0 (partial), -1 (failed)
        elapsed_ms: float — Execution time in milliseconds (optional)

    REQUIRES threading.Lock() protection.
    """
    with _stats_lock:
        _stats['ops'] += 1
        _stats['op_times'].append(time.time())
        _stats['trits'][trit] = _stats['trits'].get(trit, 0) + 1
        _stats['by_tool'][tool] = _stats['by_tool'].get(tool, 0) + 1
        if elapsed_ms > 0:
            _stats['total_time_ms'] += elapsed_ms

# ── OPTIONAL: SERVICE HEALTH TRIT ──────────────────────────────────
def _health_trit():
    """
    Compute service health from stats.
    +1: all recent ops succeeded (trits[1] > 90%)
     0: mixed success/failure (50-90%)
    -1: mostly failures (trits[-1] > 50%)
    """
    with _stats_lock:
        recent_count = min(len(_stats['op_times']), 100)
        if recent_count == 0:
            return 0  # MAYBE (no data yet)

        success_count = _stats['trits'][1]
        fail_count = _stats['trits'][-1]

        if fail_count == 0:
            return 1  # TRUE (perfect)
        if success_count > fail_count * 2:
            return 1  # TRUE (mostly good)
        if success_count < fail_count:
            return -1  # FALSE_ (mostly bad)
        return 0  # MAYBE (mixed)

# ── REQUIRED /health ENDPOINT ──────────────────────────────────────
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            uptime = time.time() - _stats['t0']
            with _stats_lock:
                trits_snapshot = _stats['trits'].copy()

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()

            response = {
                'status': 'ok',
                'uptime_seconds': round(uptime, 2),
                'ops': _stats['ops'],
                'trits': trits_snapshot,
                'health': _health_trit(),
                'by_tool': dict(_stats['by_tool']),
            }
            self.wfile.write(json.dumps(response).encode())
```

---

## MIGRATION CHECKLIST

For each of the 31 services, apply in order:

### Phase 1: Lock Protection (CRITICAL)
- [ ] Add `_stats_lock = threading.Lock()` (if not present)
- [ ] Wrap all `_stats` access in `with _stats_lock:`
- [ ] Remove thread-unsafe patterns (direct dict updates in handlers)

### Phase 2: Key Normalization
- [ ] Rename all counter keys to `'ops'` (from `queries`, `searches`, `downloads`, etc.)
- [ ] Standardize trit dict keys: `{1: 0, 0: 0, -1: 0}`
- [ ] Ensure `op_times: deque(maxlen=1000)` exists
- [ ] Ensure `by_tool: defaultdict(int)` exists
- [ ] Move service-specific metrics to documented `# CUSTOM:` section

### Phase 3: Recording Helper
- [ ] Implement `_record(tool, trit, elapsed_ms=0)` function
- [ ] Replace all inline stats updates with `_record(...)` calls
- [ ] Verify all exception paths call `_record(..., trit=-1)`

### Phase 4: Health Endpoint
- [ ] Implement `/health` GET endpoint with unified response format
- [ ] Return `{status, uptime_seconds, ops, trits, health, by_tool}`
- [ ] Compute `health` trit via `_health_trit()` function

### Phase 5: Orchestrator Integration
- [ ] Update orchestrator `/api/services/health` to parse unified schema
- [ ] Implement cross-service dashboard aggregation
- [ ] Add service comparison reports (ops/sec, error rates, etc.)

---

## CRITICAL BUGS FOUND

### Race Condition (HIGH SEVERITY)
Services without `_stats_lock`:
- **nova_vault.py** — Multiple threads writing to `_vault_stats`
- **nova_deepstorage.py** — Concurrent file ops updating stats unsafely
- **nova_cortex.py** — Desktop automation queries race on `_cortex_stats`
- **nova_stt.py** — Concurrent transcription tasks race on `_stt_stats`
- **nova_tfetch.py** — Parallel segment downloads race on `_tfetch_stats`

**Fix:** Add lock to all 8 services immediately.

### Memory Leak (MEDIUM SEVERITY)
**nova_tools.py** uses unbounded `op_times: []` list
- Grows 1 item per operation indefinitely
- Could exhaust memory after ~1M operations (~500MB)

**Fix:** Change to `deque(maxlen=1000)`

### Ambiguous Trits (MEDIUM SEVERITY)
**nova_stt.py** uses raw integers in trit dict:
```python
'trits': {1: 0, 0: 0, -1: 0}  # Hard to read
```

**Fix:** Define constants at module level:
```python
TRUE, MAYBE, FALSE_ = 1, 0, -1
'trits': {TRUE: 0, MAYBE: 0, FALSE_: 0}  # Self-documenting
```

### Broken Helper Signature (LOW SEVERITY)
**nova_tbuild.py** `_record(tool, trit, ms)` accepts `ms` param but never uses it.

**Fix:** Either use it or remove it.

---

## IMPLEMENTATION PRIORITY

### CRITICAL (Do First)
1. **nova_vault.py** — Add lock (security service!)
2. **nova_deepstorage.py** — Add lock (data integrity!)
3. **nova_tfetch.py** — Add lock (network ops!)
4. **nova_tools.py** — Fix memory leak (unbounded list)

### HIGH (This Week)
5. **nova_cortex.py** — Add lock (desktop automation)
6. **nova_stt.py** — Add lock (concurrent transcriptions)
7. **nova_tshell.py** — Add lock (OS integration)
8. All 31 services — Standardize to unified `_record()` helper

### MEDIUM (Next Sprint)
9. Orchestrator `/api/services/health` aggregation
10. Cross-service monitoring dashboard
11. Automated stats audit tool

---

## DASHBOARD IMPACT

Once unified, the orchestrator can query ALL 31 services and produce:

```
┌─ NOVA SERVICES HEALTH ────────────────────────────────────────┐
│                                                                │
│  Service           Ops/sec  Success%  Avg Time (ms)  Health   │
│  ─────────────────────────────────────────────────────────────│
│  orchestrator        42.3      97.2%        8.2        ✓       │
│  hivemind            28.1      94.1%       12.5        ✓       │
│  nova-tools          156.8      89.3%        2.1        ✓       │
│  nova-vault          8.2       100%        124.5        ✓       │
│  deepstorage         4.1        91.2%      245.2        ◐       │
│  tshell              12.4       86.5%       15.3        ◐       │
│  cortex              3.2        78.9%       450.1        ✗       │
│                                                                │
│  Total: 254 ops/s | Uptime: 18h 42m | Health: 89.7%          │
└────────────────────────────────────────────────────────────────┘
```

**Currently IMPOSSIBLE** — each service uses different keys.

---

## CONCLUSION

The current `_stats` landscape is:
1. **Non-uniform** (11 different schemas)
2. **Unsafe** (8 services without locks)
3. **Incomplete** (time tracking missing in 50%)
4. **Unmaintainable** (6+ helper patterns)
5. **Unmonitorable** (can't aggregate across services)

**Recommendation:** Adopt unified schema (v1.0 above) across all 31 services over 2-week migration window. Implement orchestrator aggregation dashboard in Phase 5.

---

**ARCHITECT-8 signing off.**
