# NovaX Trit-Packed Inference Engine — Technical Specification
## Version 0.1 | 2026-03-20

---

## 0. Model Inventory (from architecture.json + train.py)

| Parameter          | Value          | Source        |
|--------------------|----------------|---------------|
| vocab_size         | 32,768         | architecture  |
| embedding_dim (D)  | 768            | architecture  |
| num_layers (L)     | 13             | H13           |
| num_heads (H)      | 12             | architecture  |
| head_dim (HD)      | 64             | architecture  |
| ffn_dim (F)        | 2,048          | architecture  |
| max_seq_len        | 512            | architecture  |
| inner_dim          | 768 (H*HD)     | derived       |

### Parameter Counts

**Per transformer layer (ternary weights):**
- Attention Q/K/V/Out: 4 * 768 * 768 = 2,359,296
- FFN gate/up/down: 3 * 768 * 2048 = 4,718,592
- **Layer total: 7,077,888 ternary params**

**All 13 layers: 92,012,544 ternary params**

**Non-ternary (fp16):**
- Embedding: 32,768 * 768 = 25,165,824 (fp16 lookup, NOT quantized)
- RMSNorm gamma: 13 * 2 * 768 + 768 = 20,736
- Per-row scales: 13 * (4*768 + 2*2048 + 768) = 101,504
- LM head: tied to embedding (0 extra)
- **FP16 total: 25,288,064 params**

**Grand total: ~117.3M params**

---

## 1. Trit-Packed Binary Weight Format (.trit v2)

The existing v1 `.trit` file (443 MB) is JSON with 2-bit packing into u32. This spec defines a **binary** v2 format optimized for mmap and streaming.

### 1.1 TZip Encoding: 5 Trits Per Byte

Each ternary weight is {-1, 0, +1}, mapped to trit values {0, 1, 2}:

```
trit_value = weight + 1
  -1 → 0
   0 → 1
  +1 → 2
```

5 trits pack into 1 byte using base-3 positional encoding:

```
byte_value = t0 + t1*3 + t2*9 + t3*27 + t4*81

Range: 0 to 2+2*3+2*9+2*27+2*81 = 242  (fits in uint8, max 243 states)
```

**Decode:**
```
t0 = byte_value % 3;  byte_value /= 3
t1 = byte_value % 3;  byte_value /= 3
t2 = byte_value % 3;  byte_value /= 3
t3 = byte_value % 3;  byte_value /= 3
t4 = byte_value
```

### 1.2 Binary File Layout

```
Offset  Size        Field
──────────────────────────────────────────────────
0x0000  4 bytes     Magic: "NVT2" (0x4E565432)
0x0004  4 bytes     Version: 2 (uint32-LE)
0x0008  4 bytes     num_layers (uint32-LE) = 13
0x000C  4 bytes     embed_dim (uint32-LE) = 768
0x0010  4 bytes     num_heads (uint32-LE) = 12
0x0014  4 bytes     head_dim (uint32-LE) = 64
0x0018  4 bytes     ffn_dim (uint32-LE) = 2048
0x001C  4 bytes     vocab_size (uint32-LE) = 32768
0x0020  4 bytes     max_seq_len (uint32-LE) = 512
0x0024  4 bytes     total_ternary_params (uint32-LE)
0x0028  8 bytes     reserved (zero)
──────────────────────────────────────────────────
HEADER: 48 bytes (0x30)

0x0030  ...         Layer Table (13 entries, 32 bytes each = 416 bytes)
                    Per entry:
                      offset_trit  (uint64-LE) — offset into file for packed trits
                      offset_scale (uint64-LE) — offset into file for fp16 scales
                      num_ternary  (uint32-LE) — ternary param count in this layer
                      num_scales   (uint32-LE) — scale param count in this layer
                      reserved     (uint64-LE)

0x01D0  ...         Embedding Table
                      embed_offset (uint64-LE) — offset to fp16 embedding data
                      embed_size   (uint64-LE) — size in bytes

0x01E0  ...         FP16 Norm Weights
                      norm_offset  (uint64-LE) — offset to fp16 norm gammas
                      norm_size    (uint64-LE) — size in bytes

──── DATA SECTION ────

[embed_offset]      Embedding: 32768 * 768 * 2 = 48,234,496 bytes (fp16)

[layer 0 trit]      Packed trits for layer 0: 7,077,888 trits / 5 = 1,415,578 bytes
[layer 0 scale]     Scales for layer 0: (4*768 + 2*2048 + 768) * 2 = 15,616 bytes (fp16)

[layer 1 trit]      ...
[layer 1 scale]     ...
...
[layer 12 trit]     Last layer packed trits
[layer 12 scale]    Last layer scales

[norm_offset]       RMSNorm gammas: (13*2 + 1) * 768 * 2 = 41,472 bytes (fp16)
```

