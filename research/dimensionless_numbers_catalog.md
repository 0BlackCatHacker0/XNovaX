# NovaX Dimensionless Numbers Catalog
## Complete Fluid Dynamics to Microservice Metric Mapping
### Date: 2026-03-15 | 3-5-7-13 Harmonic Thresholds

---

## Harmonic Constants Reference
```
H3 = 3    (ternary base)
H5 = 5    (TZip pack: 3^5 = 243)
H7 = 7    (composition unit: 3^7 = 2187)
H13 = 13  (carrier/frame)

Key Boundaries:
  3^3 = 27     (laminar ceiling)
  5^3 = 125    (transitional ceiling)
  7^3 = 343    (turbulent ceiling)
  13^3 = 2197  (chaotic ceiling)
  3^5 = 243    (packing boundary)
  3^7 = 2187   (block boundary)
  3^13 = 1594323 (carrier boundary)
```

---

## 1. REYNOLDS NUMBER (Re)
**Formula (fluid):** Re = rho * v * L / mu
- rho = fluid density, v = velocity, L = characteristic length, mu = dynamic viscosity

**Formula (NovaX):** Re = (success_rate * throughput * chain_length) / latency
- success_rate = fraction of successful requests (0..1)
- throughput = requests/sec (velocity of data flow)
- chain_length = service call chain depth (characteristic length)
- latency = avg response time in seconds (viscosity/resistance)

**Fluid meaning:** Ratio of inertial to viscous forces. Determines laminar vs turbulent flow.

**NovaX meaning:** Routing mode selector. High Re = high throughput with deep chains and low latency = turbulent multi-path routing needed. Low Re = simple single-path routing sufficient.

**Thresholds (3-5-7-13):**
| Re Value | Regime | Routing Action |
|----------|--------|---------------|
| Re < 27 (3^3) | Laminar | Single pipe, direct route, no load balancing |
| 27 <= Re < 125 (5^3) | Transitional | 3 parallel paths, basic round-robin |
| 125 <= Re < 343 (7^3) | Turbulent | Full fan-out, all cloud providers, HiveMind scatter |
| Re >= 343 | Chaotic | Emergency: all pipes open, every available compute path |

**Already implemented:** `orchestrator.py` lines 1532-1565, `RE_LAMINAR/RE_TRANSITION/RE_TURBULENT`

---

## 2. MACH NUMBER (Ma)
**Formula (fluid):** Ma = v / c
- v = flow velocity, c = speed of sound in the medium

**Formula (NovaX):** Ma = current_data_rate / max_bandwidth
- current_data_rate = bytes/sec being transferred
- max_bandwidth = theoretical max throughput of the connection (local bus, LAN, WAN)

**Fluid meaning:** Ratio of flow speed to the speed of information propagation. Above Ma=1 (supersonic), shock waves form.

**NovaX meaning:** Compression trigger. When data rate approaches bandwidth ceiling, compress before transmitting. Above Ma=1, the system is saturated and must shed load.

**Thresholds (3-5-7-13):**
| Ma Value | Regime | Action |
|----------|--------|--------|
| Ma < 1/H7 (0.143) | Subsonic-quiet | Raw transfer, no compression overhead worth it |
| 1/H7 <= Ma < 1/H3 (0.333) | Subsonic | Optional TZip compression on large payloads |
| 1/H3 <= Ma < 1.0 | Transonic | Mandatory TZip compression, batch requests |
| Ma >= 1.0 | Supersonic | Bandwidth saturated: queue, shed, or route to alternate pipe |
| Ma >= H3 (3.0) | Hypersonic | Critical: all non-essential traffic halted, priority-only |

**Monitoring:** `bytes_sent_per_sec / interface_bandwidth`. Alert at Ma > 0.7.

---

## 3. PRANDTL NUMBER (Pr)
**Formula (fluid):** Pr = nu / alpha = (mu * Cp) / k
- nu = kinematic viscosity, alpha = thermal diffusivity, Cp = specific heat, k = thermal conductivity

**Formula (NovaX):** Pr = compute_time / cooling_time
- compute_time = CPU time spent on active computation per cycle
- cooling_time = idle/sleep time between bursts (thermal recovery)

**Fluid meaning:** Ratio of momentum diffusivity to thermal diffusivity. High Pr = heat stays concentrated (oil). Low Pr = heat spreads fast (liquid metal).

