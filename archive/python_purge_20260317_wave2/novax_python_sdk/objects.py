"""NovaX Internal Data Objects - shared language of the system."""
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from enum import Enum
import time, uuid

class Status(Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"

class RiskLevel(Enum):
    SAFE = "safe"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class Intent:
    text: str
    action: str = ""
    target: str = ""
    confidence: float = 0.0
    context: Dict[str, Any] = field(default_factory=dict)
    ts: float = field(default_factory=time.time)

@dataclass
class PolicyDecision:
    allowed: bool = True
    risk: RiskLevel = RiskLevel.SAFE
    reason: str = ""
    requires_approval: bool = False
    rules_matched: List[str] = field(default_factory=list)

@dataclass
class Job:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    intent: Optional[Intent] = None
    status: Status = Status.PENDING
    result: Any = None
    error: str = ""
    created: float = field(default_factory=time.time)
    started: float = 0.0
    finished: float = 0.0
    steps: List[Dict] = field(default_factory=list)

@dataclass
class Receipt:
    job_id: str = ""
    success: bool = True
    output: str = ""
    duration: float = 0.0
    snapshot_id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class Snapshot:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    label: str = ""
    created: float = field(default_factory=time.time)
    files: Dict[str, str] = field(default_factory=dict)
    env: Dict[str, str] = field(default_factory=dict)

@dataclass
class Thread:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:10])
    name: str = ""
    status: Status = Status.PENDING
    jobs: List[str] = field(default_factory=list)
    created: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)

@dataclass
class Incident:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    service: str = ""
    error: str = ""
    recovered: bool = False
    ts: float = field(default_factory=time.time)
    recovery_action: str = ""
