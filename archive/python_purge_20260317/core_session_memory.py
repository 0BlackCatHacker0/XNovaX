# session_memory.py — Disk-persistent session memory for NovaX
# Survives orchestrator restarts AND Claude resets.
# Conversations, actions, projects all persist to C:\NovaX\data\sessions\
#
# Orchestrator imports: record_action, get_session_actions, analyze_for_project,
#   save_project, get_projects, add_message, get_conversation, clear_conversation

import os
import json
import time
import threading
import uuid

_SESSION_DIR = r"C:\NovaX\data\sessions"
_CONVO_FILE = os.path.join(_SESSION_DIR, "conversation.jsonl")
_ACTIONS_FILE = os.path.join(_SESSION_DIR, "actions.jsonl")
_PROJECTS_FILE = os.path.join(_SESSION_DIR, "projects.json")
_SESSION_META = os.path.join(_SESSION_DIR, "session_meta.json")
_CONTEXT_FILE = os.path.join(_SESSION_DIR, "working_context.json")
_LOCK = threading.Lock()

# In-memory caches (loaded from disk on first access)
_conversation = None
_actions = None
_projects = None
_meta = None

_MAX_JSONL_LINES = 5000  # Rotate when files exceed this
_MAX_JSONL_MB = 10       # Or exceed 10MB

os.makedirs(_SESSION_DIR, exist_ok=True)


# ── Session rotation ─────────────────────────────────────────────────────────

def _rotate_if_needed(path):
    """Rotate JSONL file if it exceeds size limits. Archives old data."""
    try:
        if not os.path.isfile(path):
            return
        size_mb = os.path.getsize(path) / (1024 * 1024)
        if size_mb < _MAX_JSONL_MB:
            return
        archive = path.replace(".jsonl", f"_archive_{int(time.time())}.jsonl")
        # Keep last 500 lines, archive the rest
        lines = []
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        if len(lines) <= _MAX_JSONL_LINES:
            return
        # Write archived lines
        with open(archive, "w", encoding="utf-8") as f:
            f.writelines(lines[:-500])
        # Keep recent lines
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.writelines(lines[-500:])
        os.replace(tmp, path)
    except Exception:
        pass


# ── Disk I/O helpers ─────────────────────────────────────────────────────────

def _append_jsonl(path, obj):
    """Append a single JSON object as a line to a .jsonl file."""
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, default=str) + "\n")
    _rotate_if_needed(path)


def _read_jsonl(path, limit=None):
    """Read a .jsonl file, return list of dicts. Optional tail limit."""
    if not os.path.isfile(path):
        return []
    lines = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    lines.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    if limit:
        return lines[-limit:]
    return lines