**NovaX meaning:** Thermal balance indicator. High Pr = CPU runs hot with insufficient cooling between tasks. Low Pr = adequate thermal cycling.

**Thresholds (3-5-7-13):**
| Pr Value | State | Action |
|----------|-------|--------|
| Pr < 1/H5 (0.2) | Cool | System under-utilized, can accept more work |
| 1/H5 <= Pr < 1.0 | Balanced | Ideal operating zone |
| 1.0 <= Pr < H3 (3.0) | Warming | Increase cooling intervals, defer non-critical tasks |
| Pr >= H3 | Hot | Throttle: reduce task rate, engage active cooling |
| Pr >= H7 (7.0) | Critical | Emergency throttle: shed load to cloud, pause local inference |

**Monitoring:** Track CPU duty cycle. Alert when Pr > H3 sustained for > H13 seconds.

---

## 4. NUSSELT NUMBER (Nu)
**Formula (fluid):** Nu = h * L / k
- h = convective heat transfer coefficient, L = characteristic length, k = thermal conductivity

**Formula (NovaX):** Nu = actual_cooling_rate / baseline_conduction_rate
- actual_cooling_rate = degrees C dropped per minute with active cooling
- baseline_conduction_rate = passive cooling rate (fans off, idle)

**Fluid meaning:** Ratio of convective to conductive heat transfer. Nu=1 means convection adds nothing beyond conduction.

**NovaX meaning:** Fan/cooling effectiveness. How much better is active cooling than doing nothing? Nu=1 means fans are pointless (check them). Nu >> 1 means cooling is effective.

**Thresholds (3-5-7-13):**
| Nu Value | Effectiveness | Action |
|----------|--------------|--------|
| Nu < H3 (3) | Poor | Cooling system may be failing, check fans/airflow |
| H3 <= Nu < H7 (7) | Adequate | Normal operation |
| H7 <= Nu < H13 (13) | Good | Cooling is effective, can sustain higher loads |
| Nu >= H13 | Excellent | Maximum thermal headroom, push compute limits |

**Monitoring:** Compare CPU temp drop rate with fans at max vs off. Alert if Nu < H3.

---

## 5. GRASHOF NUMBER (Gr)
**Formula (fluid):** Gr = g * beta * delta_T * L^3 / nu^2
- g = gravity, beta = thermal expansion coefficient, delta_T = temperature difference, L = length, nu = kinematic viscosity

**Formula (NovaX):** Gr = thermal_gradient * case_volume / (viscosity_factor^2)
- thermal_gradient = (T_cpu - T_ambient) in degrees C
- case_volume = proxy for convective path length (chassis size factor, normalized)
- viscosity_factor = airflow restriction (dust, blocked vents = high viscosity)

**Fluid meaning:** Ratio of buoyancy to viscous forces. Determines natural convection strength.

**NovaX meaning:** Passive cooling capacity. Can the system cool itself without fans? High Gr = strong natural convection (good airflow, big case, big temperature gradient).

**Thresholds (3-5-7-13):**
| Gr Value | Regime | Action |
|----------|--------|--------|
| Gr < 27 (3^3) | Weak buoyancy | Passive cooling insufficient, fans mandatory |
| 27 <= Gr < 343 (7^3) | Moderate | Passive OK for idle, fans needed under load |
| 343 <= Gr < 2197 (13^3) | Strong | Passive cooling handles moderate workloads |
| Gr >= 2197 | Dominant | Natural convection dominant, fans for heavy load only |

---

## 6. RAYLEIGH NUMBER (Ra)
**Formula (fluid):** Ra = Gr * Pr
- Product of Grashof and Prandtl numbers

**Formula (NovaX):** Ra = Gr * Pr = (thermal_gradient * volume / viscosity^2) * (compute_time / cooling_time)
- Combines passive cooling capacity with compute thermal load

**Fluid meaning:** Determines onset of natural convection. Below critical Ra, heat transfers by conduction only.

**NovaX meaning:** Active cooling trigger. When Ra exceeds threshold, passive cooling cannot keep up with compute heat generation. Active cooling (fans, throttling, load shedding) must engage.