### 1.3 Size Budget

| Component              | Params       | Encoding | Bytes        | MB     |
|------------------------|-------------|----------|-------------|--------|
| Header + tables        | —           | —        | 512          | 0.00   |
| Embedding              | 25,165,824  | fp16     | 50,331,648   | 50.33  |
| Ternary weights (TZip) | 92,012,544  | 5/byte   | 18,402,509   | 18.40  |
| Per-row scales         | 101,504     | fp16     | 203,008      | 0.20   |
| RMSNorm gammas         | 20,736      | fp16     | 41,472       | 0.04   |
| **TOTAL**              | **117.3M**  |          | **68,979,149** | **68.98** |

**Compression: 443 MB (v1 JSON) → 69 MB (v2 binary). 6.4x reduction.**

Compared to float32 PyTorch checkpoint (1.41 GB best.pt): **20.5x reduction.**

### 1.4 Per-Layer Budget

Each transformer layer:
- Ternary data: 7,077,888 / 5 = 1,415,578 bytes ≈ **1.35 MB**
- Scales: 7,808 scales * 2 bytes = 15,616 bytes ≈ **0.015 MB**
- **Total per layer: ~1.37 MB**
- All 13 layers: ~17.8 MB

---

## 2. Trit Matrix Multiply Algorithm

### 2.1 Core Insight

Since every weight w[i][j] is in {-1, 0, +1}, the operation `y[i] += w[i][j] * x[j]` becomes:

```
if w == +1:  y[i] += x[j]    (addition)
if w == -1:  y[i] -= x[j]    (subtraction)
if w ==  0:  skip             (no-op)
```

**Zero multiplications. Only conditional add/subtract.**

After accumulation, apply per-row scale: `y[i] *= scale[i]`

### 2.2 Pseudocode: trit_matmul

```
function trit_matmul(x: float[N], w_packed: byte[M][cols_packed], scales: float16[M]) -> float[M]:
    // x: input vector, length N (e.g., 768)
    // w_packed: M rows of TZip-packed trits, each row = ceil(N/5) bytes
    // scales: M per-row scale factors
    // Returns: output vector, length M

    y = float[M]  // zero-initialized

    for i in 0..M:
        acc = 0.0
        j = 0  // input index
        for b in 0..cols_packed:
            byte_val = w_packed[i][b]

            // Unpack 5 trits from this byte
            for k in 0..5:
                if j >= N: break
                trit = byte_val % 3
                byte_val = byte_val / 3  // integer division

                // trit: 0 = weight is -1, 1 = weight is 0, 2 = weight is +1
                if trit == 2:
                    acc += x[j]
                elif trit == 0:
                    acc -= x[j]
                // trit == 1: skip (weight is zero)

                j += 1

        y[i] = acc * float(scales[i])

    return y
```

### 2.3 Batched Version for Sequence Processing

For a sequence of T tokens, each with D-dimensional embedding:

```
function trit_matmul_batch(X: float[T][N], w_packed: byte[M][cols_packed], scales: float16[M]) -> float[T][M]:
    Y = float[T][M]
    for t in 0..T:
        Y[t] = trit_matmul(X[t], w_packed, scales)
    return Y
```

