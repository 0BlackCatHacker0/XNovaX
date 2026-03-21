# Compressible Flow Equations Mapped to Data Compression & Ternary Quantization

## Research Date: 2026-03-15
## Purpose: Map gas dynamics (compressible N-S) to NovaX data compression pipeline with TZip (3^5=243) packing

---

## FOUNDATIONAL MAPPING

| Gas Dynamics | NovaX Data System |
|---|---|
| Gas velocity v | Data throughput rate (bytes/sec) |
| Speed of sound c | Channel bandwidth capacity (bytes/sec) |
| Mach number M = v/c | Compression Mach M = data_rate / bandwidth |
| Gas density rho | Data density (information per byte) |
| Pressure p | Queue backpressure (pending bytes) |
| Temperature T | Data entropy (randomness/incompressibility) |
| Specific heat ratio gamma | Redundancy ratio gamma_d = total_size / unique_info |
| Entropy s | Shannon entropy H |
| Nozzle cross-section A | Pipeline parallelism (concurrent streams) |
| Mass flow rate rho*v*A | Effective throughput (useful bytes/sec) |

---

## 1. MACH NUMBER: M = v/c → data_rate / compression_speed

### Gas Dynamics
The Mach number is the ratio of flow velocity to local speed of sound:

```
M = v / c
c = sqrt(gamma * R * T)    (speed of sound in ideal gas)
```

### NovaX Mapping
```
M_data = data_rate / bandwidth_capacity

Where:
  data_rate      = incoming bytes per second (the "flow velocity")
  bandwidth      = channel capacity in bytes per second (the "speed of sound")
```

### Ternary Quantization
```
M_trit = trit_rate / tzip_decode_speed

Where:
  trit_rate        = incoming trits per second
  tzip_decode_speed = 243 values unpacked per cycle (3^5 per byte)

Ternary state:
  M < 1  → trit_state = -1 (subsonic, surplus capacity)
  M = 1  → trit_state =  0 (sonic, at capacity)
  M > 1  → trit_state = +1 (supersonic, compression required)
```

### Pseudocode
```python
def mach_number(data_rate, bandwidth):
    """Compute compression Mach number."""
    M = data_rate / (bandwidth + 1e-9)
    # Ternary quantize
    if M < 0.8:
        return M, -1   # subsonic: no compression needed
    elif M <= 1.2:
        return M, 0    # transonic: light compression
    else:
        return M, +1   # supersonic: heavy compression required

# TZip-aware variant
def mach_tzip(raw_trits_per_sec, channel_bytes_per_sec):
    """Mach number in TZip domain. 1 byte = 5 trits = 243 states."""
    tzip_capacity = channel_bytes_per_sec * 5  # trits/sec capacity
    M = raw_trits_per_sec / (tzip_capacity + 1e-9)
    return M
```

---

## 2. SUBSONIC FLOW (M < 1): Data Fits in Bandwidth

### Gas Dynamics
When M < 1, disturbances propagate in all directions. Flow is smooth, predictable, and reversible. Density changes are small (nearly incompressible for M < 0.3).

```
rho/rho_0 ≈ 1 - M^2/2     (for M << 1)
```

### NovaX Mapping
Data rate is below channel capacity. No compression needed. Transmission is lossless and predictable.

```
Condition: data_rate < bandwidth
Action:    pass-through (no compression overhead)
Analogy:   incompressible flow assumption valid
```

### Ternary Regime
```
M < 0.3  → "deeply subsonic": raw ternary, no packing needed
           Each trit sent individually. Wasteful but zero latency.

0.3 < M < 1.0 → "subsonic": TZip packing optional
           Pack 5 trits → 1 byte for efficiency, but not required.

Harmonic boundary: M = 27/243 = 0.111 (laminar threshold)
                   M = 125/243 = 0.514 (transitional)
```

### Pseudocode
```python
def subsonic_handler(data, bandwidth, data_rate):
    """Handle data when M < 1. No compression required."""
    M = data_rate / bandwidth
    if M < 0.3:
        # Deeply subsonic: send raw, no overhead
        return data, "raw"
    elif M < 1.0:
        # Subsonic: optional TZip packing for efficiency
        packed = tzip_pack(data)  # 5 trits → 1 byte
        savings = 1.0 - (len(packed) / len(data))
        if savings > 0.1:  # worth it if >10% savings
            return packed, "tzip"
        return data, "raw"
```

---

## 3. SUPERSONIC FLOW (M > 1): Data Exceeds Bandwidth

### Gas Dynamics
When M > 1, flow moves faster than information (sound) can propagate upstream. Upstream conditions cannot "warn" of downstream obstacles. Shock waves form.

```
Upstream cannot influence downstream boundary conditions.
Information propagation is one-directional only.
```

### NovaX Mapping
Data arrives faster than channel can transmit. Compression is mandatory. Backpressure signals cannot reach the source fast enough.

```
Condition: data_rate > bandwidth
Action:    MUST compress. Select algorithm by M value.
Problem:   Source doesn't know channel is saturated (like supersonic flow)
Solution:  Buffering + compression + flow control signals via side-channel
```

### Compression Tier Selection by Mach Number
```
M = 1.0-1.5  → Light compression: TZip (5 trits/byte, ratio ~1.58x)
M = 1.5-3.0  → Medium compression: TZip + run-length on zero-trits
M = 3.0-5.0  → Heavy compression: TZip + entropy coding (Huffman on trit patterns)
M > 5.0      → Extreme: lossy quantization (drop least-significant trits)

Harmonic boundary: M = 343/243 = 1.412 (turbulent onset in ternary domain)
```

### Pseudocode
```python
def supersonic_handler(data, M):
    """Handle data when M > 1. Compression mandatory."""
    if M < 1.5:
        return tzip_pack(data), "tzip_light"
    elif M < 3.0:
        packed = tzip_pack(data)
        return rle_ternary(packed), "tzip_rle"
    elif M < 5.0:
        packed = tzip_pack(data)
        return huffman_ternary(packed), "tzip_huffman"
    else:
        # Lossy: quantize to fewer trits
        quantized = lossy_trit_reduce(data, target_ratio=M)
        return tzip_pack(quantized), "tzip_lossy"
```

---

## 4. SHOCK WAVES: Sudden Data Bursts Causing Queuing

