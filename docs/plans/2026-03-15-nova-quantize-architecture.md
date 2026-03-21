# nova_quantize.nova — Ternary Storage Layer Architecture
**Date:** 2026-03-15
**Port:** 9912
**File:** `C:\NovaX\nova_quantize_service.nova`
**Dependencies:** nova_ns_core.nova, nova_stdlib.nova, nova_ternary_tools_service.nova (:9894)
**Status:** DESIGN

---

## 1. PURPOSE

Make a 2TB NTFS drive hold 9-18TB of effective data by layering five
ternary-native compression techniques that compound multiplicatively.
Expose the entire pipeline through a single NovaLang service that any
other NovaX component can call via HTTP.

---

## 2. HARMONIC ALIGNMENT (3-5-7-13)

Every data structure in nova_quantize aligns to the harmonic constants
already defined in `nova_ns_core.nova`:

| Constant | Value | Role in nova_quantize |
|----------|-------|----------------------|
| H3 = 3  | 3     | Trit states per element (-1, 0, +1) |
| H5 = 5  | 5     | Trits per TWord (3^5 = 243 states, fits in 1 byte) |
| H7 = 7  | 7     | Layers in the compression pipeline |
| H13 = 13| 13    | CAS index frame header size (bytes) |
| BLOCK   | 2187  | 3^7, fundamental I/O unit for all reads/writes |

### Derived Constants

```
TWORD_STATES    = 3^5        = 243       (values per 5-trit word)
BLOCK_SIZE      = 3^7        = 2187      (bytes per storage block)
SUPERBLOCK      = BLOCK * 13 = 28431     (13 blocks = 1 superblock)
SEGMENT         = BLOCK * 7  = 15309     (7 blocks = 1 delta segment)
CAS_BUCKET      = 3^5        = 243       (hash buckets per CAS shard)
SPARSITY_THRESH = 0.33                   (same threshold as /ternary/quantize)
DEDUP_WINDOW    = 13                     (superblocks scanned for dedup)
```

---

## 3. THE SEVEN-LAYER PIPELINE

Data flows through up to 7 stages. Each stage is optional and
self-reports whether it produced a gain (trit +1), no change (trit 0),
or should be skipped for this data type (trit -1). The pipeline
short-circuits on -1 and passes data through on 0.

```
Layer 1: INGEST        Chunk raw file into 2187-byte blocks
Layer 2: CLASSIFY      Identify data type (AI weights, embeddings, text, binary, mixed)
Layer 3: TERNARY_ENCODE Convert to 5-trit TWords where profitable
Layer 4: SPARSITY_RLE  Run-length encode zero trits in ternary stream
Layer 5: CAS_DEDUP     Content-addressable dedup across block index
Layer 6: DELTA_ENCODE  Store delta against base for model families
Layer 7: SEMANTIC_COMPRESS  Dimensionality reduction for embeddings
```

### Data Flow (Text Notation)

```
                    +-----------+
  Raw File ------->| L1 INGEST |---> Block Stream (2187B each)
                    +-----------+
                          |
                    +-----------+
                    | L2 CLASSIFY|---> data_type tag per block
                    +-----------+
                          |
              +-----------+-----------+
              |                       |
     [AI weights/embeddings]     [text/binary]
              |                       |
     +----------------+      +----------------+
     | L3 TERN_ENCODE |      | (skip, trit 0) |
     +----------------+      +----------------+
              |                       |
     +----------------+      +----------------+
     | L4 SPARSE_RLE  |      | L4 SPARSE_RLE  |
     +----------------+      +----------------+
              |                       |
              +-----------+-----------+
                          |
                   +------------+
                   | L5 CAS_DEDUP|---> deduplicated block refs
                   +------------+
                          |
                   +------------+
                   | L6 DELTA   |---> base + delta for model families
                   +------------+
                          |
              +-----------+-----------+
              |                       |
     [embedding blocks]          [other blocks]
              |                       |
     +------------------+    +----------------+
     | L7 SEMANTIC_COMP |    | (skip, trit 0) |
     +------------------+    +----------------+
              |                       |
              +-----------+-----------+
                          |
                   +------------+
                   |  STORAGE   |---> .tqz files on disk
                   +------------+
```

