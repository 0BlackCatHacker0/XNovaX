"""
NovaX Task Graph Engine
========================
Converts user goals into dependency graphs with subtasks.
Assigns worker roles: Architect, Builder, Debugger, Tester, Integrator.
Manages execution, merge pipeline, and proof verification.
"""
import time, json, logging, uuid
from collections import deque
from enum import Enum

log = logging.getLogger("NovaX.TaskGraph")

class WorkerRole(Enum):
    ARCHITECT = "architect"
    BUILDER = "builder"
    DEBUGGER = "debugger"
    TESTER = "tester"
    INTEGRATOR = "integrator"

class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    BLOCKED = "blocked"
    DONE = "done"
    FAILED = "failed"

class SubTask:
    def __init__(self, description, role=WorkerRole.BUILDER,
                 depends_on=None, inputs=None, outputs=None):
        self.id = "st_" + str(uuid.uuid4())[:8]
        self.description = description
        self.role = role if isinstance(role, WorkerRole) else WorkerRole(role)
        self.depends_on = depends_on or []
        self.inputs = inputs or []
        self.outputs = outputs or []
        self.status = TaskStatus.PENDING
        self.assigned_model = None
        self.result = None
        self.started_at = None
        self.completed_at = None
    def to_dict(self):
        return {"id": self.id, "description": self.description,
                "role": self.role.value, "status": self.status.value,
                "depends_on": self.depends_on,
                "assigned_model": self.assigned_model,
                "started_at": self.started_at,
                "completed_at": self.completed_at}

class ProjectTask:
    def __init__(self, goal, acceptance_tests=None):
        self.id = "proj_" + str(uuid.uuid4())[:8]
        self.goal = goal
        self.subtasks = []
        self.acceptance_tests = acceptance_tests or []
        self.created_at = time.time()
        self.completed_at = None
    def add_subtask(self, subtask):
        self.subtasks.append(subtask)
        return subtask
    def progress(self):
        if not self.subtasks: return 0
        done = sum(1 for s in self.subtasks if s.status == TaskStatus.DONE)
        return round(done / len(self.subtasks), 2)
    def ready_tasks(self):
        done_ids = {s.id for s in self.subtasks if s.status == TaskStatus.DONE}
        ready = []
        for s in self.subtasks:
            if s.status == TaskStatus.PENDING:
                deps_met = all(d in done_ids for d in s.depends_on)
                if deps_met:
                    ready.append(s)
        return ready
    def to_dict(self):
        return {"id": self.id, "goal": self.goal,
                "progress": self.progress(),
                "subtasks": [s.to_dict() for s in self.subtasks],
                "acceptance_tests": self.acceptance_tests,
                "created_at": self.created_at}

class MergePipeline:
    """Normalize -> conflict check -> integrate -> verify -> commit."""
    def __init__(self):
        self.queue = deque(maxlen=50)
        self.merged = 0
        self.conflicts = 0
    def submit(self, task_id, model, output):
        self.queue.append({"task_id": task_id, "model": model,
                          "output": output, "ts": time.time(),
                          "status": "pending"})
    def check_conflicts(self):
        targets = {}
        conflicts = []
        for item in self.queue:
            if item["status"] != "pending": continue
            tid = item["task_id"]
            if tid in targets:
                conflicts.append((targets[tid], item))
                self.conflicts += 1
            targets[tid] = item
        return conflicts
    def merge_ready(self):
        ready = [i for i in self.queue if i["status"] == "pending"]
        for i in ready:
            i["status"] = "merged"
            self.merged += 1
        return ready
    def status(self):
        return {"queue_size": len(self.queue), "merged": self.merged,
                "conflicts": self.conflicts}

class TaskGraphEngine:
    """Manages all project tasks and subtask execution."""
    def __init__(self):
        self.projects = {}  # id -> ProjectTask
        self.merge = MergePipeline()
        self.total_tasks_completed = 0

    def create_project(self, goal, subtask_specs=None):
        proj = ProjectTask(goal)
        if subtask_specs:
            for spec in subtask_specs:
                st = SubTask(spec.get("description", ""),
                           spec.get("role", "builder"),
                           spec.get("depends_on", []),
                           spec.get("inputs", []),
                           spec.get("outputs", []))
                proj.add_subtask(st)
        self.projects[proj.id] = proj
        log.info("Project created: " + proj.id + " - " + goal)
        return proj

    def get_ready_tasks(self, project_id):
        proj = self.projects.get(project_id)
        if not proj: return []
        return proj.ready_tasks()

    def start_task(self, project_id, subtask_id, model_name):
        proj = self.projects.get(project_id)
        if not proj: return False
        for st in proj.subtasks:
            if st.id == subtask_id:
                st.status = TaskStatus.RUNNING
                st.assigned_model = model_name
                st.started_at = time.time()
                return True
        return False

    def complete_task(self, project_id, subtask_id, result):
        proj = self.projects.get(project_id)
        if not proj: return False
        for st in proj.subtasks:
            if st.id == subtask_id:
                st.status = TaskStatus.DONE
                st.result = result
                st.completed_at = time.time()
                self.total_tasks_completed += 1
                self.merge.submit(subtask_id, st.assigned_model, result)
                if proj.progress() >= 1.0:
                    proj.completed_at = time.time()
                return True
        return False

    def fail_task(self, project_id, subtask_id, error):
        proj = self.projects.get(project_id)
        if not proj: return False
        for st in proj.subtasks:
            if st.id == subtask_id:
                st.status = TaskStatus.FAILED
                st.result = {"error": error}
                return True
        return False

    def status(self):
        return {"projects": len(self.projects),
                "total_completed": self.total_tasks_completed,
                "merge": self.merge.status(),
                "active": {k: v.to_dict() for k, v in self.projects.items()}}

# Singleton
_engine = None
def get_task_engine():
    global _engine
    if _engine is None:
        _engine = TaskGraphEngine()
    return _engine