### Gas Dynamics
A shock wave is a thin region where flow properties change discontinuously. Across a normal shock:

```
M₂² = (M₁² + 2/(gamma-1)) / (2*gamma*M₁²/(gamma-1) - 1)

Pressure jump:   p₂/p₁ = 1 + 2*gamma*(M₁²-1)/(gamma+1)
Density jump:    rho₂/rho₁ = (gamma+1)*M₁² / ((gamma-1)*M₁² + 2)
Temperature jump: T₂/T₁ = p₂/p₁ * rho₁/rho₂
```

Key property: M₁ > 1 (supersonic) → M₂ < 1 (subsonic) across shock. Entropy INCREASES.

### NovaX Mapping
A "data shock" occurs when a burst of data arrives at a pipeline stage, causing:
- Sudden queue depth increase (pressure jump)
- Throughput discontinuity (velocity change from supersonic to subsonic)
- Information loss (entropy increase = irreversible transformation)

```
Shock condition: data_rate_in >> pipeline_stage_capacity

Across the shock (the queue buffer):
  M_in  > 1 (data arriving faster than processing)
  M_out < 1 (data leaves at pipeline processing rate)

  Queue depth ∝ pressure_ratio = 1 + 2*gamma_d*(M_in² - 1)/(gamma_d + 1)
  Latency spike ∝ temperature_ratio
```

### Ternary Shock Relations
```
# In TZip domain, shock = buffer overflow boundary
# 243 states per TZip byte; shock occurs at buffer = N * 243

shock_pressure_ratio(M_in, gamma_d):
    return 1 + 2 * gamma_d * (M_in**2 - 1) / (gamma_d + 1)

shock_queue_depth(M_in, gamma_d, base_queue):
    rho_ratio = (gamma_d + 1) * M_in**2 / ((gamma_d - 1) * M_in**2 + 2)
    return base_queue * rho_ratio

# Example: M_in = 2.0, gamma_d = 1.4 (typical data redundancy)
# p₂/p₁ = 1 + 2*1.4*(4-1)/2.4 = 4.5x queue pressure
# Queue depth multiplies by 2.667x
```

### Pseudocode
```python
def detect_data_shock(queue_history, window=10):
    """Detect shock wave: sudden queue depth jump."""
    recent = queue_history[-window:]
    if len(recent) < 2:
        return 0, False

    gradient = (recent[-1] - recent[0]) / (window + 1e-9)
    mean_depth = sum(recent) / len(recent)

    # Shock = queue gradient exceeds 3x mean (harmonic: 3)
    shock_detected = gradient > 3 * mean_depth

    # Compute effective Mach from queue growth
    M_shock = (1 + gradient / (mean_depth + 1e-9)) ** 0.5

    return M_shock, shock_detected

def shock_response(M_shock, gamma_d=1.4):
    """Apply shock relations to determine compression response."""
    p_ratio = 1 + 2 * gamma_d * (M_shock**2 - 1) / (gamma_d + 1)
    rho_ratio = (gamma_d + 1) * M_shock**2 / ((gamma_d - 1) * M_shock**2 + 2)
    T_ratio = p_ratio / rho_ratio

    return {
        "pressure_ratio": p_ratio,     # Queue depth multiplier
        "density_ratio": rho_ratio,     # Data density change
        "temperature_ratio": T_ratio,   # Latency multiplier
        "M_post_shock": ((M_shock**2 + 2/(gamma_d-1)) /
                         (2*gamma_d*M_shock**2/(gamma_d-1) - 1)) ** 0.5,
        "compression_needed": "heavy" if p_ratio > 3 else "medium" if p_ratio > 1.5 else "light"
    }
```

---

## 5. ISENTROPIC RELATIONS: Compression Ratio Formulas

### Gas Dynamics
For isentropic (reversible, adiabatic) processes:

```
T₂/T₁ = (p₂/p₁)^((gamma-1)/gamma)
rho₂/rho₁ = (p₂/p₁)^(1/gamma)
T₂/T₁ = (rho₂/rho₁)^(gamma-1)

As function of Mach:
T/T₀ = (1 + (gamma-1)/2 * M²)^(-1)
p/p₀ = (1 + (gamma-1)/2 * M²)^(-gamma/(gamma-1))
rho/rho₀ = (1 + (gamma-1)/2 * M²)^(-1/(gamma-1))
```

T₀, p₀, rho₀ are stagnation (total) conditions at M=0.

### NovaX Mapping — Lossless Compression Ratios
Isentropic = lossless (no entropy increase = no information loss).

```
Compression ratio CR = original_size / compressed_size

Mapping:
  p₂/p₁  → queue_pressure_ratio (how much backpressure changes)
  T₂/T₁  → entropy_density_ratio (how data entropy per byte changes)
  rho₂/rho₁ → data_density_ratio (information per byte)

Isentropic compression ratio formula for data:
  CR = (1 + (gamma_d - 1)/2 * M²)^(1/(gamma_d - 1))

Where:
  gamma_d = redundancy ratio = raw_size / unique_information
  M = data_rate / bandwidth
```

### Ternary Isentropic Relations
```
# For ternary data with TZip packing:
# gamma_ternary relates to trit redundancy

# Base: 1 trit has 3 states, 1 bit has 2 states
# Information: 1 trit = log2(3) = 1.585 bits
# Packing: 5 trits = 243 states fits in 8 bits (256 states)
# Packing efficiency: 243/256 = 0.949 (94.9% efficient)

gamma_tzip = log(243) / log(243 - redundant_states)  # ternary gamma

# Isentropic compression in TZip domain:
CR_tzip = (1 + (gamma_tzip - 1)/2 * M**2) ** (1/(gamma_tzip - 1))
```