---

## 4. DATA STRUCTURES

### 4.1 Block Header (13 bytes, H13-aligned)

```
Offset  Size  Field
0       1     magic         = 0xA3 (ternary marker: 243 decimal, trit-adjacent)
1       1     version       = 0x01
2       1     layer_flags   = bitmask of which layers were applied (7 bits for 7 layers)
3       1     data_type     = enum: 0=unknown, 1=ai_weight, 2=embedding, 3=text,
                              4=binary, 5=novalang, 6=model_delta
4       4     original_size = uint32 LE, original block size before compression
8       4     stored_size   = uint32 LE, actual bytes stored after compression
12      1     checksum      = trit-fold checksum (sum of all trits mod 3, mapped to byte)
```

Total: 13 bytes. One H13 frame.

### 4.2 TWord (5 trits packed into 1 byte)

Each trit is one of {-1, 0, +1}, encoded as {0, 1, 2} for packing.
5 trits pack into one byte: value = t0 + t1*3 + t2*9 + t3*27 + t4*81.
Range: 0..242 (243 states, fits in uint8).

```
Byte value 0   = [-1,-1,-1,-1,-1]  (all negative)
Byte value 121 = [ 0, 0, 0, 0, 0]  (all zero / neutral)
Byte value 242 = [+1,+1,+1,+1,+1]  (all positive)
```

Encoding: each original byte (0-255) maps to one TWord (0-242).
Values 243-255 are unmappable and stored as escape sequences:
  [ESCAPE_TWORD (242), raw_byte].

This means 256 source values map to 243 + 13 escaped = 256 representations.
Net overhead for escape: 13/256 = 5.1% of bytes need 2 TWords.
For AI weight data (typically fp16 quantized to int8), most values
cluster in [-127, +127] and map cleanly.

### 4.3 CAS Index Entry (per block)

```
{
    "hash":          <sha256 of raw block, truncated to 20 bytes>,
    "trit_hash":     <25-trit fingerprint, same format as tshell/ternary_index.json>,
    "ref_count":     <int, number of files referencing this block>,
    "stored_size":   <int, compressed size on disk>,
    "original_size": <int, always 2187 or remainder for final block>,
    "layer_flags":   <int, which compression layers applied>,
    "data_type":     <int, classification enum>,
    "location":      <string, path to .tqz storage file + offset>,
    "first_seen":    <float, timestamp>,
    "last_accessed": <float, timestamp for hot/warm/cold tiering>
}
```

The CAS index itself is stored as a JSON file sharded into 243 (3^5)
bucket files: `C:\NovaX\data\quantize\cas\bucket_NNN.json` where
NNN = first 2 trits of trit_hash mapped to 0-242.

### 4.4 Delta Manifest (per model family)

```
{
    "family":       "llama3.2",
    "base_model":   "llama3.2:1b",
    "base_hash":    <sha256 of base model file>,
    "variants": [
        {
            "name":        "llama3.2:3b",
            "delta_file":  "C:\\NovaX\\data\\quantize\\deltas\\llama3.2_3b.tdelta",
            "delta_size":  <int>,
            "full_size":   <int>,
            "savings_pct": <float>,
            "block_count": <int>,
            "changed_blocks": <int>
        }
    ]
}
```

### 4.5 Storage Stats Object (returned by /quantize/stats)

