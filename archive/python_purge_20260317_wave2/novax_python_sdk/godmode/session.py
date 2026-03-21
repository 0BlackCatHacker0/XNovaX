"""
NovaX God Mode - Project Orchestration Session
================================================
God Mode does NOT mean unlimited permissions.
God Mode means: the supervisor creates a controlled project session
that all models join as coordinated workers.

Models PROPOSE. NovaX EXECUTES.

Session lifecycle:
  INACTIVE -> PLANNING -> ACTIVE -> MERGING -> COMPLETE
"""
import os
import json
import time
import uuid
import logging
import threading
from enum import Enum
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional

log = logging.getLogger("NovaX.GodMode")

class SessionState(str, Enum):
    INACTIVE = "inactive"
    PLANNING = "planning"
    ACTIVE   = "active"
    MERGING  = "merging"
    PAUSED   = "paused"
    COMPLETE = "complete"

class JobStatus(str, Enum):
    QUEUED    = "queued"
    ASSIGNED  = "assigned"
    RUNNING   = "running"
    REVIEW    = "review"
    DONE      = "done"
    FAILED    = "failed"

@dataclass
class GodModeJob:
    id: str
    title: str
    description: str = ""
    assigned_model: str = ""
    role: str = ""
    status: JobStatus = JobStatus.QUEUED
    output: str = ""
    files_created: list = field(default_factory=list)
    files_modified: list = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    completed_at: float = 0.0
    dependencies: list = field(default_factory=list)

    def to_dict(self):
        d = asdict(self)
        d["status"] = self.status.value
        return d

@dataclass
class ProjectSession:
    id: str
    name: str
    description: str = ""
    state: SessionState = SessionState.INACTIVE
    workspace: str = ""
    created_at: float = field(default_factory=time.time)
    jobs: Dict[str, GodModeJob] = field(default_factory=dict)
    models: Dict[str, dict] = field(default_factory=dict)
    shared_memory: dict = field(default_factory=dict)
    events: list = field(default_factory=list)
    safety_rules: dict = field(default_factory=lambda: {
        "allow_file_write": True,
        "allow_shell_exec": True,
        "allow_network": False,
        "allow_install": False,
        "require_review": True,
        "max_concurrent_jobs": 5,
        "workspace_restricted": True,
    })

    def to_dict(self):
        d = {
            "id": self.id, "name": self.name, "description": self.description,
            "state": self.state.value, "workspace": self.workspace,
            "created_at": self.created_at,
            "jobs": {jid: j.to_dict() for jid, j in self.jobs.items()},
            "models": self.models,
            "shared_memory": self.shared_memory,
            "event_count": len(self.events),
            "recent_events": self.events[-20:],
            "safety_rules": self.safety_rules,
            "stats": self.stats(),
        }
        return d

    def stats(self):
        total = len(self.jobs)
        done = len([j for j in self.jobs.values() if j.status == JobStatus.DONE])
        running = len([j for j in self.jobs.values() if j.status == JobStatus.RUNNING])
        failed = len([j for j in self.jobs.values() if j.status == JobStatus.FAILED])
        return {"total": total, "done": done, "running": running, "failed": failed,
                "progress": round(done/total*100) if total else 0}