### 2.4 Optimized: Lookup Table Decode

Pre-compute a decode table for all 243 byte values:

```
// Build once at init
TRIT_TABLE: int8[243][5]  // 1,215 bytes, fits in L1 cache

for v in 0..243:
    tmp = v
    for k in 0..5:
        TRIT_TABLE[v][k] = (tmp % 3) - 1   // maps to {-1, 0, +1} directly
        tmp /= 3

// Inner loop becomes:
for b in 0..cols_packed:
    trits = TRIT_TABLE[w_packed[i][b]]   // single lookup, 5 trits
    for k in 0..5:
        if j >= N: break
        t = trits[k]
        if t != 0:
            acc += t * x[j]    // t is +1 or -1, so this is add or subtract
        j += 1
```

Even better — since `t` is only +1 or -1, the compiler can branch-predict:
```
    if t > 0: acc += x[j]
    else if t < 0: acc -= x[j]
```

### 2.5 SIMD Kernel Design (AVX2 / NEON)

For 8-wide SIMD (AVX2 float32):

```
// Process 8 output rows simultaneously
// Load 8 accumulator vectors (one per output row)
// For each group of 5 input elements:
//   1. Load byte from each of 8 rows → 8 bytes
//   2. Lookup TRIT_TABLE for each → 8 x 5 trits
//   3. Broadcast x[j] to all 8 lanes
//   4. Conditional add/sub based on trit sign

// Alternatively: "column-major" approach
// Process all M output rows for one input element at a time:
//   - Extract column j from all M rows (requires columnar trit storage)
//   - Multiply (add/sub) x[j] into all M accumulators

// The column-major approach is better for SIMD because:
//   - x[j] is broadcast once
//   - The trit column determines add/sub/skip for all rows
//   - Can process 8 rows per SIMD lane
```

**Columnar TZip variant** (optional future optimization):
Store trits in column-major order so that column j of all M rows is contiguous.
This allows vectorized accumulation across output rows for a single input element.

### 2.6 GPU Kernel Design (CUDA)

```cuda
// One thread block per output row (or group of rows)
// Each thread handles a chunk of the input dimension
// Shared memory: load x[] once, all threads in block read it

__global__ void trit_matmul_kernel(
    const float* x,           // [N]
    const uint8_t* w_packed,  // [M][ceil(N/5)]
    const __half* scales,     // [M]
    float* y,                 // [M]
    int M, int N
) {
    int row = blockIdx.x;           // output row
    int tid = threadIdx.x;          // thread within block
    int cols_packed = (N + 4) / 5;

    // Load x into shared memory
    extern __shared__ float sx[];
    for (int i = tid; i < N; i += blockDim.x)
        sx[i] = x[i];
    __syncthreads();

    // Each thread accumulates a portion of the dot product
    float acc = 0.0f;
    int start_byte = tid * (cols_packed / blockDim.x);
    int end_byte = (tid + 1) * (cols_packed / blockDim.x);
    if (tid == blockDim.x - 1) end_byte = cols_packed;

    for (int b = start_byte; b < end_byte; b++) {
        uint8_t packed = w_packed[row * cols_packed + b];
        int base_j = b * 5;

        // Unroll 5 trits
        #pragma unroll
        for (int k = 0; k < 5; k++) {
            int j = base_j + k;
            if (j >= N) break;
            int trit = packed % 3;
            packed /= 3;
            if (trit == 2) acc += sx[j];
            else if (trit == 0) acc -= sx[j];
        }
    }

    // Warp-level reduction
    for (int offset = 16; offset > 0; offset >>= 1)
        acc += __shfl_down_sync(0xFFFFFFFF, acc, offset);

    // Thread 0 writes result with scale
    if (tid == 0) {
        y[row] = acc * __half2float(scales[row]);
    }
}
```

---

## 3. Memory-Mapped Inference

### 3.1 Architecture

