# Navier-Stokes Energy Equation → AI Workstation Thermal Management
# NovaX Thermal Prediction & Optimization Engine

## 1. THE ENERGY EQUATION

```
ρc_p(∂T/∂t + v·∇T) = k∇²T + Φ + Q
```

Left side: thermal inertia + convective transport
Right side: conduction + viscous dissipation + heat sources

---

## 2. HARDWARE THERMAL SPECIFICATIONS

### RTX 4060 (AD107)
- TDP: 115W (reference), up to 140W with power limit
- T_throttle (GPU): 86°C
- T_hotspot_max: 100°C
- Die area: ~159 mm²
- Heat sink thermal resistance (typical): R_hs ≈ 0.15-0.25 °C/W
- Fan: dual axial, max ~2400 RPM

### AMD Ryzen 7 8845HS (Hawk Point)
- TDP: 45W (configurable 35-54W)
- Tj,max: 95°C (absolute thermal junction limit)
- PBO boost power: up to 75W sustained
- Die area: ~178 mm² (chiplet)
- IHS thermal resistance: R_ihs ≈ 0.05 °C/W
- Heat pipe cooler resistance (typical laptop): R_cooler ≈ 0.3-0.5 °C/W

### System
- Ambient T_amb: assumed 25°C (adjustable)
- System thermal mass estimate: ~0.5-1.0 kg aluminum/copper heatsink assembly
- Airflow: laptop chassis, limited to ~30 CFM max

---

## 3. TERM-BY-TERM MAPPING

### 3.1 T (Temperature) → Component Junction Temperature

```
T_junction(t) = measured via sensors (°C)
T_gpu(t)      = GPU die temperature
T_cpu(t)      = CPU die temperature
T_hotspot(t)  = maximum point temperature on die
```

The temperature field T in N-S maps directly to the spatially varying
temperature across the die surface. In practice we track:
- T_edge (die edge, cooler)
- T_center (die center, hottest)
- T_hotspot = max(T_surface) across all points

### 3.2 ρc_p (Thermal Capacity) → System Thermal Mass

```
C_thermal = m × c_p  [J/°C]
```

| Component        | Mass (kg) | c_p (J/kg·°C) | C_thermal (J/°C) |
|------------------|-----------|----------------|-------------------|
| GPU die (Si)     | 0.003     | 700            | 2.1               |
| GPU heatsink (Al)| 0.15      | 900            | 135               |
| CPU die (Si)     | 0.002     | 700            | 1.4               |
| CPU heatsink (Cu)| 0.08      | 385            | 30.8              |
| Heat pipes (Cu)  | 0.05      | 385            | 19.25             |
| **System total** | **~0.285**|                | **~188.5**        |

**Interpretation**: ρc_p determines how quickly the system absorbs heat
before temperature rises. Higher C_thermal = more thermal "buffer" =
longer time before throttling under burst workloads.

**Burst capacity**: At 115W GPU load from 25°C ambient:
```
Time to absorb 115W before any cooling = C_thermal × ΔT / P
= 135 J/°C × (86-25)°C / 115W = 71.6 seconds (heatsink only)
```
This is why GPU can burst above sustained thermal capacity for ~1 minute.

### 3.3 k∇²T (Thermal Conduction) → Heat Sink / Fan Cooling

```
Q_conduction = k × A × (T_hot - T_cold) / L  [W]
```

Maps to the entire cooling stack:

```
Q_cooling = (T_junction - T_ambient) / R_total

R_total = R_die + R_tim + R_heatsink + R_convection

GPU path:  R_total ≈ 0.02 + 0.05 + 0.20 + 0.15 = 0.42 °C/W
CPU path:  R_total ≈ 0.02 + 0.05 + 0.35 + 0.20 = 0.62 °C/W
```

**Maximum cooling capacity at thermal limit**:
```
GPU: Q_max = (86 - 25) / 0.42 = 145.2W  (above TDP — headroom exists)
CPU: Q_max = (95 - 25) / 0.62 = 112.9W  (above PBO max — safe)
```

