# NovaX Full System Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the complete NovaX AI Operating System — all 32 sections, every tool, every feature — using the A+C Hybrid approach (bottom-up foundation + vertical slice proof).

**Architecture:** Flask+SocketIO orchestrator on port 9999 coordinates all intelligence. 6 permanent drivers execute actions. Multi-AI routing (Claude cloud + Ollama local) with learned optimization. Two-Phase Intent System (think→plan→execute) with Option A/B. Persistent skill memory, task graph, workflows, profiles. Hivemind Terminal (6 tabs) and Nova Desktop (14 tools/panels) as primary UIs. VCC verifies all services. DSE reconciles desired/observed state. Arbiter controls all mutations.

**Tech Stack:** Python 3.11+, Flask, Flask-SocketIO, psutil, Anthropic API, Ollama, HTML5/CSS3/JS, WebSockets

**Existing Code (DO NOT REWRITE):**
- `core/orchestrator.py` (480 lines, 26+ endpoints) — EXTEND only
- `core/drivers.py` (281 lines, 4 drivers) — ADD web+ai drivers
- `core/claude_connector.py` (131 lines) — WORKING, leave as-is
- `core/ai_router.py` (97 lines) — WORKING, extend
- `core/task_classifier.py` (76 lines) — WORKING, leave as-is
- `core/skills_engine.py` (165 lines) — WORKING, extend for confidence scoring
- `core/vcc.py` (142 lines) — WORKING, extend for full lifecycle
- `core/state.py` (32 lines) — EXTEND significantly
- `core/tasks.py` (42 lines) — EXTEND significantly
- `core/session_memory.py` (99 lines) — EXTEND for workflows
- `core/ai_router_memory.py` (95 lines) — WORKING, leave as-is

---

## PHASE 1: Core Engine Completion (Foundation)

### Task 1.1: Unify Config System

**Files:**
- Modify: `C:\NovaX\core\config.py`

**Step 1: Rewrite config.py to load from disk + env**

Replace the 13-line stub with a proper config loader:

```python
import os
import json
from pathlib import Path

BASE_DIR = Path(r"C:\NovaX")
MEMORY_DIR = BASE_DIR / "memory"
PROFILES_DIR = BASE_DIR / "profiles"
CONFIG_DIR = BASE_DIR / "config"
NOVA_MEMORY_DIR = Path(r"C:\NovaMemory")

# API Keys
def get_anthropic_key():
    key_file = CONFIG_DIR / "anthropic.key"
    if key_file.exists():
        return key_file.read_text().strip()
    return os.environ.get("ANTHROPIC_API_KEY", "")

# Model defaults
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "mixtral")
USE_CLAUDE_FIRST = True

# Role → model mapping
ROLE_MODELS = {
    "planner": "claude",
    "coder": "deepseek",
    "terminal": "mixtral",
    "repair": "claude",
    "chat": "claude",
}

# Service ports
SERVICES = {
    "orchestrator": 9999,
    "brain": 9990,
    "websocket": 9998,
    "relay": 9877,
    "nexus": 9882,
    "sentinel": 9883,
    "hivemind_server": 9881,
    "cloud_router": 9878,
    "openclaw": 18789,
    "ollama": 11434,
}

# Personality profiles
PROFILES = ["work", "dev", "creative", "gaming"]
DEFAULT_PROFILE = "dev"

# Conversation memory
MAX_CONVERSATION_HISTORY = 12
MAX_TASK_STEPS = 20
```

**Step 2: Verify config loads**

Run: `python -c "import sys; sys.path.insert(0, r'C:\\NovaX\\core'); import config; print(config.SERVICES)"`
Expected: Dict of services printed

**Step 3: Commit**

```bash
cd C:\NovaX && git add core/config.py && git commit -m "feat: complete config system with disk+env loading"
```

---

### Task 1.2: Extend System State Awareness

**Files:**
- Modify: `C:\NovaX\core\state.py`

**Step 1: Extend state.py with full system awareness**

Add to existing 32-line file:

```python
# Add these imports at top
import shutil
import subprocess

def tool_availability():
    """Check which dev tools are installed."""
    tools = {}
    for tool in ["python", "python3", "node", "npm", "git", "docker", "code", "ollama", "pip", "pip3"]:
        try:
            result = subprocess.run([tool, "--version"], capture_output=True, text=True, timeout=5)
            tools[tool] = result.stdout.strip() or result.stderr.strip()
        except (FileNotFoundError, subprocess.TimeoutExpired):
            tools[tool] = None
    return tools

def gpu_info():
    """Get GPU info if nvidia-smi available."""
    try:
        result = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total,memory.used", "--format=csv,noheader"],
                                capture_output=True, text=True, timeout=5)
        return result.stdout.strip() if result.returncode == 0 else None
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None

def full_system_context():
    """Complete system context for AI prompt injection."""
    summary = system_summary()
    summary["tools"] = tool_availability()
    summary["gpu"] = gpu_info()
    return summary

def format_for_prompt(ctx=None):
    """Format system context as text for AI prompt injection."""
    if ctx is None:
        ctx = full_system_context()
    lines = [
        f"OS: {ctx.get('os', 'unknown')}",
        f"CPU: {ctx.get('cpu', 'unknown')} ({ctx.get('cpu_percent', '?')}% used)",
        f"RAM: {ctx.get('ram_percent', '?')}% used",
    ]
    if ctx.get("gpu"):
        lines.append(f"GPU: {ctx['gpu']}")
    apps = ctx.get("running_apps", [])[:10]
    if apps:
        lines.append(f"Running: {', '.join(apps)}")
    tools = ctx.get("tools", {})
    available = [t for t, v in tools.items() if v]
    if available:
        lines.append(f"Tools: {', '.join(available)}")
    return "\n".join(lines)
```

**Step 2: Test system context**

Run: `python -c "import sys; sys.path.insert(0, r'C:\\NovaX\\core'); import state; print(state.format_for_prompt())"`
Expected: Formatted system info

**Step 3: Commit**

```bash
cd C:\NovaX && git add core/state.py && git commit -m "feat: extend system state with tools, GPU, prompt formatting"
```

---

### Task 1.3: Extend Persistent Task Graph

**Files:**
- Modify: `C:\NovaX\core\tasks.py`

**Step 1: Extend tasks.py with full task lifecycle**

Add to existing file:

```python
def update_status(tid, status, error=None):
    """Update task status: active, paused, done, error."""
    data = load()
    if tid in data:
        data[tid]["status"] = status
        if error:
            data[tid]["error"] = error
            data[tid]["error_step"] = data[tid].get("current", 0)
        if status == "done":
            data[tid]["completed"] = datetime.now().isoformat()
        save(data)

def pause(tid):
    """Pause an active task."""
    update_status(tid, "paused")

def resume(tid):
    """Resume a paused task."""
    update_status(tid, "active")

def get_all():
    """Return all tasks grouped by status."""
    data = load()
    result = {"active": [], "paused": [], "done": [], "error": []}
    for tid, task in data.items():
        status = task.get("status", "active")
        if status in result:
            result[status].append({"id": tid, **task})
    return result

def get_history(limit=200):
    """Return completed tasks, most recent first."""
    data = load()
    done = [{"id": tid, **t} for tid, t in data.items() if t.get("status") in ("done", "error")]
    done.sort(key=lambda x: x.get("completed", x.get("created", "")), reverse=True)
    return done[:limit]

def delete(tid):
    """Remove a task."""
    data = load()
    if tid in data:
        del data[tid]
        save(data)

def step_details(tid):
    """Get current step details for a task."""
    data = load()
    if tid not in data:
        return None
    task = data[tid]
    current = task.get("current", 0)
    steps = task.get("steps", [])
    return {
        "id": tid,
        "goal": task.get("goal"),
        "current_step": current,
        "total_steps": len(steps),
        "current_action": steps[current] if current < len(steps) else None,
        "status": task.get("status"),
        "progress": f"{current}/{len(steps)}"
    }
```

**Step 2: Test task lifecycle**

Run: `python -c "import sys; sys.path.insert(0, r'C:\\NovaX\\core'); import tasks; tid = tasks.new_task('test', ['a','b','c']); print(tasks.step_details(tid)); tasks.advance(tid); print(tasks.get_all())"`

**Step 3: Commit**

```bash
cd C:\NovaX && git add core/tasks.py && git commit -m "feat: extend task graph with pause/resume/history/delete"
```

---

### Task 1.4: Add Missing Drivers (AI + Vision)

**Files:**
- Modify: `C:\NovaX\core\drivers.py`

**Step 1: Add AIDriver and VisionDriver classes**

Add after CodeDriver class:

```python
class AIDriver:
    """Talk to any AI model through the routing system."""
    name = "ai"

    def ask(self, prompt, model=None, system_prompt=None):
        try:
            from ai_router import route_with_fallback
            from claude_connector import ask_claude

            if model and model.startswith("claude"):
                response = ask_claude(prompt, system=system_prompt)
            else:
                # Try Ollama first
                import requests
                m = model or "mixtral"
                try:
                    r = requests.post("http://localhost:11434/api/generate",
                        json={"model": m, "prompt": prompt, "stream": False}, timeout=60)
                    if r.ok:
                        response = r.json().get("response", "")
                    else:
                        response = ask_claude(prompt, system=system_prompt)
                except:
                    response = ask_claude(prompt, system=system_prompt)
            return DriverResult(True, response)
        except Exception as e:
            return DriverResult(False, "", str(e))

    def execute(self, action, params):
        if action == "ask":
            return self.ask(params.get("prompt", ""), params.get("model"), params.get("system"))
        return DriverResult(False, "", f"Unknown AI action: {action}")


class VisionDriver:
    """Screen reading and UI understanding."""
    name = "vision"

    def screenshot(self):
        try:
            import subprocess
            out = Path(r"C:\NovaX\memory\screenshot.png")
            subprocess.run(["powershell", "-Command",
                f"Add-Type -AssemblyName System.Windows.Forms; "
                f"[System.Windows.Forms.Screen]::PrimaryScreen | ForEach-Object {{ "
                f"$bmp = New-Object System.Drawing.Bitmap($_.Bounds.Width, $_.Bounds.Height); "
                f"$g = [System.Drawing.Graphics]::FromImage($bmp); "
                f"$g.CopyFromScreen($_.Bounds.Location, [System.Drawing.Point]::Empty, $_.Bounds.Size); "
                f"$bmp.Save('{out}') }}"], capture_output=True, timeout=10)
            return DriverResult(True, str(out))
        except Exception as e:
            return DriverResult(False, "", str(e))

    def active_window(self):
        try:
            import subprocess
            result = subprocess.run(["powershell", "-Command",
                "Get-Process | Where-Object {$_.MainWindowTitle -ne ''} | "
                "Select-Object ProcessName, MainWindowTitle | ConvertTo-Json"],
                capture_output=True, text=True, timeout=10)
            return DriverResult(True, result.stdout)
        except Exception as e:
            return DriverResult(False, "", str(e))

    def execute(self, action, params):
        if action == "screenshot":
            return self.screenshot()
        elif action == "active_window":
            return self.active_window()
        return DriverResult(False, "", f"Unknown vision action: {action}")
```

**Step 2: Register new drivers in DriverBus**

Update DriverBus.__init__:

```python
class DriverBus:
    def __init__(self):
        self.drivers = {
            "terminal": TerminalDriver(),
            "file": FileDriver(),
            "system": SystemDriver(),
            "code": CodeDriver(),
            "ai": AIDriver(),
            "vision": VisionDriver(),
        }
```

**Step 3: Test new drivers**

Run: `python -c "import sys; sys.path.insert(0, r'C:\\NovaX\\core'); from drivers import bus; print(bus.execute('ai', 'ask', {'prompt': 'say hello', 'model': 'claude'}).output[:100])"`

**Step 4: Commit**

```bash
cd C:\NovaX && git add core/drivers.py && git commit -m "feat: add AI and Vision drivers to action bus"
```

---

### Task 1.5: Add Confidence Scoring to Skills

**Files:**
- Modify: `C:\NovaX\core\skills_engine.py`

**Step 1: Add confidence scoring functions**

Add to existing file:

```python
def update_confidence(skill_id, outcome):
    """
    Update skill confidence based on user choice.
    outcome: 'execute_a' | 'execute_a_edited' | 'execute_b' | 'cancelled' | 'error'
    """
    SCORE_MAP = {
        "execute_a": 0.10,
        "execute_a_edited": 0.03,
        "execute_b": -0.02,
        "cancelled": -0.10,
        "error": -0.15,
    }
    delta = SCORE_MAP.get(outcome, 0)
    skills = load_skills()
    if skill_id in skills:
        current = skills[skill_id].get("confidence", 0.5)
        new_conf = max(0.0, min(1.0, current + delta))
        skills[skill_id]["confidence"] = round(new_conf, 3)
        skills[skill_id]["uses"] = skills[skill_id].get("uses", 0) + 1
        skills[skill_id]["last_used"] = __import__("time").time()
        _save_skills(skills)
    return skills.get(skill_id, {}).get("confidence", 0.5)

def _save_skills(skills):
    """Save skills back to disk."""
    with open(str(SKILLS_FILE), "w") as f:
        json.dump(skills, f, indent=2)

def get_skill_suggestion_level(skill_id):
    """
    Returns suggestion behavior based on confidence.
    < 0.60: normal (show as option)
    >= 0.60: aggressive (highlight)
    >= 0.80: pre-select (Option A default)
    >= 0.90: auto-merge (merge into Option B defaults)
    """
    skills = load_skills()
    conf = skills.get(skill_id, {}).get("confidence", 0.5)
    if conf >= 0.90:
        return "auto_merge"
    elif conf >= 0.80:
        return "pre_select"
    elif conf >= 0.60:
        return "aggressive"
    return "normal"
```

**Step 2: Test confidence scoring**

Run: `python -c "import sys; sys.path.insert(0, r'C:\\NovaX\\core'); from skills_engine import *; print(update_confidence('organize_downloads', 'execute_a')); print(get_skill_suggestion_level('organize_downloads'))"`