### Pseudocode
```python
import math

def isentropic_compression_ratio(M, gamma_d):
    """Compute lossless compression ratio from Mach and redundancy ratio."""
    exponent = 1.0 / (gamma_d - 1)
    CR = (1 + (gamma_d - 1) / 2 * M**2) ** exponent
    return CR

def isentropic_relations(M, gamma_d):
    """Full isentropic property ratios."""
    factor = 1 + (gamma_d - 1) / 2 * M**2
    T_ratio = 1.0 / factor                              # T/T0
    p_ratio = factor ** (-gamma_d / (gamma_d - 1))       # p/p0
    rho_ratio = factor ** (-1.0 / (gamma_d - 1))         # rho/rho0
    return {
        "T_ratio": T_ratio,
        "p_ratio": p_ratio,
        "rho_ratio": rho_ratio,
        "compression_ratio": 1.0 / rho_ratio  # CR = rho0/rho
    }

def tzip_gamma(data_trits):
    """Compute ternary gamma from data redundancy."""
    total_states = 3 ** len(data_trits)  # if treated as single number
    unique_patterns = len(set(tuple(data_trits[i:i+5]) for i in range(0, len(data_trits)-4)))
    gamma_d = math.log(total_states) / math.log(unique_patterns + 1)
    return max(1.01, min(gamma_d, 5.0))  # clamp to physical range

# Example: M=2.0, gamma_d=1.4 (40% redundancy)
# CR = (1 + 0.2 * 4)^(1/0.4) = 1.8^2.5 = 4.36x compression
```

---

## 6. SPECIFIC HEAT RATIO: gamma = c_p/c_v → Redundancy Ratio

### Gas Dynamics
gamma (ratio of specific heats) determines how compressible a gas is:

```
gamma = c_p / c_v

Monatomic gas (He, Ar): gamma = 5/3 ≈ 1.667
Diatomic gas (air, N₂): gamma = 7/5 = 1.4
Polyatomic gas (CO₂):   gamma = 1.3

gamma determines:
  - Speed of sound: c = sqrt(gamma * R * T)
  - Shock strength: stronger shocks for higher gamma
  - Compression work: W = p₁V₁/(gamma-1) * [(p₂/p₁)^((gamma-1)/gamma) - 1]
```

### NovaX Mapping — Data Redundancy Ratio
```
gamma_d = total_data_size / unique_information_content
        = (entropy_at_constant_throughput) / (entropy_at_constant_density)
        = c_throughput / c_density

Analogies:
  gamma_d ≈ 1.0  → incompressible data (already maximally dense, e.g., encrypted)
  gamma_d ≈ 1.4  → typical structured data (JSON, logs) — 40% redundant
  gamma_d ≈ 1.67 → highly redundant data (repeated patterns, sparse matrices)
  gamma_d → ∞    → trivially compressible (all zeros, single repeated value)
```

### Ternary gamma Values
```
Data Type                    gamma_d    Ternary Analog
----------------------------------------------------------
Encrypted/random             1.001      All 243 TZip states equally likely
Dense model weights          1.1        Slight trit bias
Structured text/JSON         1.4        Moderate trit pattern repetition
Log files                    1.67       Heavy pattern repetition
Sparse data (mostly zeros)   2.5        Most trits are 0 (neutral)
Constant/repeated            ∞          Single trit value dominates

Ternary-native gamma:
  gamma_3 = log(3) / log(3 - zero_trit_fraction * 2)

  For balanced data (equal -1,0,+1):  gamma_3 = 1.0 (incompressible)
  For biased data (80% zeros):        gamma_3 = log(3)/log(1.4) ≈ 3.26
```

### Pseudocode
```python
def compute_gamma_d(data):
    """Compute redundancy ratio (data gamma) from trit stream."""
    total_trits = len(data)
    if total_trits == 0:
        return 1.4  # default

    # Count trit frequencies
    freq = {-1: 0, 0: 0, 1: 0}
    for t in data:
        freq[t] = freq.get(t, 0) + 1

    # Shannon entropy
    H = 0
    for count in freq.values():
        if count > 0:
            p = count / total_trits
            H -= p * math.log2(p)

    H_max = math.log2(3)  # 1.585 bits (maximum for ternary)

    # gamma = H_max / H (how far from maximum entropy)
    if H < 0.01:
        return 10.0  # nearly constant data

    gamma_d = H_max / H
    return max(1.001, gamma_d)

def compression_work(p1, p2, gamma_d):
    """Work required for compression (CPU cost analog)."""
    return p1 / (gamma_d - 1) * ((p2/p1) ** ((gamma_d - 1)/gamma_d) - 1)
```

---

## 7. CHOKED FLOW: Maximum Throughput at M=1

### Gas Dynamics
At a throat (minimum cross-section), flow reaches M=1 (sonic condition). This is the maximum mass flow rate possible.

```
Choked mass flow rate:
  m_dot_max = A* * p₀ * sqrt(gamma / (R * T₀)) * (2/(gamma+1))^((gamma+1)/(2*(gamma-1)))

Critical ratios at throat (M=1):
  T*/T₀ = 2 / (gamma + 1)
  p*/p₀ = (2/(gamma+1))^(gamma/(gamma-1))
  rho*/rho₀ = (2/(gamma+1))^(1/(gamma-1))
```

No matter how much you increase upstream pressure, mass flow through the throat cannot exceed m_dot_max.

### NovaX Mapping — Maximum Pipeline Throughput
```
Choked condition: pipeline_throughput = max regardless of input pressure

The "throat" = bottleneck stage in compression pipeline
  - Could be CPU (compression algorithm)
  - Could be network interface
  - Could be TZip encoder/decoder

Choked throughput:
  throughput_max = bottleneck_capacity * sqrt(gamma_d / R_data) * (2/(gamma_d+1))^((gamma_d+1)/(2*(gamma_d-1)))

Where:
  bottleneck_capacity = processing rate of narrowest pipeline stage
  R_data = data constant (bytes per trit-temperature unit)

Critical data density at choke point:
  density_critical = density_stagnation * (2/(gamma_d + 1))^(1/(gamma_d - 1))
```

### Ternary Choke Point
```
# TZip choke: 243 states per byte, pipeline limited by slowest stage

# For 5-trit TZip packing:
# Critical packing ratio at M=1 (sonic):
#   243 states → 1 byte (the throat)
#   gamma_tzip ≈ log(256)/log(243) = 1.0219 (nearly incompressible packing)

# True choke occurs when:
#   trit_input_rate = tzip_encode_rate (M=1 at encoder)
#   Increasing input beyond this just grows the queue

choke_throughput_trits = encoder_speed_bytes * 5  # 5 trits per byte at choke
```