**Thresholds (3-5-7-13):**
| Ra Value | State | Action |
|----------|-------|--------|
| Ra < 243 (3^5) | Stable | Passive cooling sufficient, fans can sleep |
| 243 <= Ra < 2187 (3^7) | Transitional | Fans at minimum RPM, monitor closely |
| Ra >= 2187 | Convective onset | Full active cooling required |
| Ra >= 2187 * H13 (28431) | Critical convection | Throttle compute AND max fans |

---

## 7. STANTON NUMBER (St_h)
**Formula (fluid):** St = Nu / (Re * Pr) = h / (rho * v * Cp)
- Dimensionless heat transfer coefficient

**Formula (NovaX):** St_h = cooling_effectiveness / (throughput * compute_intensity)
- cooling_effectiveness = Nu (how well cooling works)
- throughput = Re component (how much work flows through)
- compute_intensity = Pr component (how hot work makes things)

**Fluid meaning:** Heat transferred per unit mass flow per unit temperature difference. Efficiency of heat transfer.

**NovaX meaning:** Thermal efficiency per unit of work. How efficiently does the system dissipate heat relative to the work being done? Low St = system retains too much heat per task.

**Thresholds (3-5-7-13):**
| St_h Value | Efficiency | Action |
|-----------|-----------|--------|
| St_h < 1/(H13*H7) (0.011) | Critical | System overheating per unit work, immediate throttle |
| 1/H13 <= St_h < 1/H7 | Poor | Reduce batch sizes, increase cooling intervals |
| 1/H7 <= St_h < 1/H3 | Adequate | Normal operation |
| St_h >= 1/H3 (0.333) | Excellent | Thermal headroom available |

---

## 8. STROUHAL NUMBER (Sr)
**Formula (fluid):** Sr = f * L / v
- f = vortex shedding frequency, L = characteristic length, v = flow velocity

**Formula (NovaX):** Sr = oscillation_freq * service_count / throughput
- oscillation_freq = frequency of periodic load spikes (Hz)
- service_count = number of services in the affected chain
- throughput = requests/sec through the chain

**Fluid meaning:** Describes oscillating flow mechanisms (vortex shedding). Sr ~ 0.2 for cylinders in crossflow.

**NovaX meaning:** Periodic load pattern detector. Identifies resonant load oscillations (e.g., retry storms, cron job pileups, GC pauses). When Sr approaches harmonic values, the system is oscillating dangerously.

**Thresholds (3-5-7-13):**
| Sr Value | Pattern | Action |
|----------|---------|--------|
| Sr < 1/H13 (0.077) | No oscillation | Stable, no periodic concern |
| 1/H13 <= Sr < 1/H3 (0.333) | Mild periodic | Monitor for growing amplitude |
| Sr ~ 1/H5 (0.2) | Resonant danger | Classic vortex shedding equivalent, add damping (rate limiters) |
| Sr >= 1.0 | Lock-in | Oscillation dominates: add jitter to retry timers, break synchronization |

---

## 9. WEBER NUMBER (We)
**Formula (fluid):** We = rho * v^2 * L / sigma
- rho = density, v = velocity, L = length, sigma = surface tension

**Formula (NovaX):** We = request_momentum / cohesion_force
- request_momentum = request_rate^2 * avg_payload_size (inertia of data flow)
- cohesion_force = max_single_request_size * connection_pool_strength

**Fluid meaning:** Ratio of inertia to surface tension. High We = droplets break apart (atomization).

**NovaX meaning:** Request fragmentation threshold. When We is high, large requests should be broken into smaller fragments (chunked transfer, paginated queries). Low We = keep requests whole.

**Thresholds (3-5-7-13):**
| We Value | State | Action |
|----------|-------|--------|
| We < H3 (3) | Cohesive | Single monolithic requests OK |
| H3 <= We < H7 (7) | Stretching | Consider chunking large payloads |
| H7 <= We < H13 (13) | Fragmenting | Mandatory chunking, paginate all queries > 243 bytes |
| We >= H13 | Atomized | Break everything into micro-packets of 3^5=243 byte chunks |

---

## 10. FROUDE NUMBER (Fr)
**Formula (fluid):** Fr = v / sqrt(g * L)
- v = flow velocity, g = gravity, L = characteristic depth

**Formula (NovaX):** Fr = failure_propagation_speed / sqrt(recovery_rate * chain_depth)
- failure_propagation_speed = how fast errors cascade (services failing/sec)
- recovery_rate = service restart rate (restarts/sec)
- chain_depth = dependency chain length