def _read_json(path, default=None):
    """Read a JSON file, return parsed object or default."""
    if not os.path.isfile(path):
        return default if default is not None else {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return default if default is not None else {}


def _write_json(path, obj):
    """Write a JSON object to file atomically (write to tmp then rename)."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, default=str)
    os.replace(tmp, path)


# ── Session metadata ─────────────────────────────────────────────────────────

def _load_meta():
    global _meta
    if _meta is None:
        _meta = _read_json(_SESSION_META, {
            "session_id": str(uuid.uuid4())[:8],
            "started": time.time(),
            "last_activity": time.time(),
            "message_count": 0,
            "action_count": 0,
            "active_tasks": [],
            "working_on": "",
            "last_topic": "",
        })
    return _meta


def _save_meta():
    if _meta:
        _meta["last_activity"] = time.time()
        _write_json(_SESSION_META, _meta)


def get_session_meta():
    """Get session metadata (for continuity display)."""
    return _load_meta()


def update_session_meta(key, value):
    """Update a session metadata field."""
    meta = _load_meta()
    meta[key] = value
    _save_meta()


# ── Conversation memory (the main chat log) ──────────────────────────────────

def _load_conversation():
    global _conversation
    if _conversation is None:
        _conversation = _read_jsonl(_CONVO_FILE)
    return _conversation


def add_message(role="user", content="", **kwargs):
    """Add a conversation message. Persists immediately to disk."""
    with _LOCK:
        convo = _load_conversation()
        msg = {
            "role": role,
            "content": content,
            "time": time.time(),
            "session_id": _load_meta().get("session_id", ""),
            **{k: v for k, v in kwargs.items() if k not in ("role", "content")},
        }
        convo.append(msg)
        _append_jsonl(_CONVO_FILE, msg)

        # Update meta
        meta = _load_meta()
        meta["message_count"] = len(convo)
        if role == "user":
            meta["last_topic"] = content[:200]
        _save_meta()

        # Trim in-memory cache if huge (disk keeps everything)
        if len(convo) > 500:
            _conversation[:] = convo[-300:]

    return True


def get_conversation(limit=50):
    """Get conversation history. Returns most recent `limit` messages."""
    with _LOCK:
        convo = _load_conversation()
        return convo[-limit:]


def get_full_conversation():
    """Get ALL conversation history from disk (for session resume)."""
    return _read_jsonl(_CONVO_FILE)


def clear_conversation():
    """Clear conversation history (starts fresh session)."""
    global _conversation
    with _LOCK:
        # Archive old conversation before clearing
        if os.path.isfile(_CONVO_FILE):
            archive = _CONVO_FILE.replace(".jsonl", f"_archive_{int(time.time())}.jsonl")
            try:
                os.rename(_CONVO_FILE, archive)
            except OSError:
                pass
        _conversation = []
        # Reset meta for new session
        global _meta
        _meta = {
            "session_id": str(uuid.uuid4())[:8],
            "started": time.time(),
            "last_activity": time.time(),
            "message_count": 0,
            "action_count": 0,
            "active_tasks": [],
            "working_on": "",
            "last_topic": "",
        }
        _save_meta()
    return True


# ── Action tracking ──────────────────────────────────────────────────────────

def _load_actions():
    global _actions
    if _actions is None:
        _actions = _read_jsonl(_ACTIONS_FILE)
    return _actions


def record_action(action=None, **kwargs):
    """Record a session action. Persists to disk immediately."""
    with _LOCK:
        actions = _load_actions()
        entry = {
            "action": action,
            "time": time.time(),
            "session_id": _load_meta().get("session_id", ""),
            **kwargs,
        }
        actions.append(entry)
        _append_jsonl(_ACTIONS_FILE, entry)

        meta = _load_meta()
        meta["action_count"] = len(actions)
        _save_meta()

        if len(actions) > 500:
            _actions[:] = actions[-300:]

    return True


def get_session_actions(limit=100):
    """Get recorded actions."""
    with _LOCK:
        return _load_actions()[-limit:]


# ── Project memory ───────────────────────────────────────────────────────────

def _load_projects():
    global _projects
    if _projects is None:
        _projects = _read_json(_PROJECTS_FILE, {})
    return _projects


def analyze_for_project(text=None, **kwargs):
    """Analyze text for project context using keyword matching."""
    projects = _load_projects()
    if not text or not projects:
        return {"project": None, "confidence": 0, "tags": []}

    text_lower = text.lower()
    best_match = None
    best_score = 0

    for name, data in projects.items():
        score = 0
        tags = data.get("tags", [])
        for tag in tags:
            if tag.lower() in text_lower:
                score += 1
        if name.lower() in text_lower:
            score += 2
        if score > best_score:
            best_score = score
            best_match = name

    if best_match and best_score > 0:
        return {
            "project": best_match,
            "confidence": min(best_score / 5.0, 1.0),
            "tags": projects[best_match].get("tags", []),
        }
    return {"project": None, "confidence": 0, "tags": []}


def save_project(name, data=None):
    """Save project data to disk."""
    with _LOCK:
        projects = _load_projects()
        projects[name] = data or {}
        _write_json(_PROJECTS_FILE, projects)
    return True


def get_projects():
    """List all projects."""
    return _load_projects()


# ── Working context (what we're doing right now) ─────────────────────────────

def save_working_context(context):
    """
    Save the current working context — what tasks are active, what was
    last discussed, what files are being edited. This is what gets loaded
    on session resume so the AI knows exactly where we left off.
    """
    ctx = {
        "saved_at": time.time(),
        "session_id": _load_meta().get("session_id", ""),
        **context,
    }
    _write_json(_CONTEXT_FILE, ctx)
    return True


def load_working_context():
    """Load the saved working context for session resume."""
    return _read_json(_CONTEXT_FILE, {})


# ── Session resume builder ───────────────────────────────────────────────────

def build_resume_prompt(max_messages=20):
    """
    Build a resume prompt that gives any AI provider full context to
    continue exactly where the last session left off.
    Returns a string ready to inject as system prompt context.
    """
    meta = _load_meta()
    recent = get_conversation(max_messages)
    ctx = load_working_context()

    lines = [
        "=== SESSION CONTINUITY ===",
        f"Session: {meta.get('session_id', 'unknown')}",
        f"Messages so far: {meta.get('message_count', 0)}",
        f"Last topic: {meta.get('last_topic', 'none')}",
        f"Working on: {meta.get('working_on', 'not set')}",
    ]

    # Active tasks
    tasks = meta.get("active_tasks", [])
    if tasks:
        lines.append(f"Active tasks: {', '.join(tasks)}")

    # Working context
    if ctx:
        if ctx.get("files_being_edited"):
            lines.append(f"Files in progress: {', '.join(ctx['files_being_edited'][:5])}")
        if ctx.get("current_goal"):
            lines.append(f"Current goal: {ctx['current_goal']}")
        if ctx.get("blockers"):
            lines.append(f"Blockers: {', '.join(ctx['blockers'][:3])}")

    # Recent conversation
    if recent:
        lines.append("")
        lines.append("=== RECENT CONVERSATION ===")
        for msg in recent[-max_messages:]:
            role = msg.get("role", "?")
            content = msg.get("content", "")
            # Truncate long messages but keep enough for context
            if len(content) > 500:
                content = content[:500] + "..."
            lines.append(f"{role}: {content}")

    lines.append("=== END SESSION CONTEXT ===")
    lines.append("Continue from where we left off. Do not re-introduce yourself.")

    return "\n".join(lines)