### Pseudocode
```python
def choked_flow_throughput(bottleneck_bps, gamma_d):
    """Maximum throughput through compression pipeline."""
    critical_factor = (2 / (gamma_d + 1)) ** ((gamma_d + 1) / (2 * (gamma_d - 1)))
    m_dot_max = bottleneck_bps * math.sqrt(gamma_d) * critical_factor
    return m_dot_max

def is_choked(data_rate, bottleneck_rate, gamma_d):
    """Check if pipeline is choked (M=1 at bottleneck)."""
    M_throat = data_rate / bottleneck_rate
    choked = M_throat >= 1.0

    if choked:
        max_throughput = choked_flow_throughput(bottleneck_rate, gamma_d)
        excess = data_rate - max_throughput
        return True, max_throughput, excess  # excess must be buffered or dropped
    return False, data_rate, 0

def critical_ratios(gamma_d):
    """Property ratios at the choke point (M=1)."""
    T_star = 2 / (gamma_d + 1)                              # T*/T0
    p_star = (2 / (gamma_d + 1)) ** (gamma_d / (gamma_d - 1))  # p*/p0
    rho_star = (2 / (gamma_d + 1)) ** (1 / (gamma_d - 1))      # rho*/rho0
    return {"T_star": T_star, "p_star": p_star, "rho_star": rho_star}

# Example: gamma_d = 1.4
# T*/T0 = 0.833 (temperature drops 17% at throat)
# p*/p0 = 0.528 (pressure drops 47% at throat)
# Interpretation: data density at bottleneck is 53% of stagnation density
```

---

## 8. NORMAL SHOCK RELATIONS: Data Format Conversion Boundaries

### Gas Dynamics
Across a normal shock (perpendicular to flow):

```
M₂² = (M₁² + 2/(gamma-1)) / (2*gamma/(gamma-1) * M₁² - 1)
p₂/p₁ = 1 + 2*gamma*(M₁² - 1)/(gamma+1)
T₂/T₁ = [1 + 2*gamma*(M₁²-1)/(gamma+1)] * [2 + (gamma-1)*M₁²] / [(gamma+1)² * M₁² / (gamma-1)]
rho₂/rho₁ = (gamma+1)*M₁² / [(gamma-1)*M₁² + 2]

Entropy change: Delta_s = c_v * ln(T₂/T₁) - R * ln(rho₂/rho₁) > 0 always
```

### NovaX Mapping — Format Conversion
A normal shock = sudden format change (e.g., raw trits → TZip, JSON → binary, float32 → ternary quantized).

```
Pre-shock state (1):  data in format A at rate M₁ > 1
Post-shock state (2): data in format B at rate M₂ < 1

The shock IS the format converter.

Properties:
  - Data rate drops (M₁ > 1 → M₂ < 1): compressed data is slower but denser
  - Density increases (rho₂ > rho₁): more info per byte
  - Entropy increases (Delta_s > 0): some information lost (metadata, formatting)
  - Total pressure decreases: overall pipeline capacity reduced
```

### Ternary Format Shock Table
```
Conversion                     M_in   M_out   Info Loss (Delta_s)
-----------------------------------------------------------------
Raw trits → TZip (5→1 byte)   1.58   0.63    ~5% (packing overhead)
Float32 → Ternary quantized   4.0    0.25    ~20% (precision loss)
JSON text → Binary ternary    3.0    0.33    ~10% (structure metadata)
UTF-8 → Balanced ternary      2.5    0.40    ~8% (encoding overhead)
Model weights → 2-bit quant   16.0   0.0625  ~40% (heavy quantization)
```

### Pseudocode
```python
def normal_shock(M1, gamma_d):
    """Compute post-shock conditions for data format conversion."""
    if M1 <= 1.0:
        return None  # No shock in subsonic flow

    gm1 = gamma_d - 1
    gp1 = gamma_d + 1

    # Post-shock Mach
    M2_sq = (M1**2 + 2/gm1) / (2*gamma_d/gm1 * M1**2 - 1)
    M2 = math.sqrt(max(M2_sq, 0.001))

    # Property ratios
    p_ratio = 1 + 2*gamma_d*(M1**2 - 1)/gp1
    rho_ratio = gp1 * M1**2 / (gm1 * M1**2 + 2)
    T_ratio = p_ratio / rho_ratio

    # Entropy increase (information loss)
    # Delta_s/cv = ln(T_ratio) + (gamma-1)*ln(1/rho_ratio)
    delta_s = math.log(T_ratio) + gm1 * math.log(1/rho_ratio)
    info_loss_pct = (1 - math.exp(-delta_s)) * 100

    return {
        "M_post": M2,
        "pressure_ratio": p_ratio,
        "density_ratio": rho_ratio,
        "temperature_ratio": T_ratio,
        "entropy_increase": delta_s,
        "info_loss_percent": info_loss_pct,
        "conversion_type": "lossless" if info_loss_pct < 1 else
                          "near_lossless" if info_loss_pct < 5 else "lossy"
    }

def format_conversion_shock(source_format, target_format, data_rate, bandwidth):
    """Model format conversion as normal shock."""
    # Format-specific gamma values
    format_gamma = {
        "raw_trits": 1.67,
        "tzip": 1.4,
        "json": 1.5,
        "binary": 1.2,
        "quantized": 1.1
    }

    gamma_d = format_gamma.get(source_format, 1.4)
    M1 = data_rate / bandwidth

    if M1 > 1:
        return normal_shock(M1, gamma_d)
    else:
        return {"M_post": M1, "info_loss_percent": 0, "conversion_type": "subsonic_passthrough"}
```

---

## 9. EXPANSION WAVES: Decompression / Unpacking

### Gas Dynamics
Expansion waves (Prandtl-Meyer expansion) occur when supersonic flow turns around a convex corner. Flow accelerates, pressure drops, temperature drops. Unlike shocks, expansion is isentropic (reversible).

```
Prandtl-Meyer function:
  nu(M) = sqrt((gamma+1)/(gamma-1)) * arctan(sqrt((gamma-1)/(gamma+1) * (M²-1)))
          - arctan(sqrt(M²-1))

Turning angle: theta = nu(M₂) - nu(M₁)
```

### NovaX Mapping — Decompression Pipeline
Expansion = decompression. The reverse of compression, and critically, it is ISENTROPIC (lossless for lossless formats).

```
Expansion wave = data unpacking stage
  - TZip byte → 5 trits (expansion ratio 1:5 in trit count)
  - Compressed archive → raw files
  - Quantized weights → dequantized inference values

Properties:
  - Isentropic (lossless): decompression recovers original data perfectly
  - Flow accelerates: data rate increases (more bytes out than in)
  - Pressure drops: queue backpressure decreases
  - Temperature drops: data entropy per byte decreases (more structured)
```