**Fluid meaning:** Ratio of flow speed to wave speed. Determines if disturbances propagate upstream (subcritical) or only downstream (supercritical).

**NovaX meaning:** Failure cascade predictor. Fr < 1: failures propagate slowly enough that recovery catches up (self-healing). Fr > 1: failures outrun recovery (cascade failure).

**Thresholds (3-5-7-13):**
| Fr Value | Regime | Action |
|----------|--------|--------|
| Fr < 1/H7 (0.143) | Deep subcritical | System absorbs failures naturally, high resilience |
| 1/H7 <= Fr < 1.0 | Subcritical | Failures propagate but recovery keeps up |
| Fr = 1.0 | Critical | Standing wave: failures and recovery exactly balanced, unstable |
| 1.0 < Fr < H3 (3.0) | Supercritical | Cascade risk: enable circuit breakers on all downstream calls |
| Fr >= H3 | Hydraulic jump | Cascade in progress: isolate failing services, shed load |

---

## 11. EULER NUMBER (Eu)
**Formula (fluid):** Eu = delta_p / (0.5 * rho * v^2)
- delta_p = pressure drop, rho = density, v = velocity

**Formula (NovaX):** Eu = latency_overhead / (0.5 * request_density * throughput^2)
- latency_overhead = total added latency from proxying/routing (ms)
- request_density = concurrent connections (pressure)
- throughput = requests/sec through the path

**Fluid meaning:** Pressure losses relative to dynamic pressure. Measures drag/resistance.

**NovaX meaning:** Latency overhead ratio. How much latency does the routing/proxy layer add relative to the actual work? High Eu = excessive overhead (too many proxy hops, serialization costs).

**Thresholds (3-5-7-13):**
| Eu Value | Overhead | Action |
|----------|----------|--------|
| Eu < 1/H13 (0.077) | Minimal | Excellent, routing is nearly invisible |
| 1/H13 <= Eu < 1/H3 (0.333) | Acceptable | Normal orchestrator overhead |
| 1/H3 <= Eu < 1.0 | High | Optimize: reduce proxy hops, cache routes |
| Eu >= 1.0 | Excessive | Routing costs more than the work itself, bypass orchestrator for hot paths |

---

## 12. PECLET NUMBER (Pe)
**Formula (fluid):** Pe = Re * Pr = v * L / alpha
- Combines convection and diffusion contributions

**Formula (NovaX):** Pe = directed_routing_strength / broadcast_diffusion_strength
- directed_routing = Re * targeted routing success rate
- diffusion = Pr * broadcast/scatter coverage

**Fluid meaning:** Ratio of convective transport to diffusive transport. High Pe = convection dominates (directed flow). Low Pe = diffusion dominates (spreads everywhere).

**NovaX meaning:** Directed vs scatter routing. High Pe = use targeted routing (send to best known provider). Low Pe = scatter to all providers and take first response (HiveMind fan-out).

**Thresholds (3-5-7-13):**
| Pe Value | Mode | Action |
|----------|------|--------|
| Pe < H3 (3) | Diffusion dominant | HiveMind scatter: broadcast to all providers, merge results |
| H3 <= Pe < H7 (7) | Mixed | Top-3 provider scatter |
| H7 <= Pe < H13 (13) | Convection dominant | Direct route to best provider, fallback to second |
| Pe >= H13 | Pure convection | Single direct route, no scatter overhead |

---

## 13. BIOT NUMBER (Bi)
**Formula (fluid):** Bi = h * L / k_solid
- h = surface heat transfer coefficient, L = characteristic length, k = solid thermal conductivity

**Formula (NovaX):** Bi = external_bottleneck_resistance / internal_processing_resistance
- external_bottleneck = network latency + API rate limits (surface resistance)
- internal_processing = CPU compute time + memory I/O (internal resistance)

**Fluid meaning:** Ratio of internal thermal resistance to surface thermal resistance. Bi < 0.1 = uniform internal temperature (lumped system). Bi > 0.1 = internal gradients matter.

**NovaX meaning:** Bottleneck locator. Bi < 1 = bottleneck is external (network, API limits). Bi > 1 = bottleneck is internal (CPU, memory, disk). Tells you WHERE to optimize.