**Step 3: Commit**

```bash
cd C:\NovaX && git add core/skills_engine.py && git commit -m "feat: add confidence scoring to skill memory"
```

---

### Task 1.6: Build Workflow Memory Module

**Files:**
- Create: `C:\NovaX\core\workflows.py`

**Step 1: Implement workflow memory**

```python
"""
Workflow Memory — named macros built from repeated patterns.
Explicit naming + automatic pattern detection (3+ repeats).
"""
import json
import hashlib
import time
from pathlib import Path

WORKFLOWS_FILE = Path(r"C:\NovaX\memory\workflows.json")

def _load():
    if WORKFLOWS_FILE.exists():
        return json.loads(WORKFLOWS_FILE.read_text())
    return {}

def _save(data):
    WORKFLOWS_FILE.parent.mkdir(parents=True, exist_ok=True)
    WORKFLOWS_FILE.write_text(json.dumps(data, indent=2))

def _hash_actions(actions):
    """Hash action sequence for pattern matching."""
    normalized = json.dumps([{"driver": a.get("driver"), "action": a.get("action")} for a in actions], sort_keys=True)
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]

def save_workflow(name, actions, description=""):
    """Save a named workflow."""
    data = _load()
    data[name] = {
        "actions": actions,
        "description": description,
        "hash": _hash_actions(actions),
        "created": time.time(),
        "uses": 0,
        "last_used": None,
    }
    _save(data)
    return name

def match_workflow(actions):
    """Check if action sequence matches a saved workflow."""
    target_hash = _hash_actions(actions)
    data = _load()
    for name, wf in data.items():
        if wf.get("hash") == target_hash:
            return {"name": name, "workflow": wf}
    return None

def use_workflow(name):
    """Record workflow usage."""
    data = _load()
    if name in data:
        data[name]["uses"] = data[name].get("uses", 0) + 1
        data[name]["last_used"] = time.time()
        _save(data)
    return data.get(name)

def list_workflows():
    """List all saved workflows."""
    return _load()

def delete_workflow(name):
    """Delete a workflow."""
    data = _load()
    if name in data:
        del data[name]
        _save(data)
```

**Step 2: Test workflow save/match**

Run: `python -c "import sys; sys.path.insert(0, r'C:\\NovaX\\core'); from workflows import *; save_workflow('test', [{'driver':'terminal','action':'run'}]); print(list_workflows())"`

**Step 3: Commit**

```bash
cd C:\NovaX && git add core/workflows.py && git commit -m "feat: add workflow memory with pattern hashing"
```

---

### Task 1.7: Build Time-Aware Memory Module

**Files:**
- Create: `C:\NovaX\core\time_index.py`

**Step 1: Implement temporal memory**

```python
"""
Time-Aware Memory — understand "yesterday's setup", "the python project", etc.
"""
import json
import time
from datetime import datetime, timedelta
from pathlib import Path

INDEX_FILE = Path(r"C:\NovaX\memory\history_index.json")

def _load():
    if INDEX_FILE.exists():
        return json.loads(INDEX_FILE.read_text())
    return []

def _save(data):
    INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
    INDEX_FILE.write_text(json.dumps(data, indent=2))

def record_event(description, keywords, apps=None, size="medium"):
    """Record a completed action with temporal metadata."""
    data = _load()
    data.append({
        "time": time.time(),
        "iso": datetime.now().isoformat(),
        "description": description,
        "keywords": keywords if isinstance(keywords, list) else [keywords],
        "apps": apps or [],
        "size": size,
    })
    # Keep last 500 events
    if len(data) > 500:
        data = data[-500:]
    _save(data)

def search(query):
    """Search history by fuzzy text matching."""
    data = _load()
    query_lower = query.lower()
    results = []

    # Time references
    now = datetime.now()
    time_filters = {
        "yesterday": (now - timedelta(days=1)).date(),
        "today": now.date(),
        "last week": (now - timedelta(weeks=1)).date(),
        "this week": (now - timedelta(days=now.weekday())).date(),
    }

    date_filter = None
    for phrase, dt in time_filters.items():
        if phrase in query_lower:
            date_filter = dt
            query_lower = query_lower.replace(phrase, "").strip()
            break

    for event in reversed(data):
        score = 0
        # Keyword match
        for kw in event.get("keywords", []):
            if kw.lower() in query_lower or query_lower in kw.lower():
                score += 2
        # Description match
        if query_lower in event.get("description", "").lower():
            score += 1
        # App match
        for app in event.get("apps", []):
            if app.lower() in query_lower:
                score += 1
        # Size match
        if event.get("size", "") in query_lower:
            score += 1
        # Date filter
        if date_filter:
            event_date = datetime.fromisoformat(event["iso"]).date()
            if event_date < date_filter:
                continue
        if score > 0:
            results.append({**event, "relevance": score})

    results.sort(key=lambda x: x["relevance"], reverse=True)
    return results[:10]
```

**Step 2: Test temporal search**

Run: `python -c "import sys; sys.path.insert(0, r'C:\\NovaX\\core'); from time_index import *; record_event('set up python project', ['python','setup'], ['vscode']); print(search('python project'))"`

**Step 3: Commit**

```bash
cd C:\NovaX && git add core/time_index.py && git commit -m "feat: add time-aware memory with fuzzy search"
```

---

### Task 1.8: Build Profile Manager

**Files:**
- Create: `C:\NovaX\core\profile_manager.py`

**Step 1: Implement profile switching**