```
┌─────────────────────────────────────────────────┐
│                    .trit v2 File (69 MB)        │
│  ┌──────────┬──────────┬───────────────────────┐│
│  │  Header  │  Embed   │  Layer 0..12  │ Norms ││
│  │  (48 B)  │ (50 MB)  │  (18 MB)      │(41 KB)││
│  └──────────┴──────────┴───────────────────────┘│
└─────────────────────────────────────────────────┘
         ↑ mmap()
         │
    OS page cache handles which 4KB pages are resident
```

### 3.2 Streaming Layer-by-Layer

During inference, only one layer is active at a time:

```
function inference_forward(input_ids: int[T]) -> float[T][V]:

    // 1. Embedding lookup — touches embed section of mmap
    //    Cost: T * D * 2 bytes of embed pages = T * 1536 bytes
    x = embed_lookup(input_ids)   // float[T][D]
    x = x * sqrt(D)

    // 2. Process each transformer layer
    for layer_idx in 0..13:
        // OS loads ~1.37 MB of pages for this layer
        x = transformer_block(x, layer_idx)
        // Previous layer's pages can be evicted from RAM

    // 3. Final norm + LM head
    x = rmsnorm(x, final_norm_gamma)
    logits = trit_matmul_batch(x, lm_head_packed, lm_head_scales)

    return logits
```

**Peak resident memory per layer:**
- Ternary weights: ~1.35 MB (trit-packed, read-only via mmap)
- Scales: ~0.015 MB
- Activations: T * D * 4 bytes = 512 * 768 * 4 = 1.5 MB (float32)
- Attention scratch: T * T * H * 4 = 512 * 512 * 12 * 4 = 12.6 MB
- **Peak per layer: ~15.5 MB**

**Total working set:**
- One layer active: 15.5 MB
- Embedding (first access only, then evictable): 50 MB first pass
- KV cache (if caching): T * 2 * D * L * 4 = 512 * 2 * 768 * 13 * 4 = 40.5 MB
- **Steady-state inference: ~56 MB** (with KV cache, without embedding resident)

vs current PyTorch: **~1.5 GB** (full model in VRAM as float32)

### 3.3 KV Cache for Autoregressive Generation

During token-by-token generation, cache K and V from previous positions:

```
struct KVCache:
    k_cache: float[L][T_max][H][HD]   // 13 * 512 * 12 * 64 * 4 = 20.25 MB
    v_cache: float[L][T_max][H][HD]   // 20.25 MB
    position: int                       // current sequence position

    // Total: 40.5 MB for full 512-token context
```

Each generation step only computes Q/K/V for the new token (not the whole sequence),
then attends to the full cached K/V.

### 3.4 mmap Implementation

```
// POSIX (Linux/macOS):
fd = open("novax_llm_v1.trit", O_RDONLY)
base = mmap(NULL, file_size, PROT_READ, MAP_PRIVATE, fd, 0)
madvise(base, file_size, MADV_SEQUENTIAL)  // hint for layer streaming

// Windows (via CreateFileMapping):
hFile = CreateFileA("novax_llm_v1.trit", GENERIC_READ, ...)
hMap = CreateFileMappingA(hFile, NULL, PAGE_READONLY, ...)
base = MapViewOfFile(hMap, FILE_MAP_READ, 0, 0, 0)

// Rust:
let file = File::open("novax_llm_v1.trit")?;
let mmap = unsafe { MmapOptions::new().map(&file)? };

// NovaLang: new builtin
let mapped = mmap_open("novax_llm_v1.trit")
let layer_ptr = mmap_slice(mapped, offset, length)
```

---

## 4. NovaLang Native Path

### 4.1 New Builtins Required

Add these to novalang.py's builtin registry (currently 58+ builtins):