### Ternary Expansion
```
# TZip expansion: 1 byte (243 states) → 5 trits
# Expansion ratio: 5 trits / 1 byte = 5x trit-rate expansion
# But each trit only has 3 states vs byte's 256, so information is conserved

# Prandtl-Meyer angle for ternary:
# Maximum expansion angle = nu_max = pi/2 * (sqrt((gamma+1)/(gamma-1)) - 1)
# For gamma_d = 1.4: nu_max = 130.45 degrees
# Meaning: maximum decompression ratio before vacuum (data underflow)
```

### Pseudocode
```python
def prandtl_meyer(M, gamma_d):
    """Prandtl-Meyer expansion function (decompression capacity)."""
    if M <= 1.0:
        return 0  # No expansion in subsonic

    gp1_gm1 = (gamma_d + 1) / (gamma_d - 1)
    term = (gamma_d - 1) / (gamma_d + 1) * (M**2 - 1)

    nu = (math.sqrt(gp1_gm1) * math.atan(math.sqrt(term))
          - math.atan(math.sqrt(M**2 - 1)))
    return nu

def expansion_decompression(compressed_data, source_M, target_M, gamma_d):
    """Decompress data using expansion wave model."""
    nu1 = prandtl_meyer(source_M, gamma_d)
    nu2 = prandtl_meyer(target_M, gamma_d)
    turning_angle = nu2 - nu1

    if turning_angle < 0:
        return None, "Error: cannot compress via expansion"

    # Isentropic: use isentropic relations for decompression ratios
    relations_1 = isentropic_relations(source_M, gamma_d)
    relations_2 = isentropic_relations(target_M, gamma_d)

    expansion_ratio = relations_1["rho_ratio"] / relations_2["rho_ratio"]

    # Decompress
    decompressed = tzip_unpack(compressed_data)  # 1 byte → 5 trits

    return decompressed, {
        "expansion_ratio": expansion_ratio,
        "turning_angle_deg": math.degrees(turning_angle),
        "info_loss": 0,  # Isentropic = lossless
        "output_rate_multiplier": target_M / source_M
    }

def tzip_unpack(packed_bytes):
    """Expand TZip: 1 byte → 5 balanced trits."""
    trits = []
    for byte_val in packed_bytes:
        val = byte_val  # 0-242
        for _ in range(5):
            trit = (val % 3) - 1  # balanced: -1, 0, +1
            trits.append(trit)
            val //= 3
    return trits
```

---

## 10. DE LAVAL NOZZLE: Compression Pipeline Design

### Gas Dynamics
A de Laval (convergent-divergent) nozzle accelerates flow from subsonic to supersonic:

```
Converging section: M < 1, flow accelerates as area decreases
Throat:             M = 1, minimum area, choked flow
Diverging section:  M > 1, flow continues accelerating as area increases

Area-Mach relation:
  A/A* = (1/M) * [(2/(gamma+1)) * (1 + (gamma-1)/2 * M²)]^((gamma+1)/(2*(gamma-1)))

Where A* = throat area (minimum cross-section)
```

### NovaX Mapping — Complete Compression Pipeline

```
CONVERGING SECTION (Intake → Throat):
  Raw data → progressively compressed
  "Area" decreases = pipeline narrows = data gets denser
  M increases from ~0.3 to 1.0

  Stages:
  1. Raw input (M=0.3): Receive data, classify type
  2. Deduplication (M=0.5): Remove exact duplicates
  3. Pattern extraction (M=0.7): Identify repeated patterns
  4. TZip encoding (M=0.9): Pack 5 trits → 1 byte

THROAT (Choke Point, M=1):
  Maximum compression. Pipeline bottleneck.
  This is where format conversion happens.
  Data rate = pipeline capacity exactly.

  Stage:
  5. Core compression (M=1.0): Entropy coding at channel capacity

DIVERGING SECTION (Throat → Output):
  Two possible exit conditions:

  a) SUBSONIC EXIT (M < 1): Data stays compressed, enters slow channel
     → Storage, archival, low-bandwidth transmission

  b) SUPERSONIC EXIT (M > 1): Data re-expands for fast consumption
     → TZip unpack, decompression, ready for processing

  Stages:
  6. Channel adaptation (M=0.8 or M=1.5): Match output to destination
  7. Delivery (M varies): Final output
```

### Ternary De Laval Nozzle
```
Pipeline stage widths in TZip units:

Stage          Area (trits/cycle)   M      State
------------------------------------------------------
Input          2187 (3^7)          0.3    Subsonic intake
Dedup          729  (3^6)          0.5    Converging
Pattern        243  (3^5 = TZip)  0.7    Converging
Encode         81   (3^4)         0.9    Approaching throat
THROAT         27   (3^3)         1.0    Choked (sonic)
Expand/Store   81   (3^4)         varies Diverging
Unpack         243  (3^5)         varies Diverging
Output         2187 (3^7)         varies Full expansion

Note: areas follow 3^n harmonics! 3^7 → 3^3 → 3^7
The convergence ratio: 2187/27 = 81 = 3^4
```