class GodModeEngine:
    """Manages God Mode project orchestration sessions."""

    def __init__(self, store_path="C:/NovaX/memory/godmode_sessions.json"):
        self.session: Optional[ProjectSession] = None
        self.store_path = store_path
        self._lock = threading.Lock()

    @property
    def active(self):
        return self.session is not None and self.session.state in (
            SessionState.PLANNING, SessionState.ACTIVE, SessionState.MERGING)

    # ---------- SESSION LIFECYCLE ----------
    def create_session(self, name, description="", workspace=None):
        """Create a new God Mode session."""
        with self._lock:
            if self.active:
                return {"error": "Session already active", "session": self.session.to_dict()}

            sid = f"gm_{uuid.uuid4().hex[:8]}"
            ws = workspace or f"C:/NovaX/projects/{sid}"
            os.makedirs(ws, exist_ok=True)

            self.session = ProjectSession(
                id=sid, name=name, description=description,
                workspace=ws, state=SessionState.PLANNING,
            )
            self._emit("session_created", f"God Mode: {name}")
            log.info(f"God Mode session created: {sid} - {name}")
            return self.session.to_dict()

    def activate(self):
        """Transition from PLANNING to ACTIVE."""
        with self._lock:
            if not self.session or self.session.state != SessionState.PLANNING:
                return {"error": "No session in planning state"}
            self.session.state = SessionState.ACTIVE
            self._emit("session_activated", "God Mode is ON")
            return self.session.to_dict()

    def pause(self):
        with self._lock:
            if self.session and self.session.state == SessionState.ACTIVE:
                self.session.state = SessionState.PAUSED
                self._emit("session_paused", "God Mode paused")
            return self.status()

    def resume(self):
        with self._lock:
            if self.session and self.session.state == SessionState.PAUSED:
                self.session.state = SessionState.ACTIVE
                self._emit("session_resumed", "God Mode resumed")
            return self.status()

    def complete(self):
        """End the session."""
        with self._lock:
            if not self.session:
                return {"error": "No active session"}
            self.session.state = SessionState.COMPLETE
            self._emit("session_complete", "God Mode OFF")
            self._save()
            result = self.session.to_dict()
            self.session = None
            return result

    # ---------- MODEL MANAGEMENT ----------
    def register_model(self, model_id, role, capabilities=None):
        """Register a model as a worker in the session."""
        with self._lock:
            if not self.session:
                return {"error": "No active session"}
            self.session.models[model_id] = {
                "role": role,
                "capabilities": capabilities or [],
                "joined_at": time.time(),
                "jobs_completed": 0,
                "status": "idle",
            }
            self._emit("model_joined", f"{model_id} joined as {role}")
            return {"ok": True, "models": self.session.models}

    # ---------- JOB MANAGEMENT ----------
    def create_job(self, title, description="", assigned_model="", role="",
                   dependencies=None):
        """Create a job in the session."""
        with self._lock:
            if not self.session:
                return {"error": "No active session"}
            jid = f"job_{uuid.uuid4().hex[:6]}"
            job = GodModeJob(
                id=jid, title=title, description=description,
                assigned_model=assigned_model, role=role,
                dependencies=dependencies or [],
            )
            self.session.jobs[jid] = job
            self._emit("job_created", f"{title} -> {assigned_model or 'unassigned'}")
            return job.to_dict()

    def assign_job(self, job_id, model_id, role=""):
        with self._lock:
            if not self.session or job_id not in self.session.jobs:
                return {"error": "Job not found"}
            job = self.session.jobs[job_id]
            job.assigned_model = model_id
            job.role = role or job.role
            job.status = JobStatus.ASSIGNED
            self._emit("job_assigned", f"{job.title} -> {model_id}")
            return job.to_dict()

    def start_job(self, job_id):
        with self._lock:
            if not self.session or job_id not in self.session.jobs:
                return {"error": "Job not found"}
            job = self.session.jobs[job_id]
            # Check dependencies
            for dep in job.dependencies:
                dep_job = self.session.jobs.get(dep)
                if dep_job and dep_job.status != JobStatus.DONE:
                    return {"error": f"Dependency {dep} not complete"}
            job.status = JobStatus.RUNNING
            self._emit("job_started", f"{job.title} running")
            self._save()
            return job.to_dict()

    def complete_job(self, job_id, output="", files_created=None, files_modified=None):
        with self._lock:
            if not self.session or job_id not in self.session.jobs:
                return {"error": "Job not found"}
            job = self.session.jobs[job_id]
            job.status = JobStatus.DONE
            job.output = output
            job.files_created = files_created or []
            job.files_modified = files_modified or []
            job.completed_at = time.time()
            if job.assigned_model in self.session.models:
                self.session.models[job.assigned_model]["jobs_completed"] += 1
            self._emit("job_completed", f"{job.title} DONE")
            self._save()
            return job.to_dict()

    def fail_job(self, job_id, error=""):
        with self._lock:
            if not self.session or job_id not in self.session.jobs:
                return {"error": "Job not found"}
            job = self.session.jobs[job_id]
            job.status = JobStatus.FAILED
            job.output = error
            self._emit("job_failed", f"{job.title} FAILED: {error}")
            self._save()
            return job.to_dict()

    # ---------- SHARED MEMORY ----------
    def update_memory(self, key, value):
        """Write to project shared memory (cross-talk channel)."""
        with self._lock:
            if not self.session:
                return {"error": "No active session"}
            self.session.shared_memory[key] = value
            self._emit("memory_updated", f"{key} updated")
            self._save()
            return {"ok": True}

    def read_memory(self, key=None):
        if not self.session:
            return {}
        if key:
            return self.session.shared_memory.get(key)
        return self.session.shared_memory

    # ---------- EVENT BUS ----------
    def _emit(self, event_type, message):
        if self.session:
            self.session.events.append({
                "type": event_type, "message": message,
                "ts": time.time(),
            })

    # ---------- STATUS ----------
    def status(self):
        if not self.session:
            return {"active": False, "state": "inactive"}
        d = self.session.to_dict()
        d["active"] = self.active
        return d

    # ---------- PERSISTENCE ----------
    def _save(self):
        if not self.session:
            return
        os.makedirs(os.path.dirname(self.store_path), exist_ok=True)
        with open(self.store_path, "w", encoding="utf-8") as f:
            json.dump(self.session.to_dict(), f, indent=2, default=str)