The ∇²T term is the Laplacian — in our mapping, it represents the
spatial temperature gradient across the heatsink fins. More fins,
more surface area = larger effective ∇²T = more heat extracted.

### 3.4 Φ (Viscous Dissipation) → Electrical Power → Heat

```
Φ_compute = P_electrical × η_heat
```

Where η_heat ≈ 0.99 (virtually all electrical power becomes heat).

| Workload              | GPU Power (W) | CPU Power (W) | Total Φ (W) |
|-----------------------|---------------|---------------|--------------|
| Idle                  | 10            | 8             | 18           |
| Light inference       | 45            | 25            | 70           |
| Medium inference      | 80            | 40            | 120          |
| Full inference        | 115           | 54            | 169          |
| Burst (PBO + GPU OC)  | 140           | 75            | 215          |

**Key insight**: Φ in N-S represents irreversible energy conversion.
In computing, ALL computation is irreversible energy conversion
(Landauer's principle: erasing 1 bit → kT·ln(2) heat minimum).
Every FLOP generates heat. The RTX 4060 at ~15.11 TFLOPS generates:
```
Heat per TFLOP = 115W / 15.11 = 7.61 W/TFLOP
```

### 3.5 Q (Heat Source) → AI Inference Workload Heat Generation

```
Q_inference(t) = P_gpu(utilization) + P_cpu(utilization) + P_memory
```

For LLM inference specifically:
```
Q_llm = P_base + P_per_token × tokens_per_second

Typical values (Ollama, 7B model):
  P_base ≈ 60W (GPU) + 20W (CPU) = 80W
  P_per_token ≈ 0.5W additional per tok/s
  At 30 tok/s: Q_llm = 80 + 15 = 95W total

Typical values (Ollama, 70B model, quantized):
  P_base ≈ 100W (GPU) + 35W (CPU) = 135W
  P_per_token ≈ 1.2W additional per tok/s
  At 10 tok/s: Q_llm = 135 + 12 = 147W total
```

Q is time-varying: prompt processing (prefill) generates MORE heat
than token generation (decode) because prefill uses more parallelism.

---

## 4. DIMENSIONLESS NUMBERS → SYSTEM DIAGNOSTICS

### 4.1 Nusselt Number: Nu = hL/k → Cooling Effectiveness

```
Nu = h × L / k_air

h = heat transfer coefficient of cooling system [W/m²·°C]
L = characteristic length (heatsink fin length) [m]
k_air = thermal conductivity of air = 0.026 W/m·°C
```

**For forced convection (fans on)**:
```
Nu = 0.664 × Re^0.5 × Pr^0.33  (laminar over flat plate)
Nu = 0.037 × Re^0.8 × Pr^0.33  (turbulent)
```

**Practical mapping**:
```
Nu_effective = (T_junction - T_ambient) / (Q_total × R_convection × k_air / L)
```

| Fan Speed   | h (W/m²·°C) | Nu (L=0.05m) | Cooling Quality |
|-------------|-------------|--------------|-----------------|
| 0% (passive)| 5-10        | 10-19        | Poor            |
| 30%         | 20-30       | 38-58        | Adequate        |
| 50%         | 40-50       | 77-96        | Good            |
| 75%         | 60-80       | 115-154      | Very Good       |
| 100%        | 90-120      | 173-231      | Maximum         |

**Rule**: Nu > 100 required for sustained full-load inference.

### 4.2 Prandtl Number: Pr = μc_p/k → Computational-to-Cooling Ratio

```
Pr_system = (Computational heat generation rate) / (Cooling dissipation rate)
Pr_system = Φ_total / Q_cooling_max
```

For air: Pr_air = 0.71 (fixed, physical property)

**NovaX mapping** (dimensionless thermal stress ratio):
```
Pr_nova = P_compute / P_cool_capacity

P_compute = current total power draw [W]
P_cool_capacity = (T_limit - T_ambient) / R_total [W]
```

| State           | P_compute | P_cool_max | Pr_nova | Status          |
|-----------------|-----------|------------|---------|-----------------|
| Idle            | 18W       | 145W       | 0.12    | Cold running    |
| Light inference | 70W       | 145W       | 0.48    | Comfortable     |
| Full inference  | 169W      | 145W       | 1.17    | WILL THROTTLE   |
| Burst           | 215W      | 145W       | 1.48    | THROTTLE NOW    |

**CRITICAL THRESHOLD: Pr_nova > 1.0 means heat generation exceeds
cooling capacity — throttling is INEVITABLE. Time to throttle depends
on thermal mass (C_thermal).**

### 4.3 Rayleigh Number: Ra → Natural Convection Potential

```
Ra = g × β × (T_surface - T_ambient) × L³ / (ν × α)

g = 9.81 m/s²
β = 1/T_film (volumetric expansion, ~1/300 for air at ~27°C)
ν = 1.5e-5 m²/s (kinematic viscosity of air)
α = 2.2e-5 m²/s (thermal diffusivity of air)
L = characteristic length (heatsink height) ≈ 0.03 m
```

**At GPU thermal limit (86°C surface, 25°C ambient)**:
```
Ra = 9.81 × (1/328) × (86-25) × 0.03³ / (1.5e-5 × 2.2e-5)
Ra = 9.81 × 0.00305 × 61 × 2.7e-5 / 3.3e-10
Ra ≈ 149,300
```

Ra > 10⁴ → natural convection is significant.
Ra > 10⁹ → turbulent natural convection.

**Practical meaning**: Even with fans OFF, natural convection can
dissipate approximately:
```
Q_natural ≈ h_natural × A_heatsink × ΔT
h_natural ≈ 5-10 W/m²·°C for Ra ~ 10⁵
A_heatsink ≈ 0.02 m² (total fin area)
Q_natural ≈ 8 × 0.02 × 61 = 9.76W
```
Only ~10W passive — fans are essential for any real workload.

### 4.4 Fourier Number: Fo = αt/L² → Thermal Time Constant

```
Fo = α × t / L²

α = k / (ρ × c_p) = thermal diffusivity
t = time [s]
L = characteristic length [m]
```

**For the heatsink system**:
```
α_aluminum = 97.1e-6 m²/s
L_heatsink = 0.05 m (fin length)

Fo = 1.0 when t = L²/α = 0.05² / 97.1e-6 = 25.7 seconds
```

**Thermal time constant** τ = R_total × C_thermal:
```
GPU system: τ_gpu = 0.42 × 135 = 56.7 seconds
CPU system: τ_cpu = 0.62 × 30.8 = 19.1 seconds
```

**Meaning**: After a step change in load:
- At t = τ: temperature reaches 63.2% of final value
- At t = 3τ: temperature reaches 95% of final value
- At t = 5τ: temperature reaches 99.3% of final value

**GPU reaches thermal equilibrium in ~5 × 56.7 = 283 seconds (~4.7 min)**
**CPU reaches thermal equilibrium in ~5 × 19.1 = 95 seconds (~1.6 min)**

### 4.5 Biot Number: Bi = hL/k → Surface vs Internal Resistance

```
Bi = h × L / k_solid

h = convective heat transfer coefficient [W/m²·°C]
L = characteristic thickness [m]
k_solid = thermal conductivity of heatsink material [W/m·°C]
```

**For aluminum heatsink (k=205 W/m·°C), L=0.01m thickness**:
```
Bi = 50 × 0.01 / 205 = 0.0024
```

**Bi << 0.1 → lumped capacitance model is valid.**
This means we can treat the heatsink as a uniform temperature body,
which MASSIVELY simplifies the thermal prediction math.

**For silicon die (k=150 W/m·°C), L=0.5mm**:
```
Bi = 50 × 0.0005 / 150 = 0.00017
```
Also Bi << 0.1 → die temperature is essentially uniform.

**Critical insight**: Because Bi << 0.1 for all components, we can use
the simple lumped model for ALL thermal predictions:

```
T(t) = T_ambient + (T_initial - T_ambient) × e^(-t/τ) + (Q × R_total) × (1 - e^(-t/τ))
```

---

## 5. PREDICTIVE THERMAL THROTTLING ENGINE

### 5.1 Core Prediction Formula

Since Bi << 0.1, the lumped capacitance model gives us:

```
T(t) = T_amb + Q(t) × R_total × (1 - e^(-t/τ)) + T(0) × e^(-t/τ)

Where:
  T(t)    = predicted temperature at time t
  T_amb   = ambient temperature (25°C default)
  Q(t)    = instantaneous heat generation [W]
  R_total = total thermal resistance [°C/W]
  τ       = R_total × C_thermal [seconds]
  T(0)    = current measured temperature
```

### 5.2 Time-to-Throttle Prediction

Solving for t when T(t) = T_throttle:

```
t_throttle = -τ × ln((T_throttle - T_amb - Q×R) / (T_current - T_amb - Q×R))

Where:
  Q×R = steady-state temperature rise above ambient
```

**Example: GPU at 50°C, suddenly full 115W load**:
```
T_steady = 25 + 115 × 0.42 = 73.3°C  (below 86°C — will NOT throttle!)
```

**Example: GPU at 50°C, burst 140W load**:
```
T_steady = 25 + 140 × 0.42 = 83.8°C  (below 86°C — barely safe)
```

**Example: GPU at 50°C, 140W load, 35°C ambient (summer)**:
```
T_steady = 35 + 140 × 0.42 = 93.8°C  (ABOVE 86°C — WILL THROTTLE)
t_throttle = -56.7 × ln((86 - 93.8) / (50 - 93.8))
           = -56.7 × ln(0.178)
           = -56.7 × (-1.726)
           = 97.8 seconds (~1.6 minutes to throttle)
```

### 5.3 Maximum Sustainable Power at Given Ambient

```
P_max_sustained = (T_throttle - T_ambient) / R_total

GPU: P_max = (86 - T_amb) / 0.42
CPU: P_max = (95 - T_amb) / 0.62
```

| Ambient (°C) | GPU P_max (W) | CPU P_max (W) | Combined Max (W) |
|---------------|---------------|---------------|-------------------|
| 20            | 157.1         | 120.9         | 278.1             |
| 25            | 145.2         | 112.9         | 258.1             |
| 30            | 133.3         | 104.8         | 238.1             |
| 35            | 121.4         | 96.8          | 218.2             |
| 40            | 109.5         | 88.7          | 198.2             |

### 5.4 Maximum Sustainable Inference Rate

```
tokens_per_second_max = (P_max_sustained - P_base) / P_per_token

7B model:
  At 25°C: (145.2 + 112.9 - 80) / 0.5 = 356 tok/s (GPU-bound, not thermal-bound)
  Actual limit is compute-bound at ~30-40 tok/s

70B model (quantized, offloaded):
  At 25°C: combined 258W, base 135W → (258 - 135) / 1.2 = 102 tok/s
  At 35°C: combined 218W, base 135W → (218 - 135) / 1.2 = 69 tok/s
  Actual limit is VRAM-bound at ~8-12 tok/s
```

**Conclusion**: For this hardware, THERMAL is not the bottleneck for
inference — compute and VRAM are. Thermal only becomes limiting during:
1. Multi-model concurrent inference (HiveMind swarms)
2. High ambient temperatures (>35°C)
3. Training/fine-tuning workloads

---

## 6. OPTIMAL FAN CURVE (N-S Energy Equation Derived)

### 6.1 Principle

At thermal equilibrium: Q_generated = Q_dissipated
```
Φ + Q = k∇²T  (steady state, ∂T/∂t = 0, no convection)
```

Fan speed controls h (convective coefficient), which controls R_convection:
```
R_conv = 1 / (h × A)
h ∝ (fan_RPM)^0.8  (turbulent forced convection)
```

### 6.2 N-S Optimized Fan Curve

Target: maintain T_junction at optimal operating point (not max, not min).
Optimal = 70°C GPU, 75°C CPU (performance sweet spot, minimal degradation).

```
Required h = Q / (A × (T_target - T_ambient))

Fan% = (h / h_max)^(1/0.8) × 100
```

| GPU Power (W) | Required h (W/m²·°C) | Fan % (25°C amb) | Fan % (35°C amb) |
|---------------|----------------------|-------------------|-------------------|
| 10 (idle)     | 11.1                 | 0% (passive OK)   | 0% (passive OK)   |
| 45            | 50.0                 | 28%               | 38%               |
| 80            | 88.9                 | 45%               | 62%               |
| 115           | 127.8                | 60%               | 85%               |
| 140           | 155.6                | 72%               | 100%              |

### 6.3 Predictive Fan Ramp

Instead of reactive fan control (temperature rises → fan speeds up),
use PREDICTIVE control based on workload detection:

```
fan_speed(t) = fan_curve(Q_predicted(t + Δt_lookahead))

Where:
  Δt_lookahead = τ/3 ≈ 19 seconds (GPU), 6.4 seconds (CPU)
  Q_predicted = inference scheduler's next workload estimate
```

**Algorithm**:
1. Monitor orchestrator task queue length
2. When new inference request arrives, IMMEDIATELY set fan to predicted steady-state
3. Temperature never overshoots → no throttling → consistent performance

---

## 7. COMPLETE N-S THERMAL STATE VECTOR

For NovaX monitoring, the full thermal state at any time t:

```
Θ(t) = {
  T_gpu(t),          # GPU junction temperature [°C]
  T_cpu(t),          # CPU junction temperature [°C]
  T_hotspot(t),      # Maximum hotspot [°C]
  Pr_nova(t),        # Thermal stress ratio (>1.0 = throttle imminent)
  Nu_eff(t),         # Cooling effectiveness
  Fo(t),             # Progress toward thermal equilibrium
  t_throttle(t),     # Predicted seconds until throttle (∞ if safe)
  P_headroom(t),     # Available thermal power budget [W]
  fan_optimal(t),    # N-S derived optimal fan speed [%]
}
```

### Ternary State Classification:
```
Pr_nova < 0.5  → +1 (COLD, can add workload)
0.5 ≤ Pr < 1.0 → 0  (WARM, monitor closely)
Pr_nova ≥ 1.0  → -1 (HOT, must shed load or throttle)
```

---

## 8. SUMMARY OF KEY FORMULAS WITH HARDWARE VALUES

```
# Time to throttle (seconds)
t_throttle = -56.7 × ln((86 - 25 - P×0.42) / (T_now - 25 - P×0.42))  # GPU
t_throttle = -19.1 × ln((95 - 25 - P×0.62) / (T_now - 25 - P×0.62))  # CPU

# Max sustainable power
P_gpu_max = (86 - T_ambient) / 0.42  # Watts
P_cpu_max = (95 - T_ambient) / 0.62  # Watts

# Thermal stress ratio (Pr_nova)
Pr_nova = P_total / ((86 - T_ambient) / 0.42 + (95 - T_ambient) / 0.62)

# Optimal fan speed
fan% = ((P_total / (0.02 × (70 - T_ambient))) / 120)^1.25 × 100

# Burst duration before throttle
t_burst = C_thermal × (T_limit - T_current) / (P_burst - P_max_sustained)

# Temperature prediction
T(t) = T_amb + P×R × (1 - e^(-t/τ)) + (T_0 - T_amb) × e^(-t/τ)
```

---

## 9. IMPLEMENTATION NOTES FOR NOVAX

This mapping enables a `nova_thermal` micro-tool that:
1. Reads GPU/CPU temps via `nvidia-smi` and `ryzenadj` / WMI
2. Computes all 10 dimensionless numbers in real-time
3. Predicts throttling N seconds ahead
4. Outputs ternary state (+1/0/-1) for orchestrator routing
5. Feeds optimal fan curve to system fan controller
6. Integrates with HiveMind to shed load when Pr_nova → 1.0

The N-S energy equation gives us a PHYSICS-BASED thermal model instead
of reactive threshold-based control. This is the same approach used in
data center cooling optimization (Google DeepMind reduced cooling costs
by 40% using similar physics-informed models).