### Pseudocode
```python
def area_mach_relation(M, gamma_d):
    """A/A* for given Mach number."""
    gp1 = gamma_d + 1
    gm1 = gamma_d - 1

    term = (2/gp1) * (1 + gm1/2 * M**2)
    exponent = gp1 / (2 * gm1)

    A_ratio = (1/M) * term ** exponent
    return A_ratio

def design_nozzle_pipeline(input_rate, output_bandwidth, gamma_d):
    """Design a de Laval compression pipeline."""
    M_inlet = 0.3  # subsonic intake
    M_throat = 1.0  # choked

    # Throat area (bottleneck capacity)
    A_star = output_bandwidth  # bytes/sec at throat

    # Pipeline stage areas
    stages = []
    mach_values = [0.3, 0.5, 0.7, 0.9, 1.0, 0.8, 0.5, 0.3]  # subsonic exit
    # Or:       [0.3, 0.5, 0.7, 0.9, 1.0, 1.5, 2.0, 3.0]  # supersonic exit

    for i, M in enumerate(mach_values):
        A_ratio = area_mach_relation(M, gamma_d)
        stage_capacity = A_star * A_ratio

        # Map to ternary harmonic
        harmonic_power = round(math.log(stage_capacity) / math.log(3))
        ternary_capacity = 3 ** max(3, min(harmonic_power, 7))

        stages.append({
            "stage": i,
            "mach": M,
            "A_ratio": A_ratio,
            "capacity_bytes": stage_capacity,
            "ternary_capacity": ternary_capacity,
            "ternary_power": harmonic_power,
            "section": "converging" if i < 4 else "throat" if i == 4 else "diverging"
        })

    return stages

class DeLavalPipeline:
    """Complete compression pipeline modeled as de Laval nozzle."""

    def __init__(self, throat_capacity, gamma_d=1.4):
        self.throat = throat_capacity
        self.gamma_d = gamma_d
        self.stages = self._build_stages()

    def _build_stages(self):
        """Build 7-stage pipeline (harmonic: 7 stages)."""
        return [
            {"name": "intake",    "power": 7, "width": 3**7, "M": 0.3},  # 2187
            {"name": "dedup",     "power": 6, "width": 3**6, "M": 0.5},  # 729
            {"name": "pattern",   "power": 5, "width": 3**5, "M": 0.7},  # 243 = TZip
            {"name": "encode",    "power": 4, "width": 3**4, "M": 0.9},  # 81
            {"name": "THROAT",    "power": 3, "width": 3**3, "M": 1.0},  # 27 = choke
            {"name": "adapt",     "power": 4, "width": 3**4, "M": 0.8},  # 81
            {"name": "output",    "power": 5, "width": 3**5, "M": 0.5},  # 243
        ]

    def process(self, data_trits):
        """Push data through the nozzle pipeline."""
        current = data_trits
        results = []

        for stage in self.stages:
            M = len(current) / (stage["width"] + 1e-9)

            if stage["name"] == "dedup":
                current = self._dedup(current)
            elif stage["name"] == "pattern":
                current = self._pattern_compress(current)
            elif stage["name"] == "encode":
                current = self._tzip_encode(current)
            elif stage["name"] == "THROAT":
                current = self._entropy_code(current)
            elif stage["name"] == "adapt":
                current = self._channel_adapt(current)
            elif stage["name"] == "output":
                current = current  # passthrough

            results.append({"stage": stage["name"], "M": M, "size": len(current)})

        return current, results

    def _dedup(self, trits):
        """Remove duplicate 5-trit blocks."""
        blocks = [tuple(trits[i:i+5]) for i in range(0, len(trits)-4, 5)]
        seen = set()
        unique = []
        for b in blocks:
            if b not in seen:
                seen.add(b)
                unique.append(b)
        return [t for block in unique for t in block]

    def _pattern_compress(self, trits):
        """Replace repeated patterns with references."""
        # Simplified: run-length encode zero-runs
        result = []
        i = 0
        while i < len(trits):
            if trits[i] == 0:
                count = 0
                while i < len(trits) and trits[i] == 0 and count < 13:
                    count += 1
                    i += 1
                result.extend([0, count])  # RLE marker
            else:
                result.append(trits[i])
                i += 1
        return result

    def _tzip_encode(self, trits):
        """Pack 5 trits into 1 byte value (0-242)."""
        packed = []
        for i in range(0, len(trits), 5):
            block = trits[i:i+5]
            while len(block) < 5:
                block.append(0)  # pad
            val = sum((t + 1) * (3 ** j) for j, t in enumerate(block))
            packed.append(val)
        return packed

    def _entropy_code(self, data):
        """Entropy coding at the throat (placeholder for Huffman/ANS)."""
        return data  # In production: apply ANS or Huffman

    def _channel_adapt(self, data):
        """Adapt to output channel characteristics."""
        return data
```

---

## 11. TOTAL PRESSURE LOSS: Information Loss in Lossy Compression

### Gas Dynamics
Total (stagnation) pressure decreases across a shock. This loss is irreversible.

```
p₀₂/p₀₁ = [(gamma+1)*M₁²/((gamma-1)*M₁²+2)]^(gamma/(gamma-1))
           * [1 + 2*gamma*(M₁²-1)/(gamma+1)]^(-1/(gamma-1))

For weak shocks (M₁ close to 1): loss ≈ 0
For strong shocks (M₁ >> 1): significant total pressure loss

Total pressure recovery factor: eta = p₀₂/p₀₁
```

### NovaX Mapping — Lossy Compression Quality
```
Total pressure = total information capacity of the pipeline
Total pressure loss = information permanently destroyed by lossy compression

p₀_loss = 1 - p₀₂/p₀₁ = fraction of information permanently lost

Mapping:
  Weak shock (M~1.1): p₀_loss ≈ 0.01 → 1% info loss (near-lossless quantization)
  Moderate shock (M~2): p₀_loss ≈ 0.13 → 13% info loss (aggressive quantization)
  Strong shock (M~5): p₀_loss ≈ 0.62 → 62% info loss (extreme compression)
```

### Ternary Information Loss
```
# In ternary quantization, info loss = precision trits discarded

# Full precision: N trits → 3^N states
# Quantized: K trits (K < N) → 3^K states
# Info loss: 1 - 3^K / 3^N = 1 - 3^(K-N)

# For model weight quantization:
#   float32 (32 bits ≈ 20.2 trits) → 5 trits (TZip)
#   Info loss = 1 - 3^5/3^20.2 = 1 - 243/5.23e9 ≈ 99.99995%
#   BUT: model weights are NOT random. Effective info << 20.2 trits.
#   With N-S gamma_d ≈ 3.0 for weights: effective info ≈ 6.7 trits
#   Loss from 6.7 → 5 trits = 1 - 3^5/3^6.7 = 1 - 243/1594 ≈ 84.8%
#   Still high, but models tolerate this (redundancy in weights)
```

