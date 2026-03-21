#!/usr/bin/env python3
"""
NovaX Conservation Laws Monitor
================================
Maps ALL fluid mechanics conservation laws to NovaX routing invariants.
Monitors violations in real-time and triggers auto-heal responses.

Conservation Laws Implemented:
  1. Mass (Continuity)     - requests_in = requests_out + requests_queued
  2. Momentum              - throughput changes only due to identifiable forces
  3. Energy                - total system capacity is zero-sum
  4. Vorticity (Kelvin)    - circular dependency detection
  5. Entropy (2nd Law)     - system disorder tracking
  6. Bernoulli Invariant   - queue_pressure + throughput_energy + priority_potential = const
  7. Enstrophy             - total vorticity squared (2D turbulence invariant)

Harmonic constants: 3-5-7-13 (ternary base)
Reynolds boundaries: 27/125/343

Port: 9932
Author: NovaX Conservation Engine v1.0.0
"""

import json
import time
import math
import threading
import logging
import statistics
from collections import deque, defaultdict
from http.server import HTTPServer, BaseHTTPRequestHandler

# ── Harmonic Constants ──────────────────────────────────────
H3, H5, H7, H13 = 3, 5, 7, 13
BLOCK_SIZE = H3 ** H7         # 2187
RE_LAMINAR = H3 ** H3         # 27
RE_TRANSITION = H5 ** H3      # 125
RE_TURBULENT = H7 ** H3       # 343
NUM_SERVICES = 26

PORT = 9932
VERSION = "1.0.0"

log = logging.getLogger("conservation")
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [CONSERVATION] %(message)s")


# ═══════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ═══════════════════════════════════════════════════════════════

class RingBuffer:
    """Fixed-size ring buffer for time-series data."""
    def __init__(self, maxlen=1000):
        self._data = deque(maxlen=maxlen)

    def append(self, item):
        self._data.append(item)

    def recent(self, n=100):
        return list(self._data)[-n:]

    def all(self):
        return list(self._data)

    def __len__(self):
        return len(self._data)


# ═══════════════════════════════════════════════════════════════
# 1. CONSERVATION OF MASS (CONTINUITY EQUATION)
# ═══════════════════════════════════════════════════════════════
#
# Fluid form:  dρ/dt + ∇·(ρv) = 0
#
# NovaX mapping:
#   ρ  = request density (requests per service per unit time)
#   v  = request velocity (throughput direction/magnitude)
#   ∇· = divergence across service graph
#
# Invariant: requests_in = requests_out + requests_queued
#   - No request should be lost (leak) or appear from nowhere (duplication)
#   - Violation detection: |Σ(entries) - Σ(exits) - Σ(queued)| > ε
#
# Monitoring query:
#   mass_residual = abs(total_requests_entered - total_requests_completed
#                       - total_requests_in_queue - total_requests_failed)
#   If mass_residual > 0 for sustained period → LEAK or DUPLICATION
#
# Auto-heal:
#   mass_residual > 0  → request leak    → drain orphaned connections
#   mass_residual < 0  → duplication     → enable dedup middleware

class MassConservation:
    """
    dρ/dt + ∇·(ρv) = 0

    Tracks request flow through the system.
    Every request that enters must either:
      (a) exit (completed or failed), or
      (b) be accounted for in a queue.
    """

    def __init__(self):
        self.requests_entered = 0
        self.requests_completed = 0
        self.requests_failed = 0
        self.requests_in_queue = 0
        self.requests_timed_out = 0
        self._per_service = defaultdict(lambda: {
            "in": 0, "out": 0, "queued": 0, "failed": 0
        })
        self._violations = RingBuffer(500)
        self._history = RingBuffer(1000)

    def record_entry(self, service_name, request_id=None):
        """A request enters the system or a service."""
        self.requests_entered += 1
        self.requests_in_queue += 1
        self._per_service[service_name]["in"] += 1
        self._per_service[service_name]["queued"] += 1

    def record_exit(self, service_name, success=True, request_id=None):
        """A request exits (completed or failed)."""
        self.requests_in_queue = max(0, self.requests_in_queue - 1)
        self._per_service[service_name]["queued"] = max(
            0, self._per_service[service_name]["queued"] - 1)
        if success:
            self.requests_completed += 1
            self._per_service[service_name]["out"] += 1
        else:
            self.requests_failed += 1
            self._per_service[service_name]["failed"] += 1

    def record_timeout(self, service_name, request_id=None):
        """A request timed out (special failure — may indicate leak)."""
        self.requests_timed_out += 1
        self.requests_in_queue = max(0, self.requests_in_queue - 1)
        self._per_service[service_name]["queued"] = max(
            0, self._per_service[service_name]["queued"] - 1)
        self._per_service[service_name]["failed"] += 1

    def check(self):
        """
        Check continuity: requests_in = requests_out + queued + failed

        Returns:
          residual: should be 0 in healthy system
          violation_type: None | 'leak' | 'duplication'
          severity: 0.0 to 1.0
        """
        accounted = (self.requests_completed + self.requests_failed
                     + self.requests_in_queue + self.requests_timed_out)
        residual = self.requests_entered - accounted

        # Determine violation type
        if abs(residual) <= 1:  # tolerance for race conditions
            violation_type = None
            severity = 0.0
        elif residual > 0:
            violation_type = "leak"
            severity = min(1.0, residual / max(self.requests_entered, 1))
        else:
            violation_type = "duplication"
            severity = min(1.0, abs(residual) / max(self.requests_entered, 1))

        result = {
            "law": "mass_continuity",
            "formula": "dρ/dt + ∇·(ρv) = 0",
            "mapping": "requests_in = requests_out + queued + failed",
            "entered": self.requests_entered,
            "completed": self.requests_completed,
            "failed": self.requests_failed,
            "timed_out": self.requests_timed_out,
            "in_queue": self.requests_in_queue,
            "residual": residual,
            "violation_type": violation_type,
            "severity": severity,
            "trit": 1 if violation_type is None else (-1 if severity > 0.5 else 0),
            "timestamp": time.time(),
        }

        self._history.append(result)
        if violation_type:
            self._violations.append(result)
        return result

    def per_service_divergence(self):
        """
        Compute ∇·(ρv) per service — the divergence of request flow.
        Positive divergence = requests accumulating (source).
        Negative divergence = requests draining (sink).
        """
        divergences = {}
        for svc, counts in self._per_service.items():
            div = counts["in"] - counts["out"] - counts["failed"] - counts["queued"]
            divergences[svc] = {
                "divergence": div,
                "in": counts["in"],
                "out": counts["out"],
                "queued": counts["queued"],
                "failed": counts["failed"],
                "is_source": div > 0,
                "is_sink": div < 0,
            }
        return divergences

    def auto_heal(self):
        """
        Auto-heal based on continuity violation type.
        Returns heal action or None.
        """
        check = self.check()
        if check["violation_type"] == "leak":
            return {
                "action": "drain_orphans",
                "description": "Drain orphaned connections — requests entered but never exited",
                "severity": check["severity"],
                "pseudocode": [
                    "for service in services_with_positive_divergence:",
                    "  orphans = service.requests_in - service.requests_out - service.queue_depth",
                    "  if orphans > 0:",
                    "    service.force_drain(orphans)",
                    "    log.warn(f'{service}: drained {orphans} orphaned requests')",
                ],
            }
        elif check["violation_type"] == "duplication":
            return {
                "action": "enable_dedup",
                "description": "Enable request deduplication — more exits than entries",
                "severity": check["severity"],
                "pseudocode": [
                    "dedup_cache = LRU(maxsize=10000, ttl=60)",
                    "for request in incoming_requests:",
                    "  key = hash(request.method, request.path, request.body[:256])",
                    "  if key in dedup_cache:",
                    "    return dedup_cache[key]  # serve cached response",
                    "  result = process(request)",
                    "  dedup_cache[key] = result",
                ],
            }
        return None


