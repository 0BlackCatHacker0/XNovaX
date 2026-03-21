# TernaryFlask Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a ternary-native HTTP server framework inside NovaLang so every NovaX service can be written as a `.nova` script with 3-state responses, chunked streaming, and TSpeak integration.

**Architecture:** TFlaskRuntime class + TFlaskHandler class live inside `novalang.py`. Seven builtins (`tserve`, `troute`, `tstart`, `tpartial`, `tresolve`, `treject`, `tstatus`) expose the runtime to NovaLang scripts. Services become `.nova` files. The runtime uses `ThreadingMixIn + HTTPServer` under the hood. Every response carries `X-Ternary-State` and `X-TSpeak-Frame` headers.

**Tech Stack:** Python 3 stdlib (`http.server`, `socketserver.ThreadingMixIn`, `json`, `threading`), NovaLang interpreter, TSpeak protocol (port 9895)

---

### Task 1: TFlaskRuntime Core Class

**Files:**
- Modify: `C:\NovaX\novalang.py:1392` (insert before `# ── End Strategy Builtins`)

**Step 1: Write test script**

Create `C:\NovaX\tests\test_tflask_core.nova`:
```
// Test: tserve creates a server handle, troute registers a route
let srv = tserve(19891, "Test Server")
print(type(srv))

fn test_health() {
    return {"ok": true, "test": "passed"}
}

troute(srv, "GET", "/health", "test_health")
let st = tstatus(srv)
print(st.get("name"))
print(st.get("routes"))
```

**Step 2: Run test to verify it fails**

Run: `python C:\NovaX\novalang.py C:\NovaX\tests\test_tflask_core.nova`
Expected: FAIL — `tserve` is not defined

**Step 3: Implement TFlaskRuntime + TFlaskHandler + 4 builtins (tserve, troute, tstatus, tstart)**

Insert the following in `C:\NovaX\novalang.py` at line 1392, BEFORE `# ── End Strategy Builtins`:

```python
    # ── TernaryFlask Runtime (3-5-7-13) ──────────────────────
    # 3 states (+1/0/-1), 5 hooks, 7 builtins, 13-byte TSpeak header
    # The server IS the language — Python is just the engine.

    _tflask_servers = {}   # port -> TFlaskRuntime instance
    _tflask_current_handler = None  # thread-local: active handler for tpartial/tresolve/treject

    def _tserve(self, port, name="TFlask"):
        """Create a ternary-native threaded HTTP server. tserve(port, name) -> server handle"""
        port = int(port)
        runtime = {
            "port": port,
            "name": str(name),
            "routes": {},       # {("GET", "/path"): "handler_fn_name"}
            "hooks": {},        # {"pre_route": ["fn1", "fn2"], ...}
            "stats": {"requests": 0, "ternary": {1: 0, 0: 0, -1: 0}, "start_time": None},
            "interpreter": self,
            "_server": None,
        }
        self._tflask_servers[port] = runtime
        return runtime

    def _troute(self, server, method, path, handler_name):
        """Register a NovaLang function as a route handler. troute(server, method, path, fn_name)"""
        if not isinstance(server, dict) or "routes" not in server:
            return {"error": "Invalid server handle — use tserve() first"}
        key = (str(method).upper(), str(path))
        server["routes"][key] = str(handler_name)

    def _thook(self, server, hook_name, fn_name):
        """Register a middleware hook. thook(server, hook_name, fn_name)"""
        valid_hooks = ("pre_route", "pre_handler", "post_handler", "on_error", "on_stream")
        hook_name = str(hook_name)
        if hook_name not in valid_hooks:
            return {"error": f"Invalid hook: {hook_name}. Valid: {valid_hooks}"}
        if hook_name not in server["hooks"]:
            server["hooks"][hook_name] = []
        server["hooks"][hook_name].append(str(fn_name))

    def _tstart(self, server):
        """Start the ternary server. Blocks. tstart(server)"""
        import time as _time
        from http.server import HTTPServer, BaseHTTPRequestHandler
        from socketserver import ThreadingMixIn

        port = server["port"]
        name = server["name"]
        interpreter = server["interpreter"]
        routes = server["routes"]
        hooks = server["hooks"]
        stats = server["stats"]

        def _run_hooks(hook_name, context):
            """Run all registered hooks for a given hook point."""
            for fn_name in hooks.get(hook_name, []):
                fn = interpreter.globals.get(fn_name)
                if fn and isinstance(fn, tuple) and fn[0] == 'fn':
                    _, params, body = fn
                    local_env = Environment(interpreter.globals)
                    if params:
                        local_env.set(params[0], context)
                    for bl in body:
                        bl = bl.strip()
                        if bl.startswith('return '):
                            result = interpreter._eval(bl[7:], local_env)
                            if result is False:
                                return False  # hook rejected
                            break
                        interpreter._exec_line(bl, local_env)
                elif callable(fn):
                    result = fn(context)
                    if result is False:
                        return False
            return True

        def _call_handler(fn_name, body):
            """Call a NovaLang function by name with body arg. Returns result dict."""
            fn = interpreter.globals.get(fn_name)
            if fn is None:
                return {"error": f"Handler '{fn_name}' not found"}
            if isinstance(fn, tuple) and fn[0] == 'fn':
                _, params, fn_body = fn
                local_env = Environment(interpreter.globals)
                if params:
                    local_env.set(params[0], body)
                result = None
                for bl in fn_body:
                    bl = bl.strip()
                    if bl.startswith('return '):
                        return interpreter._eval(bl[7:], local_env)
                    interpreter._exec_line(bl, local_env)
                return result
            elif callable(fn):
                return fn(body)
            return {"error": f"Handler '{fn_name}' is not callable"}

        class TFlaskHandler(BaseHTTPRequestHandler):
            def log_message(self, fmt, *args):
                pass  # suppress default logging

            def _ternary_response(self, data, ternary_state=1, code=200):
                """Send JSON response with ternary headers."""
                body_bytes = json.dumps(data, default=str).encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "*")
                self.send_header("X-Ternary-State", str(ternary_state))
                self.send_header("X-TFlask-Server", name)
                # TSpeak frame header (13 bytes placeholder — real encoding when TSpeak is live)
                self.send_header("X-TSpeak-Frame", "0" * 13)
                self.send_header("Content-Length", str(len(body_bytes)))
                self.end_headers()
                self.wfile.write(body_bytes)

            def _start_chunked(self, ternary_state=0):
                """Begin chunked transfer for streaming responses."""
                self.send_response(200)
                self.send_header("Content-Type", "application/x-ndjson")
                self.send_header("Transfer-Encoding", "chunked")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "*")
                self.send_header("X-Ternary-State", str(ternary_state))
                self.send_header("X-TFlask-Server", name)
                self.send_header("X-TSpeak-Frame", "0" * 13)
                self.end_headers()
                self._chunked_started = True

            def _send_chunk(self, data, ternary_state=0):
                """Send one JSON line as a chunked transfer chunk."""
                if isinstance(data, dict):
                    data["ternary"] = ternary_state
                line = json.dumps(data, default=str) + "\n"
                chunk = line.encode("utf-8")
                self.wfile.write(f"{len(chunk):x}\r\n".encode())
                self.wfile.write(chunk)
                self.wfile.write(b"\r\n")
                self.wfile.flush()

            def _end_chunked(self):
                """Send final zero-length chunk to end transfer."""
                self.wfile.write(b"0\r\n\r\n")
                self.wfile.flush()

            def _handle(self, method):
                """Core request handler — routes to NovaLang functions."""
                stats["requests"] += 1
                path = self.path.split("?")[0].rstrip("/")

                # Parse query params for GET
                query_params = {}
                if "?" in self.path:
                    qs = self.path.split("?", 1)[1]
                    for pair in qs.split("&"):
                        if "=" in pair:
                            k, v = pair.split("=", 1)
                            query_params[k] = urllib.parse.unquote(v)

                # Read POST body
                body = query_params
                if method == "POST":
                    try:
                        length = int(self.headers.get("Content-Length", 0))
                        raw = self.rfile.read(length) if length > 0 else b"{}"
                        body = json.loads(raw)
                    except Exception:
                        body = {}

                # Run pre_route hooks
                context = {"method": method, "path": path, "body": body}
                if not _run_hooks("pre_route", context):
                    stats["ternary"][-1] += 1
                    self._ternary_response({"error": "Rejected by pre_route hook"}, -1, 403)
                    return

                # Route lookup
                route_key = (method, path)
                fn_name = routes.get(route_key)
                if fn_name is None:
                    # Try wildcard: ("POST", "/tools/*") pattern
                    for rk, rv in routes.items():
                        if rk[0] == method and rk[1].endswith("/*"):
                            prefix = rk[1][:-2]
                            if path.startswith(prefix):
                                fn_name = rv
                                body["_path_suffix"] = path[len(prefix):]
                                break
                if fn_name is None:
                    stats["ternary"][-1] += 1
                    self._ternary_response({"error": f"No route: {method} {path}",
                                            "routes": [f"{k[0]} {k[1]}" for k in routes]}, -1, 404)
                    return

                # Run pre_handler hooks
                if not _run_hooks("pre_handler", context):
                    stats["ternary"][-1] += 1
                    self._ternary_response({"error": "Rejected by pre_handler hook"}, -1, 403)
                    return

                # Store handler ref for tpartial/tresolve/treject
                self._chunked_started = False
                interpreter._tflask_current_handler = self

                # Call handler
                try:
                    result = _call_handler(fn_name, body)
                    # Run post_handler hooks
                    _run_hooks("post_handler", {"result": result, "path": path})

                    if self._chunked_started:
                        # Handler used streaming — send final resolve chunk
                        self._send_chunk({"result": result} if result else {"done": True}, 1)
                        self._end_chunked()
                        stats["ternary"][1] += 1
                    else:
                        # Simple handler — auto-wrap as +1
                        stats["ternary"][1] += 1
                        self._ternary_response(result if result else {"ok": True}, 1)
                except Exception as e:
                    import traceback as _tb
                    err = {"error": str(e), "traceback": _tb.format_exc()}
                    # Run on_error hooks
                    _run_hooks("on_error", err)
                    stats["ternary"][-1] += 1
                    if self._chunked_started:
                        self._send_chunk(err, -1)
                        self._end_chunked()
                    else:
                        self._ternary_response(err, -1, 500)
                finally:
                    interpreter._tflask_current_handler = None

            def do_GET(self):
                self._handle("GET")

            def do_POST(self):
                self._handle("POST")

            def do_OPTIONS(self):
                self.send_response(204)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "*")
                self.end_headers()

        class ThreadedTFlask(ThreadingMixIn, HTTPServer):
            daemon_threads = True

        stats["start_time"] = _time.time()
        server["_server"] = ThreadedTFlask(("0.0.0.0", port), TFlaskHandler)
        print(f"[TFlask] {name} ternary server on port {port}")
        print(f"[TFlask] {len(routes)} routes, {sum(len(v) for v in hooks.values())} hooks")
        print(f"[TFlask] 3-state lifecycle active | ThreadingMixIn enabled")
        try:
            server["_server"].serve_forever()
        except KeyboardInterrupt:
            server["_server"].shutdown()

    def _tpartial(self, data):
        """Send a partial/streaming chunk with ternary state 0. tpartial(data)"""
        handler = self._tflask_current_handler
        if handler is None:
            return {"error": "tpartial() can only be called inside a TFlask handler"}
        if not handler._chunked_started:
            handler._start_chunked(0)
        handler._send_chunk(data if isinstance(data, dict) else {"partial": data}, 0)
        # Run on_stream hooks
        server = None
        for s in self._tflask_servers.values():
            if s.get("interpreter") is self:
                server = s
                break
        if server:
            for fn_name in server.get("hooks", {}).get("on_stream", []):
                fn = self.globals.get(fn_name)
                if callable(fn):
                    fn(data)

    def _tresolve(self, data):
        """Send final result with ternary state +1. tresolve(data)"""
        handler = self._tflask_current_handler
        if handler is None:
            return {"error": "tresolve() can only be called inside a TFlask handler"}
        if not handler._chunked_started:
            handler._start_chunked(0)
        handler._send_chunk(data if isinstance(data, dict) else {"result": data}, 1)
        handler._end_chunked()

    def _treject(self, reason="rejected"):
        """Reject request with ternary state -1. treject(reason)"""
        handler = self._tflask_current_handler
        if handler is None:
            return {"error": "treject() can only be called inside a TFlask handler"}
        if handler._chunked_started:
            handler._send_chunk({"error": str(reason)}, -1)
            handler._end_chunked()
        else:
            handler._ternary_response({"error": str(reason)}, -1, 400)

    def _tstatus(self, server=None):
        """Get TFlask server stats. tstatus(server?)"""
        if server and isinstance(server, dict):
            import time as _time
            uptime = _time.time() - server["stats"]["start_time"] if server["stats"]["start_time"] else 0
            return {
                "name": server["name"],
                "port": server["port"],
                "routes": len(server["routes"]),
                "hooks": {k: len(v) for k, v in server["hooks"].items()},
                "requests": server["stats"]["requests"],
                "ternary_distribution": server["stats"]["ternary"],
                "uptime": round(uptime, 1),
            }
        # Return all servers
        return {p: {"name": s["name"], "routes": len(s["routes"]),
                     "requests": s["stats"]["requests"]}
                for p, s in self._tflask_servers.items()}
```