### Pseudocode
```python
def total_pressure_loss(M1, gamma_d):
    """Compute information loss fraction across a compression shock."""
    if M1 <= 1.0:
        return 0.0  # No loss in subsonic (isentropic)

    gm1 = gamma_d - 1
    gp1 = gamma_d + 1

    # Total pressure ratio across normal shock
    term1 = (gp1 * M1**2 / (gm1 * M1**2 + 2)) ** (gamma_d / gm1)
    term2 = (1 + 2*gamma_d*(M1**2 - 1)/gp1) ** (-1/gm1)

    p0_ratio = term1 * term2
    info_loss = 1.0 - p0_ratio

    return max(0, info_loss)

def quantization_info_loss(source_trits, target_trits, gamma_d):
    """Information loss when quantizing from N trits to K trits."""
    # Effective information (accounting for redundancy)
    effective_source = source_trits / gamma_d
    effective_target = min(target_trits, effective_source)

    if effective_target >= effective_source:
        return 0.0  # No loss (target has enough capacity)

    # Information loss in ternary states
    loss = 1.0 - 3**(effective_target - effective_source)

    # Map to equivalent Mach shock
    M_equiv = math.sqrt(source_trits / (target_trits + 1e-9))
    p0_loss = total_pressure_loss(M_equiv, gamma_d)

    return {
        "trit_loss": loss,
        "p0_loss": p0_loss,
        "equivalent_M": M_equiv,
        "quality": "lossless" if loss < 0.001 else
                  "high" if loss < 0.05 else
                  "medium" if loss < 0.20 else "low"
    }

# Quality tiers mapped to NovaX 3-5-7-13 harmonics:
# 3-trit quantization:  27 levels,  high loss,   fast
# 5-trit quantization:  243 levels, medium loss,  balanced (TZip native)
# 7-trit quantization:  2187 levels, low loss,    detailed
# 13-trit quantization: 1594323 levels, near-lossless, slow
```

---

## 12. STAGNATION TEMPERATURE: Maximum Data Density Before Loss

### Gas Dynamics
Stagnation temperature T₀ is the temperature a gas reaches when brought to rest adiabatically:

```
T₀ = T * (1 + (gamma-1)/2 * M²)

T₀ is the maximum temperature in the flow.
At stagnation, all kinetic energy converts to internal energy.
```

### NovaX Mapping — Maximum Data Density
```
Stagnation temperature → maximum information density achievable before
data becomes incompressible (further compression causes loss).

T₀_data = current_entropy * (1 + (gamma_d - 1)/2 * M²)

Where:
  current_entropy = Shannon entropy of data per symbol
  M = compression ratio already applied
  T₀_data = theoretical maximum entropy (incompressibility ceiling)

When T = T₀: data is at rest (fully compressed), maximum density.
Any further compression MUST be lossy (you'd exceed T₀, which is impossible
without adding energy = external information).
```

### Ternary Stagnation
```
# Maximum ternary density:
# H_max = log2(3) = 1.585 bits per trit (when all 3 states equally likely)
# This is the "stagnation temperature" of ternary data

# Actual entropy of data:
# H_actual = -sum(p_i * log2(p_i)) for i in {-1, 0, +1}

# Compression Mach:
# M = H_max / H_actual - 1 (how far from maximum density)

# At stagnation (M=0):
# Data entropy = T₀ = H_max = 1.585 bits/trit = CANNOT COMPRESS FURTHER

# TZip stagnation:
# 5 trits at maximum density = 5 * 1.585 = 7.925 bits
# 1 byte = 8 bits
# Stagnation efficiency = 7.925/8 = 99.06%
# TZip is already within 1% of thermodynamic limit!
```

### Pseudocode
```python
def stagnation_temperature(H_current, M, gamma_d):
    """Maximum data density (entropy ceiling) before lossy compression."""
    T0 = H_current * (1 + (gamma_d - 1) / 2 * M**2)
    return T0

def compression_headroom(data_trits):
    """How much more can this data be compressed losslessly?"""
    # Current entropy
    freq = {-1: 0, 0: 0, 1: 0}
    for t in data_trits:
        freq[t] = freq.get(t, 0) + 1

    total = len(data_trits)
    H = 0
    for count in freq.values():
        if count > 0:
            p = count / total
            H -= p * math.log2(p)

    H_max = math.log2(3)  # 1.585 bits/trit (stagnation)

    # Headroom = how far below stagnation
    headroom = 1.0 - H / H_max

    # Theoretical compression ratio achievable
    CR_theoretical = H_max / (H + 1e-9)

    # In TZip terms
    current_bits_per_5trits = H * 5
    tzip_bits = 8  # 1 byte
    tzip_efficiency = current_bits_per_5trits / tzip_bits

    return {
        "H_current": H,
        "H_max": H_max,
        "headroom_pct": headroom * 100,
        "max_CR": CR_theoretical,
        "tzip_utilization_pct": tzip_efficiency * 100,
        "at_stagnation": headroom < 0.01,
        "recommendation": "cannot compress further" if headroom < 0.01 else
                         "light compression possible" if headroom < 0.2 else
                         "significant compression available"
    }

def density_limit_check(data_rate, bandwidth, gamma_d):
    """Check if data is approaching stagnation (max density)."""
    M = data_rate / bandwidth
    T0 = math.log2(3) * (1 + (gamma_d - 1) / 2 * M**2)

    # At stagnation, kinetic energy → internal energy
    # In data terms: throughput speed → storage density
    max_density_bits_per_byte = min(T0 * 5, 8)  # capped at byte capacity

    return {
        "stagnation_density": T0,
        "max_bits_per_tzip_byte": max_density_bits_per_byte,
        "M_current": M,
        "pct_of_stagnation": (1 / (1 + (gamma_d-1)/2 * M**2)) * 100
    }
```

---

## UNIFIED COMPRESSIBLE FLOW COMPRESSION ENGINE

### The Complete TZip-Nozzle Pipeline