```python
"""
Profile Manager — 4 personality modes with separate memory roots.
Dev, Work, Creative, Gaming — each with own skills, workflows, routing.
"""
import json
import shutil
import time
import zipfile
from pathlib import Path

PROFILES_DIR = Path(r"C:\NovaX\profiles")
MEMORY_DIR = Path(r"C:\NovaX\memory")
STATE_FILE = MEMORY_DIR / "profile_state.json"

PROFILE_DEFAULTS = {
    "dev": {
        "behavior": "fast, terminal-heavy, code generation",
        "preferred_model": "deepseek",
        "risk_tolerance": "medium",
        "theme": "green_matrix",
    },
    "work": {
        "behavior": "careful confirmations, documentation first",
        "preferred_model": "claude",
        "risk_tolerance": "low",
        "theme": "clean",
    },
    "creative": {
        "behavior": "multi-AI brainstorming",
        "preferred_model": "claude",
        "risk_tolerance": "medium",
        "theme": "magenta_vaporwave",
    },
    "gaming": {
        "behavior": "minimal interruptions, performance",
        "preferred_model": "phi3",
        "risk_tolerance": "low",
        "theme": "purple_flare",
    },
}

MEMORY_FILES = [
    "skills.json", "history.json", "ai_routing.json",
    "workflows.json", "history_index.json", "ui_routines.json",
    "model_prefs.json", "session_capture.json",
]

def _load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"active": "dev"}

def _save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2))

def get_active():
    """Get current active profile."""
    return _load_state().get("active", "dev")

def get_profile_config(name=None):
    """Get profile configuration."""
    name = name or get_active()
    return PROFILE_DEFAULTS.get(name, PROFILE_DEFAULTS["dev"])

def switch(target):
    """Switch to a different profile. Saves current memory, loads target memory."""
    if target not in PROFILE_DEFAULTS:
        return {"error": f"Unknown profile: {target}"}

    current = get_active()
    if current == target:
        return {"status": "already_active", "profile": target}

    # Save current memory to profile dir
    current_dir = PROFILES_DIR / current
    current_dir.mkdir(parents=True, exist_ok=True)
    for f in MEMORY_FILES:
        src = MEMORY_DIR / f
        if src.exists():
            shutil.copy2(str(src), str(current_dir / f))

    # Load target memory from profile dir
    target_dir = PROFILES_DIR / target
    target_dir.mkdir(parents=True, exist_ok=True)
    for f in MEMORY_FILES:
        src = target_dir / f
        dst = MEMORY_DIR / f
        if src.exists():
            shutil.copy2(str(src), str(dst))

    _save_state({"active": target, "switched_at": time.time()})
    return {"status": "switched", "from": current, "to": target, "config": PROFILE_DEFAULTS[target]}

def export_profile(name=None):
    """Export profile as .novaxprofile zip."""
    name = name or get_active()
    profile_dir = PROFILES_DIR / name
    export_path = PROFILES_DIR / f"{name}.novaxprofile"

    with zipfile.ZipFile(str(export_path), "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("profile.json", json.dumps(PROFILE_DEFAULTS.get(name, {}), indent=2))
        for f in MEMORY_FILES:
            src = profile_dir / f
            if src.exists():
                zf.write(str(src), f)
    return str(export_path)

def import_profile(zip_path, name=None):
    """Import .novaxprofile zip."""
    with zipfile.ZipFile(zip_path, "r") as zf:
        meta = json.loads(zf.read("profile.json"))
        target_name = name or "imported"
        target_dir = PROFILES_DIR / target_name
        target_dir.mkdir(parents=True, exist_ok=True)
        zf.extractall(str(target_dir))
    return {"status": "imported", "profile": target_name}

def list_profiles():
    """List all profiles with active indicator."""
    active = get_active()
    return [{"name": p, "active": p == active, **PROFILE_DEFAULTS[p]} for p in PROFILE_DEFAULTS]
```

**Step 2: Test profile switching**

Run: `python -c "import sys; sys.path.insert(0, r'C:\\NovaX\\core'); from profile_manager import *; print(get_active()); print(switch('work')); print(get_active())"`

**Step 3: Commit**

```bash
cd C:\NovaX && git add core/profile_manager.py && git commit -m "feat: add profile manager with switch/export/import"
```

---

### Task 1.9: Build Event Bus

**Files:**
- Create: `C:\NovaX\core\event_bus.py`

**Step 1: Implement structured event bus**

```python
"""
Event Bus — structured communication for all NovaX components.
Types: SUGGESTION, BLOCKER, PATCH, DECISION, RISK, STATUS
"""
import json
import time
import threading
from collections import defaultdict
from pathlib import Path

LOG_FILE = Path(r"C:\NovaX\memory\event_log.jsonl")

class EventBus:
    VALID_TYPES = {"SUGGESTION", "BLOCKER", "PATCH", "DECISION", "RISK", "STATUS",
                   "SERVICE_UP", "SERVICE_DOWN", "REPAIR_APPLIED", "CONVERGED",
                   "TASK_STARTED", "TASK_COMPLETED", "TASK_FAILED", "SKILL_LEARNED"}

    def __init__(self):
        self._subscribers = defaultdict(list)
        self._lock = threading.Lock()
        self._history = []

    def subscribe(self, event_type, callback):
        """Subscribe to an event type."""
        with self._lock:
            self._subscribers[event_type].append(callback)

    def emit(self, event_type, data=None, source=None):
        """Emit an event to all subscribers."""
        if event_type not in self.VALID_TYPES:
            return
        event = {
            "type": event_type,
            "data": data or {},
            "source": source or "unknown",
            "timestamp": time.time(),
            "iso": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        with self._lock:
            self._history.append(event)
            if len(self._history) > 1000:
                self._history = self._history[-500:]
            # Persist
            with open(str(LOG_FILE), "a") as f:
                f.write(json.dumps(event) + "\n")
        # Notify subscribers (non-blocking)
        for cb in self._subscribers.get(event_type, []):
            try:
                cb(event)
            except Exception:
                pass
        # Also notify wildcard subscribers
        for cb in self._subscribers.get("*", []):
            try:
                cb(event)
            except Exception:
                pass

    def recent(self, limit=50, event_type=None):
        """Get recent events."""
        with self._lock:
            events = self._history
            if event_type:
                events = [e for e in events if e["type"] == event_type]
            return events[-limit:]

# Singleton
bus = EventBus()
```

**Step 2: Test event bus**

Run: `python -c "import sys; sys.path.insert(0, r'C:\\NovaX\\core'); from event_bus import bus; bus.emit('STATUS', {'msg': 'test'}); print(bus.recent())"`

**Step 3: Commit**

```bash
cd C:\NovaX && git add core/event_bus.py && git commit -m "feat: add event bus with pub/sub and persistence"
```

---

### Task 1.10: Build Arbiter (Mutation Authority)

**Files:**
- Create: `C:\NovaX\core\arbiter.py`

**Step 1: Implement arbiter**

```python
"""
Arbiter — ONLY authority for system mutations.
All drivers must go through the Arbiter. Workers propose, Arbiter executes.
"""
import json
import time
from pathlib import Path
from event_bus import bus

AUDIT_LOG = Path(r"C:\NovaX\memory\arbiter_audit.jsonl")

class Arbiter:
    def __init__(self, driver_bus):
        self.driver_bus = driver_bus
        self.pending = []
        self.god_mode = False
        self.admin_mode = False

    def propose(self, driver, action, params, risk="low", source="user"):
        """Propose an action for execution. Returns proposal ID."""
        proposal = {
            "id": f"prop_{int(time.time()*1000)}",
            "driver": driver,
            "action": action,
            "params": params,
            "risk": risk,
            "source": source,
            "status": "pending",
            "proposed_at": time.time(),
        }
        self.pending.append(proposal)
        bus.emit("SUGGESTION", proposal, source="arbiter")
        return proposal

    def approve_and_execute(self, proposal_id):
        """Execute an approved proposal through the driver bus."""
        proposal = next((p for p in self.pending if p["id"] == proposal_id), None)
        if not proposal:
            return {"error": "Proposal not found"}

        proposal["status"] = "executing"
        bus.emit("DECISION", {"proposal": proposal_id, "decision": "approved"}, source="arbiter")

        result = self.driver_bus.execute(proposal["driver"], proposal["action"], proposal["params"])

        proposal["status"] = "completed" if result.ok else "failed"
        proposal["result"] = result.to_dict()
        proposal["executed_at"] = time.time()

        # Audit log
        with open(str(AUDIT_LOG), "a") as f:
            f.write(json.dumps(proposal) + "\n")

        # Remove from pending
        self.pending = [p for p in self.pending if p["id"] != proposal_id]

        if result.ok:
            bus.emit("TASK_COMPLETED", {"proposal": proposal_id}, source="arbiter")
        else:
            bus.emit("TASK_FAILED", {"proposal": proposal_id, "error": result.error}, source="arbiter")

        return result.to_dict()

    def execute_plan(self, actions, source="user"):
        """Execute a full action plan through the arbiter."""
        results = []
        for action in actions:
            result = self.driver_bus.execute(
                action.get("driver", "terminal"),
                action.get("action", "run_command"),
                action.get("params", {})
            )
            results.append(result.to_dict())
            # Audit
            with open(str(AUDIT_LOG), "a") as f:
                f.write(json.dumps({
                    "driver": action.get("driver"),
                    "action": action.get("action"),
                    "ok": result.ok,
                    "time": time.time()
                }) + "\n")
            if not result.ok:
                bus.emit("TASK_FAILED", {"step": action, "error": result.error}, source="arbiter")
                break
        return results

    def get_pending(self):
        """Get all pending proposals."""
        return self.pending
```

