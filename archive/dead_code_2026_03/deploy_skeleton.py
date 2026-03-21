"""Deploy all NovaX OS skeleton files."""
import os

BASE = r"C:\NovaX\novax"

FILES = {
# ===== __init__.py files =====
"__init__.py": "",
"core/__init__.py": "",
"health/__init__.py": "",
"policy/__init__.py": "",
"snapshot/__init__.py": "",
"memory/__init__.py": "",
"tools/__init__.py": "",
"context/__init__.py": "",
"explain/__init__.py": "",
"api/__init__.py": "",
"events/__init__.py": "from .bus import bus, EventBus",

# ===== CORE - system brain =====
"core/orchestrator.py": '''"""Job orchestrator - receives intents, creates jobs, drives execution."""
import time
from ..objects import Job, Intent, Status, Receipt
from ..events.bus import bus, JOB_CREATED, JOB_COMPLETED, JOB_FAILED

class Orchestrator:
    def __init__(self):
        self.jobs = {}
        self.queue = []

    def submit(self, intent: Intent) -> Job:
        job = Job(intent=intent, status=Status.PENDING)
        self.jobs[job.id] = job
        self.queue.append(job.id)
        bus.emit(JOB_CREATED, {"job_id": job.id, "action": intent.action})
        return job

    def run_next(self) -> Receipt:
        if not self.queue:
            return Receipt(success=False, output="no jobs queued")
        jid = self.queue.pop(0)
        job = self.jobs[jid]
        job.status = Status.RUNNING
        job.started = time.time()
        try:
            # TODO: route to tool runner based on intent
            job.result = f"executed: {job.intent.action}"
            job.status = Status.DONE
            job.finished = time.time()
            bus.emit(JOB_COMPLETED, {"job_id": jid})
            return Receipt(job_id=jid, success=True, output=str(job.result),
                         duration=job.finished - job.started)
        except Exception as e:
            job.status = Status.FAILED
            job.error = str(e)
            job.finished = time.time()
            bus.emit(JOB_FAILED, {"job_id": jid, "error": str(e)})
            return Receipt(job_id=jid, success=False, output=str(e))

    def get(self, job_id: str) -> Job:
        return self.jobs.get(job_id)

    def active(self):
        return [j for j in self.jobs.values() if j.status in (Status.PENDING, Status.RUNNING)]

    def history(self, n=20):
        done = [j for j in self.jobs.values() if j.status in (Status.DONE, Status.FAILED)]
        return sorted(done, key=lambda j: j.finished, reverse=True)[:n]

    def cancel(self, job_id: str) -> bool:
        if job_id in self.jobs and self.jobs[job_id].status == Status.PENDING:
            self.jobs[job_id].status = Status.CANCELLED
            if job_id in self.queue:
                self.queue.remove(job_id)
            return True
        return False
''',

"core/scheduler.py": '''"""Scheduler - time-based and dependency-based job triggering."""
import threading, time

class Scheduler:
    def __init__(self):
        self.timers = {}
        self._running = False

    def every(self, name, seconds, callback):
        self.timers[name] = {"interval": seconds, "fn": callback, "last": 0}

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def _loop(self):
        while self._running:
            now = time.time()
            for name, t in self.timers.items():
                if now - t["last"] >= t["interval"]:
                    try:
                        t["fn"]()
                    except Exception as e:
                        print(f"[Scheduler] {name} error: {e}")
                    t["last"] = now
            time.sleep(1)
''',

"core/locks.py": '''"""Resource locks - prevent concurrent dangerous operations."""
import threading

class LockManager:
    def __init__(self):
        self._locks = {}
        self._global = threading.Lock()

    def acquire(self, resource: str, timeout=10) -> bool:
        with self._global:
            if resource not in self._locks:
                self._locks[resource] = threading.Lock()
        return self._locks[resource].acquire(timeout=timeout)

    def release(self, resource: str):
        if resource in self._locks:
            try:
                self._locks[resource].release()
            except RuntimeError:
                pass

    def locked(self):
        return [r for r, l in self._locks.items() if l.locked()]
''',

# ===== HEALTH - self-healing =====
"health/monitor.py": '''"""Health monitor - watches services, detects failures, triggers recovery."""
import time, subprocess
from ..objects import Incident
from ..events.bus import bus, SERVICE_CRASHED, RECOVERY_PERFORMED

class HealthMonitor:
    def __init__(self):
        self.services = {}
        self.incidents = []

    def register(self, name, probe_fn, recover_fn=None):
        self.services[name] = {
            "probe": probe_fn, "recover": recover_fn,
            "status": "unknown", "last_check": 0, "failures": 0
        }

    def check_all(self):
        results = {}
        for name, svc in self.services.items():
            try:
                ok = svc["probe"]()
                svc["status"] = "healthy" if ok else "degraded"
                if ok:
                    svc["failures"] = 0
                else:
                    svc["failures"] += 1
            except Exception as e:
                svc["status"] = "down"
                svc["failures"] += 1
                inc = Incident(service=name, error=str(e))
                self.incidents.append(inc)
                bus.emit(SERVICE_CRASHED, {"service": name, "error": str(e)})
                if svc["recover"] and svc["failures"] >= 2:
                    try:
                        svc["recover"]()
                        inc.recovered = True
                        inc.recovery_action = "auto-restart"
                        bus.emit(RECOVERY_PERFORMED, {"service": name})
                    except:
                        pass
            svc["last_check"] = time.time()
            results[name] = svc["status"]
        return results

    def status(self):
        return {n: s["status"] for n, s in self.services.items()}

    def recent_incidents(self, n=20):
        return self.incidents[-n:]
''',

"health/probes.py": '''"""Health probes - check if services are alive."""
import urllib.request, json, subprocess

def probe_http(url, timeout=5):
    try:
        r = urllib.request.urlopen(url, timeout=timeout)
        return r.status == 200
    except:
        return False

def probe_port(host, port, timeout=3):
    import socket
    try:
        s = socket.create_connection((host, port), timeout=timeout)
        s.close()
        return True
    except:
        return False

def probe_process(name):
    try:
        r = subprocess.run(f"tasklist /FI \"IMAGENAME eq {name}\" /NH",
                         shell=True, capture_output=True, text=True, timeout=5)
        return name.lower() in r.stdout.lower()
    except:
        return False

def probe_ollama():
    return probe_http("http://localhost:11434/api/tags")

def probe_brain():
    return probe_port("localhost", 9990)

def probe_bridge():
    return probe_port("localhost", 9999)
''',

# ===== POLICY - permission layer =====
"policy/engine.py": '''"""Policy engine - evaluates whether actions are allowed."""
from ..objects import PolicyDecision, RiskLevel, Intent
from ..events.bus import bus, POLICY_DENIED

class PolicyEngine:
    def __init__(self):
        self.rules = []
        self.mode = "normal"  # normal, cautious, autonomous

    def add_rule(self, name, check_fn, risk=RiskLevel.LOW):
        self.rules.append({"name": name, "check": check_fn, "risk": risk})

    def evaluate(self, intent: Intent) -> PolicyDecision:
        matched = []
        max_risk = RiskLevel.SAFE
        for rule in self.rules:
            if rule["check"](intent):
                matched.append(rule["name"])
                if rule["risk"].value > max_risk.value:
                    max_risk = rule["risk"]
        decision = PolicyDecision(
            allowed=max_risk.value <= RiskLevel.MEDIUM.value or self.mode == "autonomous",
            risk=max_risk,
            rules_matched=matched,
            requires_approval=max_risk in (RiskLevel.HIGH, RiskLevel.CRITICAL)
        )
        if not decision.allowed:
            bus.emit(POLICY_DENIED, {"intent": intent.text, "risk": max_risk.value})
        return decision

    def set_mode(self, mode):
        self.mode = mode
''',

# ===== TOOLS - execution runtime =====
"tools/runner.py": '''"""Tool runner - safe execution of commands and scripts."""
import subprocess, time, os
from ..objects import Receipt

class ToolRunner:
    def __init__(self):
        self.history = []
        self.timeout = 30

    def shell(self, cmd, cwd=None, timeout=None) -> Receipt:
        t = timeout or self.timeout
        start = time.time()
        try:
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                             timeout=t, cwd=cwd, encoding="utf-8", errors="replace")
            receipt = Receipt(success=r.returncode == 0,
                            output=r.stdout + r.stderr, duration=time.time()-start)
        except subprocess.TimeoutExpired:
            receipt = Receipt(success=False, output="TIMEOUT", duration=t)
        except Exception as e:
            receipt = Receipt(success=False, output=str(e), duration=time.time()-start)
        self.history.append({"cmd": cmd, "receipt": receipt, "ts": time.time()})
        return receipt

    def python_exec(self, code, timeout=30) -> Receipt:
        return self.shell(f'python -c "{code}"', timeout=timeout)

    def recent(self, n=10):
        return self.history[-n:]
''',

# ===== SNAPSHOT - undo reality =====
"snapshot/manager.py": '''"""Snapshot manager - capture and restore system state."""
import os, json, time, shutil
from ..objects import Snapshot
from ..events.bus import bus, SNAPSHOT_CREATED

SNAP_DIR = r"C:\NovaX\snapshots"

class SnapshotManager:
    def __init__(self):
        os.makedirs(SNAP_DIR, exist_ok=True)
        self.snapshots = []

    def create(self, label="", paths=None) -> Snapshot:
        snap = Snapshot(label=label)
        snap_path = os.path.join(SNAP_DIR, snap.id)
        os.makedirs(snap_path, exist_ok=True)
        if paths:
            for p in paths:
                if os.path.isfile(p):
                    dest = os.path.join(snap_path, os.path.basename(p))
                    shutil.copy2(p, dest)
                    snap.files[p] = dest
        meta = os.path.join(snap_path, "meta.json")
        with open(meta, "w") as f:
            json.dump({"id": snap.id, "label": label, "created": snap.created,
                       "files": snap.files}, f, indent=2)
        self.snapshots.append(snap)
        bus.emit(SNAPSHOT_CREATED, {"id": snap.id, "label": label})
        return snap

    def list_snapshots(self):
        return [{"id": s.id, "label": s.label, "created": s.created} for s in self.snapshots]

    def restore(self, snap_id) -> bool:
        snap = next((s for s in self.snapshots if s.id == snap_id), None)
        if not snap:
            return False
        for original, backup in snap.files.items():
            if os.path.isfile(backup):
                shutil.copy2(backup, original)
        return True
''',

# ===== MEMORY - continuity =====
"memory/threads.py": '''"""Memory threads - persistent task continuity across sessions."""
import os, json, time
from ..objects import Thread, Status

THREAD_DIR = r"C:\NovaX\memory\threads"

class ThreadManager:
    def __init__(self):
        os.makedirs(THREAD_DIR, exist_ok=True)
        self.threads = {}
        self._load()

    def _load(self):
        for f in os.listdir(THREAD_DIR):
            if f.endswith(".json"):
                try:
                    with open(os.path.join(THREAD_DIR, f)) as fh:
                        data = json.load(fh)
                        t = Thread(id=data["id"], name=data.get("name",""),
                                 status=Status(data.get("status","pending")))
                        t.jobs = data.get("jobs", [])
                        t.created = data.get("created", 0)
                        t.last_active = data.get("last_active", 0)
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

    def get(self, thread_id) -> Thread:
        return self.threads.get(thread_id)

    def unfinished(self):
        return [t for t in self.threads.values()
                if t.status in (Status.PENDING, Status.RUNNING)]

    def all_threads(self):
        return list(self.threads.values())
''',

# ===== CONTEXT - intent inference =====
"context/inference.py": '''"""Context inference - understand what the user/system wants."""
from ..objects import Intent

class ContextEngine:
    def __init__(self):
        self.patterns = {
            "run": ["execute", "run", "start", "launch", "do"],
            "read": ["read", "show", "display", "get", "list", "cat"],
            "write": ["write", "create", "save", "make", "set"],
            "delete": ["delete", "remove", "kill", "stop", "rm"],
            "repair": ["fix", "repair", "recover", "heal", "restart"],
        }

    def infer(self, text: str) -> Intent:
        text_lower = text.lower()
        for action, keywords in self.patterns.items():
            for kw in keywords:
                if kw in text_lower:
                    return Intent(text=text, action=action, confidence=0.7)
        return Intent(text=text, action="unknown", confidence=0.1)
''',

# ===== EXPLAIN - human understanding =====
"explain/translator.py": '''"""Explain layer - translate system events into human language."""

class Explainer:
    def __init__(self):
        self.templates = {
            "service.crashed": "{service} went down: {error}",
            "recovery.performed": "{service} was automatically restarted",
            "job.completed": "Task {job_id} finished successfully",
            "job.failed": "Task {job_id} failed: {error}",
            "policy.denied": "Action blocked (risk: {risk}): {intent}",
        }

    def explain(self, event: str, data: dict) -> str:
        tmpl = self.templates.get(event, f"{event}: {data}")
        try:
            return tmpl.format(**data)
        except:
            return f"{event}: {data}"

    def summarize_incidents(self, incidents):
        if not incidents:
            return "No incidents recorded."
        return f"{len(incidents)} incidents. Latest: {incidents[-1].error}"
''',
}

# Write all files
count = 0
for relpath, content in FILES.items():
    fullpath = os.path.join(BASE, relpath)
    os.makedirs(os.path.dirname(fullpath), exist_ok=True)
    with open(fullpath, "w", encoding="utf-8") as f:
        f.write(content)
    count += 1

print(f"Deployed {count} skeleton files to {BASE}")

# Verify imports
import sys
sys.path.insert(0, r"C:\NovaX")
try:
    from novax.objects import Job, Intent, Status
    from novax.events.bus import bus
    print("IMPORT TEST: objects + bus OK")
except Exception as e:
    print(f"IMPORT TEST FAILED: {e}")