```
{
    "drive": {
        "path":           "C:\\",
        "raw_capacity":   <int, bytes>,
        "raw_used":       <int, bytes>,
        "raw_free":       <int, bytes>
    },
    "effective": {
        "total_managed":    <int, bytes of data under nova_quantize management>,
        "stored_bytes":     <int, actual bytes on disk after all compression>,
        "effective_bytes":  <int, logical bytes represented>,
        "ratio":            <float, effective / stored>,
        "effective_free":   <int, estimated additional logical bytes that can fit>
    },
    "layers": {
        "ternary_encode": {"blocks_processed": N, "ratio": F},
        "sparsity_rle":   {"blocks_processed": N, "ratio": F},
        "cas_dedup":      {"unique_blocks": N, "total_refs": N, "dedup_ratio": F},
        "delta_encode":   {"families": N, "base_models": N, "delta_ratio": F},
        "semantic":       {"embeddings_compressed": N, "ratio": F}
    },
    "trit": 1,
    "harmonics": {"H3": 3, "H5": 5, "H7": 7, "H13": 13, "block": 2187}
}
```

---

## 5. API ROUTES

Port 9912. All routes prefixed for orchestrator proxy at `/api/quantize/*`.

### Health & Status
```
GET  /health                      Standard N-S health dict
GET  /quantize/stats              Full storage stats (Section 4.5)
GET  /quantize/pipeline/status    Per-layer enable/disable + counters
```

### Ingest & Compress
```
POST /quantize/ingest             Ingest a file or directory into managed storage
     Body: {"path": "C:\\path\\to\\file_or_dir", "recursive": true}
     Response: {"ok": true, "trit": 1, "files": N, "blocks": N,
                "raw_bytes": N, "stored_bytes": N, "ratio": F,
                "layers_applied": {...}}

POST /quantize/compress           Compress a single data buffer (for API use)
     Body: {"data": "<base64>", "data_type": "auto|ai_weight|embedding|text|binary"}
     Response: {"ok": true, "trit": 1, "compressed": "<base64>",
                "original_size": N, "stored_size": N, "ratio": F}

POST /quantize/decompress         Decompress a buffer
     Body: {"data": "<base64>"}
     Response: {"ok": true, "trit": 1, "decompressed": "<base64>",
                "stored_size": N, "original_size": N}
```

### CAS (Content-Addressable Storage)
```
POST /quantize/cas/store          Store a block, dedup automatically
     Body: {"data": "<base64>", "source_file": "path", "block_index": N}
     Response: {"ok": true, "trit": 1, "hash": "...", "is_new": bool,
                "ref_count": N}

GET  /quantize/cas/lookup         Look up block by hash
     Params: ?hash=<sha256>&trit_hash=<25-trit>
     Response: {"ok": true, "trit": 1, "found": bool, "entry": {...}}

GET  /quantize/cas/stats          CAS index statistics
     Response: {"ok": true, "trit": 1, "total_blocks": N,
                "unique_blocks": N, "dedup_ratio": F,
                "bucket_distribution": [...]}
```

### Delta Encoding (Model Families)
```
POST /quantize/delta/register     Register a model family base
     Body: {"family": "llama3.2", "base_path": "C:\\...\\llama3.2-1b"}
     Response: {"ok": true, "trit": 1, "base_hash": "...", "block_count": N}

POST /quantize/delta/create       Create delta for variant against base
     Body: {"family": "llama3.2", "variant_path": "C:\\...\\llama3.2-3b"}
     Response: {"ok": true, "trit": 1, "delta_size": N, "full_size": N,
                "savings_pct": F, "changed_blocks": N}

POST /quantize/delta/reconstruct  Reconstruct full model from base + delta
     Body: {"family": "llama3.2", "variant": "llama3.2:3b",
            "output_path": "C:\\...\\output"}
     Response: {"ok": true, "trit": 1, "reconstructed_size": N,
                "checksum_valid": bool}

GET  /quantize/delta/families     List all registered families
     Response: {"ok": true, "trit": 1, "families": [...]}
```

### Semantic Compression (Embeddings)
```
POST /quantize/semantic/compress   Compress embedding vectors
     Body: {"vectors": [[f32, ...], ...], "dimensions": N, "target_dims": N}
     Response: {"ok": true, "trit": 1, "compressed_vectors": [...],
                "projection_matrix_hash": "...",
                "original_dims": N, "target_dims": N,
                "quality_estimate": F}

POST /quantize/semantic/decompress Reconstruct embeddings
     Body: {"compressed_vectors": [...], "projection_matrix_hash": "..."}
     Response: {"ok": true, "trit": 1, "vectors": [[f32, ...], ...],
                "reconstruction_loss_estimate": F}
```

