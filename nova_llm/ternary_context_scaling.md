# Ternary Context Scaling: Mathematical Foundation
## NovaX LLM — From 512 Tokens to Trillions

### Architecture Reference (from architecture.json)
```
embed_dim    = 768
num_layers   = 13  (H13)
num_heads    = 12
head_dim     = 64
ffn_dim      = 2048
max_seq_len  = 512  (current)
BLOCK        = 2187 (3^7, target page size)
```

---

## 1. KV Cache Quantization to Trits

### 1.1 Current KV Cache Cost (float32)

Per token, per layer, we store one K vector and one V vector, each of dimension
`num_heads * head_dim = 12 * 64 = 768` floats.

```
bytes_per_token_per_layer = 2 * 768 * 4 bytes = 6,144 bytes
bytes_per_token_all_layers = 6,144 * 13 = 79,872 bytes ≈ 78 KB
```

For 512 tokens: `512 * 79,872 = 40,894,464 bytes ≈ 39 MB`

### 1.2 Ternary Quantization of K/V

**Method**: Quantize each K and V activation to {-1, 0, +1} with a per-head
scaling factor (float16).

For a vector v of dimension d:
```
δ = 0.7 * mean(|v|)                    # adaptive threshold (same as weight STE)
v_ternary[i] = +1  if v[i] > +δ
             =  0  if |v[i]| ≤ δ
             = -1  if v[i] < -δ
α = v · v_ternary / (v_ternary · v_ternary)   # optimal scaling factor (LSQ)
```

The reconstructed vector is `α * v_ternary`, where α is a single float16 scalar
per head per token per layer (for K and V separately).

**Why this works**: BitNet b1.58 (Ma et al., 2024) showed that ternary
{-1,0,+1} weights preserve >95% of full-precision quality in linear layers.
The same principle applies to KV activations because attention is bilinear:
`softmax(Q·K^T/√d) · V`. If K and V are both quantized with per-head scales,
the attention computation becomes:

```
attn = softmax(Q · (αK * K_ternary)^T / √d) · (αV * V_ternary)
     = αV * softmax(αK * Q · K_ternary^T / √d) · V_ternary
```

The scale factors αK and αV fold into the softmax temperature and output
scaling. The softmax is a monotonic-preserving operation on its inputs, so
the relative ordering of attention scores is preserved as long as
`αK * Q · K_ternary^T` has the same argmax structure as `Q · K^T`.

**Key insight**: K_ternary^T is a matrix of {-1,0,+1}, so `Q · K_ternary^T`
reduces to additions and subtractions — no multiplications needed. This is
the same computational advantage as ternary weight multiplication.

### 1.3 TZip Packing for KV Cache

TZip encodes 5 trits into 1 byte (3^5 = 243 ≤ 255).

Each K or V vector per head has `head_dim = 64` trits.
```
64 trits / 5 trits_per_byte = 13 bytes (with 1 trit wasted per vector)
```

Plus 2 bytes for the float16 scale factor = **15 bytes per head per K or V**.

```
bytes_per_token_per_layer = 2 (K+V) * 12 heads * 15 bytes = 360 bytes
bytes_per_token_all_layers = 360 * 13 layers = 4,680 bytes ≈ 4.57 KB
```

### 1.4 Compression Ratio

```
float32 KV:  79,872 bytes/token
TZip KV:      4,680 bytes/token
Ratio:        79,872 / 4,680 = 17.1× compression
```

**Alternative: 2-bit packing** (as used in weight export, 16 trits per u32):
```
64 trits * 2 bits / 8 = 16 bytes per head per K or V
+ 2 bytes scale = 18 bytes per head
bytes_per_token_all = 2 * 12 * 18 * 13 = 5,616 bytes ≈ 5.49 KB
```

TZip is 18% more efficient than 2-bit packing (4,680 vs 5,616).

### 1.5 Attention Quality Impact

| Method | Bits/value | Attention cosine sim vs fp32 | Source |
|--------|-----------|------------------------------|--------|
| fp16   | 16        | 0.9999                       | baseline |
| int8   | 8         | 0.998                        | SmoothQuant (Xiao et al., 2023) |
| int4   | 4         | 0.990                        | KIVI (Liu et al., 2024) |
| 1.58-bit (ternary) | 1.58 | 0.96-0.98 (projected) | BitNet b1.58 extrapolation |