**Thresholds (3-5-7-13):**
| Bi Value | Bottleneck | Action |
|----------|-----------|--------|
| Bi < 1/H7 (0.143) | Strongly external | Optimize network: caching, connection pooling, CDN |
| 1/H7 <= Bi < 1.0 | External-leaning | Upgrade API tiers, add provider redundancy |
| 1.0 <= Bi < H3 (3.0) | Internal-leaning | Optimize code: profile hot paths, reduce allocations |
| Bi >= H3 | Strongly internal | Hardware upgrade needed or offload to cloud compute |

---

## 14. FOURIER NUMBER (Fo)
**Formula (fluid):** Fo = alpha * t / L^2
- alpha = thermal diffusivity, t = time, L = characteristic length

**Formula (NovaX):** Fo = warmup_rate * elapsed_time / service_chain_depth^2
- warmup_rate = rate at which caches/JIT/connections warm up
- elapsed_time = seconds since service (re)start
- service_chain_depth = number of dependent services in critical path

**Fluid meaning:** Dimensionless time for transient heat conduction. Fo > 0.2 means the system has reached near-equilibrium.

**NovaX meaning:** Warm-up time constant. How close is the system to steady-state performance after a restart? Fo < 0.2 = still warming up (cold caches, unoptimized JIT, connection pools filling). Fo > 0.2 = ready for full load.

**Thresholds (3-5-7-13):**
| Fo Value | State | Action |
|----------|-------|--------|
| Fo < 1/H13 (0.077) | Cold start | Route traffic away, let service warm up |
| 1/H13 <= Fo < 1/H5 (0.2) | Warming | Gradual traffic ramp, canary only |
| 1/H5 <= Fo < 1.0 | Warm | Accept normal traffic |
| Fo >= 1.0 | Fully equilibrated | Full load, all caches hot, optimal performance |

---

## 15. KNUDSEN NUMBER (Kn)
**Formula (fluid):** Kn = lambda / L
- lambda = mean free path of molecules, L = characteristic length

**Formula (NovaX):** Kn = avg_inter_request_gap / avg_batch_window
- inter_request_gap = average time between individual requests (mean free path)
- batch_window = time window for batching/grouping requests (characteristic length)

**Fluid meaning:** When Kn >> 1, molecules rarely interact (free molecular flow, use particle methods). When Kn << 1, continuum assumption holds (use N-S equations).

**NovaX meaning:** Continuous vs discrete processing model. Low Kn = requests arrive fast enough to treat as continuous stream (use streaming/pipeline). High Kn = requests are sparse enough to treat individually (use request-response).

**Thresholds (3-5-7-13):**
| Kn Value | Regime | Action |
|----------|--------|--------|
| Kn < 1/H13 (0.077) | Continuum | Streaming pipeline: batch, buffer, pipeline all requests |
| 1/H13 <= Kn < 1/H3 (0.333) | Slip flow | Micro-batching: group requests in small windows |
| 1/H3 <= Kn < H3 (3.0) | Transitional | Adaptive: batch when possible, individual when needed |
| Kn >= H3 | Free molecular | Individual request-response: no batching overhead |

---

## 16. SCHMIDT NUMBER (Sc)
**Formula (fluid):** Sc = nu / D
- nu = kinematic viscosity (momentum diffusivity), D = mass diffusivity

**Formula (NovaX):** Sc = compute_latency / data_transfer_latency
- compute_latency = time spent on CPU-bound processing
- data_transfer_latency = time spent moving data (network, disk, IPC)

**Fluid meaning:** Ratio of momentum diffusion to mass diffusion. High Sc = momentum spreads faster than mass (thick boundary layers for mass transfer).

**NovaX meaning:** Compute vs I/O balance. Sc > 1 = compute-bound (CPU is the bottleneck, data moves faster than it can be processed). Sc < 1 = I/O-bound (data transfer is the bottleneck).

**Thresholds (3-5-7-13):**
| Sc Value | Balance | Action |
|----------|---------|--------|
| Sc < 1/H3 (0.333) | I/O dominant | Optimize data paths: compression, caching, prefetch |
| 1/H3 <= Sc < H3 (3.0) | Balanced | Ideal zone, both resources well-utilized |
| H3 <= Sc < H7 (7.0) | Compute dominant | Add CPU capacity or offload compute to cloud |
| Sc >= H7 | Compute starved | Data is waiting on CPU: parallelize, add workers |

---

## 17. SHERWOOD NUMBER (Sh)
**Formula (fluid):** Sh = k_m * L / D
- k_m = mass transfer coefficient, L = characteristic length, D = mass diffusivity