### Analysis & Optimization
```
POST /quantize/analyze            Analyze a path for compression potential
     Body: {"path": "C:\\path", "recursive": true}
     Response: {"ok": true, "trit": 1,
                "files": N, "total_bytes": N,
                "estimates": {
                    "ternary_encode": {"applicable": bool, "est_ratio": F},
                    "sparsity_rle":   {"applicable": bool, "est_ratio": F},
                    "cas_dedup":      {"applicable": bool, "est_ratio": F},
                    "delta_encode":   {"applicable": bool, "est_ratio": F},
                    "semantic":       {"applicable": bool, "est_ratio": F}
                },
                "combined_ratio": F,
                "effective_size": N,
                "recommendation": "...",
                "reynolds": N, "regime": "..."}

POST /quantize/optimize           Run optimization pass on managed storage
     Body: {"target": "all|cas|delta|semantic", "dry_run": true}
     Response: {"ok": true, "trit": 1,
                "current_stored": N, "optimized_stored": N,
                "savings": N, "actions": [...]}
```

---

## 6. LAYER SPECIFICATIONS

### Layer 1: INGEST

Reads files in BLOCK_SIZE (2187) byte chunks. Final block is padded
with trit-zero bytes (value 121 = all-zero TWord). Each block gets a
13-byte header prepended.

**Block address scheme:** file_hash[0:20] + block_index (4 bytes) = 24-byte
block ID. This ID is the CAS lookup key before hashing the content.

### Layer 2: CLASSIFY

Examines first BLOCK_SIZE of a file (or the block itself) to assign a
data_type enum. Classification rules:

```
data_type = 1 (ai_weight)    if file extension in {.bin, .safetensors, .gguf, .ggml}
                              OR byte histogram shows tight cluster around 0 with long tails
data_type = 2 (embedding)    if file extension in {.npy, .pt, .embedding}
                              OR shape metadata indicates vector array
data_type = 3 (text)         if >85% of bytes are printable ASCII/UTF-8
data_type = 4 (binary)       if entropy > 7.5 bits/byte (already compressed/encrypted)
data_type = 5 (novalang)     if file extension is .nova
data_type = 6 (model_delta)  if file is in delta manifest
data_type = 0 (unknown)      fallback
```

**Critical rule:** Layer 2 returns trit -1 for data_type 4 (already
compressed/encrypted data), which causes Layers 3-4 to skip.
Compressing random data wastes CPU for zero gain.

### Layer 3: TERNARY_ENCODE

Converts each byte in the block to a TWord (5 trits packed into 1 byte).
For AI weight data, applies threshold quantization first:

```
For each float/int value in the block:
  if value > +SPARSITY_THRESH: trit = +1
  if value < -SPARSITY_THRESH: trit = -1
  else:                        trit =  0
```

This is the same logic as the existing `/ternary/quantize` endpoint
on port 9885. The quantization threshold is configurable per data_type:

```
ai_weight:   threshold = 0.33 (standard, matches existing)
embedding:   threshold = 0.10 (tighter, preserve more information)
text:        threshold = N/A  (text uses byte-to-TWord mapping, not quantization)
novalang:    threshold = N/A  (same as text)
```

### Layer 4: SPARSITY_RLE

Run-length encode consecutive zero trits in the TWord stream.
Format: [RLE_MARKER (TWord value 0), count_tword].
Count is itself a TWord, so max run = 242 zero-TWords per RLE pair.
For longer runs, chain multiple RLE pairs.

**Expected compression for AI weight data:**
- Typical ternary weight sparsity: 42.3% zeros
- Average zero run length in quantized weights: 3-7 trits
- Expected compression ratio from sparsity alone: 1.5-1.8x

**Expected compression for text:**
- Text has less natural ternary sparsity (~15% zero TWords)
- Expected ratio: 1.05-1.15x (modest, but compounds with other layers)

### Layer 5: CAS_DEDUP

