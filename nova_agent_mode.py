"""NovaX Autonomous Agent Mode -- goal-driven task execution
Port 9944 -- breaks goals into subtasks, assigns models, self-corrects.
"""
import http.server, json, os, time, threading, uuid, urllib.request, traceback

PORT = 9944
DATA_DIR = "C:\\NovaX\\data\\goals"
CLOUD_ROUTER = "http://127.0.0.1:9878/api/v1/query"
MAX_CONCURRENT_GOALS = 2
MAX_SUBTASK_ATTEMPTS = 3

os.makedirs(DATA_DIR, exist_ok=True)

start_time = time.time()
goals_lock = threading.Lock()
goals = {}  # id -> goal dict
active_workers = {}  # goal_id -> threading.Event (pause signal)
worker_count_lock = threading.Lock()
running_count = 0


# --- Persistence ---

def goal_path(goal_id):
    return os.path.join(DATA_DIR, goal_id + ".json")


def save_goal(goal):
    goal["updated"] = time.time()
    path = goal_path(goal["id"])
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(goal, f, indent=2)
    os.replace(tmp, path)


def load_goals():
    """Load all goals from disk on startup."""
    if not os.path.isdir(DATA_DIR):
        return
    for fname in os.listdir(DATA_DIR):
        if not fname.endswith(".json"):
            continue
        try:
            with open(os.path.join(DATA_DIR, fname), "r", encoding="utf-8") as f:
                g = json.load(f)
            # Reset any active goals to paused (crash recovery)
            if g.get("status") == "active":
                g["status"] = "paused"
                save_goal(g)
            goals[g["id"]] = g
        except Exception:
            pass


def cloud_query(prompt, model=None):
    """Send a prompt to Cloud Router and return the response text."""
    payload = {"prompt": prompt}
    if model:
        payload["model"] = model
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        CLOUD_ROUTER,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        # Cloud Router returns response in various fields
        return body.get("response") or body.get("text") or body.get("content") or str(body)
    except Exception as e:
        return None


# --- Goal Decomposition ---

DECOMPOSE_PROMPT = """You are a task decomposition engine. Break the following goal into 3-7 concrete subtasks.
Each subtask must be self-contained and actionable.
Return ONLY a JSON array of objects with fields: "description" (string), "dependencies" (array of 0-based subtask indices this depends on).
No markdown, no explanation, just the JSON array.

Goal: {goal}"""


def decompose_goal(description):
    """Use Cloud Router to break a goal into subtasks."""
    prompt = DECOMPOSE_PROMPT.replace("{goal}", description)
    raw = cloud_query(prompt)
    if not raw:
        # Fallback: single subtask
        return [{"description": description, "dependencies": []}]
    # Extract JSON array from response
    try:
        # Try to find JSON array in response
        start = raw.find("[")
        end = raw.rfind("]") + 1
        if start >= 0 and end > start:
            items = json.loads(raw[start:end])
            if isinstance(items, list) and len(items) >= 1:
                return items
    except Exception:
        pass
    # Fallback
    return [{"description": description, "dependencies": []}]


def build_subtasks(decomposed):
    """Convert decomposed items into subtask dicts."""
    subtasks = []
    for i, item in enumerate(decomposed):
        deps = item.get("dependencies", [])
        # Validate dependency indices
        valid_deps = [d for d in deps if isinstance(d, int) and 0 <= d < len(decomposed) and d != i]
        subtasks.append({
            "id": i,
            "description": item.get("description", "subtask %d" % i),
            "status": "pending",
            "assigned_model": None,
            "attempts": 0,
            "max_attempts": MAX_SUBTASK_ATTEMPTS,
            "result": None,
            "dependencies": valid_deps
        })
    return subtasks


# --- Execution Engine ---

MODELS_FALLBACK = [None, "openai/gpt-4o-mini", "mistral"]


def execute_subtask(subtask, goal):
    """Execute a single subtask, retrying with different models on failure."""
    context_parts = []
    # Gather results from dependencies
    for dep_id in subtask["dependencies"]:
        for st in goal["subtasks"]:
            if st["id"] == dep_id and st["result"]:
                context_parts.append("Previous result for '%s': %s" % (st["description"], st["result"][:2000]))

    context = "\n\n".join(context_parts)
    prompt = subtask["description"]
    if context:
        prompt = "Context from previous steps:\n%s\n\nTask: %s" % (context, prompt)
    prompt += "\n\nProvide a thorough, complete response."

    for attempt_idx in range(subtask["max_attempts"]):
        model = MODELS_FALLBACK[attempt_idx % len(MODELS_FALLBACK)]
        subtask["attempts"] = attempt_idx + 1
        subtask["assigned_model"] = model or "default"
        subtask["status"] = "running"
        save_goal(goal)

        result = cloud_query(prompt, model=model)
        if result and len(result.strip()) > 5:
            subtask["status"] = "completed"
            subtask["result"] = result
            save_goal(goal)
            return True
        time.sleep(2)

    subtask["status"] = "failed"
    subtask["result"] = "Failed after %d attempts" % subtask["max_attempts"]
    save_goal(goal)
    return False


