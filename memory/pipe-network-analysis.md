# Pipe Network Analysis → NovaX Service Mesh Routing

## Complete Fluid Mechanics Mapping for Service Mesh Optimization

---

## 1. HARDY-CROSS METHOD → Iterative Load Balancing

### Fluid Mechanics
The Hardy-Cross method solves for flow distribution in closed-loop pipe networks by iterative correction. Given an initial estimated flow distribution that satisfies continuity (mass balance at every node), it adjusts flows around each loop until head losses balance.

**Core equation:**
```
Correction ΔQ = -Σ(h_f_i) / Σ(∂h_f_i/∂Q_i)

Where:
  h_f_i = head loss in pipe i (using Darcy-Weisbach)
  ∂h_f_i/∂Q_i = derivative of head loss w.r.t. flow
  Summation is around a closed loop
```

For Darcy-Weisbach with turbulent flow (h_f proportional to Q²):
```
ΔQ = -Σ(f_i × L_i × Q_i² / (2g × D_i × A_i²)) / Σ(2 × f_i × L_i × |Q_i| / (2g × D_i × A_i²))
     = -Σ(h_f_i) / Σ(2 × |h_f_i| / Q_i)
```

### NovaX Mapping
Each "loop" = a set of alternative service paths that connect the same source/sink. The "head loss" = latency. Continuity = all requests are handled (none dropped).

| Fluid Term | NovaX Term |
|---|---|
| Pipe network | Service mesh topology |
| Node | Service endpoint or load balancer |
| Loop | Set of alternative routing paths (A→C vs A→B→C) |
| Flow Q | Request rate (req/s) through a path |
| Head loss h_f | End-to-end latency through a path |
| Continuity at node | All incoming requests = all outgoing requests (no drops) |
| Correction ΔQ | Request redistribution delta |
| Convergence | All paths in a loop have equal latency |

**Key insight**: At equilibrium, parallel paths between the same endpoints should have equal latency. If path A has higher latency, shift requests to path B until they balance — exactly Hardy-Cross.

### Hardy-Cross Pseudocode for NovaX

```python
def hardy_cross_load_balance(mesh, tolerance=5, max_iterations=50):
    """
    mesh.loops: list of routing loops (alternative paths between same endpoints)
    mesh.paths: dict of path_id -> PathInfo(services, flow_rate, latency)
    tolerance: max allowed latency imbalance in ms
    max_iterations: convergence limit

    Returns: balanced flow distribution
    """

    # STEP 1: Initial flow estimate — distribute evenly
    for loop in mesh.loops:
        total_demand = loop.total_request_rate
        n_paths = len(loop.paths)
        for path in loop.paths:
            path.flow_rate = total_demand / n_paths

    # STEP 2: Iterative correction
    for iteration in range(max_iterations):
        max_imbalance = 0

        for loop in mesh.loops:
            # Compute latency for each path at current flow
            # Convention: clockwise paths positive, counter-clockwise negative
            sum_latency = 0.0       # Σ h_f (signed)
            sum_derivative = 0.0    # Σ |∂h_f/∂Q|

            for path in loop.paths:
                latency = compute_path_latency(path)  # Darcy-Weisbach analog
                sign = path.direction  # +1 or -1 based on loop convention

                sum_latency += sign * latency
                # For quadratic model: ∂h/∂Q = 2h/Q
                if path.flow_rate > 0:
                    sum_derivative += 2 * abs(latency) / path.flow_rate

            # Correction
            if sum_derivative > 0:
                delta_q = -sum_latency / sum_derivative
            else:
                delta_q = 0

            # Apply correction to all paths in this loop
            for path in loop.paths:
                path.flow_rate += path.direction * delta_q
                # Enforce minimum flow (no negative request rates)
                path.flow_rate = max(path.flow_rate, 0.01)

            max_imbalance = max(max_imbalance, abs(sum_latency))

        # STEP 3: Check convergence
        if max_imbalance < tolerance:
            return ConvergenceResult(
                status=+1,  # ternary: converged
                iterations=iteration + 1,
                distribution={p.id: p.flow_rate for loop in mesh.loops for p in loop.paths}
            )

    return ConvergenceResult(
        status=0,  # ternary: partial convergence
        iterations=max_iterations,
        distribution={p.id: p.flow_rate for loop in mesh.loops for p in loop.paths}
    )


def compute_path_latency(path):
    """
    Darcy-Weisbach analog for a service chain path.
    latency = Σ [f_i × (L_i / D_i) × (v_i² / 2)]  +  Σ K_j × (v²/2)

    Where for each service i in the chain:
      f_i = friction_factor (from Moody chart analog)
      L_i = chain_depth (number of downstream hops)
      D_i = capacity (max req/s)
      v_i = throughput = flow_rate / capacity
      K_j = minor loss coefficient for overhead j
    """
    total_latency = 0.0

    for service in path.services:
        Re = compute_reynolds(service, path.flow_rate)
        f = moody_friction_factor(Re, service.error_rate)

        throughput_ratio = path.flow_rate / service.capacity

        # Major loss: processing latency
        major_loss = f * (service.chain_depth / service.capacity) * (throughput_ratio ** 2) / 2

        # Minor losses: overhead
        minor_loss = sum(k * (throughput_ratio ** 2) / 2 for k in service.minor_loss_coefficients)

        total_latency += service.base_latency + major_loss + minor_loss

    return total_latency
```