```python
class CompressibleFlowEngine:
    """
    NovaX compression engine using compressible flow equations.
    Maps gas dynamics to data compression with ternary (3^5=243) TZip packing.
    """

    HARMONICS = {3: 27, 5: 243, 7: 2187, 13: 1594323}  # 3^n

    def __init__(self, bandwidth, gamma_d=1.4):
        self.bandwidth = bandwidth
        self.gamma_d = gamma_d
        self.nozzle = DeLavalPipeline(bandwidth, gamma_d)

    def analyze(self, data_trits, data_rate):
        """Full compressible flow analysis of data stream."""
        M = data_rate / self.bandwidth

        result = {
            "mach": M,
            "regime": self._regime(M),
            "gamma_d": compute_gamma_d(data_trits),
            "headroom": compression_headroom(data_trits),
        }

        if M > 1:
            result["shock"] = normal_shock(M, self.gamma_d)
            result["total_pressure_loss"] = total_pressure_loss(M, self.gamma_d)
            result["compression_strategy"] = self._select_strategy(M)

        result["choked"] = is_choked(data_rate, self.bandwidth, self.gamma_d)
        result["stagnation"] = stagnation_temperature(
            result["headroom"]["H_current"], M, self.gamma_d
        )
        result["isentropic"] = isentropic_relations(M, self.gamma_d)

        return result

    def compress(self, data_trits, data_rate):
        """Compress data through de Laval nozzle pipeline."""
        M = data_rate / self.bandwidth

        if M < 0.3:
            return data_trits, "raw"  # deeply subsonic
        elif M < 1.0:
            return self.nozzle.process(data_trits)  # subsonic pipeline
        else:
            # Supersonic: must pass through shock first
            shock = normal_shock(M, self.gamma_d)
            compressed, stages = self.nozzle.process(data_trits)
            return compressed, {"stages": stages, "shock": shock}

    def decompress(self, compressed_data):
        """Decompress via expansion wave (isentropic, lossless)."""
        return tzip_unpack(compressed_data)

    def _regime(self, M):
        if M < 0.3: return "deeply_subsonic"
        if M < 0.8: return "subsonic"
        if M < 1.2: return "transonic"
        if M < 5.0: return "supersonic"
        return "hypersonic"

    def _select_strategy(self, M):
        if M < 1.5: return "tzip_only"
        if M < 3.0: return "tzip_rle"
        if M < 5.0: return "tzip_huffman"
        return "tzip_lossy"


# Ternary state summary for all 12 concepts:
TERNARY_COMPRESSION_STATES = {
    "mach":          {-1: "subsonic",      0: "sonic",        +1: "supersonic"},
    "shock":         {-1: "no_shock",      0: "weak_shock",   +1: "strong_shock"},
    "isentropic":    {-1: "expanding",     0: "neutral",      +1: "compressing"},
    "gamma":         {-1: "dense_data",    0: "typical",      +1: "sparse_data"},
    "choked":        {-1: "below_limit",   0: "at_limit",     +1: "over_limit"},
    "normal_shock":  {-1: "no_conversion", 0: "light_convert",+1: "heavy_convert"},
    "expansion":     {-1: "compressed",    0: "neutral",      +1: "expanded"},
    "nozzle_stage":  {-1: "converging",    0: "throat",       +1: "diverging"},
    "pressure_loss": {-1: "lossless",      0: "near_lossless",+1: "lossy"},
    "stagnation":    {-1: "compressible",  0: "near_limit",   +1: "at_limit"},
    "burst":         {-1: "steady",        0: "fluctuating",  +1: "shock_wave"},
    "decompression": {-1: "packed",        0: "partial",      +1: "fully_expanded"},
}
```

---

## KEY FORMULAS QUICK REFERENCE

| # | Concept | Gas Dynamics Formula | Data Compression Formula |
|---|---------|---------------------|-------------------------|
| 1 | Mach | M = v/c | M = data_rate / bandwidth |
| 2 | Subsonic | M < 1, smooth flow | data fits, no compression |
| 3 | Supersonic | M > 1, shocks form | data exceeds, must compress |
| 4 | Shock | p₂/p₁ = 1+2g(M²-1)/(g+1) | queue_burst = 1+2g_d(M²-1)/(g_d+1) |
| 5 | Isentropic | T₂/T₁=(p₂/p₁)^((g-1)/g) | CR = (1+(g_d-1)/2*M²)^(1/(g_d-1)) |
| 6 | Gamma | g = cp/cv | g_d = H_max / H_actual |
| 7 | Choked | m_max at M=1 | throughput_max at bottleneck |
| 8 | Normal shock | M₁>1 → M₂<1 | format_A(fast) → format_B(dense) |
| 9 | Expansion | Prandtl-Meyer, isentropic | decompression, lossless |
| 10 | De Laval | converge-throat-diverge | compress-bottleneck-expand |
| 11 | p₀ loss | p₀₂/p₀₁ < 1 across shock | info permanently lost in lossy |
| 12 | T₀ stag | T₀ = T(1+(g-1)/2*M²) | max_density = H(1+(g_d-1)/2*M²) |

## 3-5-7-13 HARMONIC INTEGRATION

```
3^3  = 27    → Throat width (choke point, Reynolds laminar boundary)
3^5  = 243   → TZip byte (5 trits per byte, core packing unit)
3^7  = 2187  → Block size (full intake/output width)
3^13 = 1.59M → Carrier frame (maximum precision quantization)

Nozzle area ratio: 3^7 / 3^3 = 3^4 = 81 (convergence ratio)
TZip efficiency: 243/256 = 94.9% byte utilization
Stagnation: 5 * log2(3) / 8 = 99.06% of byte capacity at max entropy
```

---

## IMPLEMENTATION PRIORITY

1. **Mach classifier** (1-2-3-4-5): Determine compression regime from data rate vs bandwidth
2. **TZip core** (5 trits → 1 byte, 1 byte → 5 trits): Already defined in NovaX
3. **Gamma calculator** (6): Measure data redundancy from trit distribution
4. **Choke detector** (7): Alert when pipeline hits maximum throughput
5. **De Laval pipeline** (10): 7-stage compression with 3^n harmonic widths
6. **Shock detector** (4): Identify data bursts from queue gradient
7. **Normal shock converter** (8): Format conversion with loss estimation
8. **Isentropic ratios** (5): Lossless compression ratio prediction
9. **Total pressure loss** (11): Quantify information loss in lossy modes
10. **Stagnation analysis** (12): Identify incompressibility ceiling
11. **Expansion waves** (9): Decompression pipeline
12. **Full engine** (all): CompressibleFlowEngine class

---

## Sources & References
- Anderson, J.D. "Modern Compressible Flow" (3rd ed.) — canonical gas dynamics textbook
- Shapiro, A.H. "Dynamics and Thermodynamics of Compressible Fluid Flow"
- NovaX N-S Masterfile: `C:\Users\Jupit\Downloads\navier_stokes_masterfile.txt`
- NovaX Ternary Masterfile: `C:\Users\Jupit\Downloads\TERNARY_LANGUAGE_MASTERFILE_ADVANCED.txt`
- NovaX Complementary Frameworks: `C:\NovaX\memory\complementary-math-frameworks.md`