**Step 4: Register the 7+1 builtins**

In `_setup_builtins()` (after line 710, after TSpeak builtins), add:

```python
        # TernaryFlask builtins (7 server + 1 hook = the ternary server framework)
        g.set('tserve', self._tserve)
        g.set('troute', self._troute)
        g.set('tstart', self._tstart)
        g.set('tpartial', self._tpartial)
        g.set('tresolve', self._tresolve)
        g.set('treject', self._treject)
        g.set('tstatus', self._tstatus)
        g.set('thook', self._thook)
```

**Step 5: Run test to verify it passes**

Run: `python C:\NovaX\novalang.py C:\NovaX\tests\test_tflask_core.nova`
Expected: Output includes `dict`, `Test Server`, `1` (1 route registered)

**Step 6: Syntax check**

Run: `python -c "import py_compile; py_compile.compile(r'C:\NovaX\novalang.py', doraise=True)"`
Expected: No errors

---

### Task 2: Live Server Test

**Files:**
- Create: `C:\NovaX\tests\test_tflask_server.nova`

**Step 1: Write a minimal TFlask server script**

Create `C:\NovaX\tests\test_tflask_server.nova`:
```
// Minimal TFlask server — tests tserve + troute + tstart
let server = tserve(19891, "TFlask Test")

fn health() {
    return {"ok": true, "service": "tflask-test", "ternary": true}
}

fn echo(body) {
    return {"echo": body, "ternary_state": 1}
}

troute(server, "GET", "/health", "health")
troute(server, "POST", "/echo", "echo")
tstart(server)
```

