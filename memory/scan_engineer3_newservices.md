# ENGINEER-3: New Services Audit (6 files)

## SUMMARY
| File | HIGH | MEDIUM | LOW | Top Issue |
|------|------|--------|-----|-----------|
| nova_tbus.py | 1 | 2 | 2 | Unbounded _topics dict |
| nova_tbuffer.py | 1 | 2 | 2 | Unbounded _entry_index dict |
| nova_tresilience.py | 1 | 2 | 2 | Unbounded _circuits + _buckets |
| nova_tintelligence.py | 0 | 3 | 3 | Duplicate entry IDs after deque wraps |
| nova_twatch.py | 1 | 3 | 2 | Unlocked mutation in sweep thread |
| nova_tmesh.py | 0 | 3 | 3 | O(N) log eviction + sequential health |
| **TOTALS** | **4** | **15** | **14** | |

## HIGH FIXES NEEDED
1. nova_tbus.py:13 — Add MAX_TOPICS=1000, prune oldest
2. nova_tbuffer.py:16 — Bound _entry_index to MAX_ENTRIES, sync with deque eviction
3. nova_tresilience.py:18,98 — Max size on _circuits + _buckets (10000, LRU evict)
4. nova_twatch.py:124 — Hold _lock during all svc mutations in _sweep()

## KEY MEDIUM FIXES
- nova_tintelligence.py:68 — entry_id duplicates after deque wraps (use uuid or monotonic counter)
- nova_tmesh.py:89 — Use deque(maxlen=1000) instead of list.pop(0)
- nova_tmesh.py:243 — Parallelize health checks (sequential = 42s worst case)
- nova_tresilience.py:136 — THROTTLE counted as "allowed" in stats
- nova_twatch.py:96 — CREATE_NO_WINDOW is Windows-only

## POSITIVE FINDINGS
- All ports unique, no conflicts
- All use tserve() correctly from nova_tlight
- All use tbody_safe() for input validation
- All bind 127.0.0.1 (not 0.0.0.0)
- TRUE/MAYBE/FALSE_ used correctly everywhere
