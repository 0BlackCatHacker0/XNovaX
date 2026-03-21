"""
NovaX Arbiter - Single Mutation Authority
==========================================
Only component allowed to change system reality.
All workers submit proposals. Arbiter approves/denies.
Prevents storm loops and race conditions.
"""
import time, threading, logging, json, os, subprocess
from collections import deque
from enum import Enum

log = logging.getLogger("NovaX.Arbiter")

class Decision(Enum):
    APPROVED = "approved"
    DENIED = "denied"
    REVISE = "revise"
    DEFERRED = "deferred"

class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class SystemState(Enum):
    GREEN = "green"       # full cognition
    YELLOW = "yellow"     # degraded fallback
    ORANGE = "orange"     # rebuilding thinker
    RED = "red"           # infrastructure repair
    SAFE = "safe"         # minimal mode

class ActionProposal:
    def __init__(self, task_id, proposed_by, command, target_files=None,
                 risk_level="low", expected_proofs=None, reason=""):
        self.id = str(int(time.time()*1000))
        self.task_id = task_id
        self.proposed_by = proposed_by
        self.command = command
        self.target_files = target_files or []
        self.risk = risk_level if isinstance(risk_level, RiskLevel) else RiskLevel(risk_level)
        self.expected_proofs = expected_proofs or []
        self.reason = reason
        self.decision = None
        self.decided_at = None
        self.executed = False
        self.exec_result = None
        self.ts = time.time()
    def to_dict(self):
        return {"id": self.id, "task_id": self.task_id, "proposed_by": self.proposed_by,
                "command": self.command, "risk": self.risk.value, "reason": self.reason,
                "decision": self.decision.value if self.decision else None,
                "executed": self.executed, "ts": self.ts}

class Arbiter:
    """
    The Arbiter decides what reality should be.
    It prevents infinite loops and race conditions.
    Only Arbiter can approve: restart, kill, model swap, rebuild, fallback.
    """
    def __init__(self):
        self.state = SystemState.GREEN
        self.proposals = deque(maxlen=200)
        self.approved = deque(maxlen=100)
        self.denied = deque(maxlen=100)
        self.restart_counts = {}      # service -> count
        self.restart_cooldowns = {}   # service -> last_restart_time
        self.max_restarts_per_hour = 5
        self.cooldown_seconds = 30
        self.lock = threading.Lock()
        self.total_approved = 0
        self.total_denied = 0
        self.total_executed = 0
        self.events = deque(maxlen=100)

    def _emit(self, msg):
        self.events.append({"msg": msg, "ts": time.time()})
        log.info("Arbiter: " + msg)

    def submit(self, proposal):
        """Submit an action proposal for arbiter decision."""
        with self.lock:
            self.proposals.append(proposal)
            decision = self._evaluate(proposal)
            proposal.decision = decision
            proposal.decided_at = time.time()
            if decision == Decision.APPROVED:
                self.approved.append(proposal)
                self.total_approved += 1
                self._emit("APPROVED: " + proposal.command[:60])
            else:
                self.denied.append(proposal)
                self.total_denied += 1
                self._emit("DENIED: " + proposal.command[:60] + " reason=" + decision.value)
            return decision

    def _evaluate(self, proposal):
        """Evaluate whether to approve a proposal."""
        # Rule 1: Check restart cooldown
        svc = proposal.proposed_by
        if "restart" in proposal.command.lower() or "start" in proposal.command.lower():
            now = time.time()
            last = self.restart_cooldowns.get(svc, 0)
            if now - last < self.cooldown_seconds:
                return Decision.DENIED
            count = self.restart_counts.get(svc, 0)
            if count >= self.max_restarts_per_hour:
                self._emit("STORM BLOCK: " + svc + " hit restart limit")
                return Decision.DENIED

        # Rule 2: High risk needs extra checks
        if proposal.risk in (RiskLevel.HIGH, RiskLevel.CRITICAL):
            if self.state == SystemState.RED:
                return Decision.DEFERRED

        # Rule 3: Check for conflicting proposals
        for p in list(self.approved)[-10:]:
            if p.command == proposal.command and time.time() - p.ts < 5:
                return Decision.DENIED  # duplicate

        return Decision.APPROVED

    def execute_approved(self, proposal):
        """Execute an approved proposal."""
        if proposal.decision != Decision.APPROVED:
            return {"ok": False, "error": "not approved"}
        try:
            r = subprocess.run(proposal.command, shell=True,
                             capture_output=True, text=True, timeout=30)
            proposal.executed = True
            proposal.exec_result = r.returncode == 0
            self.total_executed += 1
            # Track restart counts
            if "restart" in proposal.command.lower() or "start" in proposal.command.lower():
                svc = proposal.proposed_by
                self.restart_counts[svc] = self.restart_counts.get(svc, 0) + 1
                self.restart_cooldowns[svc] = time.time()
            self._emit("EXECUTED: " + proposal.command[:60] + " rc=" + str(r.returncode))
            return {"ok": r.returncode == 0, "stdout": r.stdout[:500], "stderr": r.stderr[:200]}
        except Exception as e:
            proposal.exec_result = False
            return {"ok": False, "error": str(e)}

    def propose_and_execute(self, task_id, proposed_by, command, risk="low", reason=""):
        """Shortcut: submit + execute if approved."""
        p = ActionProposal(task_id, proposed_by, command, risk_level=risk, reason=reason)
        decision = self.submit(p)
        if decision == Decision.APPROVED:
            return self.execute_approved(p)
        return {"ok": False, "decision": decision.value}

    def update_state(self, cognitive_ok, execution_ok):
        """Update system state based on guardian assessments."""
        if cognitive_ok and execution_ok:
            self.state = SystemState.GREEN
        elif cognitive_ok and not execution_ok:
            self.state = SystemState.RED
        elif not cognitive_ok and execution_ok:
            self.state = SystemState.ORANGE
        elif not cognitive_ok and not execution_ok:
            self.state = SystemState.SAFE

    def reset_restart_counts(self):
        """Reset hourly restart counters."""
        self.restart_counts = {}
        self._emit("Restart counters reset")

    def status(self):
        return {
            "state": self.state.value,
            "total_approved": self.total_approved,
            "total_denied": self.total_denied,
            "total_executed": self.total_executed,
            "restart_counts": dict(self.restart_counts),
            "recent_proposals": [p.to_dict() for p in list(self.proposals)[-10:]],
            "events": [e for e in list(self.events)[-15:]],
        }