**Step 2: Start the test server in background**

Run: `python C:\NovaX\novalang.py C:\NovaX\tests\test_tflask_server.nova &`
Expected: `[TFlask] TFlask Test ternary server on port 19891`

**Step 3: Test GET /health with ternary headers**

Run: `curl -s -v http://localhost:19891/health 2>&1 | grep -E "X-Ternary|X-TFlask|X-TSpeak|ok"`
Expected:
```
< X-Ternary-State: 1
< X-TFlask-Server: TFlask Test
< X-TSpeak-Frame: 0000000000000
{"ok": true, "service": "tflask-test", "ternary": true}
```

**Step 4: Test POST /echo**

Run: `curl -s -X POST http://localhost:19891/echo -H "Content-Type: application/json" -d '{"hello":"world"}' 2>&1`
Expected: `{"echo": {"hello": "world"}, "ternary_state": 1}`

**Step 5: Test 404 route with ternary -1 state**

Run: `curl -s -v http://localhost:19891/nonexistent 2>&1 | grep -E "X-Ternary|error"`
Expected:
```
< X-Ternary-State: -1
{"error": "No route: GET /nonexistent", ...}
```

**Step 6: Kill test server**

Run: `taskkill //F //FI "WINDOWTITLE eq *19891*"` or kill the background process

---

### Task 3: Streaming (tpartial / tresolve / treject)

**Files:**
- Create: `C:\NovaX\tests\test_tflask_stream.nova`

**Step 1: Write streaming test server**