The 2-4% attention degradation from ternary KV can be partially recovered via:
1. **Residual correction**: Store `v - α*v_ternary` as a sparse fp16 vector for
   the top-k largest residuals (k=8 per head adds 16 bytes, <10% overhead)
2. **Hot-token fp16**: Keep the most recent `RE_LAMINAR = 27` tokens in full
   fp16 for high-fidelity local attention
3. **Outlier channels**: Following SmoothQuant, keep 2-3 outlier channels per
   head in fp16 (6 bytes overhead per head, negligible)

---

## 2. Hierarchical Memory Architecture

### 2.1 Three-Tier Design

```
┌─────────────────────────────────────────────────┐
│  TIER 1: VRAM (Hot)     — 8 GB budget           │
│  Format: fp16 KV for recent + ternary TZip      │
│  Latency: 0.1-1 μs                              │
│  Contains: active attention window               │
├─────────────────────────────────────────────────┤
│  TIER 2: RAM (Warm)     — 32 GB budget           │
│  Format: TZip-packed ternary KV + scales         │
│  Latency: 10-100 ns system memory               │
│  Contains: recently evicted pages                │
├─────────────────────────────────────────────────┤
│  TIER 3: Disk (Cold)    — 1+ TB budget           │
│  Format: TZip + LZ4 compressed pages            │
│  Latency: 0.1-1 ms (NVMe SSD)                   │
│  Contains: full conversation history             │
│  Includes: per-page attention summary vectors    │
└─────────────────────────────────────────────────┘
```

### 2.2 Page Structure

One page = 2187 tokens (BLOCK = 3^7).

```
page_size_tzip = 2187 tokens * 4,680 bytes/token = 10,235,160 bytes ≈ 9.76 MB
page_size_fp16 = 2187 tokens * 2 * 12 * 64 * 2 bytes * 13 = 51,757,056 bytes ≈ 49.4 MB
```

Each page also stores:
- **Summary vector**: mean of all K vectors per head per layer, fp16.
  Size: `13 layers * 12 heads * 64 dims * 2 bytes = 19,968 bytes ≈ 20 KB`
- **Page metadata**: token range, timestamp, Reynolds number, access count.
  Size: 256 bytes
- **Attention digest**: top-27 most-attended token positions per head (for
  sparse retrieval). Size: `13 * 12 * 27 * 2 bytes = 8,424 bytes ≈ 8 KB`

Total page overhead: ~28 KB (0.3% of page data).

### 2.3 Reynolds Number Eviction Policy

Define the Reynolds number for a page as a measure of attention turbulence:

```
Re(page) = (ρ * v * L) / μ

where:
  ρ = access_frequency     (hits in last N queries / N)
  v = recency_velocity     (1.0 / seconds_since_last_access, normalized)
  L = content_salience     (max attention score this page received from any query)
  μ = age_viscosity        (log2(age_in_tokens + 1) / log2(total_tokens + 1))
```

Normalized so Re ∈ [0, ∞):

```
Re = (access_freq * recency * max_attn) / age_factor
```

**Eviction thresholds** (from 3-5-7-13 constants):

| Re range | Regime | Action |
|----------|--------|--------|
| Re < 27 (3^3) | Laminar | Keep in current tier (stable, useful) |
| 27 ≤ Re < 125 (5^3) | Transitional | Monitor, candidate for demotion |
| 125 ≤ Re < 343 (7^3) | Weakly turbulent | Demote one tier on next eviction pass |
| Re ≥ 343 | Fully turbulent | Evict immediately (compress + demote) |

**Wait — Re should be INVERTED for eviction**: high Re in fluid dynamics
means turbulent (chaotic, unpredictable). For memory, high turbulence means
the page is "noisy" — low utility. So:

```
Re(page) = age_factor / (access_freq * recency * max_attn + ε)
```

- Frequently accessed, recent, high-attention pages → low Re → laminar → KEEP
- Old, unused, low-attention pages → high Re → turbulent → EVICT

### 2.4 Approximate Attention Over Cold Pages

For a query Q attending over a cold page (on disk), we avoid loading the
full 9.76 MB page by using the **summary vectors**:

```
attn_approx(Q, page_j) = softmax(Q · S_j^T / √d)
```

where `S_j` is the page's summary K-vector (mean of all K vectors in the page).
This gives a single scalar attention weight per head per layer for the
entire page.

If `attn_approx > threshold_load` (calibrated per model), promote the page
to warm/hot tier and compute full attention.

**Hierarchical attention protocol**:

```
1. Compute full attention over VRAM pages (hot)
2. Compute summary attention over RAM page summaries (warm)
3. If any warm summary attention > threshold: load that page to VRAM, evict lowest-Re VRAM page
4. For cold pages: only check summaries periodically (every BLOCK tokens)
5. Aggregate: final_attn = α_hot * attn_hot + α_warm * attn_warm_approx
   where α_hot + α_warm = 1, α_hot ≥ 0.9 (local context dominates)
```

---

## 3. Context Scaling Math

### 3.1 Memory Budgets

Assume model weights consume a fixed VRAM footprint:
```
Model params: ~117M (from architecture: 768 embed, 13 layers, 12 heads, 2048 ffn)
  Actually let's compute:
    Embedding:  32768 * 768 = 25,165,824
    Per layer:
      Q,K,V,O projections: 4 * 768 * 768 = 2,359,296
      FFN gate+up+down: 3 * 768 * 2048 = 4,718,592
      Norms + scales: ~3,000
      Subtotal: ~7,080,888
    13 layers: 92,051,544
    LM head (tied): 0
    Total: ~117,217,368 ≈ 117M

  In fp32 (training): 117M * 4 = 468 MB
  In ternary (inference): 117M * 2 bits / 8 = 29.25 MB (+ scales ≈ 35 MB)
```

**Available VRAM for KV cache** (inference, ternary weights):
```
total_vram       = 8,192 MB  (8 GB)
model_weights    =    35 MB  (ternary packed + scales)
activations      =   200 MB  (buffer for batch=1 forward pass)
cuda_overhead    =   200 MB
kv_budget_vram   = 7,757 MB
```

**Available RAM for KV cache**:
```
total_ram        = 32,768 MB (32 GB)
os_overhead      =  4,000 MB
kv_budget_ram    = 28,768 MB
```

### 3.2 Tokens per Tier

#### Tier 1: VRAM — TZip Ternary KV

```
bytes_per_token = 4,680 bytes = 4.57 KB

tokens_vram = 7,757 MB / 4.57 KB = 7,757 * 1024 * 1024 / 4,680
            = 7,757 * 1,048,576 / 4,680
            = 8,132,755,456 / 4,680
            = 1,737,776 tokens
            ≈ 1.74 million tokens
```

#### Tier 1 (hybrid): fp16 recent + TZip older

Keep the most recent 2187 tokens (1 BLOCK) in fp16 for maximum quality:
```
fp16_kv_per_token = 2 * 12 * 64 * 2 * 13 = 39,936 bytes ≈ 39 KB
fp16_block_cost = 2187 * 39,936 = 87,320,832 bytes ≈ 83.3 MB

remaining_vram = 7,757 - 83.3 = 7,673.7 MB
tzip_tokens = 7,673.7 MB / 4.57 KB ≈ 1,720,000

total_vram_tokens = 2,187 + 1,720,000 ≈ 1,722,187 tokens
                  ≈ 1.72 million tokens (≈ 787 BLOCKs)
```

#### Tier 2: RAM — TZip Ternary KV

```
tokens_ram = 28,768 MB / 4.57 KB
           = 28,768 * 1,048,576 / 4,680
           = 30,165,626,880 / 4,680
           = 6,445,220 tokens
           ≈ 6.45 million tokens (≈ 2,949 BLOCKs)
```

#### Combined VRAM + RAM

```
total_tokens_memory = 1,722,187 + 6,445,220 = 8,167,407 tokens
                    ≈ 8.17 million tokens
```

#### Tier 3: Disk — Compressed TZip

TZip ternary data compresses well with LZ4 because:
- Ternary values cluster (many zeros in attention)
- Estimated LZ4 ratio on TZip data: 2.5-3× (ternary has low entropy: ≤1.58 bits)

```
compressed_bytes_per_token ≈ 4,680 / 2.7 ≈ 1,733 bytes ≈ 1.69 KB

For 1 TB disk:
tokens_disk = 1,000 GB / 1.69 KB = 1,000 * 1,073,741,824 / 1,733
            = 619,642,255 tokens
            ≈ 620 million tokens (≈ 283,000 BLOCKs)
```

For 4 TB disk:
```
tokens_disk_4tb ≈ 2.48 billion tokens
```

### 3.3 Reaching Trillions: Sparse + Distributed

To reach trillions of tokens, we need **sparse attention** — not every token
attends to every other token. The key insight:

**Claim**: With ternary KV + hierarchical memory + sparse attention, the system
can address T tokens in context with only O(√T) tokens loaded at any time.

**Proof sketch**:

Define a hierarchical attention tree with branching factor B = 3 (ternary!):
```
Level 0: Individual tokens (leaves)
Level 1: Groups of 3 tokens, represented by summary
Level 2: Groups of 9 tokens (3 level-1 groups)
...
Level k: Groups of 3^k tokens
Level 7: Groups of 3^7 = 2187 tokens = 1 BLOCK (page)
Level 14: Groups of 3^14 = 4,782,969 tokens ≈ 4.78M
Level 21: Groups of 3^21 = 10,460,353,203 tokens ≈ 10.46B
```

At each level, we store a summary vector. To attend over T tokens:
1. Compute exact attention over hot tokens: O(BLOCK) = O(2187)
2. Compute summary attention at each level: O(log_3(T)) summaries per level
3. Total summaries consulted: O(3 * log_3(T)) (top-3 per level)
4. Pages promoted for full attention: O(log_3(T))

For T = 1 trillion (10^12):
```
log_3(10^12) = 12 * log_3(10) = 12 * 2.096 ≈ 25.15
Summaries consulted: 3 * 25 = 75
Pages promoted: ≈ 25 (worst case)
Tokens in full attention: 2187 + 25 * 2187 = 56,862 tokens
Memory for active set: 56,862 * 4,680 = 266,114,160 bytes ≈ 254 MB
```

This fits comfortably in VRAM. The remaining trillion tokens exist as a
hierarchy of summaries:
```
Summary overhead per page: 20 KB (from Section 2.2)
Pages for 1T tokens: 10^12 / 2187 ≈ 457,247,372 pages
Summary storage: 457M * 20 KB = 9.14 TB
```

This requires distributed storage (see Section 4), or deeper summarization:
```
Level-2 summaries (per 3 pages = 6561 tokens): 20 KB each
Level-2 pages: 457M / 3 ≈ 152M → 3.05 TB
...
Level-7 summaries (per 2187 pages ≈ 4.78M tokens): 20 KB each
Level-7 count: 457M / 2187 ≈ 209,000 → 4.18 GB  ← fits in RAM!
```

**Summary**: To address 1 trillion tokens:
- **4.18 GB** of hierarchical summaries (fits in RAM)
- **Disk**: raw pages stored compressed, loaded on demand
- **VRAM**: active working set of ~50K tokens at any time
- **Effective context**: 1 trillion tokens, with O(log_3(T)) lookup latency

### 3.4 Summary Table

| Tier | Storage | Format | Tokens | Latency |
|------|---------|--------|--------|---------|
| Hot (VRAM) | 7.7 GB | fp16 recent + TZip | 1.72M | <1 μs |
| Warm (RAM) | 28.8 GB | TZip | 6.45M | <1 μs |
| Cold (Disk 1TB) | 1 TB | TZip+LZ4 | 620M | <1 ms |
| Cold (Disk 4TB) | 4 TB | TZip+LZ4 | 2.48B | <1 ms |
| Sparse+Hierarchical | 4.18 GB summaries | Summary tree | **1T addressable** | O(log₃T) |

---

## 4. Distributed Context (Hivemind)

### 4.1 Setup

N instances of NovaX, each holding one or more BLOCKs of context.
Instance i holds pages P_i = {p_{i,1}, p_{i,2}, ...}, each page containing
2187 tokens of TZip-packed KV cache.

### 4.2 Cross-Instance Attention

**Problem**: A query Q on instance 0 needs to attend over KV on instance j.

**Solution**: Two-phase distributed attention.

**Phase 1 — Summary probe** (low bandwidth):
```
Instance 0 broadcasts: Q_summary = mean(Q[-27:])  # last RE_LAMINAR tokens
                        Shape: [12 heads, 64 dim] = 1,536 floats = 3 KB

Each instance j computes:
  relevance_j = max_over_pages(Q_summary · S_j^T / √d)
  Returns: relevance_j (1 scalar per head = 24 bytes)

Network cost: 3 KB broadcast + 24 bytes * N responses
For N=1000: 3 KB + 24 KB = 27 KB total
```

**Phase 2 — Selective full attention** (high bandwidth, few instances):
```
Select top-k instances by relevance (k = 3, ternary!).
Instance 0 sends full Q to these k instances.
Each selected instance j computes:
  attn_j = softmax(Q · K_j^T / √d) · V_j
  Returns: attn_j (shape: [seq_len, 12, 64]) + attn_weights

Network cost per instance: seq_len * 768 * 2 bytes (fp16)
For seq_len=2187: 2187 * 768 * 2 = 3.36 MB per instance
Total for k=3: ~10 MB
```