**Step 2: Test arbiter**

Run: `python -c "import sys; sys.path.insert(0, r'C:\\NovaX\\core'); from drivers import bus as db; from arbiter import Arbiter; a = Arbiter(db); p = a.propose('system','get_system_info',{}); print(a.approve_and_execute(p['id']))"`

**Step 3: Commit**

```bash
cd C:\NovaX && git add core/arbiter.py && git commit -m "feat: add arbiter as sole mutation authority"
```

---

### Task 1.11: Build Desired-State Engine

**Files:**
- Create: `C:\NovaX\core\dse.py`

**Step 1: Implement DSE**

```python
"""
Desired-State Engine — reconciles observed state to desired state.
Profiles: IDLE, AI_WORKSPACE_ON, GAME_MODE_ON, DEV_MODE_ON, etc.
"""
import json
import time
from pathlib import Path
from event_bus import bus

STATE_DIR = Path(r"C:\NovaX\memory")
OBSERVED_FILE = STATE_DIR / "observed_state.json"
DESIRED_FILE = STATE_DIR / "desired_state.json"
PLAN_FILE = STATE_DIR / "last_plan.json"

DSE_PROFILES = {
    "IDLE": {"services": ["orchestrator"], "models": [], "apps": []},
    "DEV_MODE_ON": {"services": ["orchestrator", "brain", "relay", "ollama"], "models": ["deepseek", "mixtral"], "apps": ["code"]},
    "AI_WORKSPACE_ON": {"services": ["orchestrator", "brain", "relay", "ollama", "nexus"], "models": ["claude", "mixtral", "deepseek"], "apps": []},
    "GAME_MODE_ON": {"services": ["orchestrator"], "models": [], "apps": []},
    "MODELING_3D_ON": {"services": ["orchestrator", "brain"], "models": ["llava"], "apps": ["blender"]},
    "SAFE_MODE": {"services": ["orchestrator"], "models": [], "apps": []},
    "PANIC_OFF": {"services": [], "models": [], "apps": []},
}

def _load(path, default=None):
    if path.exists():
        return json.loads(path.read_text())
    return default or {}

def _save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))

def get_observed():
    """Get current observed system state."""
    from state import system_summary
    from vcc import get_vcc_status
    summary = system_summary()
    vcc = get_vcc_status()
    return {
        "services": {k: v.get("state") == "TRUSTED" for k, v in vcc.items()},
        "running_apps": summary.get("running_apps", []),
        "timestamp": time.time(),
    }

def get_desired():
    """Get desired state."""
    return _load(DESIRED_FILE, {"profile": "IDLE"})

def set_desired(profile_name):
    """Set desired state from profile."""
    if profile_name not in DSE_PROFILES:
        return {"error": f"Unknown profile: {profile_name}"}
    desired = {"profile": profile_name, **DSE_PROFILES[profile_name], "set_at": time.time()}
    _save(DESIRED_FILE, desired)
    bus.emit("STATUS", {"desired_profile": profile_name}, source="dse")
    return desired

def diff():
    """Calculate difference between observed and desired."""
    observed = get_observed()
    desired = get_desired()

    diffs = []
    # Services that should be running but aren't
    for svc in desired.get("services", []):
        if not observed.get("services", {}).get(svc, False):
            diffs.append({"type": "service_missing", "service": svc, "action": "start"})

    # Apps that should be open but aren't
    running_lower = [a.lower() for a in observed.get("running_apps", [])]
    for app in desired.get("apps", []):
        if app.lower() not in running_lower:
            diffs.append({"type": "app_missing", "app": app, "action": "launch"})

    return {"diffs": diffs, "converged": len(diffs) == 0}

def plan():
    """Generate an execution plan to reach desired state."""
    d = diff()
    actions = []
    for item in d["diffs"]:
        if item["type"] == "service_missing":
            actions.append({"driver": "system", "action": "open_app", "params": {"app": f"novax_{item['service']}"}, "risk": "medium"})
        elif item["type"] == "app_missing":
            actions.append({"driver": "system", "action": "open_app", "params": {"app": item["app"]}, "risk": "low"})
    p = {"actions": actions, "diffs": d["diffs"], "generated_at": time.time()}
    _save(PLAN_FILE, p)
    return p

def killswitch(mode="safe"):
    """Emergency stop. safe=stop services, panic=kill everything."""
    if mode == "panic":
        set_desired("PANIC_OFF")
        bus.emit("STATUS", {"killswitch": "PANIC_OFF"}, source="dse")
    else:
        set_desired("SAFE_MODE")
        bus.emit("STATUS", {"killswitch": "SAFE_MODE"}, source="dse")
    return {"status": f"killswitch_{mode}_activated"}
```

**Step 2: Test DSE**

Run: `python -c "import sys; sys.path.insert(0, r'C:\\NovaX\\core'); from dse import *; print(set_desired('DEV_MODE_ON')); print(diff())"`

**Step 3: Commit**

```bash
cd C:\NovaX && git add core/dse.py && git commit -m "feat: add desired-state engine with profiles and reconciliation"
```

---

### Task 1.12: Build Context Watcher

**Files:**
- Create: `C:\NovaX\core\context_watcher.py`

**Step 1: Implement app watcher for auto profile switching**