After Layers 3-4, compute SHA-256 of the compressed block content.
Look up in CAS index:
- **HIT:** Increment ref_count, store only a 24-byte block reference. Trit +1.
- **MISS:** Store compressed block, create new CAS entry. Trit 0.

CAS index is sharded into 243 bucket files (H5-aligned).
Bucket selection: take first 5 trits of trit_hash, convert to
0-242 integer.

**Dedup expectations by data category:**

| Category | Expected Dedup | Why |
|----------|---------------|-----|
| Ollama models (102 installed) | 30-60% | Shared transformer attention + FFN layer patterns |
| Embedding caches | 10-20% | Similar prefix/normalization blocks |
| NovaLang source | 5-15% | Shared import headers, boilerplate |
| General files | 2-5% | Some OS/framework duplication |

### Layer 6: DELTA_ENCODE

Only applies to registered model families. After CAS dedup, blocks
that are unique to a variant (not in base) are stored as delta blocks.

Delta block format:
```
[Block Header (13 bytes)]
[Base block hash (20 bytes)]
[XOR delta payload (variable)]
```

The delta payload is the XOR of the variant block with the
corresponding base block. XOR deltas compress extremely well with
Layer 4 (sparsity RLE) because similar weights produce mostly-zero
XOR output.

**Registration flow:**
1. User registers base model via `/quantize/delta/register`
2. Service ingests base model, indexes all blocks in CAS
3. User creates variant via `/quantize/delta/create`
4. Service ingests variant, for each block:
   a. If identical to base block -> CAS dedup handles it (Layer 5)
   b. If different -> XOR with corresponding base block -> store delta
5. Reconstruction: for each block, if delta -> XOR delta with base block

**Expected savings for Ollama model families:**

| Family | Base Size | Variants | Delta Overhead | Savings |
|--------|-----------|----------|----------------|---------|
| llama3.2 | 1.3 GB | 3b, 8b, 70b | 5-15% per variant | 70-85% |
| mistral | 4.1 GB | 7b, moe | 8-12% per variant | 75-88% |
| phi3 | 2.3 GB | mini, medium | 10-15% per variant | 70-80% |
| codellama | 3.8 GB | 7b, 13b, 34b | 5-10% per variant | 80-90% |

### Layer 7: SEMANTIC_COMPRESS

Only applies to data_type 2 (embeddings). Uses ternary PCA:

1. Collect N embedding vectors of dimension D
2. Compute covariance matrix (D x D) in ternary: quantize to trits first
3. Find top K eigenvectors where K captures 90%+ variance
   (typical K = D/10 for well-structured embeddings)
4. Project: compressed = vectors @ projection_matrix[:, :K]
5. Store projection_matrix in CAS (shared across same-model embeddings)
6. Store compressed vectors (K dimensions instead of D)

**Size reduction:** D/K ratio, typically 5-10x for embeddings.
Combined with ternary quantization (fp32 -> trit): 32 * (D/K) = 160-320x
theoretical maximum per embedding element.

**Quality guarantee:** Reconstruction cosine similarity > 0.95 with
the original vectors. If below threshold, fall back to Layer 3+4 only
(trit = -1 on Layer 7).

---

## 7. STORAGE LAYOUT ON DISK

```
C:\NovaX\data\quantize\
    cas\
        bucket_000.json          CAS shard 0 (of 243)
        bucket_001.json          CAS shard 1
        ...
        bucket_242.json          CAS shard 242
    blocks\
        00\                      First 2 hex chars of block hash
            00\                  Next 2 hex chars
                <hash>.tqb      Compressed block file (.tqb = ternary quantized block)
    deltas\
        <family>_<variant>.tdelta   Delta files per model variant
    manifests\
        delta_<family>.json      Delta manifest per family
        ingest_<hash>.json       Per-file ingest manifest (block list, metadata)
    semantic\
        proj_<hash>.tqp          Projection matrices (.tqp = ternary quantized projection)
    stats.json                   Persistent stats (loaded on boot)
    config.json                  Layer enable/disable, thresholds, paths
```