Create `C:\NovaX\tests\test_tflask_stream.nova`:
```
// Test streaming: tpartial sends chunks, tresolve sends final
let server = tserve(19892, "TFlask Stream Test")

fn health() {
    return {"ok": true}
}

fn stream_test(body) {
    tpartial({"step": 1, "msg": "Starting..."})
    tpartial({"step": 2, "msg": "Processing..."})
    tpartial({"step": 3, "msg": "Almost done..."})
    return {"final": "complete", "steps": 3}
}

fn reject_test(body) {
    treject("Not allowed")
}

troute(server, "GET", "/health", "health")
troute(server, "POST", "/stream", "stream_test")
troute(server, "POST", "/reject", "reject_test")
tstart(server)
```

**Step 2: Start server and test streaming**

Run: `python C:\NovaX\novalang.py C:\NovaX\tests\test_tflask_stream.nova &`
Then: `curl -s -N -X POST http://localhost:19892/stream -H "Content-Type: application/json" -d '{}'`

Expected (4 JSON lines — 3 partials + 1 resolve):
```
{"step": 1, "msg": "Starting...", "ternary": 0}
{"step": 2, "msg": "Processing...", "ternary": 0}
{"step": 3, "msg": "Almost done...", "ternary": 0}
{"result": {"final": "complete", "steps": 3}, "ternary": 1}
```

**Step 3: Test reject**

Run: `curl -s -v -X POST http://localhost:19892/reject -H "Content-Type: application/json" -d '{}' 2>&1 | grep -E "X-Ternary|error"`
Expected:
```
< X-Ternary-State: -1
{"error": "Not allowed"}
```

**Step 4: Kill test server**

---

### Task 4: Middleware Hooks

**Files:**
- Create: `C:\NovaX\tests\test_tflask_hooks.nova`

**Step 1: Write hook test server**

Create `C:\NovaX\tests\test_tflask_hooks.nova`:
```
// Test middleware hooks: pre_route, pre_handler, on_error
let server = tserve(19893, "TFlask Hook Test")
let hook_log = []

fn log_pre_route(ctx) {
    print(f"pre_route: {ctx.get(\"path\")}")
    return true
}

fn log_pre_handler(ctx) {
    print(f"pre_handler: {ctx.get(\"path\")}")
    return true
}

fn health() {
    return {"ok": true, "hooks": "active"}
}

fn crash_test(body) {
    // This will error — division by zero
    let x = 1 / 0
    return {"never": "reached"}
}

thook(server, "pre_route", "log_pre_route")
thook(server, "pre_handler", "log_pre_handler")
troute(server, "GET", "/health", "health")
troute(server, "POST", "/crash", "crash_test")
tstart(server)
```

**Step 2: Start server, test hooks fire**

Run: `python C:\NovaX\novalang.py C:\NovaX\tests\test_tflask_hooks.nova &`
Then: `curl -s http://localhost:19893/health`
Expected: `{"ok": true, "hooks": "active"}` and server stdout shows `pre_route: /health` and `pre_handler: /health`

**Step 3: Test on_error hook**

Run: `curl -s -X POST http://localhost:19893/crash -H "Content-Type: application/json" -d '{}' 2>&1`
Expected: JSON with `"error"` field and `X-Ternary-State: -1`

**Step 4: Kill test server**

---

### Task 5: First Service Migration — nova_tools.nova

**Files:**
- Create: `C:\NovaX\nova_tools_tflask.nova` (parallel to existing Python nova_tools.py)

**Step 1: Write the nova_tools TFlask service**