```python
"""
Context Watcher — monitors foreground window, suggests profile switches.
"""
import json
import time
import subprocess
from pathlib import Path

RULES_FILE = Path(r"C:\NovaX\memory\context_rules.json")

DEFAULT_RULES = {
    "dev": ["Code.exe", "code.exe", "pycharm64.exe", "idea64.exe", "cursor.exe"],
    "work": ["WINWORD.EXE", "EXCEL.EXE", "POWERPNT.EXE", "OUTLOOK.EXE", "Teams.exe"],
    "creative": ["blender.exe", "photoshop.exe", "gimp-2.10.exe", "krita.exe", "obs64.exe"],
    "gaming": ["steam.exe", "EpicGamesLauncher.exe", "retroarch.exe"],
}

def _load_rules():
    if RULES_FILE.exists():
        return json.loads(RULES_FILE.read_text())
    return DEFAULT_RULES

def get_foreground_app():
    """Get the current foreground window process name."""
    try:
        result = subprocess.run(["powershell", "-Command",
            "(Get-Process | Where-Object {$_.MainWindowHandle -eq "
            "(Add-Type '[DllImport(\"user32.dll\")] public static extern IntPtr GetForegroundWindow();' "
            "-Name Win32 -PassThru)::GetForegroundWindow()}).ProcessName"],
            capture_output=True, text=True, timeout=5)
        return result.stdout.strip()
    except:
        return None

def detect_profile(process_name=None):
    """Detect which profile matches the current foreground app."""
    if not process_name:
        process_name = get_foreground_app()
    if not process_name:
        return None

    rules = _load_rules()
    exe = process_name if process_name.endswith(".exe") else process_name + ".exe"

    for profile, apps in rules.items():
        if exe in apps or process_name in [a.replace(".exe", "") for a in apps]:
            return profile
    return None

def add_rule(profile, exe_name):
    """Add a new context rule."""
    rules = _load_rules()
    if profile not in rules:
        rules[profile] = []
    if exe_name not in rules[profile]:
        rules[profile].append(exe_name)
    RULES_FILE.write_text(json.dumps(rules, indent=2))
```

**Step 2: Test context detection**

Run: `python -c "import sys; sys.path.insert(0, r'C:\\NovaX\\core'); from context_watcher import *; print(detect_profile('Code'))"`

**Step 3: Commit**

```bash
cd C:\NovaX && git add core/context_watcher.py && git commit -m "feat: add context watcher for auto profile switching"
```

---

### Task 1.13: Build Environment Manager

**Files:**
- Create: `C:\NovaX\core\environment_manager.py`

**Step 1: Implement environment bootstrapping**

```python
"""
Environment Manager — workspace preparation when switching profiles/projects.
"""
import json
from pathlib import Path

ENVS_FILE = Path(r"C:\NovaX\memory\environments.json")

DEFAULT_ENVIRONMENTS = {
    "dev": {
        "actions": [
            {"driver": "system", "action": "open_app", "params": {"app": "code"}, "risk": "low"},
            {"driver": "terminal", "action": "run_command", "params": {"cmd": "ollama serve"}, "risk": "low"},
        ],
        "description": "Open VS Code, start Ollama for local AI",
    },
    "work": {
        "actions": [
            {"driver": "system", "action": "open_app", "params": {"app": "outlook"}, "risk": "low"},
        ],
        "description": "Open Outlook for email",
    },
    "creative": {
        "actions": [
            {"driver": "system", "action": "open_app", "params": {"app": "blender"}, "risk": "low"},
            {"driver": "system", "action": "open_app", "params": {"app": "krita"}, "risk": "low"},
        ],
        "description": "Open Blender and Krita",
    },
    "gaming": {
        "actions": [
            {"driver": "system", "action": "open_app", "params": {"app": "steam"}, "risk": "low"},
        ],
        "description": "Open Steam",
    },
}

def _load():
    if ENVS_FILE.exists():
        return json.loads(ENVS_FILE.read_text())
    return DEFAULT_ENVIRONMENTS

def _save(data):
    ENVS_FILE.parent.mkdir(parents=True, exist_ok=True)
    ENVS_FILE.write_text(json.dumps(data, indent=2))

def get_environment(profile):
    """Get workspace bootstrap actions for a profile."""
    envs = _load()
    return envs.get(profile, {"actions": [], "description": "No environment configured"})

def save_environment(profile, actions, description=""):
    """Save custom environment for a profile."""
    envs = _load()
    envs[profile] = {"actions": actions, "description": description}
    _save(envs)

def propose_bootstrap(profile):
    """Generate bootstrap proposal for UI display."""
    env = get_environment(profile)
    return {
        "profile": profile,
        "description": env.get("description", ""),
        "actions": env.get("actions", []),
        "requires_approval": True,
    }
```

**Step 2: Test environment proposal**

Run: `python -c "import sys; sys.path.insert(0, r'C:\\NovaX\\core'); from environment_manager import *; print(propose_bootstrap('dev'))"`

**Step 3: Commit**

```bash
cd C:\NovaX && git add core/environment_manager.py && git commit -m "feat: add environment manager for workspace bootstrapping"
```

---

## PHASE 2: Wire Orchestrator to All Modules

### Task 2.1: Integrate All New Modules into Orchestrator

**Files:**
- Modify: `C:\NovaX\core\orchestrator.py`

**Step 1: Add imports for all new modules**

Add to top of orchestrator.py:

```python
from workflows import save_workflow as wf_save, list_workflows as wf_list, match_workflow
from time_index import record_event, search as time_search
from profile_manager import switch as profile_switch, get_active as active_profile, list_profiles, export_profile, import_profile
from event_bus import bus as event_bus
from arbiter import Arbiter
from dse import get_observed, get_desired, set_desired, diff as dse_diff, plan as dse_plan, killswitch
from context_watcher import detect_profile
from environment_manager import propose_bootstrap
import config
```

**Step 2: Initialize arbiter**

After driver bus initialization:
```python
from arbiter import Arbiter
arbiter = Arbiter(bus)
```

**Step 3: Add missing endpoints**

Add these routes:

```python
@app.route("/workflow/save", methods=["POST"])
def route_workflow_save():
    data = request.json
    name = wf_save(data.get("name"), data.get("actions", []), data.get("description", ""))
    return jsonify({"status": "saved", "name": name})

@app.route("/workflow/list", methods=["GET"])
def route_workflow_list():
    return jsonify(wf_list())

@app.route("/profile/switch", methods=["POST"])
def route_profile_switch():
    data = request.json
    result = profile_switch(data.get("profile", "dev"))
    return jsonify(result)

@app.route("/profile/list", methods=["GET"])
def route_profile_list():
    return jsonify(list_profiles())

@app.route("/profile/export", methods=["GET"])
def route_profile_export():
    path = export_profile()
    return send_file(path, as_attachment=True)

@app.route("/profile/import", methods=["POST"])
def route_profile_import():
    # Handle file upload
    if "file" in request.files:
        f = request.files["file"]
        save_path = Path(r"C:\NovaX\profiles") / f.filename
        f.save(str(save_path))
        result = import_profile(str(save_path))
        return jsonify(result)
    return jsonify({"error": "No file provided"}), 400

@app.route("/task/pause", methods=["POST"])
def route_task_pause():
    from tasks import get_active, pause
    tid, _ = get_active()
    if tid:
        pause(tid)
        return jsonify({"status": "paused", "task_id": tid})
    return jsonify({"error": "No active task"})

@app.route("/task/active", methods=["GET"])
def route_task_active():
    from tasks import get_active, step_details
    tid, _ = get_active()
    if tid:
        return jsonify(step_details(tid))
    return jsonify({"active": None})

@app.route("/task/history", methods=["GET"])
def route_task_history():
    from tasks import get_history
    return jsonify(get_history())

@app.route("/step", methods=["POST"])
def route_step():
    from tasks import get_active, advance, step_details
    tid, task = get_active()
    if not tid:
        return jsonify({"error": "No active task"})
    # Execute current step
    steps = task.get("steps", [])
    current = task.get("current", 0)
    if current < len(steps):
        result = arbiter.execute_plan([steps[current]])
        advance(tid)
        return jsonify({"step": current, "result": result, "details": step_details(tid)})
    return jsonify({"status": "task_complete"})

@app.route("/run", methods=["POST"])
def route_run():
    data = request.json or {}
    n = min(data.get("steps", 5), 20)
    from tasks import get_active, advance, step_details
    tid, task = get_active()
    if not tid:
        return jsonify({"error": "No active task"})
    results = []
    for _ in range(n):
        steps = task.get("steps", [])
        current = task.get("current", 0)
        if current >= len(steps):
            break
        result = arbiter.execute_plan([steps[current]])
        advance(tid)
        results.append(result)
        if not result[0].get("ok", True) if result else True:
            break
    return jsonify({"executed": len(results), "results": results, "details": step_details(tid)})

@app.route("/control/observed", methods=["GET"])
def route_control_observed():
    return jsonify(get_observed())

@app.route("/control/desired", methods=["GET"])
def route_control_desired():
    return jsonify(get_desired())

@app.route("/control/diff", methods=["GET"])
def route_control_diff():
    return jsonify(dse_diff())

@app.route("/control/request", methods=["POST"])
def route_control_request():
    data = request.json
    result = set_desired(data.get("profile", "IDLE"))
    return jsonify(result)

@app.route("/control/profile/apply", methods=["POST"])
def route_control_profile_apply():
    data = request.json
    return jsonify(set_desired(data.get("profile", "IDLE")))

@app.route("/control/profile/list", methods=["GET"])
def route_control_profile_list():
    from dse import DSE_PROFILES
    return jsonify(list(DSE_PROFILES.keys()))

@app.route("/control/killswitch/safe", methods=["POST"])
def route_killswitch_safe():
    return jsonify(killswitch("safe"))

@app.route("/control/killswitch/panic", methods=["POST"])
def route_killswitch_panic():
    return jsonify(killswitch("panic"))

@app.route("/api/metrics", methods=["GET"])
def route_metrics():
    from tasks import get_all
    task_data = get_all()
    total = sum(len(v) for v in task_data.values())
    done = len(task_data.get("done", []))
    return jsonify({
        "uptime": _fmt_uptime(),
        "total_tasks": total,
        "completed_tasks": done,
        "success_rate": round(done / max(total, 1) * 100, 1),
        "active_model": active_profile(),
        "loaded_skills": len(list_skills()),
        "version": "3.0.0",
    })

@app.route("/project/suggest", methods=["POST"])
def route_project_suggest():
    return jsonify(propose_bootstrap(active_profile()))

@app.route("/repair", methods=["POST"])
def route_repair():
    data = request.json
    error = data.get("error", "Unknown error")
    step = data.get("step", {})
    # Ask Claude for repair plan
    from claude_connector import ask_claude
    repair_prompt = f"A NovaX action failed. Error: {error}. Failed step: {json.dumps(step)}. Suggest a repair plan as JSON array of actions."
    response = ask_claude(repair_prompt)
    try:
        repair_plan = json.loads(response)
    except:
        repair_plan = [{"driver": "terminal", "action": "run_command", "params": {"cmd": "echo Repair needed"}, "risk": "low"}]
    return jsonify({"repair_plan": repair_plan, "original_error": error})
```

**Step 4: Inject system context into /think**

Modify the existing /think handler to include system state and conversation memory:

```python
# In the /think handler, before calling Claude:
from state import format_for_prompt
system_context = format_for_prompt()
conversation = get_conversation()  # from session_memory

enhanced_prompt = f"""System State:
{system_context}

Recent Conversation:
{json.dumps(conversation[-6:], indent=2)}

User Request: {text}"""
```

**Step 5: Test all new endpoints**

Run: `curl http://localhost:9999/api/metrics`
Run: `curl http://localhost:9999/control/observed`
Run: `curl http://localhost:9999/profile/list`

**Step 6: Commit**

```bash
cd C:\NovaX && git add core/orchestrator.py && git commit -m "feat: integrate all modules into orchestrator — 40+ endpoints"
```

---

## PHASE 3: Vertical Slice Proof

### Task 3.1: End-to-End Flow Test

**Goal:** Type "open notepad" → AI plans → shows Option A/B → click Execute → notepad opens → skill saved → VCC green

**Step 1: Start the orchestrator**

```bash
cd C:\NovaX && python core/orchestrator.py
```

**Step 2: Test /think**

```bash
curl -X POST http://localhost:9999/think -H "Content-Type: application/json" -d "{\"text\": \"open notepad\"}"
```

Expected: JSON with `optionA` (if skill exists) and `optionB` (AI-generated plan)

**Step 3: Test /execute**

```bash
curl -X POST http://localhost:9999/execute -H "Content-Type: application/json" -d "{\"actions\": [{\"driver\": \"system\", \"action\": \"open_app\", \"params\": {\"app\": \"notepad\"}}]}"
```

Expected: Notepad opens, JSON result with ok:true

**Step 4: Test VCC**

```bash
curl http://localhost:9999/api/vcc
```

Expected: Service status for all known services

**Step 5: Test metrics**

```bash
curl http://localhost:9999/api/metrics
```

Expected: JSON with uptime, tasks, success rate

**Step 6: If all pass, commit**

```bash
cd C:\NovaX && git add -A && git commit -m "feat: vertical slice proof — full think→execute→vcc flow working"
```

---

## PHASE 4: Hivemind Terminal (All 6 Tabs)

### Task 4.1: Wire Hivemind Terminal Tab to Real API

**Files:**
- Modify: `C:\NovaX\web\hivemind.html`

**Step 1: Update API calls in Terminal tab**

Ensure the Terminal tab sends commands to `http://localhost:9999/think` for prompt processing and `http://localhost:9999/execute` for action execution. Wire the @claude prefix to force Claude routing, !cmd to terminal driver shell passthrough.

**Step 2: Wire Tasks tab to /task/active and /task/history**

Fetch from `http://localhost:9999/task/active` and display current task with step progress. Fetch from `http://localhost:9999/task/history` for completed tasks.

**Step 3: Wire Archive tab to /task/history with limit=200**

**Step 4: Wire Metrics tab to /api/metrics**

Fetch and display: uptime, total tasks, active model, success rate, loaded skills, version.

**Step 5: Wire VCC tab to /api/vcc**

Fetch and display service grid with green/red per service and port numbers.

**Step 6: Wire Skills tab to /api/skills**

Fetch and display clickable skill grid. On click, populate terminal input with skill trigger.

**Step 7: Test all 6 tabs**

Open `http://localhost:9999/hivemind.html` and verify each tab shows real data.

**Step 8: Commit**

```bash
cd C:\NovaX && git add web/hivemind.html && git commit -m "feat: wire all 6 hivemind tabs to real API endpoints"
```

---

## PHASE 5: Nova Desktop (Full OS Shell)

### Task 5.1: Build Nova Desktop with All Panels