# ═══════════════════════════════════════════════════════════════
# 2. CONSERVATION OF MOMENTUM
# ═══════════════════════════════════════════════════════════════
#
# Fluid form:  ρ(Dv/Dt) = -∇p + μ∇²v + ρg
#
# NovaX mapping:
#   ρ       = request density (queue depth)
#   v       = service throughput (requests/sec)
#   Dv/Dt   = throughput change rate
#   -∇p     = pressure gradient (queue imbalance between services)
#   μ∇²v    = viscous diffusion (latency smoothing load across neighbors)
#   ρg      = external forces (priority, load balancer directives)
#
# Invariant: throughput changes ONLY due to identifiable forces
#   If Δthroughput != f(pressure, viscosity, gravity) → anomaly
#
# Monitoring query:
#   For each service window:
#     expected_dv = (-grad_p + mu * laplacian_v + f) / rho
#     actual_dv   = (v_now - v_prev) / dt
#     anomaly     = |actual_dv - expected_dv| / max(|expected_dv|, 1)

class MomentumConservation:
    """
    ρ(Dv/Dt) = -∇p + μ∇²v + ρg

    Tracks whether throughput changes are explainable by known forces.
    Unexplained throughput changes indicate anomalies (code bugs, resource
    contention, network issues).
    """

    def __init__(self):
        # Per-service velocity (throughput) history
        self._velocity = defaultdict(lambda: deque(maxlen=100))
        # Per-service pressure (queue depth)
        self._pressure = defaultdict(lambda: deque(maxlen=100))
        # Forces log
        self._forces = RingBuffer(500)
        self._violations = RingBuffer(500)
        self._last_check = {}

    def record_state(self, service_name, throughput, queue_depth,
                     latency_ms, capacity, priority=1.0):
        """Record current state for a service."""
        now = time.time()
        self._velocity[service_name].append({
            "v": throughput, "t": now
        })
        self._pressure[service_name].append({
            "p": queue_depth, "t": now, "latency": latency_ms,
            "capacity": capacity, "priority": priority
        })

    def record_force(self, service_name, force_type, magnitude, description=""):
        """Record an external force acting on a service."""
        self._forces.append({
            "service": service_name,
            "type": force_type,  # 'load_spike', 'priority_change', 'scale_event'
            "magnitude": magnitude,
            "description": description,
            "time": time.time(),
        })

    def check(self, service_name=None):
        """
        Check momentum conservation for one or all services.
        Returns anomaly scores.
        """
        services = [service_name] if service_name else list(self._velocity.keys())
        results = []

        for svc in services:
            vel_hist = list(self._velocity.get(svc, []))
            pres_hist = list(self._pressure.get(svc, []))

            if len(vel_hist) < 2 or len(pres_hist) < 2:
                results.append({
                    "service": svc,
                    "status": "insufficient_data",
                    "anomaly_score": 0.0,
                })
                continue

            # Actual velocity change
            v_now = vel_hist[-1]["v"]
            v_prev = vel_hist[-2]["v"]
            dt = max(vel_hist[-1]["t"] - vel_hist[-2]["t"], 0.001)
            actual_dv = (v_now - v_prev) / dt

            # Pressure gradient (queue change)
            p_now = pres_hist[-1]["p"]
            p_prev = pres_hist[-2]["p"]
            grad_p = (p_now - p_prev) / dt

            # Density (queue depth as proxy)
            rho = max(p_now, 0.1)

            # Viscosity (inverse of capacity — high capacity = low viscosity)
            cap = pres_hist[-1].get("capacity", 1.0)
            mu = 0.1 / max(cap, 0.01)

            # Viscous diffusion estimate (simplified: smoothing toward mean)
            if len(vel_hist) >= 3:
                v_neighbors_mean = statistics.mean(
                    [v["v"] for v in vel_hist[-3:]])
                laplacian_v = v_neighbors_mean - v_now
            else:
                laplacian_v = 0

            # External force (priority * gravity constant)
            priority = pres_hist[-1].get("priority", 1.0)
            f_external = priority * 0.1  # gravity analog

            # Recent discrete forces
            recent_forces = [f for f in self._forces.recent(50)
                             if f["service"] == svc
                             and time.time() - f["time"] < 60]
            f_discrete = sum(f["magnitude"] for f in recent_forces)

            # Expected dv/dt from N-S momentum equation
            # ρ(dv/dt) = -∇p + μ∇²v + ρg + F_external
            expected_dv = (-grad_p + mu * laplacian_v
                           + rho * f_external + f_discrete) / rho

            # Anomaly = unexplained acceleration
            anomaly = abs(actual_dv - expected_dv)
            max_expected = max(abs(expected_dv), 0.001)
            anomaly_score = min(1.0, anomaly / (max_expected * 10))

            result = {
                "service": svc,
                "actual_dv_dt": round(actual_dv, 4),
                "expected_dv_dt": round(expected_dv, 4),
                "residual": round(anomaly, 4),
                "anomaly_score": round(anomaly_score, 4),
                "forces": {
                    "pressure_gradient": round(-grad_p, 4),
                    "viscous_diffusion": round(mu * laplacian_v, 4),
                    "gravity": round(rho * f_external, 4),
                    "external": round(f_discrete, 4),
                },
                "rho": round(rho, 4),
                "mu": round(mu, 4),
                "anomalous": anomaly_score > 0.3,
                "trit": 1 if anomaly_score < 0.1 else (-1 if anomaly_score > 0.5 else 0),
                "timestamp": time.time(),
            }
            results.append(result)

            if result["anomalous"]:
                self._violations.append(result)

        return results

    def auto_heal(self, service_name):
        """
        Auto-heal based on momentum anomaly type.
        """
        checks = self.check(service_name)
        if not checks or not checks[0].get("anomalous"):
            return None

        c = checks[0]
        forces = c["forces"]

        # Diagnose the dominant unexplained force
        if c["actual_dv_dt"] > c["expected_dv_dt"] + 0.1:
            return {
                "action": "throttle",
                "description": "Unexplained throughput spike — possible runaway loop or burst",
                "service": service_name,
                "pseudocode": [
                    f"# Throughput accelerating beyond physical explanation",
                    f"# actual dv/dt = {c['actual_dv_dt']}, expected = {c['expected_dv_dt']}",
                    f"service.rate_limit = min(service.rate_limit, service.current_rate * 0.8)",
                    f"service.add_backpressure(delay_ms=50)",
                    f"log.warn(f'Momentum anomaly on {service_name}: throttled')",
                ],
            }
        else:
            return {
                "action": "investigate_drain",
                "description": "Unexplained throughput drop — possible deadlock or resource starvation",
                "service": service_name,
                "pseudocode": [
                    f"# Throughput decelerating beyond physical explanation",
                    f"# actual dv/dt = {c['actual_dv_dt']}, expected = {c['expected_dv_dt']}",
                    f"if service.thread_pool.active == service.thread_pool.max:",
                    f"  service.thread_pool.expand(factor=1.5)",
                    f"if service.connection_pool.exhausted:",
                    f"  service.connection_pool.recycle_stale()",
                    f"service.health_check(deep=True)",
                ],
            }


