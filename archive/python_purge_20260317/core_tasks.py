# tasks.py — Task Graph: manages multi-step task execution
# Supports create, get_active, advance, pause, load, step_details, history
# Orchestrator uses: tasks.get_active(), tasks.advance(tid), tasks.step_details(tid),
#                    tasks.load(), tasks.pause(tid), tasks.get_history(), tasks.get_all()

import time
import uuid

_tasks = {}       # {tid: task_dict}
_active_tid = None
_history = []


def create_task(name, steps=None, **kwargs):
    """Create a new task with optional steps."""
    global _active_tid
    tid = str(uuid.uuid4())[:8]
    task = {
        "id": tid,
        "name": name,
        "steps": steps or [],
        "current": 0,
        "status": "active",
        "created": time.time(),
        **kwargs,
    }
    _tasks[tid] = task
    _active_tid = tid
    return task


def get_active():
    """Get the currently active task. Returns (tid, task) or (None, None)."""
    if _active_tid and _active_tid in _tasks:
        task = _tasks[_active_tid]
        if task.get("status") == "active":
            return (_active_tid, task)
    # Find any active task
    for tid, task in _tasks.items():
        if task.get("status") == "active":
            return (tid, task)
    return (None, None)


def advance(tid):
    """Advance a task to the next step."""
    task = _tasks.get(tid)
    if task:
        task["current"] = task.get("current", 0) + 1
        if task["current"] >= len(task.get("steps", [])):
            task["status"] = "complete"
            _history.append({
                "tid": tid,
                "name": task.get("name", ""),
                "completed": time.time(),
                "steps": len(task.get("steps", [])),
            })
        return True
    return False


def step_details(tid):
    """Get details about current step of a task."""
    task = _tasks.get(tid)
    if not task:
        return {"error": "Task not found"}
    steps = task.get("steps", [])
    current = task.get("current", 0)
    return {
        "tid": tid,
        "name": task.get("name", ""),
        "status": task.get("status", "unknown"),
        "current_step": current,
        "total_steps": len(steps),
        "current_action": steps[current] if current < len(steps) else None,
        "progress": round(current / max(len(steps), 1) * 100, 1),
    }


def pause(tid):
    """Pause a task."""
    task = _tasks.get(tid)
    if task:
        task["status"] = "paused"
        return True
    return False


def load():
    """Load all tasks (returns the full tasks dict)."""
    return _tasks


def get_all():
    """Get all tasks as a list."""
    return list(_tasks.values())


def get_tasks(status=None):
    """Get tasks, optionally filtered by status."""
    tasks_list = list(_tasks.values())
    if status:
        return [t for t in tasks_list if t.get("status") == status]
    return tasks_list


def get_history():
    """Get completed task history."""
    return _history


def update_task(name, **kwargs):
    """Update a task by name."""
    for tid, task in _tasks.items():
        if task.get("name") == name:
            task.update(kwargs)
            return task
    return None


def delete_task(name):
    """Delete a task by name."""
    to_remove = [tid for tid, t in _tasks.items() if t.get("name") == name]
    for tid in to_remove:
        del _tasks[tid]
    return bool(to_remove)
