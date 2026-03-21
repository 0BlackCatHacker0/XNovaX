"""
NovaX God Mode Project Orchestration
======================================
Creates Project Sessions where all models collaborate.
Models propose actions. NovaX executes actions.
Roles: Architect, Builder, Debugger, Optimizer, Integrator.
"""
import uuid
import time
import json
import threading
import logging
from enum import Enum

log = logging.getLogger("NovaX.GodMode")

class Role(Enum):
    ARCHITECT = "architect"
    BUILDER = "builder"
    DEBUGGER = "debugger"
    OPTIMIZER = "optimizer"
    INTEGRATOR = "integrator"
    UNASSIGNED = "unassigned"

class TaskStatus(Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    COMPLETE = "complete"
    FAILED = "failed"
    BLOCKED = "blocked"

# ============================================================
#  PROJECT TASK
# ============================================================
class ProjectTask:
    def __init__(self, description, role=Role.UNASSIGNED, depends_on=None):
        self.id = str(uuid.uuid4())[:10]
        self.description = description
        self.role = role
        self.status = TaskStatus.PENDING
        self.assigned_model = None
        self.depends_on = depends_on or []
        self.output = None
        self.created_at = time.time()
        self.completed_at = None

    def to_dict(self):
        return {
            "id": self.id, "description": self.description,
            "role": self.role.value, "status": self.status.value,
            "assigned_model": self.assigned_model,
            "depends_on": self.depends_on,
            "output": self.output,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }

# ============================================================
#  PROJECT SESSION
# ============================================================
class ProjectSession:
    """
    God Mode project session where models collaborate.
    Shared memory, shared filesystem, task map, execution policy.
    """
    def __init__(self, name, description=""):
        self.id = str(uuid.uuid4())[:12]
        self.name = name
        self.description = description
        self.created_at = time.time()
        self.status = "active"

        # Shared state
        self.shared_memory = {}      # key -> value store
        self.shared_files = []       # list of file paths
        self.task_map = {}           # task_id -> ProjectTask
        self.events = []             # structured event log
        self.execution_policy = "sequential"  # sequential, parallel, manual

        # Model assignments
        self.model_roles = {}        # model_name -> Role

        self._lock = threading.Lock()

    def add_task(self, description, role=Role.UNASSIGNED, depends_on=None):
        task = ProjectTask(description, role, depends_on)
        with self._lock:
            self.task_map[task.id] = task
            self._emit("task.created", {"task_id": task.id, "description": description})
        log.info(f"GodMode: Task created: {task.id} - {description[:60]}")
        return task

    def assign_model(self, model_name, role):
        if isinstance(role, str):
            role = Role(role)
        self.model_roles[model_name] = role
        self._emit("model.assigned", {"model": model_name, "role": role.value})
        log.info(f"GodMode: {model_name} assigned as {role.value}")

    def assign_task(self, task_id, model_name):
        task = self.task_map.get(task_id)
        if not task:
            return {"ok": False, "error": "task not found"}
        task.assigned_model = model_name
        task.status = TaskStatus.ASSIGNED
        self._emit("task.assigned", {"task_id": task_id, "model": model_name})
        return {"ok": True}

    def start_task(self, task_id):
        task = self.task_map.get(task_id)
        if not task:
            return {"ok": False, "error": "task not found"}
        # Check dependencies
        for dep_id in task.depends_on:
            dep = self.task_map.get(dep_id)
            if dep and dep.status != TaskStatus.COMPLETE:
                task.status = TaskStatus.BLOCKED
                return {"ok": False, "error": f"blocked by {dep_id}", "blocked": True}
        task.status = TaskStatus.IN_PROGRESS
        self._emit("task.started", {"task_id": task_id})
        return {"ok": True}

    def complete_task(self, task_id, output=None):
        task = self.task_map.get(task_id)
        if not task:
            return {"ok": False, "error": "task not found"}
        task.status = TaskStatus.COMPLETE
        task.output = output
        task.completed_at = time.time()
        self._emit("task.completed", {"task_id": task_id, "output_preview": str(output)[:100] if output else None})
        log.info(f"GodMode: Task completed: {task_id}")

        # Check if unblocked tasks can now start
        self._check_unblocked()
        return {"ok": True}

    def fail_task(self, task_id, error=None):
        task = self.task_map.get(task_id)
        if not task:
            return {"ok": False}
        task.status = TaskStatus.FAILED
        task.output = error
        self._emit("task.failed", {"task_id": task_id, "error": str(error)[:200]})
        return {"ok": True}

    def _check_unblocked(self):
        """Check if any blocked tasks can now proceed."""
        for task in self.task_map.values():
            if task.status == TaskStatus.BLOCKED:
                all_done = all(
                    self.task_map.get(d, task).status == TaskStatus.COMPLETE
                    for d in task.depends_on
                )
                if all_done:
                    task.status = TaskStatus.PENDING
                    self._emit("task.unblocked", {"task_id": task.id})

    def set_memory(self, key, value):
        with self._lock:
            self.shared_memory[key] = value

    def get_memory(self, key, default=None):
        return self.shared_memory.get(key, default)

    def add_file(self, path):
        if path not in self.shared_files:
            self.shared_files.append(path)

    def _emit(self, event_type, data):
        self.events.append({
            "type": event_type, "data": data, "ts": time.time()
        })
        if len(self.events) > 500:
            self.events = self.events[-500:]

    def progress(self):
        total = len(self.task_map)
        if total == 0:
            return 0.0
        done = sum(1 for t in self.task_map.values() if t.status == TaskStatus.COMPLETE)
        return round(done / total * 100, 1)

    def next_tasks(self):
        """Return tasks ready to execute (pending, no unmet dependencies)."""
        ready = []
        for task in self.task_map.values():
            if task.status != TaskStatus.PENDING:
                continue
            deps_met = all(
                self.task_map.get(d, task).status == TaskStatus.COMPLETE
                for d in task.depends_on
            )
            if deps_met:
                ready.append(task)
        return ready

    def to_dict(self):
        return {
            "id": self.id, "name": self.name, "description": self.description,
            "status": self.status, "created_at": self.created_at,
            "progress": self.progress(),
            "tasks": {tid: t.to_dict() for tid, t in self.task_map.items()},
            "model_roles": {m: r.value for m, r in self.model_roles.items()},
            "shared_memory_keys": list(self.shared_memory.keys()),
            "shared_files": self.shared_files,
            "events_count": len(self.events),
            "execution_policy": self.execution_policy,
        }

# ============================================================
#  GOD MODE CONTROLLER
# ============================================================
class GodModeController:
    """Manages all God Mode project sessions."""
    def __init__(self):
        self.sessions = {}   # id -> ProjectSession
        self.active_session = None
        self._lock = threading.Lock()

    def create_session(self, name, description=""):
        session = ProjectSession(name, description)
        with self._lock:
            self.sessions[session.id] = session
            self.active_session = session.id
        log.info(f"GodMode: Session created: {session.id} - {name}")
        return session

    def get_session(self, session_id=None):
        sid = session_id or self.active_session
        return self.sessions.get(sid)

    def close_session(self, session_id=None):
        sid = session_id or self.active_session
        session = self.sessions.get(sid)
        if session:
            session.status = "closed"
            log.info(f"GodMode: Session closed: {sid}")
            return {"ok": True}
        return {"ok": False}

    def list_sessions(self):
        return {sid: s.to_dict() for sid, s in self.sessions.items()}

    def status(self):
        active = self.get_session()
        return {
            "sessions": len(self.sessions),
            "active": self.active_session,
            "active_progress": active.progress() if active else None,
            "active_tasks": len(active.task_map) if active else 0,
        }