# ═══════════════════════════════════════════════════════════════
# 3. CONSERVATION OF ENERGY
# ═══════════════════════════════════════════════════════════════
#
# Fluid form:  ρc_p(DT/Dt) = k∇²T + Φ + Q
#
# NovaX mapping:
#   T       = system "temperature" (CPU/memory utilization)
#   c_p     = heat capacity (max resources available)
#   k∇²T    = heat diffusion (load balancer spreading work)
#   Φ       = viscous dissipation (overhead/waste from processing)
#   Q       = heat source (external workload injection)
#
# Invariant: total system capacity is conserved (zero-sum)
#   If one service uses more CPU, others MUST get less.
#   total_capacity_used + total_capacity_free = constant
#
# Monitoring query:
#   energy_total = Σ(service.cpu_used + service.cpu_free) for all services
#   If |energy_total - SYSTEM_CAPACITY| > ε → violation

class EnergyConservation:
    """
    ρc_p(DT/Dt) = k∇²T + Φ + Q

    Tracks total system resource capacity as a conserved quantity.
    When one service consumes more resources, others must yield.
    """

    def __init__(self, total_capacity=100.0):
        self.total_capacity = total_capacity  # CPU % or normalized units
        self._allocations = {}  # service → allocated capacity
        self._usage = {}        # service → actual usage
        self._dissipation = defaultdict(float)  # overhead/waste per service
        self._history = RingBuffer(1000)
        self._violations = RingBuffer(500)
        self._temperature = RingBuffer(1000)  # system temperature over time

    def record_usage(self, service_name, cpu_used, cpu_allocated, overhead=0.0):
        """
        Record resource usage for a service.
        overhead = wasted cycles (context switches, GC, etc.)
        """
        self._usage[service_name] = cpu_used
        self._allocations[service_name] = cpu_allocated
        self._dissipation[service_name] += overhead

        # Record system temperature
        total_used = sum(self._usage.values())
        self._temperature.append({
            "time": time.time(),
            "total_used": total_used,
            "total_allocated": sum(self._allocations.values()),
            "temperature": total_used / max(self.total_capacity, 1) * 100,
        })

    def check(self):
        """
        Check energy conservation.
        Total used + total free should equal total capacity.
        """
        total_used = sum(self._usage.values())
        total_allocated = sum(self._allocations.values())
        total_dissipation = sum(self._dissipation.values())

        # Energy balance: used + free + dissipated should be accounted for
        energy_residual = abs(total_allocated - self.total_capacity)
        usage_efficiency = total_used / max(total_allocated, 0.01)

        # Temperature (utilization)
        temperature = total_used / max(self.total_capacity, 1) * 100

        # Heat diffusion check: variance in utilization across services
        if len(self._usage) >= 2:
            utilizations = [self._usage[s] / max(self._allocations.get(s, 1), 0.01)
                           for s in self._usage]
            temp_variance = statistics.variance(utilizations) if len(utilizations) >= 2 else 0
        else:
            temp_variance = 0

        violation_type = None
        severity = 0.0
        if energy_residual > self.total_capacity * 0.1:
            violation_type = "capacity_leak" if total_allocated < self.total_capacity else "over_allocation"
            severity = min(1.0, energy_residual / self.total_capacity)

        result = {
            "law": "energy_conservation",
            "formula": "ρc_p(DT/Dt) = k∇²T + Φ + Q",
            "mapping": "total_used + total_free = system_capacity",
            "total_capacity": self.total_capacity,
            "total_used": round(total_used, 2),
            "total_allocated": round(total_allocated, 2),
            "total_dissipation": round(total_dissipation, 4),
            "temperature": round(temperature, 2),
            "efficiency": round(usage_efficiency, 4),
            "heat_variance": round(temp_variance, 4),
            "energy_residual": round(energy_residual, 4),
            "violation_type": violation_type,
            "severity": severity,
            "trit": 1 if violation_type is None else (-1 if severity > 0.5 else 0),
            "timestamp": time.time(),
        }

        self._history.append(result)
        if violation_type:
            self._violations.append(result)
        return result

    def auto_heal(self):
        """Auto-heal energy violations."""
        check = self.check()
        if check["violation_type"] == "over_allocation":
            return {
                "action": "rebalance_capacity",
                "description": "Over-allocated resources exceed physical capacity — rebalance",
                "pseudocode": [
                    "total_over = sum(allocations) - system_capacity",
                    "# Scale down proportionally from highest consumers",
                    "sorted_services = sort(services, key=lambda s: s.allocated, reverse=True)",
                    "for svc in sorted_services:",
                    "  excess = svc.allocated - svc.actual_used",
                    "  if excess > 0:",
                    "    svc.allocated -= min(excess, total_over * svc.allocated / total_allocated)",
                    "    total_over -= reclaimed",
                    "    if total_over <= 0: break",
                ],
            }
        elif check["violation_type"] == "capacity_leak":
            return {
                "action": "reclaim_capacity",
                "description": "Unallocated capacity detected — assign to starved services",
                "pseudocode": [
                    "free = system_capacity - sum(allocations)",
                    "starved = [s for s in services if s.usage / s.allocated > 0.9]",
                    "for svc in starved:",
                    "  grant = free / len(starved)",
                    "  svc.allocated += grant",
                ],
            }
        return None


# ═══════════════════════════════════════════════════════════════
# 4. CONSERVATION OF VORTICITY (KELVIN'S CIRCULATION THEOREM)
# ═══════════════════════════════════════════════════════════════
#
# Fluid form:  D/Dt ∮ v·dl = 0  (in inviscid flow)
#
# NovaX mapping:
#   Circulation Γ = ∮ v·dl around a closed service loop
#   In healthy system, circular dependency patterns don't grow.
#   If circulation increases → viscosity (latency) is changing → unhealthy.
#
# Detection: trace request paths, find cycles, measure cycle latency.
#   If cycle latency grows over time → circulation is increasing → violation.
#
# Monitoring:
#   For each detected cycle C = [S1→S2→...→Sn→S1]:
#     Γ = Σ throughput_i along cycle
#     dΓ/dt should ≈ 0 in healthy system
#     |dΓ/dt| > threshold → growing circular dependency