### 4.3 Attention Merging

Given attention outputs from the local instance and k remote instances:

```
attn_local = softmax(Q · K_local^T / √d) · V_local     # [T, H, D]
attn_j     = softmax(Q · K_j^T / √d) · V_j              # [T, H, D]  for each j

# Correct merging requires log-sum-exp of attention logits:
# Let s_local = Q · K_local^T / √d,  s_j = Q · K_j^T / √d

# Each instance returns: (attn_output, log_sum_exp_of_scores)
# LSE_local = log(sum(exp(s_local)))    per query position per head
# LSE_j     = log(sum(exp(s_j)))

# Merged output:
LSE_total = log(exp(LSE_local) + Σ_j exp(LSE_j))

w_local = exp(LSE_local - LSE_total)
w_j     = exp(LSE_j - LSE_total)

attn_merged = w_local * attn_local + Σ_j w_j * attn_j
```

This is **exact** — not an approximation. It produces identical results to
computing attention over the concatenated KV cache. The proof:

```
softmax([s_1; s_2]) · [V_1; V_2]
= [exp(s_1)/Z_total · V_1 ; exp(s_2)/Z_total · V_2]
= (Z_1/Z_total) * softmax(s_1)·V_1 + (Z_2/Z_total) * softmax(s_2)·V_2
= w_1 * attn_1 + w_2 * attn_2

where Z_i = sum(exp(s_i)), Z_total = Z_1 + Z_2
and w_i = Z_i / Z_total = exp(LSE_i) / exp(LSE_total)
```

### 4.4 Tripple Voting for Block Importance

Each instance computes a ternary "relevance vote" for each of its pages:

```
vote(page_p, query_Q) ∈ {-1, 0, +1}

+1: page is highly relevant   (summary_attn > μ + σ)
 0: page is neutral           (|summary_attn - μ| ≤ σ)
-1: page is irrelevant        (summary_attn < μ - σ)

where μ, σ are the mean and std of summary attention scores across all pages.
```

**Tripple aggregation** across N instances:
```
For each page p across the network:
  votes = [vote_1(p), vote_2(p), ..., vote_N(p)]  (each ∈ {-1, 0, +1})

  consensus = sum(votes) / N    ∈ [-1, +1]

  if consensus > +1/3:  PROMOTE (load into querying instance's hot tier)
  if consensus ∈ [-1/3, +1/3]:  NEUTRAL (keep in place)
  if consensus < -1/3:  DEMOTE (eligible for eviction)
```

The thresholds are 1/3 boundaries — ternary decision on the consensus itself.

### 4.5 Effective Context Calculation

Given N instances, each with capacity C_i pages:

```
Effective context (exact attention):
  T_exact = T_local + k * BLOCK
  where k = 3 (top-k remote instances per query)
  T_exact = 2187 + 3 * 2187 = 8,748 tokens

Effective context (approximate, via summaries):
  T_approx = Σ_i C_i * BLOCK
  For N instances, each with 2,949 pages (from RAM budget):
  T_approx = N * 2,949 * 2,187

  N = 10:     64,514,130 tokens    ≈ 64.5 million
  N = 100:    645,141,300 tokens   ≈ 645 million
  N = 1,000:  6,451,413,000 tokens ≈ 6.45 billion
  N = 10,000: 64,514,130,000 tokens ≈ 64.5 billion
```

With disk backing per instance (620M tokens each):
```
  N = 10:     6.2 billion tokens
  N = 100:    62 billion tokens
  N = 1,000:  620 billion tokens
  N = 1,621:  1.005 trillion tokens  ← TRILLION THRESHOLD
  N = 10,000: 6.2 trillion tokens
```

### 4.6 Network Bandwidth Requirements

Per query, the network traffic is:
```
Phase 1 (broadcast): 3 KB * N
Phase 2 (selective): 10 MB * 3 = 30 MB

For N=1000:
  Phase 1: 3 MB (fan-out, parallelizable)
  Phase 2: 30 MB (point-to-point)
  Total: ~33 MB per query

On 1 Gbps LAN: 33 MB / 125 MB/s = 264 ms latency
On 10 Gbps LAN: 33 MB / 1250 MB/s = 26 ms latency
```