---

## 2. DARCY-WEISBACH EQUATION → Latency Model

### Fluid Mechanics
```
h_f = f × (L/D) × (v² / 2g)

Where:
  h_f = head loss (energy loss per unit weight)
  f = Darcy friction factor (dimensionless)
  L = pipe length
  D = pipe diameter
  v = flow velocity
  g = gravitational acceleration
```

### NovaX Mapping
```
latency = friction_factor × (chain_length / capacity) × (throughput² / 2)

Where:
  latency        [ms]    = total added delay beyond base
  friction_factor [-]    = f(Re, error_rate) from Moody analog
  chain_length   [-]     = number of services in the processing chain
  capacity       [req/s] = maximum throughput of the bottleneck service
  throughput     [req/s] = current request rate
```

| Darcy-Weisbach | NovaX Analog | Units |
|---|---|---|
| h_f (head loss) | Added latency beyond baseline | ms |
| f (friction factor) | Service quality degradation factor | dimensionless |
| L (pipe length) | Chain length (# services in path) | count |
| D (pipe diameter) | Service capacity (max req/s) | req/s |
| v (velocity) | Current throughput | req/s |
| g (gravity) | Normalization constant (set to 1 for simplicity, or calibrate) | — |
| ρ (density) | Request complexity / payload size | bytes |

**Why quadratic in throughput?** As throughput approaches capacity, latency grows non-linearly due to queueing effects (M/M/1 queue latency is 1/(capacity - throughput), which for moderate loads approximates a power law). The v² term captures this convexity.

**Practical formula for NovaX:**
```
added_latency_ms = f × (n_services / max_rps) × (current_rps² / (2 × CALIBRATION_CONST))

Where CALIBRATION_CONST is tuned empirically per deployment.
```

---

## 3. MOODY CHART → Service Quality Chart

### Fluid Mechanics
The Moody chart relates friction factor f to Reynolds number Re and relative roughness (epsilon/D).

**Laminar region (Re < 2300):**
```
f = 64 / Re
```

**Turbulent region (Re > 4000) — Colebrook equation:**
```
1/sqrt(f) = -2 × log10(epsilon/(3.7×D) + 2.51/(Re×sqrt(f)))
```
This is implicit in f; solved iteratively or via approximations (e.g., Swamee-Jain).

**Transition region (2300 < Re < 4000):**
Unstable, oscillates between laminar and turbulent.

### NovaX Mapping

**Reynolds number analog:**
```
Re_nova = (request_rate × payload_size) / service_viscosity

Where:
  request_rate   = current req/s to the service
  payload_size   = average request size in bytes
  service_viscosity = processing overhead per byte (ms/byte)
                     = inverse of service efficiency
```

Interpretation:
- **Low Re (< 27)**: Laminar — service is lightly loaded, predictable latency, linear scaling
- **Transition (27-343)**: Unpredictable — latency jitter, occasional timeouts
- **High Re (> 343)**: Turbulent — heavy load, chaotic latency, requires active management

(Boundaries use the 3-5-7-13 harmonic: 3^3=27, 7^3=343)

**Roughness epsilon → Error rate:**
```
epsilon = service_error_rate  (fraction 0.0 to 1.0)
Relative roughness = epsilon / capacity
```

A "smooth" service (low error rate) has lower friction. A "rough" service (high error rate) causes more energy loss (latency).

**NovaX Moody Chart:**

```
Friction Factor (f)
     |
0.10 |  xxxxxxx                          epsilon/D = 0.05 (5% error rate)
     |         xxxxxxxx
0.08 |                 xxxxxxxx           epsilon/D = 0.02
     |  xxx                   xxxxxxx
0.06 |     xxxxx                          epsilon/D = 0.01
     |          xxxxxx
0.04 |  LAMINAR      xxxxxxxxxxxxx        epsilon/D = 0.001 (smooth)
     |  f=64/Re            xxxxxxxxxxxx
0.02 |  xxxxxxxxx                  xxxxxx epsilon/D = 0.0001
     |           xxxxxxxx
0.01 |______|________|_____________|______
     1     27       343          2187     Re_nova
          (3^3)    (7^3)        (3^7)

     LAMINAR  TRANSITION   TURBULENT
```

**Friction factor computation for NovaX:**
```python
def moody_friction_factor(Re_nova, error_rate):
    """
    Returns friction factor for a NovaX service.

    Re_nova: Reynolds number analog
    error_rate: service error rate (0.0 to 1.0), maps to roughness
    """
    epsilon = error_rate

    # Laminar: Re < 27
    if Re_nova < 27:
        return 64.0 / max(Re_nova, 0.1)

    # Transition: 27 <= Re < 343 — interpolate
    if Re_nova < 343:
        f_laminar = 64.0 / Re_nova
        f_turbulent = colebrook_solve(Re_nova, epsilon)
        # Linear interpolation by position in transition band
        t = (Re_nova - 27) / (343 - 27)
        return f_laminar * (1 - t) + f_turbulent * t

    # Turbulent: Re >= 343 — Colebrook (iterative)
    return colebrook_solve(Re_nova, epsilon)


def colebrook_solve(Re, epsilon, capacity=1.0, max_iter=20, tol=1e-6):
    """
    Solve Colebrook equation iteratively:
    1/sqrt(f) = -2*log10(epsilon/(3.7*capacity) + 2.51/(Re*sqrt(f)))

    Uses Swamee-Jain initial guess then Newton refinement.
    """
    relative_roughness = epsilon / max(capacity, 0.001)

    # Swamee-Jain approximation (explicit, good initial guess)
    import math
    term1 = relative_roughness / 3.7
    term2 = 5.74 / (Re ** 0.9)
    f = 0.25 / (math.log10(term1 + term2) ** 2)

    # Newton-Raphson refinement
    for _ in range(max_iter):
        sqrt_f = math.sqrt(f)
        lhs = 1.0 / sqrt_f
        rhs = -2.0 * math.log10(relative_roughness / 3.7 + 2.51 / (Re * sqrt_f))
        residual = lhs - rhs

        if abs(residual) < tol:
            break

        # Derivative of residual w.r.t. f
        d_lhs = -0.5 / (f * sqrt_f)
        d_rhs = -2.0 * (2.51 * 0.5 / (Re * f * sqrt_f)) / (
            math.log(10) * (relative_roughness / 3.7 + 2.51 / (Re * sqrt_f))
        )
        d_residual = d_lhs - d_rhs

        f = f - residual / d_residual
        f = max(f, 1e-8)

    return f
```

---

## 4. PARALLEL PIPES → Load-Balanced Replicas

### Fluid Mechanics
For parallel pipes connecting the same two nodes:
- Head loss is **equal** across all parallel branches (h_f1 = h_f2 = ... = h_fn)
- Total flow = sum of individual flows: Q_total = Q_1 + Q_2 + ... + Q_n
- Equivalent resistance: `1/K_eq = Σ(1/K_i)` where `h_f = K × Q²`

### NovaX Mapping
Parallel pipes = **replicas of the same service** or **alternative services** behind a load balancer.

```
At equilibrium:
  latency_replica_1 = latency_replica_2 = ... = latency_replica_n

Total capacity:
  capacity_total = capacity_1 + capacity_2 + ... + capacity_n

Flow distribution:
  Each replica gets flow proportional to its capacity (inverse of its resistance).
```

| Parallel Pipes | NovaX Replicas |
|---|---|
| Same head loss across all branches | Equal latency target across replicas |
| Total flow = sum of flows | Total throughput = sum of replica throughputs |
| Higher diameter = more flow | Higher capacity = more requests routed |
| Adding a pipe = more total capacity | Adding a replica = more total capacity |

**Equivalent capacity for heterogeneous replicas:**
```python
def parallel_equivalent_capacity(replicas):
    """
    For replicas with different capacities, compute equivalent.
    Using resistance K where latency = K * flow^2:
      K_i = friction_factor_i * chain_length_i / capacity_i
      1/sqrt(K_eq) = Σ 1/sqrt(K_i)
    """
    sum_inv_sqrt_k = 0
    for r in replicas:
        K_i = r.friction_factor * r.chain_length / r.capacity
        sum_inv_sqrt_k += 1.0 / (K_i ** 0.5)

    K_eq = 1.0 / (sum_inv_sqrt_k ** 2)
    return K_eq


def optimal_flow_split(replicas, total_flow):
    """
    Distribute flow so all replicas have equal latency.
    For quadratic model: Q_i proportional to 1/sqrt(K_i)
    """
    resistances = []
    for r in replicas:
        K_i = r.friction_factor * r.chain_length / r.capacity
        resistances.append(1.0 / (K_i ** 0.5))

    total_inv = sum(resistances)
    return {r.id: total_flow * (inv_k / total_inv)
            for r, inv_k in zip(replicas, resistances)}
```

---

## 5. SERIES PIPES → Service Chains

### Fluid Mechanics
For pipes in series:
- Flow is **equal** through all pipes: Q_1 = Q_2 = ... = Q_n
- Total head loss = sum of individual losses: h_total = h_1 + h_2 + ... + h_n
- Equivalent resistance: K_eq = K_1 + K_2 + ... + K_n

### NovaX Mapping
Series pipes = **service chain** (e.g., API Gateway → Auth → Business Logic → Database).

```
Through a service chain:
  request_rate is the SAME through all services (one request traverses all)
  total_latency = latency_service_1 + latency_service_2 + ... + latency_service_n
```

| Series Pipes | Service Chain |
|---|---|
| Equal flow in all pipes | Same request passes through each service |
| Total head loss = sum | Total latency = sum of service latencies |
| Bottleneck = smallest pipe | Bottleneck = lowest-capacity service |
| Equivalent diameter < smallest | Chain capacity limited by weakest link |

**Critical insight — bottleneck identification:**
```python
def chain_analysis(services, request_rate):
    """
    Analyze a service chain. The chain is only as strong as its weakest link.
    """
    total_latency = 0
    bottleneck = None
    min_headroom = float('inf')

    for svc in services:
        Re = compute_reynolds(svc, request_rate)
        f = moody_friction_factor(Re, svc.error_rate)

        throughput_ratio = request_rate / svc.capacity
        svc_latency = svc.base_latency + f * (1.0 / svc.capacity) * (throughput_ratio ** 2) / 2
        total_latency += svc_latency

        headroom = svc.capacity - request_rate
        if headroom < min_headroom:
            min_headroom = headroom
            bottleneck = svc

    return {
        "total_latency_ms": total_latency,
        "bottleneck_service": bottleneck.id,
        "bottleneck_headroom": min_headroom,
        "chain_capacity": bottleneck.capacity,  # chain limited by bottleneck
        "ternary_status": +1 if min_headroom > 0.2 * bottleneck.capacity else
                           0 if min_headroom > 0 else -1
    }
```

---

## 6. MINOR LOSSES → Overhead

### Fluid Mechanics
Minor losses come from fittings, valves, bends, contractions, expansions:
```
h_minor = K × (v² / 2g)

Where K = loss coefficient (empirical):
  Sharp entrance:      K = 0.5
  Rounded entrance:    K = 0.03
  Sudden expansion:    K = (1 - A1/A2)²
  Sudden contraction:  K ≈ 0.42(1 - A2/A1)
  90° bend:            K = 0.3 - 1.5
  Globe valve (open):  K = 10
  Gate valve (open):   K = 0.15
  Check valve:         K = 2.0
```

### NovaX Mapping

| Pipe Fitting | Service Overhead | K (typical ms multiplier) |
|---|---|---|
| Sharp entrance | Cold start / no connection pool | 0.50 |
| Rounded entrance | Warm connection, keep-alive | 0.03 |
| Sudden expansion | Scale-up handoff (1→N replicas) | (1 - cap_old/cap_new)² |
| Sudden contraction | Scale-down / funnel to bottleneck | 0.42(1 - cap_new/cap_old) |
| 90-degree bend | Protocol translation (HTTP→gRPC) | 0.3 - 1.5 |
| Globe valve (open) | Full auth check (OAuth, JWT verify) | 10.0 |
| Gate valve (open) | Simple API key check | 0.15 |
| Check valve | Rate limiter / circuit breaker check | 2.0 |
| Pipe exit | Response serialization + network TX | 1.0 |
| Tee junction | Fan-out to multiple downstream services | 1.8 |

**NovaX minor loss computation:**
```python
MINOR_LOSS_COEFFICIENTS = {
    "cold_start":           0.50,
    "warm_connection":      0.03,
    "json_serialize":       0.20,
    "json_deserialize":     0.20,
    "protobuf_serialize":   0.05,
    "protobuf_deserialize": 0.05,
    "auth_jwt_verify":      10.0,
    "auth_api_key":         0.15,
    "rate_limit_check":     2.0,
    "circuit_breaker":      2.0,
    "logging_sync":         0.50,
    "logging_async":        0.02,
    "protocol_translate":   1.0,
    "tls_handshake":        5.0,
    "tls_resume":           0.30,
    "fan_out":              1.8,
    "response_compress":    0.80,
}

def compute_minor_losses(service, throughput_ratio):
    """Sum all minor losses for a service transition."""
    total = 0
    for overhead_type in service.overhead_types:
        K = MINOR_LOSS_COEFFICIENTS.get(overhead_type, 0.1)
        total += K * (throughput_ratio ** 2) / 2
    return total
```

---

## 7. WATER HAMMER → Request Spike

### Fluid Mechanics
Water hammer occurs when a valve is suddenly closed in a pipe carrying flowing fluid. The kinetic energy of the moving fluid converts to a pressure wave that travels upstream at the speed of sound in the fluid.

```
Joukowsky equation:
  ΔP = ρ × c × ΔV

Where:
  ΔP = pressure rise
  ρ  = fluid density
  c  = wave speed (speed of sound in the pipe)
  ΔV = change in velocity (= full velocity if instant closure)

Wave speed in pipe:
  c = sqrt(K_fluid / (ρ × (1 + K_fluid × D / (E × t))))

Where:
  K_fluid = bulk modulus of fluid
  E = elastic modulus of pipe wall
  t = pipe wall thickness
  D = pipe diameter
```

### NovaX Mapping

When a service is abruptly shut down, all requests that were flowing to it must be absorbed by remaining services — a "pressure spike."

| Water Hammer | Request Spike |
|---|---|
| Sudden valve closure | Service crash / abrupt shutdown |
| Pressure wave | Latency/error spike propagating upstream |
| Wave speed c | Speed of failure detection (health check interval) |
| Pressure rise ΔP | Request overload factor on remaining services |
| Pipe rupture | Cascade failure (remaining services also crash) |
| Slow valve closure | Graceful shutdown (drain connections) |
| Surge tank | Request queue / buffer |
| Relief valve | Circuit breaker |

**Joukowsky equation for NovaX:**
```
overload_factor = request_rate × detection_speed × capacity_fraction_lost

Where:
  request_rate          = total req/s flowing through the dying service
  detection_speed       = 1 / health_check_interval_seconds
  capacity_fraction_lost = capacity_of_dead_service / total_cluster_capacity
```

**Prevention strategies (mapped from hydraulic engineering):**

```python
class WaterHammerPrevention:
    """
    Fluid engineering solutions → NovaX equivalents
    """

    # 1. SLOW VALVE CLOSURE → Graceful shutdown
    @staticmethod
    def graceful_shutdown(service, drain_time_s=30):
        """
        Stop accepting new requests immediately.
        Drain existing connections over drain_time_s.
        Gradually shift traffic to replicas using Hardy-Cross rebalancing.
        """
        service.accepting_new = False
        service.drain_deadline = time.time() + drain_time_s
        # Orchestrator sees health=DRAINING, shifts new requests away
        return +1

    # 2. SURGE TANK → Request buffer
    @staticmethod
    def request_buffer(service, max_queue_depth=1000):
        """
        Buffer requests during spike instead of rejecting immediately.
        Like a surge tank absorbing pressure waves.
        """
        if service.queue_depth < max_queue_depth:
            service.queue.append(request)
            return 0  # buffered, not yet processed
        else:
            return -1  # buffer overflow, reject

    # 3. RELIEF VALVE → Circuit breaker
    @staticmethod
    def circuit_breaker(service, error_threshold=0.5, cooldown_s=30):
        """
        When error rate exceeds threshold, open circuit.
        Like a relief valve opening to prevent pipe rupture.
        Prevents cascade failure.
        """
        if service.error_rate > error_threshold:
            service.circuit = "OPEN"
            service.circuit_reset_at = time.time() + cooldown_s
            return -1  # requests fail-fast
        elif service.circuit == "OPEN" and time.time() > service.circuit_reset_at:
            service.circuit = "HALF-OPEN"
            return 0   # allow test requests
        else:
            service.circuit = "CLOSED"
            return +1  # normal flow

    # 4. CHECK VALVE → No backpressure propagation
    @staticmethod
    def backpressure_isolation(upstream, downstream):
        """
        Prevent downstream failure from propagating upstream.
        Like a check valve preventing reverse flow.
        """
        if downstream.latency > downstream.sla_limit:
            upstream.shed_load_to(downstream, factor=0.5)
            return 0
        return +1

    # 5. WAVE SPEED REDUCTION → Faster failure detection
    @staticmethod
    def fast_detection(health_check_interval=1.0):
        """
        Faster health checks = detect failures sooner = smaller spike.
        Analogous to reducing wave speed (slower wave = less pressure rise).

        Actually the analogy is inverted: faster detection REDUCES overload_factor.
        In hydraulics, longer pipe = more stored kinetic energy.
        In NovaX, longer detection delay = more requests pile up.

        overload = accumulated_requests = rate × detection_delay
        """
        return health_check_interval  # lower = better
```

---

## UNIFIED ROUTING MODEL

Combining all seven concepts into a single routing decision engine:

```python
class PipeNetworkRouter:
    """
    NovaX service mesh router using pipe network analysis.

    Combines:
    - Hardy-Cross iterative load balancing
    - Darcy-Weisbach latency model
    - Moody chart friction factors
    - Parallel/series pipe analysis
    - Minor loss accounting
    - Water hammer prevention
    """

    def __init__(self, mesh_topology):
        self.mesh = mesh_topology
        self.flow_distribution = {}
        self.convergence_history = []
        self.REYNOLDS_LAMINAR = 27     # 3^3
        self.REYNOLDS_TURBULENT = 343  # 7^3
        self.BLOCK_SIZE = 2187         # 3^7

    def route_request(self, request):
        """
        Main routing decision for a single request.
        Returns the optimal path through the service mesh.
        """
        # 1. Check water hammer — any service in spike recovery?
        for svc in self.mesh.services:
            if svc.circuit == "OPEN":
                # Exclude from candidate paths
                self.mesh.disable_path_through(svc)

        # 2. Get candidate paths (parallel options)
        candidates = self.mesh.get_paths(request.source, request.destination)

        # 3. Score each path using Darcy-Weisbach + minor losses
        scored = []
        for path in candidates:
            # Series analysis: total latency through chain
            total_latency = 0
            chain_capacity = float('inf')

            for i, svc in enumerate(path.services):
                # Major loss
                Re = self.compute_reynolds(svc)
                f = moody_friction_factor(Re, svc.error_rate)
                throughput_ratio = svc.current_load / svc.capacity
                major = f * (len(path.services) / svc.capacity) * (throughput_ratio ** 2) / 2

                # Minor losses at transitions
                minor = 0
                if i == 0:
                    minor += MINOR_LOSS_COEFFICIENTS["warm_connection"]
                if i > 0:
                    minor += MINOR_LOSS_COEFFICIENTS["json_deserialize"]
                    minor += MINOR_LOSS_COEFFICIENTS["json_serialize"]
                for overhead in svc.overhead_types:
                    minor += MINOR_LOSS_COEFFICIENTS.get(overhead, 0)
                minor *= (throughput_ratio ** 2) / 2

                total_latency += svc.base_latency + major + minor
                chain_capacity = min(chain_capacity, svc.capacity - svc.current_load)

            scored.append({
                "path": path,
                "latency": total_latency,
                "headroom": chain_capacity,
                "ternary": +1 if chain_capacity > 10 else (0 if chain_capacity > 0 else -1)
            })

        # 4. Select best path (lowest latency with positive headroom)
        viable = [s for s in scored if s["ternary"] >= 0]
        if not viable:
            return None  # all paths saturated — trigger water hammer prevention

        best = min(viable, key=lambda s: s["latency"])
        return best["path"]

    def rebalance(self):
        """
        Run Hardy-Cross iteration to rebalance all loops.
        Called periodically (every 3-7 seconds per harmonic).
        """
        return hardy_cross_load_balance(self.mesh, tolerance=5, max_iterations=50)

    def compute_reynolds(self, service):
        """
        Re = (request_rate × avg_payload) / viscosity
        """
        return (service.current_load * service.avg_payload_bytes) / service.viscosity

    def get_moody_chart_data(self):
        """
        Generate Moody chart data for all services.
        Used for the NovaX monitoring dashboard.
        """
        chart = []
        for svc in self.mesh.services:
            Re = self.compute_reynolds(svc)
            f = moody_friction_factor(Re, svc.error_rate)
            chart.append({
                "service": svc.id,
                "reynolds": Re,
                "friction": f,
                "error_rate": svc.error_rate,
                "region": "laminar" if Re < 27 else ("transition" if Re < 343 else "turbulent"),
                "status": +1 if f < 0.04 else (0 if f < 0.08 else -1)
            })
        return chart
```

---

## TERNARY INTEGRATION

All results expressed in ternary (-1, 0, +1):

| Condition | Ternary | Meaning |
|---|---|---|
| Re < 27, f < 0.04 | +1 | Laminar, smooth, optimal |
| 27 < Re < 343, or 0.04 < f < 0.08 | 0 | Transition, needs monitoring |
| Re > 343, f > 0.08 | -1 | Turbulent, intervention needed |
| Hardy-Cross converged | +1 | Balanced |
| Hardy-Cross partial | 0 | Partially balanced |
| Hardy-Cross diverged | -1 | Unstable, manual intervention |
| Headroom > 20% | +1 | Healthy |
| 0 < Headroom < 20% | 0 | Caution |
| Headroom <= 0 | -1 | Overloaded |
| Circuit breaker closed | +1 | Normal flow |
| Circuit breaker half-open | 0 | Testing recovery |
| Circuit breaker open | -1 | Service isolated |

---

## 3-5-7-13 HARMONIC INTEGRATION

| Harmonic | Pipe Network Use |
|---|---|
| 3 (ternary base) | All states: +1/0/-1 |
| 5 (TZip pack, 3^5=243) | Max parallel replicas per service group |
| 7 (composition unit, 3^7=2187) | Max block size for request batching |
| 13 (carrier/frame) | Health check cycle: every 13 seconds for deep, 3 for shallow |
| 3^3=27 | Laminar→transition boundary |
| 7^3=343 | Transition→turbulent boundary |
| 3^7=2187 | Maximum request buffer depth (surge tank capacity) |

---

## SUMMARY TABLE

| Fluid Mechanics Concept | NovaX Service Mesh Analog | Key Equation |
|---|---|---|
| Hardy-Cross method | Iterative load balancer | ΔQ = -Σh/Σ(2h/Q) |
| Darcy-Weisbach | Latency model | lat = f(L/D)(v²/2) |
| Moody chart | Service quality dashboard | f = f(Re, epsilon) |
| Parallel pipes | Replicated services | cap_total = Σcap_i |
| Series pipes | Service chains | lat_total = Σlat_i |
| Minor losses | Overhead (auth, serde, TLS) | h = K(v²/2) |
| Water hammer | Request spike / cascade failure | ΔP = ρcΔv |
| Surge tank | Request buffer/queue | Absorbs spikes |
| Relief valve | Circuit breaker | Prevents cascade |
| Check valve | Backpressure isolation | No reverse propagation |
| Slow valve closure | Graceful shutdown / drain | Prevents spikes |
| Reynolds number | Load classification | Re = rate×size/viscosity |
| Friction factor | Service degradation factor | From Moody analog |
| Roughness epsilon | Service error rate | Higher = more friction |
