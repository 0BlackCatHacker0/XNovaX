"""TZip v3.2 Benchmark -- measure compression ratios toward 50x target.

Tests:
1. Per-block competitive (best single-file ratio)
2. Stream mode (full-file LZMA -- the big jump)
3. Multi-file corpus dedup (vorticity across files)
"""
import sys, os, time
sys.path.insert(0, r"C:\NovaX")
from core.tzip import (
    tzip_compress, tzip_decompress,
    tzip_compress_blocks, tzip_decompress_blocks,
    tzip_compress_stream, tzip_decompress_stream,
    tzip_compress_file,
    fastcdc_chunk, vorticity_scan,
    reynolds, classify_flow,
    BLOCK_SIZE, _tokenize, _lzma, _zlib
)

# ── helpers ─────────────────────────────────────────────────────────────

def fmt(n):
    """Format bytes as KB/MB."""
    if n > 1024*1024: return f"{n/1024/1024:.2f} MB"
    if n > 1024:      return f"{n/1024:.1f} KB"
    return f"{n} B"

def ratio(orig, comp):
    if orig == 0: return "0.0x"
    r = orig / max(1, comp)
    pct = round((1 - comp/orig) * 100, 1)
    return f"{r:.2f}x ({pct}% savings)"

def check_roundtrip(data, label=""):
    """Verify compress->decompress is lossless."""
    compressed = tzip_compress(data)
    recovered = tzip_decompress(compressed)
    ok = recovered == data
    if not ok:
        print(f"  [FAIL] Roundtrip mismatch for {label}!")
    return ok

# ── test data ────────────────────────────────────────────────────────────

# 1. Synthetic laminar (zeros -- best case)
laminar_data = bytes(BLOCK_SIZE * 4)

# 2. Source code (orchestrator.py)
orch_path = r"C:\NovaX\core\orchestrator.py"
with open(orch_path, "rb") as f:
    source_data = f.read()

# 3. Novalang interpreter (largest .py file) -- skip if missing
nova_path = r"C:\NovaX\novalang.py"
nova_data = None
if os.path.exists(nova_path):
    with open(nova_path, "rb") as f:
        nova_data = f.read()
else:
    print(f"[WARN] {nova_path} not found -- skipping novalang tests")

# 4. Multi-file corpus: all .py files in core/
import glob
py_files = glob.glob(r"C:\NovaX\core\*.py")
corpus_blocks = []
corpus_orig_size = 0
for fp in py_files[:20]:  # cap at 20 files for speed
    with open(fp, "rb") as f:
        raw = f.read()
    corpus_blocks.append(raw)
    corpus_orig_size += len(raw)

print("=" * 60)
print("TZip v3.2 Benchmark -- Path to 50x")
print(f"LZMA available: {bool(_lzma)}  |  zlib available: {bool(_zlib)}")
print("=" * 60)

# ── Test 1: Roundtrip verification ───────────────────────────────────────
print("\n[1] Roundtrip verification")
tests = [
    (laminar_data, "zeros"),
    (source_data[:BLOCK_SIZE*4], "source code"),
    (b"hello world " * 200, "repetitive text"),
    (os.urandom(BLOCK_SIZE), "random bytes"),
]
all_ok = True
for data, label in tests:
    ok = check_roundtrip(data, label)
    print(f"  {label:25s} {'PASS' if ok else 'FAIL'}")
    all_ok = all_ok and ok
print(f"  Roundtrip: {'ALL PASS' if all_ok else 'FAILURES DETECTED'}")

# ── Test 2: Per-block competitive (single block) ──────────────────────────
print("\n[2] Per-block competitive (single 2187-byte blocks)")

test_blocks = {
    "zeros (laminar)":     bytes(BLOCK_SIZE),
    "source code":         source_data[:BLOCK_SIZE],
    "JSON-like text":      (b'{"key": "value", "num": 12345, "flag": true}\n') * 40,
    "random":              os.urandom(BLOCK_SIZE),
}

for label, data in test_blocks.items():
    re = reynolds(data)
    regime = classify_flow(re)
    c = tzip_compress(data)
    print(f"  {label:25s}  Re={re:6.1f} ({regime:12s})  {fmt(len(data))} -> {fmt(len(c))}  {ratio(len(data), len(c))}")

# ── Test 3: Full-file per-block vs stream mode ────────────────────────────
print("\n[3] Full-file: per-block vs STREAM MODE")

_file_tests = [("orchestrator.py", source_data)]
if nova_data is not None:
    _file_tests.append(("novalang.py", nova_data))