Create `C:\NovaX\nova_tools_tflask.nova`:
```
// Nova Tools — TernaryFlask edition
// Replaces nova_tools.py (port 9891) with pure NovaLang
// 7 tools: read, write, grep, glob, run, edit, pipe

let server = tserve(19891, "Nova Tools TFlask")

fn health() {
    return {"ok": true, "service": "nova-tools-tflask", "tools": 7, "ternary": true}
}

fn status() {
    let st = nova_tools_status()
    return st
}

fn tool_read(body) {
    let path = body.get("path")
    return nova_read(path)
}

fn tool_write(body) {
    let path = body.get("path")
    let content = body.get("content")
    return nova_write(path, content)
}

fn tool_grep(body) {
    let pattern = body.get("pattern")
    let path = body.get("path")
    return nova_grep(pattern, path)
}

fn tool_glob(body) {
    let pattern = body.get("pattern")
    let path = body.get("path")
    return nova_glob(pattern, path)
}

fn tool_run(body) {
    let command = body.get("command")
    return nova_run(command)
}

fn tool_edit(body) {
    let path = body.get("path")
    let old = body.get("old_string")
    let new_str = body.get("new_string")
    return nova_edit(path, old, new_str)
}

fn tool_pipe(body) {
    let steps = body.get("steps")
    return nova_pipe(steps)
}

troute(server, "GET", "/health", "health")
troute(server, "GET", "/tools/status", "status")
troute(server, "POST", "/tools/read", "tool_read")
troute(server, "POST", "/tools/write", "tool_write")
troute(server, "POST", "/tools/grep", "tool_grep")
troute(server, "POST", "/tools/glob", "tool_glob")
troute(server, "POST", "/tools/run", "tool_run")
troute(server, "POST", "/tools/edit", "tool_edit")
troute(server, "POST", "/tools/pipe", "tool_pipe")
tstart(server)
```

**Step 2: Start on test port and verify side-by-side**

Run: `python C:\NovaX\novalang.py C:\NovaX\nova_tools_tflask.nova &`

**Step 3: Compare outputs — Python vs TFlask**

Run both:
```bash
curl -s http://localhost:9891/health
curl -s http://localhost:19891/health
```
Expected: Both return `{"ok": true, "service": "nova-tools..."}` — TFlask version has `X-Ternary-State: 1` header.

Run:
```bash
curl -s -X POST http://localhost:9891/tools/read -H "Content-Type: application/json" -d '{"path":"C:\\NovaX\\novalang.py"}' | python -c "import sys,json; print(len(json.load(sys.stdin).get('content','')))"
curl -s -X POST http://localhost:19891/tools/read -H "Content-Type: application/json" -d '{"path":"C:\\NovaX\\novalang.py"}' | python -c "import sys,json; print(len(json.load(sys.stdin).get('content','')))"
```
Expected: Both return the same content length.

**Step 4: Verify ternary headers on TFlask version**

Run: `curl -s -v http://localhost:19891/health 2>&1 | grep "X-Ternary"`
Expected: `< X-Ternary-State: 1`

**Step 5: Kill test server**

---

### Task 6: Desktop Panel + launch.json

**Files:**
- Modify: `C:\NovaX\web\nova_desktop.html` (add TFlask panel)
- Modify: `C:\NovaX\.claude\launch.json` (add nova-tools-tflask entry)

**Step 1: Add TFlask panel to PANELS array**

In `nova_desktop.html`, find the PANELS array and add:
```javascript
{id:'tflask',icon:'\u{2697}',name:'TFlask',color:'#ff6b35'}
```

**Step 2: Add dispatch entry**

In the dispatch map, add:
```javascript
tflask:loadTFlask
```

**Step 3: Add loadTFlask function**

Before `</script>`, add:
```javascript
async function loadTFlask(){
  const el=panelEl('tflask');
  el.innerHTML='<h2 style="color:#ff6b35">\u{2697}\uFE0F TernaryFlask</h2><p>Loading...</p>';
  try{
    // Query all known TFlask servers for status
    const ports=[19891];
    let html='<h2 style="color:#ff6b35">\u{2697}\uFE0F TernaryFlask Runtime</h2>';
    html+='<div style="display:grid;gap:8px">';
    for(const p of ports){
      try{
        const r=await fetch('http://localhost:'+p+'/health');
        const h=r.headers;
        const d=await r.json();
        const ts=h.get('X-Ternary-State')||'?';
        html+='<div class="card" style="border-left:3px solid #ff6b35;padding:12px">';
        html+='<b>'+d.service+'</b> :'+p;
        html+=' <span style="color:'+(ts==='1'?'#30d158':'#ff453a')+'">T:'+ts+'</span>';
        html+='<br><small>'+JSON.stringify(d)+'</small>';
        html+='</div>';
      }catch(e){
        html+='<div class="card" style="border-left:3px solid #ff453a;padding:12px">';
        html+='Port '+p+': offline</div>';
      }
    }
    html+='</div>';
    html+='<div style="margin-top:16px;padding:12px;background:#1a1a2e;border-radius:8px">';
    html+='<b style="color:#ff6b35">3-5-7-13 Harmonics</b><br>';
    html+='<span style="color:#aaa">3 states \u00B7 5 hooks \u00B7 7 builtins \u00B7 13-byte TSpeak</span>';
    html+='</div>';
    el.innerHTML=html;
  }catch(e){el.innerHTML='<p style="color:#ff453a">'+e+'</p>';}
}
```

