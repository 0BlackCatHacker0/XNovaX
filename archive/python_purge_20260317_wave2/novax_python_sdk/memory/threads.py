"""Memory threads - persistent task continuity across sessions."""
import os, json, time
from ..objects import Thread, Status

THREAD_DIR = "C:/NovaX/memory/threads"

class ThreadManager:
    def __init__(self):
        os.makedirs(THREAD_DIR, exist_ok=True)
        self.threads = {}
        self._load()

    def _load(self):
        if not os.path.isdir(THREAD_DIR): return
        for f in os.listdir(THREAD_DIR):
            if f.endswith(".json"):
                try:
                    with open(os.path.join(THREAD_DIR, f)) as fh:
                        d = json.load(fh)
                        t = Thread(id=d["id"], name=d.get("name",""),
                                 status=Status(d.get("status","pending")))
                        t.jobs = d.get("jobs", [])
                        t.created = d.get("created", 0)
                        t.last_active = d.get("last_active", 0)
                        self.threads[t.id] = t
                except: pass

    def _save(self, thread):
        path = os.path.join(THREAD_DIR, f"{thread.id}.json")
        with open(path, "w") as f:
            json.dump({"id": thread.id, "name": thread.name,
                       "status": thread.status.value, "jobs": thread.jobs,
                       "created": thread.created, "last_active": thread.last_active}, f)

    def create(self, name="") -> Thread:
        t = Thread(name=name, status=Status.RUNNING)
        self.threads[t.id] = t
        self._save(t)
        return t

    def get(self, tid): return self.threads.get(tid)
    def unfinished(self):
        return [t for t in self.threads.values() if t.status in (Status.PENDING, Status.RUNNING)]
    def all_threads(self): return list(self.threads.values())