class VorticityConservation:
    """
    D/Dt ∮ v·dl = 0

    Tracks circular dependencies in the service graph.
    Growing circulation indicates viscosity changes (latency degradation).
    """

    def __init__(self):
        self._call_graph = defaultdict(lambda: defaultdict(int))  # from → to → count
        self._cycle_history = RingBuffer(500)
        self._circulation = {}  # cycle_key → [Γ values over time]
        self._violations = RingBuffer(500)

    def record_call(self, from_service, to_service, latency_ms=0):
        """Record a service-to-service call."""
        self._call_graph[from_service][to_service] += 1

    def detect_cycles(self, max_depth=7):
        """
        Detect cycles in the service call graph using DFS.
        max_depth = H7 (harmonic constant, composition unit).
        """
        cycles = []
        visited = set()

        def dfs(node, path, depth):
            if depth > max_depth:
                return
            for neighbor, count in self._call_graph.get(node, {}).items():
                if neighbor == path[0] and len(path) > 1:
                    cycles.append(list(path) + [neighbor])
                elif neighbor not in visited and neighbor not in path:
                    dfs(neighbor, path + [neighbor], depth + 1)

        for start in list(self._call_graph.keys()):
            dfs(start, [start], 0)

        return cycles

    def measure_circulation(self, cycle):
        """
        Measure circulation Γ = Σ throughput around a cycle.
        """
        gamma = 0
        for i in range(len(cycle) - 1):
            from_svc = cycle[i]
            to_svc = cycle[i + 1]
            gamma += self._call_graph.get(from_svc, {}).get(to_svc, 0)
        return gamma

    def check(self):
        """Check vorticity conservation across all detected cycles."""
        cycles = self.detect_cycles()
        results = []

        for cycle in cycles:
            cycle_key = "→".join(cycle)
            gamma = self.measure_circulation(cycle)

            if cycle_key not in self._circulation:
                self._circulation[cycle_key] = deque(maxlen=50)
            self._circulation[cycle_key].append({
                "gamma": gamma, "time": time.time()
            })

            # Compute dΓ/dt
            hist = list(self._circulation[cycle_key])
            if len(hist) >= 2:
                dg = hist[-1]["gamma"] - hist[-2]["gamma"]
                dt = max(hist[-1]["time"] - hist[-2]["time"], 0.001)
                dgamma_dt = dg / dt
            else:
                dgamma_dt = 0

            growing = abs(dgamma_dt) > 1.0  # threshold

            result = {
                "cycle": cycle_key,
                "circulation_gamma": gamma,
                "d_gamma_dt": round(dgamma_dt, 4),
                "growing": growing,
                "cycle_length": len(cycle) - 1,
                "trit": 1 if not growing else (-1 if abs(dgamma_dt) > 5 else 0),
            }
            results.append(result)

            if growing:
                self._violations.append(result)

        return {
            "law": "vorticity_kelvin",
            "formula": "D/Dt ∮ v·dl = 0",
            "mapping": "circular dependencies should not grow",
            "cycles_detected": len(cycles),
            "growing_cycles": sum(1 for r in results if r.get("growing")),
            "cycles": results,
            "trit": 1 if all(not r["growing"] for r in results) else -1,
            "timestamp": time.time(),
        }

    def auto_heal(self):
        """Break growing circular dependencies."""
        check = self.check()
        growing = [c for c in check.get("cycles", []) if c.get("growing")]
        if not growing:
            return None

        return {
            "action": "break_cycles",
            "description": f"Break {len(growing)} growing circular dependencies",
            "cycles": [c["cycle"] for c in growing],
            "pseudocode": [
                "for cycle in growing_cycles:",
                "  # Find the weakest link (lowest throughput edge)",
                "  weakest = min(cycle.edges, key=lambda e: e.throughput)",
                "  # Insert async queue to break synchronous cycle",
                "  weakest.convert_to_async()",
                "  # Add circuit breaker on the weakest link",
                "  weakest.add_circuit_breaker(threshold=5, timeout=30)",
                "  log.warn(f'Broke cycle {cycle} at {weakest}')",
            ],
        }


# ═══════════════════════════════════════════════════════════════
# 5. CONSERVATION OF ENTROPY (SECOND LAW OF THERMODYNAMICS)
# ═══════════════════════════════════════════════════════════════
#
# Fluid form:  Ds/Dt >= 0
#
# NovaX mapping:
#   s = system entropy = measure of disorder
#   Entropy metric = latency variance + error rate variance + queue depth variance
#   Entropy can only INCREASE without active intervention
#   Active "cooling" = optimization, garbage collection, cache warming
#
# Monitoring:
#   S(t) = Σ [ -p_i * log(p_i) ]  where p_i = fraction of requests to service i
#   Plus latency_variance and error_variance
#   If S decreases without intervention → violation (means measurement error)
#   If S increases too fast → system degrading, needs cooling