**Step 4: Add launch.json entry for nova-tools-tflask**

In `C:\NovaX\.claude\launch.json`, add to configurations array:
```json
{
  "name": "nova-tools-tflask",
  "runtimeExecutable": "python",
  "runtimeArgs": ["C:\\NovaX\\novalang.py", "C:\\NovaX\\nova_tools_tflask.nova"],
  "port": 19891
}
```

**Step 5: Verify panel renders**

Start server, open desktop, click TFlask panel. Should show server name, port, ternary state, health data.

---

### Task 7: Wire into Orchestrator

**Files:**
- Modify: `C:\NovaX\core\orchestrator.py` (add TFlask proxy routes)

**Step 1: Find existing proxy pattern**

Read `orchestrator.py` and find where `/api/tools/*` routes are proxied.

**Step 2: Add TFlask status route**

Add a new Flask route:
```python
@app.get("/api/tflask/status")
def tflask_status():
    return _proxy_get("http://localhost:19891/health")
```

**Step 3: Verify through orchestrator**

Run: `curl -s http://localhost:9999/api/tflask/status`
Expected: Health response from TFlask nova_tools

---

## Execution Order & Dependencies

```
Task 1 (Core Class)
  |
  v
Task 2 (Live Server Test) -- depends on Task 1
  |
  v
Task 3 (Streaming) -- depends on Task 2
  |
  v
Task 4 (Hooks) -- depends on Task 2
  |
  v
Task 5 (Service Migration) -- depends on Tasks 1-4
  |
  v
Task 6 (Desktop + launch.json) -- depends on Task 5
  |
  v
Task 7 (Orchestrator wiring) -- depends on Task 5
```

Tasks 3 and 4 are independent of each other but both need Task 2.
Tasks 6 and 7 are independent of each other but both need Task 5.

---

## Verification Checklist

1. `tserve(port, name)` creates server handle without crash
2. `troute()` registers handlers, `tstatus()` reports route count
3. `tstart()` binds port with ThreadingMixIn (threaded by default)
4. GET /health returns JSON with `X-Ternary-State: 1` header
5. POST /echo returns body with ternary headers
6. Unknown route returns `X-Ternary-State: -1` with 404
7. `tpartial()` sends chunked JSON lines with `"ternary": 0`
8. `tresolve()` sends final chunk with `"ternary": 1`
9. `treject()` sends error chunk with `"ternary": -1`
10. `thook()` registers middleware, hooks fire in order
11. `on_error` hook catches handler crashes
12. nova_tools_tflask.nova returns identical results to nova_tools.py
13. TFlask version has ternary headers, Python version does not
14. Desktop panel shows TFlask server status
15. Orchestrator proxies to TFlask service

## Files Summary

| File | Action | Est. Lines |
|------|--------|------------|
| `C:\NovaX\novalang.py` | Modify: add TFlaskRuntime + 8 builtins | ~280 |
| `C:\NovaX\tests\test_tflask_core.nova` | Create: unit test | ~10 |
| `C:\NovaX\tests\test_tflask_server.nova` | Create: integration test | ~15 |
| `C:\NovaX\tests\test_tflask_stream.nova` | Create: streaming test | ~20 |
| `C:\NovaX\tests\test_tflask_hooks.nova` | Create: hook test | ~25 |
| `C:\NovaX\nova_tools_tflask.nova` | Create: first service migration | ~60 |
| `C:\NovaX\web\nova_desktop.html` | Modify: add TFlask panel | ~40 |
| `C:\NovaX\.claude\launch.json` | Modify: add entry | ~5 |
| `C:\NovaX\core\orchestrator.py` | Modify: add proxy route | ~10 |
| **Total** | | **~465** |
