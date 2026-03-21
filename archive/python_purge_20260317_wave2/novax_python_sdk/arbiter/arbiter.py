"""
NovaX Arbiter - Single Mutation Authority
==========================================
The ONLY component allowed to change system reality.
All workers submit proposals. Arbiter decides.
Prevents restart storms, race conditions, infinite loops.
"""
import time, socket, subprocess, os, threading, json, logging
from collections import deque
from enum import Enum

log = logging.getLogger("NovaX.Arbiter")

class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class Decision(Enum):
    APPROVED = "APPROVED"
    DENIED = "DENIED"
    REVISE = "REVISE"
    DEFERRED = "DEFERRED"

class SystemState(Enum):
    GREEN = "GREEN"        # full cognition
    YELLOW = "YELLOW"      # degraded, fallback active
    ORANGE = "ORANGE"      # rebuilding thinker
    RED = "RED"            # infrastructure repair
    SAFE = "SAFE"          # minimal mode

class ActionProposal:
    def __init__(self, proposed_by, action_type, command=None,
                 target_files=None, risk=RiskLevel.LOW, task_id=None,
                 expected_proofs=None, reason=""):
        self.id = str(int(time.time() * 1000000))
        self.proposed_by = proposed_by
        self.action_type = action_type
        self.command = command
        self.target_files = target_files or []
        self.risk = risk if isinstance(risk, RiskLevel) else RiskLevel(risk)
        self.task_id = task_id
        self.expected_proofs = expected_proofs or []
        self.reason = reason
        self.ts = time.time()
        self.decision = None
        self.decision_reason = ""
        self.executed = False
        self.result = None
    def to_dict(self):
        return {"id": self.id, "proposed_by": self.proposed_by,
                "action_type": self.action_type, "command": self.command,
                "risk": self.risk.value, "task_id": self.task_id,
                "decision": self.decision.value if self.decision else None,
                "decision_reason": self.decision_reason,
                "executed": self.executed, "ts": self.ts}

class Arbiter:
    """Single authority for all system mutations."""
    def __init__(self):
        self.state = SystemState.GREEN
        self.proposals = deque(maxlen=200)
        self.decisions = deque(maxlen=200)
        self.active_locks = {}       # resource -> owner
        self.restart_tracker = {}    # service -> [timestamps]
        self.max_restarts_per_hour = 5
        self.restart_cooldown = 30   # seconds
        self._lock = threading.Lock()
        self.total_approved = 0
        self.total_denied = 0
        self.active_thinker = None   # which AI is primary
        self.fallback_thinker = None
        self.running = True

    def submit(self, proposal):
        """Submit an action proposal for Arbiter decision."""
        with self._lock:
            self.proposals.append(proposal)
            decision = self._evaluate(proposal)
            proposal.decision = decision
            self.decisions.append(proposal)
            if decision == Decision.APPROVED:
                self.total_approved += 1
                result = self._execute(proposal)
                proposal.executed = True
                proposal.result = result
                log.info("Arbiter APPROVED: " + proposal.action_type + " by " + proposal.proposed_by)
                return {"decision": "APPROVED", "result": result}
            else:
                self.total_denied += 1
                log.warning("Arbiter DENIED: " + proposal.action_type + " - " + proposal.decision_reason)
                return {"decision": decision.value, "reason": proposal.decision_reason}

    def _evaluate(self, p):
        """Evaluate whether to approve a proposal."""
        # Rule 1: Check restart rate limiting
        if p.action_type in ("restart", "kill", "rebuild"):
            svc = p.command or p.proposed_by
            now = time.time()
            history = self.restart_tracker.get(svc, [])
            # Clean old entries
            history = [t for t in history if now - t < 3600]
            self.restart_tracker[svc] = history
            if len(history) >= self.max_restarts_per_hour:
                p.decision_reason = "Max restarts exceeded for " + svc
                return Decision.DENIED
            if history and now - history[-1] < self.restart_cooldown:
                p.decision_reason = "Cooldown active for " + svc
                return Decision.DEFERRED

        # Rule 2: Check lock conflicts
        for f in p.target_files:
            if f in self.active_locks and self.active_locks[f] != p.proposed_by:
                p.decision_reason = "Resource locked by " + self.active_locks[f]
                return Decision.DENIED

        # Rule 3: Risk assessment
        if p.risk == RiskLevel.CRITICAL and self.state in (SystemState.RED, SystemState.SAFE):
            p.decision_reason = "System in " + self.state.value + ", critical actions blocked"
            return Decision.DENIED

        # Rule 4: Approve with tracking
        if p.action_type in ("restart", "kill"):
            svc = p.command or p.proposed_by
            if svc not in self.restart_tracker:
                self.restart_tracker[svc] = []
            self.restart_tracker[svc].append(time.time())

        return Decision.APPROVED

    def _execute(self, p):
        """Execute an approved proposal."""
        try:
            if p.command:
                r = subprocess.run(p.command, shell=True, capture_output=True,
                                 text=True, timeout=30)
                return {"ok": r.returncode == 0, "output": r.stdout[:500],
                        "error": r.stderr[:200] if r.returncode != 0 else ""}
            return {"ok": True, "output": "no-op"}
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": "timeout"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def acquire_lock(self, resource, owner):
        with self._lock:
            if resource in self.active_locks:
                return False
            self.active_locks[resource] = owner
            return True

    def release_lock(self, resource, owner):
        with self._lock:
            if self.active_locks.get(resource) == owner:
                del self.active_locks[resource]
                return True
            return False

    def set_thinker(self, primary, fallback=None):
        self.active_thinker = primary
        self.fallback_thinker = fallback
        log.info("Arbiter: thinker=" + str(primary) + " fallback=" + str(fallback))

    def get_active_thinker(self):
        return self.active_thinker or "ollama"

    def update_state(self, new_state):
        old = self.state
        self.state = new_state if isinstance(new_state, SystemState) else SystemState(new_state)
        if old != self.state:
            log.info("Arbiter state: " + old.value + " -> " + self.state.value)

    def status(self):
        return {"state": self.state.value,
                "active_thinker": self.active_thinker,
                "fallback_thinker": self.fallback_thinker,
                "total_approved": self.total_approved,
                "total_denied": self.total_denied,
                "active_locks": dict(self.active_locks),
                "restart_tracker": {k: len(v) for k, v in self.restart_tracker.items()},
                "recent_decisions": [p.to_dict() for p in list(self.decisions)[-10:]]}

# Singleton
_arbiter = None
def get_arbiter():
    global _arbiter
    if _arbiter is None:
        _arbiter = Arbiter()
    return _arbiter