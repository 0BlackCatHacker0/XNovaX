# NovaX Stats Inconsistency - QUICK FIX GUIDE

## THE PROBLEM (60 seconds)
**31 services, 31 different _stats dictionaries = impossible to monitor**

- 6 different counter names (ops, queries, downloads, searches, scans, transcriptions)
- 8 services without thread locks (RACE CONDITIONS)
- 9 services missing time tracking (can't calculate latency)
- 1 service with unbounded list (MEMORY LEAK)
- 8 different helper function patterns

**Result:** Cannot aggregate health, cannot build dashboard, cannot trend performance.

---

## THE SOLUTION (Copy-Paste Ready)

### Step 1: Add This to Every Service (after imports)

```python
import threading
from collections import deque, defaultdict
import time

# If not already defined in your constants section:
H3, H5, H7, H13 = 3, 5, 7, 13
TRUE, MAYBE, FALSE_ = 1, 0, -1

# ── UNIFIED STATS ──────────────────────────────────────────────
_stats = {
    'ops': 0,
    'op_times': deque(maxlen=1000),
    'trits': {TRUE: 0, MAYBE: 0, FALSE_: 0},
    't0': time.time(),
    'by_tool': defaultdict(int),
    'total_time_ms': 0,
    'errors': 0,
}

_stats_lock = threading.Lock()

def _record(tool: str, trit: int, elapsed_ms: float = 0):
    """Record an operation. Thread-safe."""
    with _stats_lock:
        _stats['ops'] += 1
        _stats['op_times'].append(time.time())
        _stats['trits'][trit] = _stats['trits'].get(trit, 0) + 1
        _stats['by_tool'][tool] = _stats['by_tool'].get(tool, 0) + 1
        if elapsed_ms > 0:
            _stats['total_time_ms'] += elapsed_ms

def _health_trit():
    """Return service health: TRUE (ok), MAYBE (degraded), FALSE_ (critical)."""
    with _stats_lock:
        total = sum(_stats['trits'].values())
        if total == 0: return MAYBE
        success = _stats['trits'].get(TRUE, 0)
        fail = _stats['trits'].get(FALSE_, 0)
        if fail == 0: return TRUE
        if success > fail * 9: return TRUE
        if success > fail: return MAYBE
        return FALSE_
```

### Step 2: Delete Old Patterns

**Remove these if they exist in your service:**

- Old `_stats` dict definition
- Old helper: `_record_query()`, `_record_op()`, `_vault_trit()`, `_storage_trit()`, etc.
- Old pattern: `with _stats_lock:` in multiple places (consolidate into `_record()`)
- Old pattern: Direct `_stats['ops'] += 1` in handlers (use `_record()` instead)

### Step 3: Replace All Stats Updates

**Find and replace:**

```python
# BEFORE:
with _stats_lock:
    _stats['queries'] += 1
    _stats['query_times'].append(time.time())
    _stats['trits'][trit] = _stats['trits'].get(trit, 0) + 1

# AFTER:
_record('sql', trit, elapsed_ms=12.5)
```

**Another example:**

```python
# BEFORE:
_stats['ops'] += 1
_stats['by_tool']['grep'] += 1

# AFTER:
_record('grep', TRUE, elapsed_ms=2.1)
```

**Pattern: Always end your operation handler with:**

```python
try:
    # ... do work
    trit = TRUE if success else MAYBE
    elapsed = time.time() - t_start
    _record(tool_name, trit, elapsed_ms=elapsed * 1000)
except Exception as e:
    _record(tool_name, FALSE_, elapsed_ms=elapsed * 1000)
    # ... error handling
```

### Step 4: Update /health Endpoint

**Replace your old /health handler with:**

```python
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()

            uptime = time.time() - _stats['t0']
            with _stats_lock:
                trits = _stats['trits'].copy()
                by_tool = dict(_stats['by_tool'])

            response = {
                'status': 'ok',
                'port': PORT,
                'uptime_seconds': round(uptime, 2),
                'ops': _stats['ops'],
                'trits': trits,
                'health': _health_trit(),
                'by_tool': by_tool,
            }
            self.wfile.write(json.dumps(response).encode())
            return
```

---

## PRIORITY FIXES (Do First)

### CRITICAL (This Week)

1. **nova_vault.py** ← Security service needs lock
   ```python
   # Add to file:
   _stats_lock = threading.Lock()

   # Then wrap all _stats access:
   with _stats_lock:
       _stats['ops'] += 1
   ```

2. **nova_deepstorage.py** ← Data integrity needs lock
   ```python
   # Same as above
   ```

3. **nova_tools.py** ← Fix memory leak!
   ```python
   # CHANGE THIS:
   _tool_stats = {'op_times': [], ...}

   # TO THIS:
   _tool_stats = {'op_times': deque(maxlen=1000), ...}
   ```

4. **nova_tfetch.py** ← Network ops need lock
   ```python
   # Add lock + consolidate handlers
   ```

5. **nova_cortex.py, nova_stt.py, nova_tshell.py** ← Add locks (same pattern)

### HIGH (Next 2 Weeks)

6. **All 31 services:**
   - Apply unified schema (copy-paste template above)
   - Replace all counter names with 'ops'
   - Implement `_record()` helper
   - Update `/health` endpoint

---

## VALIDATION CHECKLIST

After migrating a service:

- [ ] Does `_stats` have these keys? ops, op_times, trits, t0, by_tool, total_time_ms
- [ ] Does `_record()` exist and take (tool, trit, elapsed_ms)?
- [ ] Does every operation call `_record()` exactly once?
- [ ] Does exception handler call `_record(..., FALSE_)`?
- [ ] Does `/health` GET return unified JSON format?
- [ ] Can you make 100 concurrent requests without crashes? (stress test)
- [ ] Does trit distribution make sense? (most +1, some 0, few -1?)

---

## EXPECTED RESULTS

**Before:**
```json
{
  "queries": 42,
  "query_times": [ ... ],
  "trits": {1: 35, 0: 5, -1: 2}
}
```

**After (UNIFIED):**
```json
{
  "status": "ok",
  "port": 9911,
  "uptime_seconds": 3600.5,
  "ops": 42,
  "trits": {1: 35, 0: 5, -1: 2},
  "health": 1,
  "by_tool": {"sql": 30, "kv": 12}
}
```

---

## DASHBOARD IMPACT

Once all 31 services are unified, orchestrator can do:

```
GET /api/services/health
200 OK

{
  "timestamp": 1741182000,
  "services_up": 28,
  "services_down": 3,
  "total_ops": 45892,
  "avg_ops_per_second": 12.7,
  "system_health": 1,
  "details": {
    "9881": {"status": "ok", "ops": 5000, "health": 1},
    "9891": {"status": "ok", "ops": 8000, "health": 1},
    "9892": {"status": "ok", "ops": 230, "health": 0},
    ...
  }
}
```

**Currently impossible.** Once unified, you get this for free.

---

## CUSTOM METRICS (Optional Per-Service)

If your service tracks extra stuff, add it:

```python
_stats = {
    # Unified (always here)
    'ops': 0,
    'op_times': deque(maxlen=1000),
    'trits': {TRUE: 0, MAYBE: 0, FALSE_: 0},
    't0': time.time(),
    'by_tool': defaultdict(int),
    'total_time_ms': 0,

    # CUSTOM: Your domain-specific metrics
    'bytes_processed': 0,      # nova_tools.py
    'cache_hits': 0,           # nova_tbuffer.py
    'db_size': 0,              # nova_tquery.py
}
```

**Rules:**
- Mark with `# CUSTOM:` comment
- Protect with `_stats_lock` when updating
- Include in `/health` response (optional)
- Document in code what each means

---

## IF YOU GET STUCK

1. **Unified schema template:** `C:\NovaX\memory\unified-stats-schema-v1.md`
2. **Detailed analysis:** `C:\NovaX\memory\stats-schema-analysis.md`
3. **Inconsistency matrix:** `C:\NovaX\memory\stats-inconsistency-matrix.txt`

---

## EFFORT ESTIMATE

Per service: **20-30 minutes**
- 5 min: Read old code, understand pattern
- 10 min: Apply template, update counter names
- 5 min: Find all stats updates, replace with `_record()`
- 5 min: Update `/health` endpoint
- 5 min: Test locally

**All 31 services:** ~15 hours spread over 2 weeks = 1 hour/day

---

## BOTTOM LINE

**Current state:** Each service is its own snowflake → No aggregation → No dashboard → No monitoring.

**After fix:** One schema for all 31 → Instant aggregation → System-wide health → SLA tracking.

**Start with the 5 critical services this week, then tackle the rest at 3-4 per day.**

---

**ARCHITECT-8 out. ✓**