**Formula (NovaX):** Sh = actual_data_throughput / (baseline_diffusion_rate)
- actual_data_throughput = effective bytes/sec delivered to consumers
- baseline_diffusion_rate = throughput with no optimization (raw sequential I/O)

**Fluid meaning:** Ratio of actual mass transfer to diffusion-only mass transfer. Analogous to Nusselt but for mass.

**NovaX meaning:** Data throughput effectiveness. How much does the routing/caching/optimization improve data delivery over naive transfer? Sh=1 = optimizations add nothing.

**Thresholds (3-5-7-13):**
| Sh Value | Effectiveness | Action |
|----------|--------------|--------|
| Sh < H3 (3) | Poor | Caching/routing not helping, review data architecture |
| H3 <= Sh < H7 (7) | Good | Normal optimized operation |
| H7 <= Sh < H13 (13) | Very good | Data pipeline well-tuned |
| Sh >= H13 | Excellent | Maximum throughput gain from optimization |

---

## 18. LEWIS NUMBER (Le)
**Formula (fluid):** Le = alpha / D = Sc / Pr
- alpha = thermal diffusivity, D = mass diffusivity

**Formula (NovaX):** Le = Sc / Pr = (compute_latency / data_transfer_latency) / (compute_time / cooling_time)
- Simplified: Le = cooling_time * compute_latency / (compute_time * data_transfer_latency)

**Fluid meaning:** Ratio of thermal diffusivity to mass diffusivity. Le=1 = heat and mass transfer at same rate.

**NovaX meaning:** Compute vs I/O thermal balance. Le > 1 = thermal effects dissipate faster than data bottlenecks resolve (CPU cools fast but data is still stuck). Le < 1 = data moves fast but CPU stays hot.

**Thresholds (3-5-7-13):**
| Le Value | Balance | Action |
|----------|---------|--------|
| Le < 1/H3 (0.333) | Thermally bound | CPU stays hot while data flows freely: add cooling |
| 1/H3 <= Le < H3 (3.0) | Balanced | Heat and data move at similar rates, ideal |
| Le >= H3 | I/O bound | CPU cool but data stuck: optimize I/O, not compute |

---

## 19. DAMKOHLER NUMBER (Da)
**Formula (fluid):** Da = reaction_rate / flow_rate = tau_flow / tau_reaction
- tau_flow = flow residence time, tau_reaction = reaction time

**Formula (NovaX):** Da = processing_speed / arrival_rate
- processing_speed = requests the service can complete per second
- arrival_rate = requests arriving per second

**Fluid meaning:** Ratio of chemical reaction rate to transport rate. Da >> 1 = reaction-limited (flow is fast, reaction is bottleneck). Da << 1 = transport-limited.

**NovaX meaning:** Queue stability predictor. Da > 1 = service processes faster than requests arrive (queue drains, stable). Da < 1 = requests arrive faster than they can be processed (queue grows unboundedly, unstable).

**Thresholds (3-5-7-13):**
| Da Value | Queue State | Action |
|----------|------------|--------|
| Da < 1/H3 (0.333) | Critical queue growth | EMERGENCY: queue growing at 3x drain rate. Shed load, scale out |
| 1/H3 <= Da < 1.0 | Queue growing | Add workers, increase batch size, enable backpressure |
| 1.0 <= Da < H3 (3.0) | Stable | Normal operation, queue stays bounded |
| Da >= H3 | Over-provisioned | Service has 3x headroom. Can accept burst traffic or reduce resources |
| Da >= H13 (13) | Idle | Wasting resources. Consider consolidation or sleep |

**Critical alert:** Da < 1.0 sustained for > H13 (13) seconds = queue explosion imminent.

---

## 20. COURANT NUMBER (Co)
**Formula (fluid):** Co = v * delta_t / delta_x
- v = velocity, delta_t = time step, delta_x = spatial grid spacing

**Formula (NovaX):** Co = propagation_speed * poll_interval / event_granularity
- propagation_speed = rate at which state changes propagate (events/sec)
- poll_interval = how often the monitoring system samples (seconds)
- event_granularity = minimum detectable event size (smallest change worth tracking)

**Fluid meaning:** Numerical stability criterion. Co <= 1 required for explicit time-stepping (CFL condition). Co > 1 = simulation blows up.