### File format: .tqb (Ternary Quantized Block)

```
[Block Header: 13 bytes]
[Compressed payload: stored_size bytes]
```

Multiple blocks can be packed into a single .tqb file for sequential
access. In that case, blocks are concatenated and the manifest tracks
offsets.

---

## 8. N-S INTEGRATION

nova_quantize uses Navier-Stokes flow metrics to tune its own behavior:

| Reynolds Regime | Behavior |
|-----------------|----------|
| Laminar (Re < 27) | Full 7-layer pipeline, thorough analysis, no rush |
| Transitional (27 <= Re < 125) | Skip Layer 7 (semantic), reduce CAS scan window to 7 |
| Turbulent (125 <= Re < 343) | Skip Layers 6+7, reduce CAS to local-only dedup |
| Chaotic (Re >= 343) | Ingest + CAS dedup only (Layers 1+2+5), queue rest for later |

This means under heavy load, nova_quantize degrades gracefully:
it always stores data (never blocks writes), but defers expensive
compression to background passes when the system calms down.

**Background optimization loop:** Every 13 seconds (H13-aligned), if
Reynolds is laminar, run one optimization pass on the oldest
un-optimized superblock. This ensures data eventually gets fully
compressed even if it was ingested during high load.

---

## 9. INTEGRATION WITH EXISTING SERVICES

### 9.1 Orchestrator (:9999)
Proxy routes under `/api/quantize/*` -> `localhost:9912/quantize/*`.
Health check at `/api/quantize/health`.

### 9.2 Ternary Server (:9885)
nova_quantize calls `/ternary/quantize` for value-to-trit conversion
when it detects the existing endpoint is faster than internal quantization.
This deduplicates the quantization logic (DRY principle).

### 9.3 Ternary Tools (:9894)
- Uses TCache (`/ttools/cache/*`) for hot block caching
- Uses TIndex (`/ttools/index`) to register managed files in the global index
- Uses TDiff (`/ttools/diff`) for delta computation
- Uses TForge (`/ttools/forge`) to classify NovaLang files

### 9.4 Hivemind (:9881)
nova_quantize registers as a queryable service. Hivemind can ask
"how much space do I need for model X?" via `/quantize/analyze`.

### 9.5 TShell / ternary_index.json
Shares the same `trit_hash` (25-trit fingerprint) and `sha256` format
already used by the existing ternary index. CAS entries are
cross-compatible with TIndex entries.

---

## 10. EFFECTIVE CAPACITY MODEL

The multiplicative capacity formula, with conservative and aggressive
estimates:

```
Raw Capacity (C) = 2,000 GB

Layer                        Conservative   Aggressive   Applies To
─────────────────────────────────────────────────────────────────────
NTFS LZX (OS-level)         x1.3           x1.5         all files
Ternary sparsity (L3+L4)    x1.4           x1.7         AI data (60% of drive)
CAS dedup (L5)              x1.3           x1.5         all managed files
Delta encoding (L6)         x1.2           x1.4         model families (30% of drive)
Semantic compression (L7)   x1.3           x2.0         embeddings (10% of drive)

Combined (weighted average by data mix):
  Conservative: C x 1.3 x 1.25 x 1.3 x 1.1 x 1.05 = C x 2.46
  Aggressive:   C x 1.5 x 1.5  x 1.5 x 1.2 x 1.15 = C x 4.66

Effective Conservative: 2,000 x 2.46 =  ~4.9 TB
Effective Moderate:     2,000 x 3.5  =  ~7.0 TB
Effective Aggressive:   2,000 x 4.66 =  ~9.3 TB
Effective Maximum:      2,000 x 9.3  = ~18.6 TB  (ideal data: all AI, high dedup)
```

Note: the "maximum" figure requires nearly all data to be AI weights
with high model family overlap. The conservative figure assumes a
mixed-use drive. Real-world expectation for a NovaX drive with 102
Ollama models and substantial embedding caches: **7-9 TB effective**.

### Reporting