| Builtin              | Signature                                                  | Returns          |
|----------------------|------------------------------------------------------------|------------------|
| `trit_matmul`        | `trit_matmul(x_f32, w_trit_packed, scales_f16, M, N)`     | float[M]         |
| `trit_decode`        | `trit_decode(packed_byte)`                                 | int[5] in {-1,0,+1} |
| `mmap_open`          | `mmap_open(filepath)`                                      | handle           |
| `mmap_slice`         | `mmap_slice(handle, offset, length)`                       | byte[]           |
| `mmap_close`         | `mmap_close(handle)`                                       | +1/0/-1          |
| `tensor_new`         | `tensor_new(shape, dtype)`                                 | tensor handle    |
| `tensor_rmsnorm`     | `tensor_rmsnorm(x, gamma, eps)`                            | float[]          |
| `tensor_softmax`     | `tensor_softmax(x)`                                        | float[]          |
| `tensor_rope`        | `tensor_rope(q, k, position, head_dim)`                    | (q_rot, k_rot)   |

### 4.2 trit_matmul Builtin Implementation (C/Rust backing)

This is the performance-critical kernel. It must be implemented in native code
(C or Rust), callable from NovaLang via FFI.

```rust
// Rust implementation for novalang.exe FFI

/// Precomputed decode table: 243 entries, each 5 trits as i8 {-1, 0, +1}
static TRIT_LUT: [[i8; 5]; 243] = {
    let mut table = [[0i8; 5]; 243];
    let mut v = 0u8;
    while v < 243 {
        let mut tmp = v;
        let mut k = 0;
        while k < 5 {
            table[v as usize][k] = (tmp % 3) as i8 - 1;
            tmp /= 3;
            k += 1;
        }
        v += 1;
    }
    table
};

/// Core trit matmul: y = (W_ternary * x) * scales
/// w_packed: row-major, M rows, each ceil(N/5) bytes
/// x: float32[N], scales: float16[M], y: float32[M]
pub fn trit_matmul(
    x: &[f32],             // input vector [N]
    w_packed: &[u8],       // packed weights [M * cols_packed]
    scales: &[f16],        // per-row scales [M]
    m: usize,              // output dim
    n: usize,              // input dim
) -> Vec<f32> {
    let cols_packed = (n + 4) / 5;
    let mut y = vec![0.0f32; m];

    for i in 0..m {
        let row = &w_packed[i * cols_packed..(i + 1) * cols_packed];
        let mut acc = 0.0f32;
        let mut j = 0usize;

        for &byte_val in row.iter() {
            let trits = &TRIT_LUT[byte_val as usize];

            // Unrolled 5-wide
            for k in 0..5 {
                if j >= n { break; }
                let t = trits[k];
                if t == 1 {
                    acc += x[j];
                } else if t == -1 {
                    acc -= x[j];
                }
                // t == 0: no-op (weight is zero)
                j += 1;
            }
        }

        y[i] = acc * f16::to_f32(scales[i]);
    }

    y
}
```

### 4.3 NovaLang Inference Script

Full inference in NovaLang (pseudocode using new builtins):