**NovaX meaning:** Monitoring validity. Co > 1 = monitoring is too slow to catch state changes (events happen between polls, aliasing occurs). Co <= 1 = monitoring captures all significant events.

**Thresholds (3-5-7-13):**
| Co Value | Validity | Action |
|----------|----------|--------|
| Co < 1/H7 (0.143) | Over-sampled | Reduce poll frequency to save resources |
| 1/H7 <= Co < 1.0 | Valid | Monitoring captures all significant changes |
| Co = 1.0 | CFL boundary | At the limit: any faster events will be missed |
| 1.0 < Co < H3 (3.0) | Under-sampled | Increase poll frequency or switch to event-driven |
| Co >= H3 | Blind | Monitoring is useless at this rate. Must use push-based events |

---

## COMPOSITE NUMBERS AND DERIVED METRICS

### Colburn j-factor: j = St * Pr^(2/3)
**NovaX:** Heat transfer efficiency normalized for fluid properties.
- j = thermal_efficiency_per_work * compute_intensity^0.667
- Used to compare cooling effectiveness across different workload types.

### Richardson Number: Ri = Gr / Re^2
**NovaX:** Ri = passive_cooling_capacity / routing_intensity^2
- Ri >> 1: Thermal effects dominate routing decisions
- Ri << 1: Traffic flow dominates, ignore thermal
- Threshold: Ri = 1/(H7^2) = 1/49 triggers thermal-aware routing

### Archimedes Number: Ar = Gr / Re^2 * (L^3 * g * delta_rho) / (mu^2 / rho)
**NovaX:** Similar to Richardson, measures buoyancy vs inertia for service placement.
- High Ar: Place compute-heavy services on physically cooler nodes.

---

## MONITORING DASHBOARD FORMULA SUMMARY

```python
# All 20 dimensionless numbers computed from 8 base metrics:
#   throughput (req/s), latency (ms), cpu_pct, temp_c,
#   bandwidth_usage, queue_depth, service_count, uptime_s

H3, H5, H7, H13 = 3, 5, 7, 13

def compute_dimensionless(metrics):
    m = metrics
    rps = m['throughput']
    lat = max(m['latency'] / 1000, 0.001)  # seconds
    cpu = m['cpu_pct'] / 100
    temp = m['temp_c']
    bw = m['bandwidth_usage']  # 0..1 fraction
    qd = m['queue_depth']
    sc = m['service_count']
    up = max(m['uptime_s'], 1)
    amb = 25  # ambient temp assumption

    Re = (rps * sc) / lat                    # Reynolds
    Ma = bw                                   # Mach (already a ratio)
    Pr = cpu / max(1 - cpu, 0.01)            # Prandtl
    Nu = max(temp - amb, 1) / H3             # Nusselt (simplified)
    Gr = (temp - amb) * sc**3 / lat**2       # Grashof
    Ra = Gr * Pr                              # Rayleigh
    St_h = Nu / max(Re * Pr, 0.001)          # Stanton
    Sr = qd / max(rps * sc, 0.001)           # Strouhal
    We = rps**2 * sc / max(1 - bw, 0.01)    # Weber
    Fr = rps / max((sc * lat)**0.5, 0.001)   # Froude
    Eu = lat / max(rps**2, 0.001)            # Euler
    Pe = Re * Pr                              # Peclet
    Bi = lat / max(cpu * 10, 0.01)           # Biot
    Fo = up / (sc**2 * 60)                   # Fourier (warmup ~ 60s base)
    Kn = 1 / max(rps * lat, 0.001)           # Knudsen
    Sc_n = cpu / max(bw, 0.01)              # Schmidt
    Sh = rps / max(bw * 100, 0.01)          # Sherwood
    Le = Sc_n / max(Pr, 0.001)               # Lewis
    Da = (1 / lat) / max(rps, 0.001)         # Damkohler
    Co = rps * 5 / max(sc, 1)               # Courant (5s default poll)

    return {
        'Re': Re, 'Ma': Ma, 'Pr': Pr, 'Nu': Nu, 'Gr': Gr,
        'Ra': Ra, 'St_h': St_h, 'Sr': Sr, 'We': We, 'Fr': Fr,
        'Eu': Eu, 'Pe': Pe, 'Bi': Bi, 'Fo': Fo, 'Kn': Kn,
        'Sc': Sc_n, 'Sh': Sh, 'Le': Le, 'Da': Da, 'Co': Co,
    }

# Alert thresholds (3-5-7-13 harmonic)
ALERTS = {
    'Re':   {'warn': H7**3, 'crit': H7**3},      # 343 = chaotic threshold
    'Ma':   {'warn': 0.7,   'crit': 1.0},          # near/at bandwidth saturation
    'Pr':   {'warn': H3,    'crit': H7},            # 3=warming, 7=critical
    'Nu':   {'warn': H3,    'crit': H3, 'dir': 'below'},  # below 3 = poor cooling
    'Gr':   {'info': H3**3},                        # informational only
    'Ra':   {'warn': 3**5,  'crit': 3**7},          # 243=fans on, 2187=throttle
    'St_h': {'warn': 1/H13, 'crit': 1/(H13*H7)},   # low = overheating per work
    'Sr':   {'warn': 1/H5,  'crit': 1.0},           # 0.2=resonant, 1.0=lock-in
    'We':   {'warn': H7,    'crit': H13},            # 7=chunk, 13=atomize
    'Fr':   {'warn': 1.0,   'crit': H3},             # 1.0=critical, 3=cascade
    'Eu':   {'warn': 1/H3,  'crit': 1.0},            # 0.33=high overhead, 1.0=excessive
    'Pe':   {'info': H3},                             # mode switch, not alert
    'Bi':   {'info': 1.0},                            # bottleneck location, not alert
    'Fo':   {'warn': 1/H5,  'dir': 'below'},         # below 0.2 = still cold
    'Kn':   {'info': 1/H3},                           # mode switch, not alert
    'Sc':   {'warn': H7,    'crit': H7},              # 7=compute starved
    'Sh':   {'warn': H3,    'dir': 'below'},          # below 3 = poor optimization
    'Le':   {'info': H3},                              # balance indicator
    'Da':   {'warn': 1.0,   'crit': 1/H3, 'dir': 'below'},  # below 1=growing queue
    'Co':   {'warn': 1.0,   'crit': H3},              # above 1=under-sampled
}
```