class EntropyConservation:
    """
    Ds/Dt >= 0

    Tracks system disorder. Entropy naturally increases;
    active optimization ("cooling") is needed to reduce it.
    """

    def __init__(self):
        self._request_distribution = defaultdict(int)  # service → count
        self._latency_samples = RingBuffer(1000)
        self._error_samples = RingBuffer(1000)
        self._entropy_history = RingBuffer(1000)
        self._cooling_events = RingBuffer(200)
        self._violations = RingBuffer(500)

    def record_request(self, service_name, latency_ms, success=True):
        """Record a request for entropy calculation."""
        self._request_distribution[service_name] += 1
        self._latency_samples.append({
            "service": service_name, "latency": latency_ms,
            "time": time.time()
        })
        if not success:
            self._error_samples.append({
                "service": service_name, "time": time.time()
            })

    def record_cooling(self, action_type, description=""):
        """Record an optimization/cooling event."""
        self._cooling_events.append({
            "type": action_type,
            "description": description,
            "time": time.time(),
        })

    def compute_entropy(self):
        """
        Compute Shannon entropy of request distribution.
        S = -Σ p_i * log(p_i)
        """
        total = sum(self._request_distribution.values())
        if total == 0:
            return 0.0

        entropy = 0.0
        for count in self._request_distribution.values():
            if count > 0:
                p = count / total
                entropy -= p * math.log(p + 1e-10)
        return entropy

    def compute_latency_entropy(self, window=300):
        """
        Compute entropy of latency distribution (variance-based).
        Higher variance = more disorder.
        """
        cutoff = time.time() - window
        recent = [s["latency"] for s in self._latency_samples.recent(500)
                  if s["time"] > cutoff]
        if len(recent) < 2:
            return 0.0
        return statistics.variance(recent)

    def check(self):
        """Check entropy conservation (second law)."""
        current_entropy = self.compute_entropy()
        latency_entropy = self.compute_latency_entropy()

        # Combined entropy metric
        total_entropy = current_entropy + math.log(1 + latency_entropy)

        # Check if entropy decreased without cooling
        hist = self._entropy_history.recent(10)
        recent_cooling = [c for c in self._cooling_events.recent(20)
                         if time.time() - c["time"] < 60]

        violation_type = None
        severity = 0.0

        if len(hist) >= 2:
            prev_entropy = hist[-1].get("total_entropy", total_entropy)
            delta_s = total_entropy - prev_entropy

            if delta_s < -0.1 and not recent_cooling:
                # Entropy decreased without cooling — suspicious
                violation_type = "entropy_decrease_without_cooling"
                severity = min(1.0, abs(delta_s))
            elif delta_s > 1.0:
                # Rapid entropy increase — system degrading fast
                violation_type = "rapid_entropy_increase"
                severity = min(1.0, delta_s / 5.0)

        result = {
            "law": "entropy_second_law",
            "formula": "Ds/Dt >= 0",
            "mapping": "system disorder only increases without active cooling",
            "distribution_entropy": round(current_entropy, 4),
            "latency_variance": round(latency_entropy, 4),
            "total_entropy": round(total_entropy, 4),
            "recent_cooling_events": len(recent_cooling),
            "violation_type": violation_type,
            "severity": severity,
            "trit": 1 if violation_type is None else (-1 if severity > 0.5 else 0),
            "timestamp": time.time(),
        }

        self._entropy_history.append(result)
        if violation_type:
            self._violations.append(result)
        return result

    def auto_heal(self):
        """Trigger cooling actions when entropy rises too fast."""
        check = self.check()
        if check["violation_type"] == "rapid_entropy_increase":
            return {
                "action": "active_cooling",
                "description": "System entropy rising rapidly — trigger optimization pass",
                "severity": check["severity"],
                "pseudocode": [
                    "# Phase 1: Cache warming (reduce latency variance)",
                    "for service in hot_services:",
                    "  service.warm_cache(top_queries=100)",
                    "",
                    "# Phase 2: GC + connection pool cleanup",
                    "for service in all_services:",
                    "  service.gc_collect()",
                    "  service.connection_pool.evict_stale()",
                    "",
                    "# Phase 3: Rebalance request distribution",
                    "router.rebalance(target_entropy=log(N_services))",
                    "",
                    "# Phase 4: Log cooling event",
                    "conservation.record_cooling('auto_cool', 'entropy threshold exceeded')",
                ],
            }
        elif check["violation_type"] == "entropy_decrease_without_cooling":
            return {
                "action": "audit_metrics",
                "description": "Entropy decreased without cooling — possible measurement error",
                "pseudocode": [
                    "# Second law violation: entropy cannot decrease spontaneously",
                    "# This indicates a measurement or accounting error",
                    "metrics.recalibrate()",
                    "for service in services:",
                    "  assert service.request_counter.monotonic()",
                    "  service.health_check(deep=True)",
                ],
            }
        return None


# ═══════════════════════════════════════════════════════════════
# 6. BERNOULLI INVARIANT
# ═══════════════════════════════════════════════════════════════
#
# Fluid form:  p + ½ρv² + ρgz = constant (along streamline)
#
# NovaX mapping (per service chain / streamline):
#   p       = queue_pressure (queue depth normalized)
#   ½ρv²    = throughput_energy (kinetic: ½ * density * throughput²)
#   ρgz     = priority_potential (priority level × position in chain)
#
# Invariant: queue_pressure + throughput_energy + priority_potential = const
#   Along any request processing chain (streamline).
#   If throughput increases, queue pressure must decrease (and vice versa).
#
# Monitoring:
#   For each service chain [S1→S2→...→Sn]:
#     B_i = p_i + 0.5 * rho_i * v_i² + rho_i * g * z_i
#     B should be constant along the chain
#     |B_i - B_j| > threshold → violation

class BernoulliInvariant:
    """
    p + ½ρv² + ρgz = constant along streamline

    Tracks the Bernoulli constant along service chains.
    Violations indicate energy injection/extraction within the pipeline.
    """

    GRAVITY = 0.1  # analog of gravitational constant

    def __init__(self):
        self._service_states = {}  # service → {p, v, rho, z, priority}
        self._chain_history = RingBuffer(500)
        self._violations = RingBuffer(500)

    def record_state(self, service_name, queue_depth, throughput,
                     density=1.0, priority_level=1, chain_position=0):
        """
        Record Bernoulli state for a service.
        chain_position = z (height in the processing pipeline).
        """
        p = queue_depth  # pressure
        v = throughput   # velocity
        rho = max(density, 0.1)
        z = chain_position
        g = self.GRAVITY

        # Bernoulli number
        B = p + 0.5 * rho * v**2 + rho * g * z

        self._service_states[service_name] = {
            "p": p, "v": v, "rho": rho, "z": z,
            "priority": priority_level,
            "B": B,
            "components": {
                "pressure": round(p, 4),
                "kinetic": round(0.5 * rho * v**2, 4),
                "potential": round(rho * g * z, 4),
            },
            "time": time.time(),
        }

    def check_chain(self, chain):
        """
        Check Bernoulli invariant along a service chain.
        chain = list of service names representing a streamline.
        """
        if not chain or len(chain) < 2:
            return {"status": "insufficient_chain"}

        B_values = []
        details = []
        for svc in chain:
            state = self._service_states.get(svc)
            if not state:
                continue
            B_values.append(state["B"])
            details.append({
                "service": svc,
                "B": round(state["B"], 4),
                **state["components"],
            })

        if len(B_values) < 2:
            return {"status": "insufficient_data"}

        # Bernoulli constant should be uniform along chain
        B_mean = statistics.mean(B_values)
        B_variance = statistics.variance(B_values) if len(B_values) >= 2 else 0
        max_deviation = max(abs(b - B_mean) for b in B_values)

        violation = max_deviation > B_mean * 0.2 if B_mean > 0 else max_deviation > 1.0

        result = {
            "law": "bernoulli_invariant",
            "formula": "p + ½ρv² + ρgz = const",
            "mapping": "queue_pressure + throughput_energy + priority_potential = const",
            "chain": "→".join(chain),
            "B_mean": round(B_mean, 4),
            "B_variance": round(B_variance, 4),
            "max_deviation": round(max_deviation, 4),
            "details": details,
            "violation": violation,
            "severity": min(1.0, max_deviation / max(B_mean, 0.01)) if violation else 0,
            "trit": 1 if not violation else -1,
            "timestamp": time.time(),
        }

        self._chain_history.append(result)
        if violation:
            self._violations.append(result)
        return result

    def check_all_pairs(self):
        """Check Bernoulli between all service pairs."""
        services = list(self._service_states.keys())
        violations = []
        for i in range(len(services)):
            for j in range(i + 1, len(services)):
                result = self.check_chain([services[i], services[j]])
                if result.get("violation"):
                    violations.append(result)
        return {
            "pairs_checked": len(services) * (len(services) - 1) // 2,
            "violations": len(violations),
            "details": violations[:10],  # top 10
        }

    def auto_heal(self, chain):
        """Auto-heal Bernoulli violations along a chain."""
        check = self.check_chain(chain)
        if not check.get("violation"):
            return None

        # Find where B deviates most
        details = check.get("details", [])
        if len(details) < 2:
            return None

        B_mean = check["B_mean"]
        anomalous = max(details, key=lambda d: abs(d["B"] - B_mean))

        if anomalous["B"] > B_mean:
            return {
                "action": "reduce_pressure_or_speed",
                "service": anomalous["service"],
                "description": f"Bernoulli too high at {anomalous['service']} — reduce queue or throttle",
                "pseudocode": [
                    f"# B = {anomalous['B']:.2f} vs mean {B_mean:.2f}",
                    f"if {anomalous['service']}.queue_depth > threshold:",
                    f"  {anomalous['service']}.shed_load(fraction=0.2)",
                    f"elif {anomalous['service']}.throughput > target:",
                    f"  {anomalous['service']}.rate_limit(target_rate)",
                ],
            }
        else:
            return {
                "action": "boost_flow",
                "service": anomalous["service"],
                "description": f"Bernoulli too low at {anomalous['service']} — needs more throughput",
                "pseudocode": [
                    f"# B = {anomalous['B']:.2f} vs mean {B_mean:.2f}",
                    f"{anomalous['service']}.scale_up(workers=+2)",
                    f"{anomalous['service']}.warm_cache()",
                ],
            }