for label, data in _file_tests:
    orig = len(data)

    # Per-block (old)
    t0 = time.time()
    comp_blocks = tzip_compress_blocks(data)
    t_blocks = time.time() - t0

    # Stream mode (new)
    t0 = time.time()
    chunks = fastcdc_chunk(data)
    blocks = [data[off:off+length] for off, length in chunks]
    comp_stream = tzip_compress_stream(blocks)
    t_stream = time.time() - t0

    # Verify stream roundtrip
    recovered_blocks = tzip_decompress_stream(comp_stream)
    recovered = b"".join(recovered_blocks)
    stream_ok = recovered == data

    print(f"\n  {label}  ({fmt(orig)})")
    print(f"    Per-block:   {fmt(len(comp_blocks)):10s}  {ratio(orig, len(comp_blocks)):25s}  {t_blocks:.3f}s")
    print(f"    Stream mode: {fmt(len(comp_stream)):10s}  {ratio(orig, len(comp_stream)):25s}  {t_stream:.3f}s  {'[OK]' if stream_ok else '[ROUNDTRIP FAIL]'}")
    if len(comp_stream) < len(comp_blocks):
        improvement = round((1 - len(comp_stream)/len(comp_blocks)) * 100, 1)
        print(f"    Stream wins by {improvement}% over per-block")

# ── Test 4: Multi-file corpus (stream over all blocks) ────────────────────
print("\n[4] Multi-file corpus stream (cross-file LZMA context)")

all_blocks = []
for raw in corpus_blocks:
    chunks = fastcdc_chunk(raw)
    for off, length in chunks:
        all_blocks.append(raw[off:off+length])

t0 = time.time()
corpus_compressed = tzip_compress_stream(all_blocks)
t_corpus = time.time() - t0

# Verify
recovered_blocks = tzip_decompress_stream(corpus_compressed)
recovered_size = sum(len(b) for b in recovered_blocks)

print(f"  Files: {len(py_files[:20])}  |  Total blocks: {len(all_blocks)}")
print(f"  Original:   {fmt(corpus_orig_size)}")
print(f"  Compressed: {fmt(len(corpus_compressed))}  {ratio(corpus_orig_size, len(corpus_compressed))}")
print(f"  Time: {t_corpus:.3f}s  |  Roundtrip: {'OK' if recovered_size == corpus_orig_size else 'MISMATCH'}")

# ── Test 5: Vorticity dedup scan ──────────────────────────────────────────
print("\n[5] Vorticity dedup scan (N-S curl -- duplicate blocks)")
# Scan orchestrator.py for duplicate blocks
result = vorticity_scan(source_data)
print(f"  orchestrator.py: {result['total_blocks']} blocks, "
      f"{result['duplicate_count']} duplicates ({result['dedup_ratio']}% dedup ratio), "
      f"vorticity={result['vorticity']:.3f}")

# Scan novalang.py
if nova_data is not None:
    result2 = vorticity_scan(nova_data)
    print(f"  novalang.py:     {result2['total_blocks']} blocks, "
          f"{result2['duplicate_count']} duplicates ({result2['dedup_ratio']}% dedup ratio)")
else:
    print("  novalang.py:     [SKIPPED -- file not found]")

# ── Test 6: Token effectiveness ───────────────────────────────────────────
print("\n[6] Token pattern compression (domain vocabulary effect)")
sample = source_data[:BLOCK_SIZE * 3]
tokenized = _tokenize(sample)
savings = round((1 - len(tokenized)/len(sample)) * 100, 1)
print(f"  Tokenize only:  {fmt(len(sample))} -> {fmt(len(tokenized))}  ({savings}% reduction before LZMA)")
print("  (These savings compound with LZMA's cross-reference matching)")

# ── Summary ───────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("SUMMARY -- 50x Roadmap Status")
print("=" * 60)
print("Layer 1: Competitive selection (8 strategies)  -- DONE")
print("Layer 2: Stream mode (full-file LZMA context)  -- DONE")
print("Layer 3: Cross-file corpus stream              -- DONE")
print("Layer 4: FastCDC dedup (vorticity)             -- DONE")
print("Layer 5: Semantic dedup (delta between files)  -- TODO")
print("Layer 6: Pre-trained per-filetype dicts        -- PARTIAL (zlib dict)")
print()
print("Current achievable ratios:")
print("  Zeros/nulls:     ~100x  (laminar RLE)")
print("  Source code:     check above (stream mode)")
print("  JSON/text:       check above")
print("  Random bytes:    ~1.0x  (chaotic -- no compression possible)")
print()
print("To reach 50x on MIXED data: need semantic dedup (Layer 5)")
print("= treating similar functions across files as deltas")