For local instances (same machine, shared memory): <1 ms.

---

## 5. Implementation Plan

### Phase 1: KV Cache Quantization (Week 1-2)

1. **Add TernaryKVCache class** to `train.py`:
   ```python
   class TernaryKVCache:
       """Per-layer KV cache with ternary quantization + TZip packing."""
       def __init__(self, num_heads, head_dim, max_tokens, device):
           # Packed storage: ceil(head_dim / 5) bytes per head per K/V
           self.pack_size = math.ceil(head_dim / 5)  # 13 bytes for dim=64
           self.scales_k = torch.zeros(max_tokens, num_heads, dtype=torch.float16, device=device)
           self.scales_v = torch.zeros(max_tokens, num_heads, dtype=torch.float16, device=device)
           self.packed_k = torch.zeros(max_tokens, num_heads, self.pack_size, dtype=torch.uint8, device=device)
           self.packed_v = torch.zeros(max_tokens, num_heads, self.pack_size, dtype=torch.uint8, device=device)
           self.length = 0

       def append(self, k, v):
           """Quantize and store K, V vectors for one new token."""
           # k, v: [num_heads, head_dim]
           for h in range(k.shape[0]):
               self.scales_k[self.length, h], self.packed_k[self.length, h] = tzip_encode(k[h])
               self.scales_v[self.length, h], self.packed_v[self.length, h] = tzip_encode(v[h])
           self.length += 1

       def get_kv(self, start, end):
           """Decode K, V for token range [start, end)."""
           # Returns: k [end-start, heads, dim], v [end-start, heads, dim]
           ...
   ```

2. **Implement tzip_encode / tzip_decode** as CUDA kernels or PyTorch ops:
   ```
   tzip_encode(vec_fp32) → (scale_fp16, packed_uint8[13])
   tzip_decode(scale_fp16, packed_uint8[13]) → vec_fp32[64]
   ```

3. **Benchmark** attention quality: run eval set with fp32 KV vs ternary KV,
   measure perplexity delta. Target: <5% perplexity increase.

### Phase 2: Hierarchical Memory (Week 3-4)

1. **PageManager** class managing VRAM/RAM/disk tiers
2. **Reynolds eviction** with the formula from Section 2.3
3. **Page summary computation** on eviction from VRAM to RAM
4. **Disk serialization** with LZ4 compression

### Phase 3: Sparse Hierarchical Attention (Week 5-6)

1. **Summary tree** construction (ternary branching, 7 levels to cover 1 BLOCK)
2. **Approximate attention** over summaries
3. **Dynamic page promotion** based on summary attention scores
4. Benchmark: measure recall@k for relevant tokens vs brute-force

### Phase 4: Distributed Hivemind Context (Week 7-8)

1. **Cross-instance attention protocol** (Phase 1 + Phase 2 from Section 4.2)
2. **LSE-based exact merging** implementation
3. **Tripple voting** integration with existing Hivemind service on port 9881
4. Benchmark: distributed vs local attention quality

---

## 6. Key Equations Summary

### Ternary Quantization
```
δ = 0.7 * mean(|v|)
q(v_i) = sign(v_i) * 𝟙(|v_i| > δ)
α = (v · q(v)) / (q(v) · q(v))
v̂ = α * q(v)
```

### Memory per Token (TZip)
```
B_token = 2 * H * (⌈D/5⌉ + 2) * L
        = 2 * 12 * (13 + 2) * 13
        = 4,680 bytes
```

### Reynolds Eviction
```
Re(page) = age_factor / (freq * recency * max_attn + ε)
Evict if Re ≥ 343 (7³)
```

### Distributed Attention Merging (Exact)
```
LSE_i = logsumexp(Q · K_i^T / √d)
w_i = exp(LSE_i - logsumexp({LSE_1, ..., LSE_n}))
attn_merged = Σ_i w_i * attn_i
```

### Context Capacity
```
T_vram  = (VRAM - model - overhead) / B_token ≈ 1.72M tokens
T_ram   = RAM_available / B_token             ≈ 6.45M tokens
T_disk  = Disk / (B_token / compression)      ≈ 620M tokens per TB
T_hive  = N_instances * T_per_instance        → trillions at N≥1,621
```

### Sparse Attention Complexity
```
Active tokens per query: O(BLOCK + k * log₃(T) * BLOCK)
For T = 10¹², k = 3:  ≈ 56,862 active tokens (254 MB in VRAM)
```