# ═══════════════════════════════════════════════════════════════
# 7. ENSTROPHY CONSERVATION (2D TURBULENCE INVARIANT)
# ═══════════════════════════════════════════════════════════════
#
# Fluid form:  Z = ½∫ω² dA  (conserved in 2D inviscid flow)
#
# NovaX mapping:
#   ω = local "vorticity" = rate of circular calls at a service node
#   Z = total enstrophy = sum of squared per-node vorticities
#   In healthy system, enstrophy is bounded
#   Enstrophy explosion → turbulence cascade → system instability
#
# This is a higher-order conservation law that complements vorticity.

class EnstrophyConservation:
    """
    Z = ½∫ω² dA

    Tracks enstrophy (squared vorticity) as a system stability metric.
    Enstrophy growth indicates turbulent cascade.
    """

    def __init__(self):
        self._node_vorticity = defaultdict(float)  # service → ω
        self._history = RingBuffer(500)

    def update_vorticity(self, service_name, circular_call_rate):
        """Update per-node vorticity (circular call rate)."""
        self._node_vorticity[service_name] = circular_call_rate

    def compute_enstrophy(self):
        """Z = ½ Σ ω_i²"""
        return 0.5 * sum(w**2 for w in self._node_vorticity.values())

    def check(self):
        Z = self.compute_enstrophy()
        hist = self._history.recent(10)

        dZ_dt = 0
        if hist:
            Z_prev = hist[-1].get("enstrophy", Z)
            dt = max(time.time() - hist[-1].get("timestamp", time.time()), 0.001)
            dZ_dt = (Z - Z_prev) / dt

        result = {
            "law": "enstrophy_conservation",
            "formula": "Z = ½∫ω² dA",
            "mapping": "sum of squared circular call rates bounded in healthy system",
            "enstrophy": round(Z, 4),
            "dZ_dt": round(dZ_dt, 4),
            "growing": dZ_dt > 1.0,
            "per_node": {k: round(v, 4) for k, v in self._node_vorticity.items()},
            "trit": 1 if dZ_dt <= 0.1 else (-1 if dZ_dt > 5 else 0),
            "timestamp": time.time(),
        }
        self._history.append(result)
        return result


# ═══════════════════════════════════════════════════════════════
# UNIFIED CONSERVATION MONITOR
# ═══════════════════════════════════════════════════════════════

class ConservationMonitor:
    """
    Unified monitor for all 7 conservation laws.
    Provides a single dashboard showing violation state.
    """

    def __init__(self):
        self.mass = MassConservation()
        self.momentum = MomentumConservation()
        self.energy = EnergyConservation()
        self.vorticity = VorticityConservation()
        self.entropy = EntropyConservation()
        self.bernoulli = BernoulliInvariant()
        self.enstrophy = EnstrophyConservation()
        self._dashboard_history = RingBuffer(500)

    def full_check(self):
        """Run all conservation law checks and return unified dashboard."""
        mass = self.mass.check()
        momentum_results = self.momentum.check()
        energy = self.energy.check()
        vorticity = self.vorticity.check()
        entropy_result = self.entropy.check()
        bernoulli = self.bernoulli.check_all_pairs()
        enstrophy = self.enstrophy.check()

        # Compute overall health trit
        trits = [
            mass.get("trit", 0),
            energy.get("trit", 0),
            vorticity.get("trit", 0),
            entropy_result.get("trit", 0),
            enstrophy.get("trit", 0),
        ]
        # Add momentum trits
        for m in momentum_results:
            trits.append(m.get("trit", 0))

        overall_trit = 1 if all(t == 1 for t in trits) else (
            -1 if any(t == -1 for t in trits) else 0)

        violations = []
        if mass.get("violation_type"):
            violations.append({"law": "mass", "type": mass["violation_type"],
                              "severity": mass["severity"]})
        if energy.get("violation_type"):
            violations.append({"law": "energy", "type": energy["violation_type"],
                              "severity": energy["severity"]})
        if vorticity.get("growing_cycles", 0) > 0:
            violations.append({"law": "vorticity", "type": "growing_circulation",
                              "severity": 0.5})
        if entropy_result.get("violation_type"):
            violations.append({"law": "entropy", "type": entropy_result["violation_type"],
                              "severity": entropy_result["severity"]})
        if enstrophy.get("growing"):
            violations.append({"law": "enstrophy", "type": "enstrophy_cascade",
                              "severity": 0.5})
        for m in momentum_results:
            if m.get("anomalous"):
                violations.append({"law": "momentum", "service": m["service"],
                                  "type": "unexplained_acceleration",
                                  "severity": m["anomaly_score"]})
        if bernoulli.get("violations", 0) > 0:
            violations.append({"law": "bernoulli",
                              "type": "streamline_energy_imbalance",
                              "count": bernoulli["violations"],
                              "severity": 0.5})

        dashboard = {
            "conservation_laws": {
                "mass": {
                    "status": "ok" if not mass.get("violation_type") else "VIOLATION",
                    "trit": mass.get("trit", 0),
                    "residual": mass.get("residual", 0),
                    "detail": mass.get("violation_type"),
                },
                "momentum": {
                    "status": "ok" if not any(m.get("anomalous") for m in momentum_results) else "ANOMALY",
                    "services_checked": len(momentum_results),
                    "anomalous": sum(1 for m in momentum_results if m.get("anomalous")),
                },
                "energy": {
                    "status": "ok" if not energy.get("violation_type") else "VIOLATION",
                    "trit": energy.get("trit", 0),
                    "temperature": energy.get("temperature", 0),
                    "efficiency": energy.get("efficiency", 0),
                },
                "vorticity": {
                    "status": "ok" if vorticity.get("growing_cycles", 0) == 0 else "GROWING",
                    "trit": vorticity.get("trit", 0),
                    "cycles": vorticity.get("cycles_detected", 0),
                    "growing": vorticity.get("growing_cycles", 0),
                },
                "entropy": {
                    "status": "ok" if not entropy_result.get("violation_type") else "VIOLATION",
                    "trit": entropy_result.get("trit", 0),
                    "total_entropy": entropy_result.get("total_entropy", 0),
                },
                "bernoulli": {
                    "status": "ok" if bernoulli.get("violations", 0) == 0 else "IMBALANCED",
                    "pairs_checked": bernoulli.get("pairs_checked", 0),
                    "violations": bernoulli.get("violations", 0),
                },
                "enstrophy": {
                    "status": "ok" if not enstrophy.get("growing") else "CASCADE",
                    "trit": enstrophy.get("trit", 0),
                    "Z": enstrophy.get("enstrophy", 0),
                    "dZ_dt": enstrophy.get("dZ_dt", 0),
                },
            },
            "overall_trit": overall_trit,
            "overall_status": "HEALTHY" if overall_trit == 1 else (
                "CRITICAL" if overall_trit == -1 else "DEGRADED"),
            "total_violations": len(violations),
            "violations": violations,
            "timestamp": time.time(),
        }

        self._dashboard_history.append(dashboard)
        return dashboard

    def auto_heal_all(self):
        """Run auto-heal for all violated laws."""
        actions = []

        mass_heal = self.mass.auto_heal()
        if mass_heal:
            actions.append({"law": "mass", **mass_heal})

        # Momentum — check each service
        for svc in list(self.momentum._velocity.keys()):
            mom_heal = self.momentum.auto_heal(svc)
            if mom_heal:
                actions.append({"law": "momentum", **mom_heal})

        energy_heal = self.energy.auto_heal()
        if energy_heal:
            actions.append({"law": "energy", **energy_heal})

        vorticity_heal = self.vorticity.auto_heal()
        if vorticity_heal:
            actions.append({"law": "vorticity", **vorticity_heal})

        entropy_heal = self.entropy.auto_heal()
        if entropy_heal:
            actions.append({"law": "entropy", **entropy_heal})

        return {
            "actions_proposed": len(actions),
            "actions": actions,
            "timestamp": time.time(),
        }