SYNTHESIZE_PROMPT = """You are a synthesis engine. Combine the following subtask results into a coherent final result for the goal.

Goal: {goal}

Subtask results:
{results}

Provide a well-structured, comprehensive final result."""


def synthesize_results(goal):
    """Combine all subtask results into a final answer."""
    parts = []
    for st in goal["subtasks"]:
        if st["result"] and st["status"] == "completed":
            parts.append("## %s\n%s" % (st["description"], st["result"][:3000]))
    if not parts:
        return "No subtask results available."
    results_text = "\n\n".join(parts)
    prompt = SYNTHESIZE_PROMPT.replace("{goal}", goal["description"]).replace("{results}", results_text)
    result = cloud_query(prompt)
    return result or results_text


def get_ready_subtasks(goal):
    """Find subtasks whose dependencies are all completed."""
    ready = []
    for st in goal["subtasks"]:
        if st["status"] != "pending":
            continue
        deps_met = True
        for dep_id in st["dependencies"]:
            for other in goal["subtasks"]:
                if other["id"] == dep_id and other["status"] != "completed":
                    deps_met = False
                    break
            if not deps_met:
                break
        if deps_met:
            ready.append(st)
    return ready


def goal_worker(goal_id):
    """Main worker loop for executing a goal."""
    global running_count
    pause_event = active_workers.get(goal_id)
    goal = goals.get(goal_id)
    if not goal:
        return

    try:
        goal["status"] = "active"
        save_goal(goal)

        while True:
            # Check pause
            if pause_event and pause_event.is_set():
                goal["status"] = "paused"
                save_goal(goal)
                return

            ready = get_ready_subtasks(goal)
            if not ready:
                # Check if all done or some failed
                all_done = all(st["status"] in ("completed", "failed") for st in goal["subtasks"])
                if all_done:
                    break
                # No ready tasks but not all done -- deadlock or waiting
                time.sleep(1)
                continue

            # Execute ready subtasks in parallel (up to 3 at a time)
            threads = []
            batch = ready[:3]
            for st in batch:
                t = threading.Thread(target=execute_subtask, args=(st, goal), daemon=True)
                t.start()
                threads.append(t)

            for t in threads:
                t.join(timeout=300)

            # Check pause again after batch
            if pause_event and pause_event.is_set():
                goal["status"] = "paused"
                save_goal(goal)
                return

        # All subtasks processed -- synthesize
        failed_count = sum(1 for st in goal["subtasks"] if st["status"] == "failed")
        completed_count = sum(1 for st in goal["subtasks"] if st["status"] == "completed")

        if completed_count == 0:
            goal["status"] = "failed"
            goal["result"] = "All subtasks failed."
        else:
            goal["result"] = synthesize_results(goal)
            goal["status"] = "completed" if failed_count == 0 else "completed"
        save_goal(goal)

    except Exception as e:
        goal["status"] = "failed"
        goal["result"] = "Worker error: %s" % str(e)
        save_goal(goal)
    finally:
        with worker_count_lock:
            running_count -= 1
        active_workers.pop(goal_id, None)


def start_goal(goal_id):
    """Start executing a goal in a background thread."""
    global running_count
    with worker_count_lock:
        if running_count >= MAX_CONCURRENT_GOALS:
            return False, "Max concurrent goals (%d) reached" % MAX_CONCURRENT_GOALS
        running_count += 1

    pause_event = threading.Event()
    active_workers[goal_id] = pause_event
    t = threading.Thread(target=goal_worker, args=(goal_id,), daemon=True)
    t.start()
    return True, "started"


# --- HTTP Handler ---

class AgentHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json_response(self, code, data):
        self.send_response(code)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data, default=str).encode("utf-8"))

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return {}

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?")[0].rstrip("/")

        if path == "/health":
            self._json_response(200, {
                "status": "ok",
                "trit": 1,
                "service": "nova_agent_mode",
                "port": PORT,
                "goals_total": len(goals),
                "goals_running": running_count,
                "uptime": int(time.time() - start_time)
            })

        elif path == "/agent/goals":
            with goals_lock:
                summary = []
                for g in goals.values():
                    summary.append({
                        "id": g["id"],
                        "description": g["description"][:200],
                        "status": g["status"],
                        "subtask_count": len(g.get("subtasks", [])),
                        "created": g.get("created"),
                        "updated": g.get("updated")
                    })
            self._json_response(200, {"goals": summary})

        elif path.startswith("/agent/goal/"):
            goal_id = path.split("/agent/goal/")[1]
            with goals_lock:
                goal = goals.get(goal_id)
            if goal:
                self._json_response(200, goal)
            else:
                self._json_response(404, {"error": "Goal not found"})

        elif path == "/agent/running":
            with goals_lock:
                running = [g for g in goals.values() if g["status"] == "active"]
            self._json_response(200, {"running": running, "count": len(running)})

        else:
            self._json_response(404, {"error": "Not found"})

    def do_POST(self):
        path = self.path.split("?")[0].rstrip("/")
        body = self._read_body()

        if path == "/agent/goal":
            desc = body.get("description", "").strip()
            if not desc:
                self._json_response(400, {"error": "description required"})
                return

            goal_id = str(uuid.uuid4())[:12]
            # Decompose into subtasks
            decomposed = decompose_goal(desc)
            subtasks = build_subtasks(decomposed)

            goal = {
                "id": goal_id,
                "description": desc,
                "status": "pending",
                "subtasks": subtasks,
                "created": time.time(),
                "updated": time.time(),
                "result": None
            }
            with goals_lock:
                goals[goal_id] = goal
            save_goal(goal)
            self._json_response(201, goal)

        elif path.startswith("/agent/goal/") and path.endswith("/start"):
            goal_id = path.split("/agent/goal/")[1].replace("/start", "")
            with goals_lock:
                goal = goals.get(goal_id)
            if not goal:
                self._json_response(404, {"error": "Goal not found"})
                return
            if goal["status"] == "active":
                self._json_response(409, {"error": "Goal already running"})
                return
            if goal["status"] == "completed":
                self._json_response(409, {"error": "Goal already completed"})
                return

            ok, msg = start_goal(goal_id)
            if ok:
                self._json_response(200, {"status": "started", "goal_id": goal_id})
            else:
                self._json_response(429, {"error": msg})

        elif path.startswith("/agent/goal/") and path.endswith("/pause"):
            goal_id = path.split("/agent/goal/")[1].replace("/pause", "")
            evt = active_workers.get(goal_id)
            if evt:
                evt.set()  # Signal pause
                self._json_response(200, {"status": "pausing", "goal_id": goal_id})
            else:
                self._json_response(404, {"error": "Goal not actively running"})

        elif path.startswith("/agent/goal/") and path.endswith("/resume"):
            goal_id = path.split("/agent/goal/")[1].replace("/resume", "")
            with goals_lock:
                goal = goals.get(goal_id)
            if not goal:
                self._json_response(404, {"error": "Goal not found"})
                return
            if goal["status"] != "paused":
                self._json_response(409, {"error": "Goal is not paused, status: %s" % goal["status"]})
                return

            # Reset pending subtasks and restart
            ok, msg = start_goal(goal_id)
            if ok:
                self._json_response(200, {"status": "resumed", "goal_id": goal_id})
            else:
                self._json_response(429, {"error": msg})

        else:
            self._json_response(404, {"error": "Not found"})

    def do_DELETE(self):
        path = self.path.split("?")[0].rstrip("/")

        if path.startswith("/agent/goal/"):
            goal_id = path.split("/agent/goal/")[1]
            # Signal pause if running
            evt = active_workers.get(goal_id)
            if evt:
                evt.set()
            with goals_lock:
                goal = goals.pop(goal_id, None)
            if goal:
                # Remove file
                try:
                    os.remove(goal_path(goal_id))
                except Exception:
                    pass
                self._json_response(200, {"status": "deleted", "goal_id": goal_id})
            else:
                self._json_response(404, {"error": "Goal not found"})
        else:
            self._json_response(404, {"error": "Not found"})


# --- Main ---

def main():
    load_goals()
    print("[AgentMode] Loaded %d goals from disk" % len(goals))
    server = http.server.HTTPServer(("0.0.0.0", PORT), AgentHandler)
    print("[AgentMode] Running on port %d" % PORT)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("[AgentMode] Shutting down")
        server.server_close()


if __name__ == "__main__":
    main()