`/quantize/stats` returns both stored_bytes and effective_bytes.
The NovaX desktop panel can show:

```
Drive C:  [====================] 1.2 TB used
Effective: [========]            6.8 TB represented
Ratio:     5.67x
Technique breakdown:
  Ternary encode:  1.4x on 780 GB
  Sparsity RLE:    1.3x on 780 GB
  CAS dedup:       1.4x (38% shared blocks across 102 models)
  Delta encode:    1.3x (12 model families, 47 variants)
  Semantic:        2.1x on 89 GB embeddings
```

---

## 11. CONFIGURATION (config.json)

```json
{
    "version": "1.0.0",
    "port": 9912,
    "data_root": "C:\\NovaX\\data\\quantize",
    "managed_paths": [
        "C:\\NovaX\\models",
        "C:\\NovaX\\embeddings",
        "C:\\NovaX\\data"
    ],
    "layers": {
        "ternary_encode": {"enabled": true, "threshold_ai": 0.33, "threshold_embed": 0.10},
        "sparsity_rle":   {"enabled": true, "min_run": 3},
        "cas_dedup":      {"enabled": true, "bucket_count": 243, "scan_window": 13},
        "delta_encode":   {"enabled": true, "auto_detect_families": true},
        "semantic":       {"enabled": true, "min_variance_captured": 0.90, "min_cosine_sim": 0.95}
    },
    "background": {
        "optimize_interval_s": 13,
        "max_blocks_per_pass": 2187
    },
    "ns_window_s": 13,
    "block_size": 2187,
    "superblock_size": 28431
}
```

---

## 12. BOOT SEQUENCE

```
1. Load config.json (or create defaults)
2. Load stats.json (or initialize empty)
3. Load CAS index (scan bucket files, build in-memory hash map)
4. Load delta manifests
5. Register with orchestrator via POST /api/services/register
6. Start background optimization loop (every H13 seconds)
7. Listen on port 9912
8. Print harmonic banner
```

---

## 13. IMPLEMENTATION PRIORITY

Phase 1 (MVP):
  - Layers 1, 2, 5 (Ingest, Classify, CAS Dedup)
  - /health, /quantize/stats, /quantize/ingest, /quantize/cas/*
  - Enough to prove dedup on Ollama models

Phase 2:
  - Layers 3, 4 (Ternary Encode, Sparsity RLE)
  - /quantize/compress, /quantize/decompress
  - Measurable size reduction on AI weight files

Phase 3:
  - Layer 6 (Delta Encoding)
  - /quantize/delta/* endpoints
  - Model family registration and variant diffing

Phase 4:
  - Layer 7 (Semantic Compression)
  - /quantize/semantic/* endpoints
  - Embedding-specific optimizations

Phase 5:
  - /quantize/analyze, /quantize/optimize
  - N-S adaptive pipeline tuning
  - Desktop panel integration
  - Background optimization loop

---

## 14. RISKS AND MITIGATIONS

| Risk | Impact | Mitigation |
|------|--------|------------|
| Data corruption in CAS | Total: block lost | SHA-256 verify on every read; trit-fold checksum in header |
| Dedup ratio lower than expected | Moderate: less savings | Conservative estimates in reporting; analyze before ingest |
| Semantic compression quality loss | Moderate: bad embeddings | Hard floor at 0.95 cosine sim; fallback to no-compress |
| Delta reconstruction failure | High: model unusable | Full checksum validation; keep raw for 7 days before purge |
| CAS index corruption | High: can't find blocks | Index is rebuildable from block files (scan + rehash) |
| High Reynolds during ingest | Low: slow compression | Graceful degradation; background catch-up loop |

---

## 15. METRICS FOR SUCCESS

After Phase 1 deployment, validate:
1. CAS dedup ratio on 102 Ollama models is >= 1.2x
2. Block ingest throughput >= 100 MB/s (limited by disk, not CPU)
3. Block retrieval latency < 5ms for cached, < 50ms for cold
4. Zero data corruption across 1M block read/write cycles
5. Stats endpoint accurately reports effective vs stored bytes