# ═══════════════════════════════════════════════════════════════
# HTTP SERVER
# ═══════════════════════════════════════════════════════════════

_monitor = ConservationMonitor()
_lock = threading.Lock()


class ConservationHandler(BaseHTTPRequestHandler):
    """HTTP handler for conservation monitoring service."""

    def log_message(self, format, *args):
        log.info(format % args)

    def _send_json(self, data, status=200):
        body = json.dumps(data, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self):
        length = int(self.headers.get("Content-Length", 0))
        if length:
            return json.loads(self.rfile.read(length))
        return {}

    def do_GET(self):
        if self.path == "/health":
            self._send_json({
                "status": "ok",
                "service": "conservation_monitor",
                "version": VERSION,
                "laws": 7,
                "ternary": True,
                "self_trit": 1,
            })

        elif self.path == "/api/conservation/dashboard":
            with _lock:
                dashboard = _monitor.full_check()
            self._send_json(dashboard)

        elif self.path == "/api/conservation/mass":
            with _lock:
                self._send_json(_monitor.mass.check())

        elif self.path == "/api/conservation/momentum":
            with _lock:
                self._send_json(_monitor.momentum.check())

        elif self.path == "/api/conservation/energy":
            with _lock:
                self._send_json(_monitor.energy.check())

        elif self.path == "/api/conservation/vorticity":
            with _lock:
                self._send_json(_monitor.vorticity.check())

        elif self.path == "/api/conservation/entropy":
            with _lock:
                self._send_json(_monitor.entropy.check())

        elif self.path == "/api/conservation/bernoulli":
            with _lock:
                self._send_json(_monitor.bernoulli.check_all_pairs())

        elif self.path == "/api/conservation/enstrophy":
            with _lock:
                self._send_json(_monitor.enstrophy.check())

        elif self.path == "/api/conservation/auto-heal":
            with _lock:
                self._send_json(_monitor.auto_heal_all())

        elif self.path == "/api/conservation/formulas":
            self._send_json({
                "conservation_laws": {
                    "1_mass": {
                        "name": "Conservation of Mass (Continuity)",
                        "formula": "dρ/dt + ∇·(ρv) = 0",
                        "novax": "requests_in = requests_out + requests_queued",
                        "variables": {
                            "ρ": "request density (requests per service per unit time)",
                            "v": "request velocity (throughput magnitude/direction)",
                            "∇·": "divergence across service graph",
                        },
                        "violation_meaning": "Request leak (residual > 0) or duplication (residual < 0)",
                        "monitor": "mass_residual = |entered - completed - queued - failed|",
                        "auto_heal": "leak → drain orphans, duplication → enable dedup",
                    },
                    "2_momentum": {
                        "name": "Conservation of Momentum",
                        "formula": "ρ(Dv/Dt) = -∇p + μ∇²v + ρg",
                        "novax": "throughput changes only from identifiable forces",
                        "variables": {
                            "ρ": "queue depth (request density)",
                            "v": "throughput (requests/sec)",
                            "p": "queue pressure (backlog)",
                            "μ": "viscosity (inverse capacity — high cap = low viscosity)",
                            "g": "external forces (priority, manual scaling)",
                        },
                        "violation_meaning": "Unexplained throughput change = anomaly",
                        "monitor": "anomaly = |actual_dv/dt - expected_dv/dt| / expected",
                        "auto_heal": "spike → throttle, drop → investigate deadlock/starvation",
                    },
                    "3_energy": {
                        "name": "Conservation of Energy",
                        "formula": "ρc_p(DT/Dt) = k∇²T + Φ + Q",
                        "novax": "total system capacity = constant (zero-sum)",
                        "variables": {
                            "T": "system temperature (CPU/memory utilization)",
                            "c_p": "heat capacity (max available resources)",
                            "k∇²T": "heat diffusion (load balancer spreading work)",
                            "Φ": "viscous dissipation (overhead/waste)",
                            "Q": "heat source (external workload)",
                        },
                        "violation_meaning": "Resources appear/disappear = over/under allocation",
                        "monitor": "|total_allocated - system_capacity| > threshold",
                        "auto_heal": "over → scale down proportionally, under → assign to starved",
                    },
                    "4_vorticity": {
                        "name": "Conservation of Vorticity (Kelvin's Theorem)",
                        "formula": "D/Dt ∮ v·dl = 0",
                        "novax": "circular dependencies don't grow in healthy system",
                        "variables": {
                            "∮ v·dl": "circulation Γ = total throughput around a service cycle",
                            "D/Dt": "material derivative (following the flow)",
                        },
                        "violation_meaning": "Growing cycle latency = viscosity changing",
                        "monitor": "|dΓ/dt| > threshold for any cycle [S1→S2→...→Sn→S1]",
                        "auto_heal": "break weakest link in cycle with async queue + circuit breaker",
                    },
                    "5_entropy": {
                        "name": "Conservation of Entropy (Second Law)",
                        "formula": "Ds/Dt >= 0",
                        "novax": "system disorder only increases without active cooling",
                        "variables": {
                            "s": "entropy = -Σ p_i log(p_i) + log(1 + latency_variance)",
                            "cooling": "optimization events (GC, cache warming, rebalance)",
                        },
                        "violation_meaning": "Decrease without cooling = measurement error; rapid increase = degradation",
                        "monitor": "S(t) via Shannon entropy of request distribution + latency variance",
                        "auto_heal": "rapid increase → cache warm + GC + rebalance; decrease → audit metrics",
                    },
                    "6_bernoulli": {
                        "name": "Bernoulli Invariant",
                        "formula": "p + ½ρv² + ρgz = constant",
                        "novax": "queue_pressure + throughput_energy + priority_potential = const per chain",
                        "variables": {
                            "p": "queue_pressure (queue depth, normalized)",
                            "½ρv²": "throughput_energy (kinetic: ½ × density × throughput²)",
                            "ρgz": "priority_potential (priority × chain position)",
                        },
                        "violation_meaning": "Energy injected/extracted within pipeline",
                        "monitor": "variance of B along each service chain (streamline)",
                        "auto_heal": "high B → shed load or throttle; low B → scale up",
                    },
                    "7_enstrophy": {
                        "name": "Enstrophy Conservation (2D Turbulence)",
                        "formula": "Z = ½∫ω² dA",
                        "novax": "sum of squared circular call rates bounded in healthy system",
                        "variables": {
                            "ω": "per-node vorticity (circular call rate)",
                            "Z": "enstrophy (total squared vorticity)",
                        },
                        "violation_meaning": "Enstrophy growth = turbulent cascade = instability",
                        "monitor": "dZ/dt > threshold",
                        "auto_heal": "reduce circular calls at highest-vorticity nodes",
                    },
                },
                "harmonic_constants": {
                    "H3": 3, "H5": 5, "H7": 7, "H13": 13,
                    "BLOCK_SIZE": BLOCK_SIZE,
                    "RE_LAMINAR": RE_LAMINAR,
                    "RE_TRANSITION": RE_TRANSITION,
                    "RE_TURBULENT": RE_TURBULENT,
                },
            })

        else:
            self._send_json({"error": "not found"}, 404)

    def do_POST(self):
        data = self._read_json()

        if self.path == "/api/conservation/mass/entry":
            with _lock:
                _monitor.mass.record_entry(
                    data.get("service", "unknown"),
                    data.get("request_id"))
            self._send_json({"ok": True})

        elif self.path == "/api/conservation/mass/exit":
            with _lock:
                _monitor.mass.record_exit(
                    data.get("service", "unknown"),
                    data.get("success", True),
                    data.get("request_id"))
            self._send_json({"ok": True})

        elif self.path == "/api/conservation/momentum/state":
            with _lock:
                _monitor.momentum.record_state(
                    data.get("service", "unknown"),
                    data.get("throughput", 0),
                    data.get("queue_depth", 0),
                    data.get("latency_ms", 0),
                    data.get("capacity", 1.0),
                    data.get("priority", 1.0))
            self._send_json({"ok": True})

        elif self.path == "/api/conservation/energy/usage":
            with _lock:
                _monitor.energy.record_usage(
                    data.get("service", "unknown"),
                    data.get("cpu_used", 0),
                    data.get("cpu_allocated", 0),
                    data.get("overhead", 0))
            self._send_json({"ok": True})

        elif self.path == "/api/conservation/vorticity/call":
            with _lock:
                _monitor.vorticity.record_call(
                    data.get("from_service", ""),
                    data.get("to_service", ""),
                    data.get("latency_ms", 0))
            self._send_json({"ok": True})

        elif self.path == "/api/conservation/entropy/request":
            with _lock:
                _monitor.entropy.record_request(
                    data.get("service", "unknown"),
                    data.get("latency_ms", 0),
                    data.get("success", True))
            self._send_json({"ok": True})

        elif self.path == "/api/conservation/bernoulli/state":
            with _lock:
                _monitor.bernoulli.record_state(
                    data.get("service", "unknown"),
                    data.get("queue_depth", 0),
                    data.get("throughput", 0),
                    data.get("density", 1.0),
                    data.get("priority_level", 1),
                    data.get("chain_position", 0))
            self._send_json({"ok": True})

        elif self.path == "/api/conservation/enstrophy/vorticity":
            with _lock:
                _monitor.enstrophy.update_vorticity(
                    data.get("service", "unknown"),
                    data.get("circular_call_rate", 0))
            self._send_json({"ok": True})

        elif self.path == "/api/conservation/bulk":
            # Bulk update — accepts all law data at once
            with _lock:
                if "mass_entries" in data:
                    for e in data["mass_entries"]:
                        _monitor.mass.record_entry(e.get("service"), e.get("id"))
                if "mass_exits" in data:
                    for e in data["mass_exits"]:
                        _monitor.mass.record_exit(e.get("service"), e.get("success", True))
                if "momentum_states" in data:
                    for s in data["momentum_states"]:
                        _monitor.momentum.record_state(
                            s.get("service"), s.get("throughput", 0),
                            s.get("queue_depth", 0), s.get("latency_ms", 0),
                            s.get("capacity", 1.0), s.get("priority", 1.0))
                if "energy_usages" in data:
                    for u in data["energy_usages"]:
                        _monitor.energy.record_usage(
                            u.get("service"), u.get("cpu_used", 0),
                            u.get("cpu_allocated", 0), u.get("overhead", 0))
                if "calls" in data:
                    for c in data["calls"]:
                        _monitor.vorticity.record_call(
                            c.get("from"), c.get("to"), c.get("latency_ms", 0))
                if "requests" in data:
                    for r in data["requests"]:
                        _monitor.entropy.record_request(
                            r.get("service"), r.get("latency_ms", 0), r.get("success", True))
            self._send_json({"ok": True})

        else:
            self._send_json({"error": "not found"}, 404)


def main():
    log.info(f"Starting Conservation Monitor on port {PORT}")
    log.info(f"Tracking 7 conservation laws: mass, momentum, energy, vorticity, entropy, bernoulli, enstrophy")
    log.info(f"Reynolds boundaries: laminar<{RE_LAMINAR}, transitional<{RE_TRANSITION}, turbulent<{RE_TURBULENT}")

    server = HTTPServer(("127.0.0.1", PORT), ConservationHandler)
    log.info(f"Conservation Monitor listening on http://127.0.0.1:{PORT}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("Conservation Monitor stopped")
        server.server_close()


if __name__ == "__main__":
    main()