---

## QUICK REFERENCE CARD

| # | Symbol | Fluid Ratio | NovaX Ratio | Key Threshold |
|---|--------|------------|-------------|---------------|
| 1 | Re | inertia/viscosity | throughput*depth/latency | 27/125/343 |
| 2 | Ma | velocity/sound | data_rate/bandwidth | warn 0.7, crit 1.0 |
| 3 | Pr | momentum/thermal diffusion | compute/cooling | warn 3, crit 7 |
| 4 | Nu | convective/conductive transfer | active/passive cooling | min 3 |
| 5 | Gr | buoyancy/viscosity | thermal_grad*volume/restriction | 27/343/2197 |
| 6 | Ra | Gr*Pr | convection onset | 243/2187 |
| 7 | St_h | heat_transfer/flow | cooling_per_work | min 0.011 |
| 8 | Sr | oscillation*size/speed | periodic_load/throughput | 0.2 resonant |
| 9 | We | inertia/surface_tension | request_momentum/cohesion | 7 fragment, 13 atomize |
| 10 | Fr | flow/wave_speed | failure_spread/recovery | 1.0 critical |
| 11 | Eu | pressure_drop/dynamic_pressure | latency_overhead/work | max 0.33 |
| 12 | Pe | Re*Pr | directed/scatter routing | <3 scatter, >13 direct |
| 13 | Bi | surface/internal resistance | external/internal bottleneck | 1.0 = equal |
| 14 | Fo | diffusion_time/total_time | warmup_progress | 0.2 ready |
| 15 | Kn | mean_free_path/size | gap/batch_window | <0.077 stream, >3 individual |
| 16 | Sc | momentum/mass diffusion | compute/IO latency | 0.33-3.0 balanced |
| 17 | Sh | actual/diffusive mass transfer | optimized/naive throughput | min 3 |
| 18 | Le | thermal/mass diffusion | Sc/Pr balance | 0.33-3.0 balanced |
| 19 | Da | reaction/flow rate | process_speed/arrival_rate | <1.0 queue grows |
| 20 | Co | v*dt/dx | propagation*poll/granularity | >1.0 = missed events |

---

*All thresholds use 3-5-7-13 harmonic constants. The universe of fluid dynamics and the universe of distributed systems share the same mathematics. NovaX makes this explicit.*