```nova
// novax_trit_inference.nova — Pure NovaLang inference, no Python

let model_path = "C:/NovaX/nova_llm/checkpoints/novax_llm_v2.trit"

// ── Load model via mmap ──
let model = mmap_open(model_path)
let header = trit_header_parse(mmap_slice(model, 0, 48))
let layer_table = trit_layer_table(mmap_slice(model, 48, 416))

// ── Build decode LUT (243 entries) ──
let TRIT_LUT = trit_build_lut()

// ── Embedding lookup ──
fn embed(token_id, model, header):
    let embed_offset = header.embed_offset
    let dim = header.embed_dim
    // Read fp16 row, convert to f32
    let row_bytes = mmap_slice(model, embed_offset + token_id * dim * 2, dim * 2)
    return fp16_to_f32(row_bytes)

// ── Single transformer layer ──
fn transformer_layer(x, layer_idx, model, layer_table):
    let layer = layer_table[layer_idx]
    let trit_data = mmap_slice(model, layer.offset_trit, layer.trit_size)
    let scale_data = mmap_slice(model, layer.offset_scale, layer.scale_size)

    // RMSNorm → Attention
    let h = tensor_rmsnorm(x, layer.attn_norm_gamma, 1e-6)

    // Q, K, V projections (each is a trit_matmul)
    let D = 768
    let inner = 768
    let q_packed = slice(trit_data, 0, inner * D / 5)
    let q_scales = slice(scale_data, 0, inner * 2)
    let q = trit_matmul(h, q_packed, q_scales, inner, D)

    // ... K, V, Out projections similarly offset ...

    // Attention computation
    let attn_out = multihead_attention(q, k, v, num_heads, head_dim)
    let x2 = x + trit_matmul(attn_out, out_packed, out_scales, D, inner)

    // RMSNorm → FFN (SwiGLU)
    let h2 = tensor_rmsnorm(x2, layer.ffn_norm_gamma, 1e-6)
    let gate = gelu(trit_matmul(h2, gate_packed, gate_scales, F, D))
    let up = trit_matmul(h2, up_packed, up_scales, F, D)
    let ffn_out = trit_matmul(gate * up, down_packed, down_scales, D, F)

    return x2 + ffn_out

// ── Full forward pass ──
fn forward(token_ids):
    // Embed
    let x = []
    for3 id in token_ids:
        let e = embed(id, model, header)
        x = append(x, scale(e, sqrt(768)))

    // 13 transformer layers
    for3 i in range(0, 13):
        x = transformer_layer(x, i, model, layer_table)

    // Final norm + LM head
    x = tensor_rmsnorm(x, final_norm_gamma, 1e-6)
    let logits = trit_matmul(x[-1], lm_head_packed, lm_head_scales, 32768, 768)
    return logits

// ── Autoregressive generation ──
fn generate(prompt, max_tokens):
    let ids = encode(prompt)
    for3 step in range(0, max_tokens):
        let logits = forward(ids)
        let next_id = sample_top_k(logits, 13, 0.7)
        if3 next_id == 2:   // EOS
            return decode(ids)
        ids = append(ids, next_id)
    return decode(ids)
```

### 4.4 Builtin Registration in novalang.py

Each builtin follows the micro-tool pattern (returns +1/0/-1 for status):

```python
# In novalang.py builtin registry:
"trit_matmul": {
    "args": ["x_f32", "w_packed", "scales", "M", "N"],
    "body": lambda args, env: _native_trit_matmul(args[0], args[1], args[2], args[3], args[4]),
    "doc": "Ternary matrix multiply: y = (W_trit * x) * scales. No multiplications."
},
"mmap_open": {
    "args": ["filepath"],
    "body": lambda args, env: _native_mmap_open(args[0]),
    "doc": "Memory-map a file for zero-copy reads."
},
```

The `_native_*` functions would call into a compiled shared library
(`trit_engine.dll` on Windows, `trit_engine.so` on Linux) via ctypes or cffi.

---

## 5. Conversion Script: v1 JSON → v2 Binary

Pseudocode for the one-time conversion from the existing 443 MB JSON `.trit`
to the new 69 MB binary format:

```python
def convert_v1_to_v2(v1_path, v2_path):
    # Load existing JSON trit file
    with open(v1_path) as f:
        v1 = json.load(f)

    config = v1["config"]["model"]
    D = config["embedding_dim"]      # 768
    L = config["num_layers"]         # 13
    V = config["vocab_size"]         # 32768
    F = config["ffn_dim"]            # 2048

    with open(v2_path, "wb") as out:
        # ── Write header (48 bytes) ──
        out.write(b"NVT2")
        out.write(struct.pack("<I", 2))       # version
        out.write(struct.pack("<I", L))
        out.write(struct.pack("<I", D))
        out.write(struct.pack("<I", config["num_heads"]))
        out.write(struct.pack("<I", config["head_dim"]))
        out.write(struct.pack("<I", F))
        out.write(struct.pack("<I", V))
        out.write(struct.pack("<I", config["max_seq_len"]))
        out.write(struct.pack("<I", v1["total_ternary_params"]))
        out.write(b"\x00" * 8)               # reserved

        # ── Placeholder for layer table (filled after data write) ──
        layer_table_offset = out.tell()
        out.write(b"\x00" * (L * 32))        # 13 * 32 = 416 bytes

        # ── Embed/norm offset table ──
        embed_table_offset = out.tell()
        out.write(b"\x00" * 32)              # 4 uint64s

        # ── Write embedding data (fp16) ──
        embed_data_offset = out.tell()
        embed_weights = v1["layers"]["token_emb.embedding.weight"]
        embed_f16 = np.array(embed_weights, dtype=np.float16)
        out.write(embed_f16.tobytes())

        # ── Write each layer's trit-packed weights + scales ──
        layer_entries = []
        for layer_idx in range(L):
            prefix = f"layers.{layer_idx}."

            # Collect all ternary weight names for this layer
            ternary_names = [
                f"{prefix}attn.q_proj.weight",
                f"{prefix}attn.k_proj.weight",
                f"{prefix}attn.v_proj.weight",
                f"{prefix}attn.out_proj.weight",
                f"{prefix}ffn_gate.weight",
                f"{prefix}ffn_up.weight",
                f"{prefix}ffn_down.weight",
            ]
            scale_names = [n.replace(".weight", ".scale") for n in ternary_names]

            # Pack trits using TZip (5 per byte, base-3)
            trit_offset = out.tell()
            total_ternary = 0
            for name in ternary_names:
                u32_packed = v1["layers"][name]  # list of u32 (v1: 16 trits per u32, 2-bit)
                # Decode v1 2-bit → raw trits → re-encode as TZip
                raw_trits = decode_v1_u32_to_trits(u32_packed)
                tzip_bytes = encode_trits_to_tzip(raw_trits)
                out.write(bytes(tzip_bytes))
                total_ternary += len(raw_trits)

            # Write scales (fp16)
            scale_offset = out.tell()
            total_scales = 0
            for name in scale_names:
                scale_vals = v1["layers"][name]  # list of float16
                scale_f16 = np.array(scale_vals, dtype=np.float16)
                out.write(scale_f16.tobytes())
                total_scales += len(scale_vals)

            layer_entries.append((trit_offset, scale_offset, total_ternary, total_scales))

        # ── Write norm weights ──
        norm_offset = out.tell()
        # ... write all RMSNorm gamma vectors as fp16 ...

        # ── Backfill layer table ──
        out.seek(layer_table_offset)
        for trit_off, scale_off, n_tern, n_scale in layer_entries:
            out.write(struct.pack("<QQ II Q", trit_off, scale_off, n_tern, n_scale, 0))

        # ── Backfill embed/norm offset table ──
        out.seek(embed_table_offset)
        out.write(struct.pack("<QQ QQ",
            embed_data_offset, V * D * 2,
            norm_offset, norm_size))


def encode_trits_to_tzip(trits):
    """Pack list of trit values {0,1,2} into TZip bytes (5 per byte)."""
    result = []
    for i in range(0, len(trits), 5):
        chunk = trits[i:i+5]
        byte_val = 0
        for k, t in enumerate(chunk):
            byte_val += t * (3 ** k)
        result.append(byte_val)
    return result
```

---

## 6. Performance Projections

### 6.1 Arithmetic Comparison

| Operation         | Float32 matmul          | Trit matmul              |
|-------------------|------------------------|--------------------------|
| Multiplications   | M * N = 589,824/layer  | **0** (add/sub only)     |
| Additions         | M * N                  | ~M * N * density         |
| Memory reads (weights) | M * N * 4 bytes   | M * N / 5 bytes          |
| Memory bandwidth  | 1x baseline            | **20x less** (trit-packed) |

Weight density (non-zero ratio) depends on training. Typical ternary: ~60-70% non-zero.
For 70% density: effective ops ≈ 0.7 * M * N additions.

### 6.2 Throughput Estimates (RTX 4060, 8GB VRAM)