**Files:**
- Modify or Create: `C:\NovaX\web\nova_desktop.html`

This is the main OS shell with:
- Bottom-center glass prompt bar
- Plan drawer with Option A/B
- Service status dots
- Profile selector
- Model override dropdown

**Desktop Tool Panels to build:**

1. **Code Editor** — Monaco editor (VS Code's editor engine), connected to file_driver
2. **Terminal** — xterm.js terminal, connected to terminal_driver
3. **File Manager** — Tree view connected to /api/fs/list, /api/fs/read, /api/fs/write
4. **Universal Debugger** — Process viewer + log stream
5. **Package Manager** — UI for apt/pip/npm/choco
6. **Network Monitor** — Service health from /api/vcc + port status
7. **Process Manager** — From /api/processes
8. **System Monitor** — CPU/RAM/Disk from /api/system
9. **Settings** — Profile management from /profile/*
10. **dApp Launcher** — XRPL placeholder panel
11. **AI Playground** — Direct /think interface with model selector
12. **Workflow Designer** — Visual workflow builder
13. **Skill Browser** — From /api/skills
14. **Log Viewer** — WebSocket event stream

Each panel is a draggable/resizable window in the desktop environment.

**Step 1: Create the HTML/CSS/JS shell**

Build the desktop with glassmorphism aesthetic, Nova Cyan (#00ffff), Ether Purple (#ab00ff), Stellar Black (#111111). Matrix rain background. Bottom prompt bar.

**Step 2: Add panel launcher (taskbar/dock)**

Icon-based launcher for each of the 14 tools.

**Step 3: Wire prompt bar to /think and /execute**

**Step 4: Wire plan drawer to show Option A/B**

**Step 5: Wire each panel to its respective API endpoint**

**Step 6: Test desktop**

Open `http://localhost:9999/nova_desktop.html` and verify all panels work.

**Step 7: Commit**

```bash
cd C:\NovaX && git add web/nova_desktop.html && git commit -m "feat: nova desktop OS shell with all 14 tool panels"
```

---

## PHASE 6: Services Stack

### Task 6.1: Create Brain Server (Port 9990)

**Files:**
- Create: `C:\NovaX\core\brain_server.py`

Simple Flask server that wraps Ollama API calls. Provides /generate and /chat endpoints that proxy to Ollama with NovaX-specific system prompts.

### Task 6.2: Create Relay Server (Port 9877)

**Files:**
- Create: `C:\NovaX\core\relay_server.py`

Relay that accepts commands from hivemind.html and forwards to orchestrator. Provides CORS-enabled endpoints for browser-based execution.

### Task 6.3: Service Launcher Script

**Files:**
- Create: `C:\NovaX\start_all.py`

Python script that starts all NovaX services in order: orchestrator → brain → relay → sentinel. Checks port availability before starting. Reports status.

### Task 6.4: Commit

```bash
cd C:\NovaX && git add core/brain_server.py core/relay_server.py start_all.py && git commit -m "feat: add brain, relay servers and unified launcher"
```

---

## PHASE 7: Advanced Layers

### Task 7.1: NCP CLI

**Files:**
- Create: `C:\NovaX\novax_cli.py`

Command-line interface: `novax bootstrap`, `novax status`, `novax diff`, `novax plan`, `novax apply`, `novax set-desired --profile DEV_MODE_ON`.

### Task 7.2: UI Memory (Visual Automation)

**Files:**
- Create: `C:\NovaX\core\ui_memory.py`

Records UI interaction sequences, stores in memory/ui_routines.json, offers replay after 3+ uses.

### Task 7.3: Project Learner

**Files:**
- Modify: `C:\NovaX\core\project_learner.py`

Watches session actions, detects project patterns (4+ actions), offers to save as project environment.

### Task 7.4: Repair Engine

**Files:**
- Modify: `C:\NovaX\core\repair_engine.py`

When a step fails: diagnose error → ask Claude for fix → propose repair plan → user approves → retry.

### Task 7.5: Commit

```bash
cd C:\NovaX && git add -A && git commit -m "feat: add NCP CLI, UI memory, project learner, repair engine"
```

---

## PHASE 8: Extended Features

### Task 8.1: XRPL Wallet Integration

**Files:**
- Create: `C:\NovaX\core\xrpl_wallet.py`

Native XRPL wallet using xrpl-py. Basic operations: create wallet, check balance, send XRP. NovaCoin support placeholder.

### Task 8.2: Voice Layer

**Files:**
- Create: `C:\NovaX\core\voice.py`

Wake word "Nova" detection using speech_recognition. Commands routed through /think. Espeak for voice feedback.

### Task 8.3: Module System

**Files:**
- Create: `C:\NovaX\core\module_manager.py`

Install/remove Nova modules (Nova-Dev, Nova-AI, Nova-Game, etc.). Each module has manifest.json defining dependencies and install steps.

### Task 8.4: Commit

```bash
cd C:\NovaX && git add -A && git commit -m "feat: add XRPL wallet, voice layer, module system"
```

---

## PHASE 9: OS Installation & Polish

### Task 9.1: Windows Shell Replacement

**Files:**
- Create: `C:\NovaX\installer\shell_replace.py`

Register Nova Desktop as Windows shell replacement (HKCU\Software\Microsoft\Windows NT\CurrentVersion\Winlogon\Shell). Keeps all credentials, drivers. Toggle back to Explorer.

### Task 9.2: Boot Sound & Branding

**Files:**
- Create: `C:\NovaX\web\assets\boot.js`

Matrix animation, boot voice "Welcome to NovaX", synth chord, mode-specific themes.

### Task 9.3: Enterprise Installer Update

Update the existing `NovaX-v3.0.0-Enterprise/` with all new files and services.

### Task 9.4: Final Integration Test

Start all services, open Nova Desktop, test:
1. Prompt → Plan → Execute flow
2. All 14 desktop panels
3. All 6 Hivemind tabs
4. Profile switching
5. VCC all green
6. Skill learning
7. Task persistence

### Task 9.5: Commit

```bash
cd C:\NovaX && git add -A && git commit -m "feat: NovaX v3.0.0 complete — all 32 sections built"
```

---

## Summary

| Phase | Tasks | What Gets Built |
|-------|-------|----------------|
| 1 | 1.1-1.13 | Config, state, tasks, drivers, skills, workflows, time memory, profiles, event bus, arbiter, DSE, context watcher, environment manager |
| 2 | 2.1 | Wire all modules into orchestrator — 40+ endpoints |
| 3 | 3.1 | Vertical slice proof: prompt → plan → execute → skill → VCC |
| 4 | 4.1 | Hivemind Terminal — all 6 tabs with real data |
| 5 | 5.1 | Nova Desktop — OS shell with 14 tool panels |
| 6 | 6.1-6.3 | Brain server, relay server, unified launcher |
| 7 | 7.1-7.4 | NCP CLI, UI memory, project learner, repair engine |
| 8 | 8.1-8.3 | XRPL wallet, voice layer, module system |
| 9 | 9.1-9.4 | Windows shell, boot branding, installer, final test |
