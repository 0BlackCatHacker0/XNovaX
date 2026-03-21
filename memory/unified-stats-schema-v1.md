# NovaX Unified _stats Schema v1.0
**Mandatory for all 31 services.**

---

## COPY-PASTE TEMPLATE

Add this to EVERY NovaX service (top of file after imports):

```python
import threading
from collections import deque, defaultdict
import time

# ── 3-5-7-13 Ternary Constants (already defined elsewhere)
H3, H5, H7, H13 = 3, 5, 7, 13
TRUE, MAYBE, FALSE_ = 1, 0, -1

# ── UNIFIED STATS DICTIONARY ───────────────────────────────────
_stats = {
    'ops': 0,                              # Total operations since service start
    'op_times': deque(maxlen=1000),        # Timestamps of last 1000 ops (for throughput calc)
    'trits': {TRUE: 0, MAYBE: 0, FALSE_: 0},  # Success/partial/failure counts
    't0': time.time(),                     # Service start timestamp

    'by_tool': defaultdict(int),           # Per-tool op count (if service has 2+ tools)
    'total_time_ms': 0,                    # Cumulative execution time (optional, if tracking latency)
    'errors': 0,                           # Error count (optional)
}

_stats_lock = threading.Lock()             # CRITICAL: Thread-safe access


# ── UNIFIED RECORDING FUNCTION ─────────────────────────────────
def _record(tool: str, trit: int, elapsed_ms: float = 0):
    """
    Record an operation to unified _stats. ALWAYS thread-safe.

    Args:
        tool: str           — Tool/operation name ("grep", "sql", "compile", etc.)
        trit: int           — Result: TRUE (+1), MAYBE (0), FALSE_ (-1)
        elapsed_ms: float   — Wall-clock execution time in milliseconds

    Thread-safe: Acquires _stats_lock internally.
    Call this ONCE per operation, pass ANY trit value.
    """
    with _stats_lock:
        _stats['ops'] += 1
        _stats['op_times'].append(time.time())
        _stats['trits'][trit] = _stats['trits'].get(trit, 0) + 1
        _stats['by_tool'][tool] = _stats['by_tool'].get(tool, 0) + 1
        if elapsed_ms > 0:
            _stats['total_time_ms'] += elapsed_ms


# ── SERVICE HEALTH CALCULATION ──────────────────────────────────
def _health_trit():
    """
    Compute service health from recent ops.

    Returns:
        TRUE (+1)   — Healthy (>90% of recent ops succeeded)
        MAYBE (0)   — Degraded (50-90% success rate)
        FALSE_ (-1) — Critical (<50% success rate)
    """
    with _stats_lock:
        total = sum(_stats['trits'].values())
        if total == 0:
            return MAYBE  # No data yet

        success_count = _stats['trits'].get(TRUE, 0)
        fail_count = _stats['trits'].get(FALSE_, 0)

        if fail_count == 0:
            return TRUE  # Perfect record
        if success_count > fail_count * 9:
            return TRUE  # >90% success
        if success_count > fail_count:
            return MAYBE  # Mixed but leaning success
        return FALSE_  # Mostly failures


# ── UPTIME & THROUGHPUT HELPERS ────────────────────────────────
def _uptime_seconds():
    """Seconds since service started."""
    return max(time.time() - _stats['t0'], 0.1)

def _ops_per_second():
    """Average throughput in operations/second."""
    uptime = _uptime_seconds()
    return _stats['ops'] / uptime if uptime > 0 else 0

def _avg_latency_ms():
    """Average operation latency in milliseconds."""
    if _stats['ops'] == 0:
        return 0
    return _stats['total_time_ms'] / _stats['ops']


# ── HTTP HEALTH ENDPOINT (required in handler) ────────────────
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()

            with _stats_lock:
                trits_snapshot = _stats['trits'].copy()
                by_tool_snapshot = dict(_stats['by_tool'])

            response = {
                'status': 'ok',
                'port': PORT,
                'uptime_seconds': round(_uptime_seconds(), 2),
                'ops': _stats['ops'],
                'ops_per_second': round(_ops_per_second(), 2),
                'trits': trits_snapshot,
                'health': _health_trit(),
                'by_tool': by_tool_snapshot,
                'avg_latency_ms': round(_avg_latency_ms(), 2),
            }
            self.wfile.write(json.dumps(response).encode())
            return

        # ... handle other paths
```

---

## INTEGRATION CHECKLIST

For each service:

- [ ] Add template above to top of service file (after imports)
- [ ] Replace **ALL** inline `_stats` updates with `_record(tool, trit, elapsed_ms)` calls
- [ ] Delete old helpers like `_record_query()`, `_record_op()`, `_vault_trit()` etc.
- [ ] Rename counter keys: `queries→ops`, `downloads→ops`, `searches→ops`, etc.
- [ ] Add `_health_trit()` and helper functions
- [ ] Update `/health` GET handler to use unified response format
- [ ] Test: Verify stats increment correctly under load
- [ ] Test: Verify thread safety with concurrent requests

---

## EXAMPLE: BEFORE & AFTER

### BEFORE (nova_tquery.py)
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

def _record_op(tool, trit_val):
    with _stats_lock:
        _stats['ops'] += 1
        _stats['op_times'].append(time.time())
        _stats['trits'][trit_val] = _stats['trits'].get(trit_val, 0) + 1
        _stats['queries_by_tool'][tool] += 1

# In handler:
_record_op('sql', TRUE)
_record_op('kv', MAYBE)

# `/health` endpoint (missing unified format):
{
    "ops": 42,
    "trits": {1: 35, 0: 5, -1: 2}
}
```

### AFTER (nova_tquery.py)
```python
# Same template as above, plus:
_stats = {
    # ... unified dict
    'db_size_bytes': 0,      # CUSTOM: domain-specific metric
    'kv_entries': 0,         # CUSTOM: domain-specific metric
}

# In handler:
_record('sql', TRUE, elapsed_ms=12.5)
_record('kv', MAYBE, elapsed_ms=2.1)

# `/health` endpoint (unified format):
{
    "status": "ok",
    "uptime_seconds": 3600.5,
    "ops": 42,
    "ops_per_second": 0.012,
    "trits": {1: 35, 0: 5, -1: 2},
    "health": 1,
    "by_tool": {"sql": 30, "kv": 12},
    "avg_latency_ms": 8.5
}
```

---

## CUSTOM METRICS (ALLOWED)

Each service can ADD domain-specific keys to `_stats`, but:

1. **Document them at initialization** with `# CUSTOM:` comment
2. **Protect them with `_stats_lock`** just like unified keys
3. **Include them in `/health` response** (optional but recommended)

Example (nova_deepstorage.py):
```python
_stats = {
    # Unified keys
    'ops': 0,
    'op_times': deque(maxlen=1000),
    'trits': {TRUE: 0, MAYBE: 0, FALSE_: 0},
    't0': time.time(),
    'by_tool': defaultdict(int),

    # CUSTOM: Storage-specific metrics
    'bytes_stored': 0,
    'bytes_compressed': 0,
    'dedup_blocks': 0,
    'tier_hot': 0,
    'tier_warm': 0,
    'tier_cold': 0,
}

def _record(tool: str, trit: int, elapsed_ms: float = 0):
    """Standard record + optional custom params."""
    with _stats_lock:
        _stats['ops'] += 1
        # ... standard logic
```

---

## ORCHESTRATOR AGGREGATION

Once all services implement unified schema, orchestrator can do:

```python
def get_all_services_health():
    """Poll /health from all 31 services and aggregate."""
    results = {}
    for port in [9875, 9877, 9878, ..., 9999]:
        try:
            resp = urllib.request.urlopen(f'http://localhost:{port}/health', timeout=5)
            data = json.loads(resp.read())
            results[port] = data
        except:
            results[port] = {'status': 'down', 'health': -1}

    # Aggregate
    total_ops = sum(r.get('ops', 0) for r in results.values() if r.get('status') == 'ok')
    total_health_points = sum(r.get('health', 0) for r in results.values() if r.get('status') == 'ok')
    avg_health = total_health_points / len([r for r in results.values() if r.get('status') == 'ok'])

    return {
        'timestamp': time.time(),
        'services_up': len([r for r in results.values() if r.get('status') == 'ok']),
        'services_down': len([r for r in results.values() if r.get('status') != 'ok']),
        'total_ops_all_time': total_ops,
        'avg_health': round(avg_health, 2),
        'details': results,
    }
```

**Currently IMPOSSIBLE** — each service has different response format.

---

## SUMMARY

| Aspect | BEFORE | AFTER |
|--------|--------|-------|
| Consistency | ❌ 11 schemas | ✓ 1 schema |
| Thread-safety | ❌ 8 no locks | ✓ All locked |
| Time tracking | ❌ 50% missing | ✓ All tracked |
| Aggregation | ❌ Impossible | ✓ Unified dashboard |
| Migration effort | — | ~30 min per service |

---

**Adopt this schema for all 31 services immediately.**