| Metric                          | Float32 (current)  | Trit v2 (projected) |
|---------------------------------|--------------------|----------------------|
| Model in VRAM                   | ~1.4 GB            | ~69 MB               |
| Weight memory bandwidth/token   | ~450 MB            | ~22 MB               |
| Tokens/sec (generation)         | ~15-25 tok/s       | ~80-150 tok/s        |
| Time to first token             | ~200 ms            | ~50-80 ms            |
| Max batch size (8GB VRAM)       | 1-2                | 8-16                 |

The primary bottleneck for LLM inference is **memory bandwidth**, not compute.
By shrinking weights 20x, we shift from memory-bound to compute-bound,
unlocking the GPU's full arithmetic throughput.

### 6.3 CPU Inference (no GPU needed)

With weights at 69 MB and per-layer footprint of ~15 MB, the entire model
fits comfortably in CPU cache hierarchy:

| Level   | Size (typical) | What fits                          |
|---------|----------------|------------------------------------|
| L1      | 64 KB          | TRIT_LUT (1.2 KB) + hot accum     |
| L2      | 512 KB         | One weight matrix row group        |
| L3      | 16 MB          | One full layer + activations       |
| RAM     | 32 GB          | Entire model + KV cache            |

Projected CPU throughput (Zen 4, single core): ~5-10 tok/s
With AVX2 (8-wide SIMD): ~15-30 tok/s
With multithreading (8 cores): ~40-80 tok/s

---

## 7. Implementation Roadmap

### Phase 1: Binary Format + Converter (1-2 days)
- [ ] Implement `convert_v1_to_v2.py`: JSON .trit → binary .trit v2
- [ ] Validate: decode v2, compare against v1 weights bit-for-bit
- [ ] File: `C:\NovaX\nova_llm\trit_converter.py`

### Phase 2: Python Trit Inference (2-3 days)
- [ ] `trit_inference.py`: Pure Python trit_matmul using numpy
- [ ] mmap-based weight loading
- [ ] Validate: identical logits to current float32 inference_server.py
- [ ] Benchmark: measure actual throughput improvement

### Phase 3: Native Trit Kernel (3-5 days)
- [ ] Rust library `trit_engine` with trit_matmul, mmap, LUT
- [ ] Compile to `trit_engine.dll` (Windows) / `.so` (Linux)
- [ ] Python ctypes wrapper for validation
- [ ] SIMD (AVX2) inner loop

### Phase 4: NovaLang Integration (2-3 days)
- [ ] Register new builtins in novalang.py: trit_matmul, mmap_open, etc.
- [ ] Wire builtins to Rust FFI via ctypes
- [ ] Write `novax_trit_inference.nova` — full inference in NovaLang
- [ ] Validate: identical outputs to Python path

### Phase 5: GPU Kernel (optional, 3-5 days)
- [ ] CUDA kernel for trit_matmul
- [ ] Integration via cupy or direct CUDA compilation
- [ ] Benchmark against float32 PyTorch baseline

---

## 8. Summary of Key Numbers

```
Model:          117.3M params, 13 layers, 768 dim, 12 heads
Ternary params: 92M (78.5% of total)
FP16 params:    25.3M (21.5%, mostly embedding)

File sizes:
  best.pt (float32 PyTorch):  1,414 MB
  novax_llm_v1.trit (JSON):     443 MB
  novax_llm_v2.trit (binary):    69 MB  ← target

Memory during inference:
  Current (PyTorch float32):  ~1,400 MB in VRAM
  Trit v2 (mmap streaming):     ~56 MB working set

Arithmetic:
  Float32: 92M multiplications per token per layer
  Trit:    0 multiplications, ~64M additions per token per layer

Ternary encoding:
  3^5 = 243 states per byte (TZip)
  1.585 bits/trit (information-theoretic: log2(3))
  1.6 bits/trit actual (5 trits in 8 bits)
  Efficiency: 99.1% of Shannon limit
```
