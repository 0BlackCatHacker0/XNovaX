"""
NovaX Task Graph Engine - God Mode Job Decomposition
=====================================================
User goals become dependency graphs.
Subtasks assigned to workers with roles.
Merge pipeline: normalize -> conflict check -> integrate -> verify -> commit.
"""
import time, threading, logging, json, uuid
from collections import deque
from enum import Enum

log = logging.getLogger("NovaX.TaskGraph")

class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    BLOCKED = "blocked"
    DONE = "done"
    FAILED = "failed"

class WorkerRole(Enum):
    ARCHITECT = "architect"
    BUILDER = "builder"
    DEBUGGER = "debugger"
    TESTER = "tester"
    INTEGRATOR = "integrator"

class SubTask:
    def __init__(self, description, role="builder", depends_on=None):
        self.id = "st_" + str(uuid.uuid4())[:8]
        self.description = description
        self.role = role if isinstance(role, WorkerRole) else WorkerRole(role)
        self.depends_on = depends_on or []
        self.status = TaskStatus.PENDING
        self.assigned_to = None
        self.output = None
        self.started_at = None
        self.finished_at = None
    def is_ready(self, completed_ids):
        return all(dep in completed_ids for dep in self.depends_on)
    def to_dict(self):
        return {"id": self.id, "description": self.description[:80],
                "role": self.role.value, "status": self.status.value,
                "assigned_to": self.assigned_to, "depends_on": self.depends_on}

class ProjectTask:
    """A full project broken into subtasks with dependencies."""
    def __init__(self, goal, acceptance_tests=None):
        self.id = "proj_" + str(uuid.uuid4())[:8]
        self.goal = goal
        self.subtasks = {}          # id -> SubTask
        self.acceptance_tests = acceptance_tests or []
        self.status = TaskStatus.PENDING
        self.created_at = time.time()
        self.finished_at = None
    def add_subtask(self, description, role="builder", depends_on=None):
        st = SubTask(description, role, depends_on)
        self.subtasks[st.id] = st
        return st.id
    def completed_ids(self):
        return [sid for sid, st in self.subtasks.items() if st.status == TaskStatus.DONE]
    def ready_tasks(self):
        done = set(self.completed_ids())
        return [st for st in self.subtasks.values()
                if st.status == TaskStatus.PENDING and st.is_ready(done)]
    def progress(self):
        total = len(self.subtasks)
        if total == 0: return 0.0
        done = sum(1 for st in self.subtasks.values() if st.status == TaskStatus.DONE)
        return round(done / total, 2)
    def is_complete(self):
        return all(st.status == TaskStatus.DONE for st in self.subtasks.values())
    def to_dict(self):
        return {"id": self.id, "goal": self.goal[:100], "status": self.status.value,
                "progress": self.progress(),
                "subtasks": [st.to_dict() for st in self.subtasks.values()],
                "total": len(self.subtasks),
                "done": len(self.completed_ids())}

class TaskGraphEngine:
    """Manages project task graphs for God Mode multi-model collaboration."""
    def __init__(self, router=None, arbiter=None, eventbus=None):
        self.router = router
        self.arbiter = arbiter
        self.eventbus = eventbus
        self.projects = {}           # id -> ProjectTask
        self.active_project = None

    def create_project(self, goal, subtasks_list=None):
        """Create a new project from a goal."""
        project = ProjectTask(goal)
        if subtasks_list:
            for st_def in subtasks_list:
                desc = st_def.get("description", "")
                role = st_def.get("role", "builder")
                deps = st_def.get("depends_on", [])
                project.add_subtask(desc, role, deps)
        project.status = TaskStatus.PENDING
        self.projects[project.id] = project
        self.active_project = project.id
        log.info("Project created: " + project.id + " - " + goal[:60])
        return project

    def decompose_goal(self, goal):
        """Use Router to ask AI to decompose a goal into subtasks."""
        if not self.router:
            return None
        prompt = ("Break this goal into 4-8 subtasks with roles. "
                  "Roles: architect, builder, debugger, tester, integrator. "
                  "Return JSON array: [{description, role, depends_on:[]}]. "
                  "Goal: " + goal)
        packet = self.router.route_text(prompt)
        if packet.success and packet.response:
            try:
                # Try to parse JSON from response
                text = packet.response
                start = text.find("[")
                end = text.rfind("]") + 1
                if start >= 0 and end > start:
                    subtasks = json.loads(text[start:end])
                    return self.create_project(goal, subtasks)
            except json.JSONDecodeError:
                pass
        # Fallback: create basic structure
        project = ProjectTask(goal)
        project.add_subtask("Design architecture for: " + goal, "architect")
        project.add_subtask("Build core implementation", "builder")
        project.add_subtask("Debug and fix issues", "debugger")
        project.add_subtask("Write tests", "tester")
        project.add_subtask("Integrate and finalize", "integrator")
        project.status = TaskStatus.PENDING
        self.projects[project.id] = project
        self.active_project = project.id
        return project

    def execute_next(self):
        """Execute the next ready subtask in the active project."""
        if not self.active_project:
            return None
        project = self.projects.get(self.active_project)
        if not project:
            return None
        ready = project.ready_tasks()
        if not ready:
            if project.is_complete():
                project.status = TaskStatus.DONE
                project.finished_at = time.time()
                return {"status": "project_complete", "progress": 1.0}
            return {"status": "blocked", "ready": 0}

        task = ready[0]
        task.status = TaskStatus.RUNNING
        task.started_at = time.time()
        project.status = TaskStatus.RUNNING

        # Route to AI
        if self.router:
            prompt = "Role: " + task.role.value + ". Task: " + task.description
            packet = self.router.route_text(prompt)
            task.assigned_to = packet.routed_to
            if packet.success:
                task.output = packet.response
                task.status = TaskStatus.DONE
                task.finished_at = time.time()
                if self.eventbus:
                    self.eventbus.publish("status", task.role.value,
                        task.description[:60] + " -> DONE", task_id=project.id)
            else:
                task.status = TaskStatus.FAILED
        else:
            task.status = TaskStatus.DONE
            task.output = "No router connected"
            task.finished_at = time.time()

        return {"subtask": task.to_dict(), "progress": project.progress()}

    def run_all(self):
        """Execute all subtasks in dependency order."""
        results = []
        for _ in range(50):  # safety limit
            r = self.execute_next()
            if not r: break
            results.append(r)
            if r.get("status") in ("project_complete", "blocked"):
                break
        return results

    def status(self):
        return {
            "active_project": self.active_project,
            "projects": {pid: p.to_dict() for pid, p in self.projects.items()},
            "total_projects": len(self.projects),
        }
