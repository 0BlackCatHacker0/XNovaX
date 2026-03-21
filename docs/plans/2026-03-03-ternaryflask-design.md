# TernaryFlask Design — Ternary-Native Server Framework for NovaX

## Vision

Everything ternary. Everything NovaLang. Python/JS/Rust are engines underneath — NovaLang is the language developers write in.

TernaryFlask replaces Python's `http.server` across all 20+ NovaX services with a NovaLang-native server framework. Services become `.nova` scripts. Every response carries ternary state (+1/0/-1) and TSpeak frames. Every problem becomes a tool.

TernaryFlask is the foundation for converting 150+ Linux tools into ternary-native NovaLang builtins — the full NovaX operating system.

---

## Problem

20 out of 26 NovaX services use single-threaded `HTTPServer` with identical boilerplate:
- `_read_body()`, `_json()`, `do_OPTIONS()`, CORS headers — copy-pasted everywhere
- Single-threaded: one blocked request (cluster_query: 60-150s) blocks ALL requests
- No streaming: client sees nothing until full response is ready
- No ternary semantics: responses are binary (200 OK or error)
- Written in Python when NovaLang exists for exactly this purpose

---

## Architecture

### Philosophy
- NovaLang = the language (what developers write)
- Python = the engine (what runs underneath, like V8 is C++ for JavaScript)
- TernaryFlask runtime = Python class inside `novalang.py` — invisible to the developer

### 3-5-7-13 Harmonic Mapping

| Constant | Maps to | Details |
|----------|---------|---------|
| **3** | Ternary states | +1 (accept), 0 (processing), -1 (reject) |
| **5** | Middleware hooks | pre_route, pre_handler, post_handler, on_error, on_stream |
| **7** | Server builtins | tserve, troute, tstart, tpartial, tresolve, treject, tstatus |
| **13** | TSpeak frame header | 13-byte header on every ternary-aware response, 13 belief dimensions |

---

## The 7 Builtins

| Builtin | Signature | Returns | Purpose |
|---------|-----------|---------|---------|
| `tserve` | `tserve(port, name)` | server handle | Create threaded ternary server |
| `troute` | `troute(server, method, path, handler_name)` | void | Register NovaLang fn as route handler |
| `tstart` | `tstart(server)` | blocks | Start serving (ThreadingMixIn + serve_forever) |
| `tpartial` | `tpartial(data)` | void | Send chunked partial with ternary state 0 |
| `tresolve` | `tresolve(data)` | void | Send final result with ternary state +1 |
| `treject` | `treject(reason)` | void | Reject with ternary state -1 |
| `tstatus` | `tstatus(server)` | dict | Server stats, ternary distribution, TSpeak frames |

### The 5 Middleware Hooks

Registered via: `thook(server, hook_name, handler_fn_name)`

| Hook | When | Use case |
|------|------|----------|
| `pre_route` | Before path matching | Auth, rate limiting |
| `pre_handler` | After route match, before handler | Validate body schema |
| `post_handler` | After handler returns | Add TSpeak encoding |
| `on_error` | Handler crashes | Return -1 with traceback |
| `on_stream` | Each tpartial chunk | Compress, add metrics |

---

## Ternary State Lifecycle

```
Request arrives
    |
    v
 [  -1  ] <--- treject(reason) --- [   0   ] --- tresolve(data) ---> [  +1  ]
  REJECT                            PROCESS                           ACCEPT
                                      |
                                      +--- tpartial(data) --- loops back to 0
```

### What the client sees (chunked transfer):

```
HTTP/1.1 200 OK
Transfer-Encoding: chunked
X-Ternary-State: 0
X-TSpeak-Frame: <13 bytes>
Content-Type: application/json

{"ternary": 0, "partial": "Model 1 responded..."}
{"ternary": 0, "partial": "Model 2 responded..."}
{"ternary": 1, "result": {"response": "merged answer", "models": 3}}
```

### Simple handlers (no streaming):

Handler returns a dict -> runtime auto-wraps as ternary +1. Streaming is opt-in.

---

## Service Migration

### Before (Python — 50 lines boilerplate per service):

```python
from http.server import HTTPServer, BaseHTTPRequestHandler
import json

class ToolHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args): pass
    def _json(self, data, code=200):
        body = json.dumps(data, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        # ... 10 more lines of headers ...
    def do_OPTIONS(self): # ... CORS boilerplate ...
    def do_GET(self): # ... path parsing ...
    def do_POST(self): # ... body parsing ...

server = HTTPServer(("0.0.0.0", 9891), ToolHandler)
server.serve_forever()
```

### After (NovaLang — pure logic):

```
let server = tserve(9891, "Nova Tools")

fn health() {
    return {"ok": true, "service": "nova-tools", "tools": 7}
}

fn read_file(body) {
    let path = body.get("path")
    return nova_read(path)
}

troute(server, "GET", "/health", "health")
troute(server, "POST", "/tools/read", "read_file")
tstart(server)
```

### Migration order:
1. Build runtime + 7 builtins in novalang.py
2. Convert nova_tools (simplest, 7 routes) to .nova
3. Verify through orchestrator
4. Roll to next service one at a time
5. Python services keep running until .nova replacement is tested

---

## Hivemind Upgrade

Each TernaryFlask feature directly strengthens the hivemind:

| Feature | Hivemind upgrade |
|---------|-----------------|
| Threading by default | cluster_query no longer blocks health/classify |
| Chunked streaming | Scatter sends each model response as it arrives |
| Ternary state header | Models tagged +1/0/-1, pressure gradient uses directly |
| TSpeak frame on every response | Phase 1.5 DIDT encoding at protocol level |
| 5 middleware hooks | on_stream = live BCI alignment as models respond |
| treject(-1) | Timeout/error models rejected immediately, scatter doesn't wait |
| tpartial(0) | Vortex deliberation streams judge responses real-time |

### Hivemind cluster_query as streaming (after migration):

```
{"ternary": 0, "phase": "scatter", "model": "novax-solar", "time_ms": 3200}
{"ternary": 0, "phase": "scatter", "model": "novax-neural-chat", "time_ms": 8100}
{"ternary": 0, "phase": "tspeak", "encoded": true, "agreement": 0.72}
{"ternary": 0, "phase": "pressure", "ranked": ["novax-solar", "novax-neural-chat"]}
{"ternary": 0, "phase": "vortex", "mode": "standard", "judges": 2}
{"ternary": 1, "response": "final answer", "models_responded": 2}
```

---

## Ternary Tools Roadmap

TernaryFlask enables converting 150+ Linux tools into NovaLang builtins:

- **Already built**: nova_tools, nova_vault, deepstorage, ternary_tools, tspeak, tshell
- **Tier 1** (core utils): tls, tsed, tawk, tjq, tsort, ttree — extend nova_tools
- **Tier 2** (networking): tcurl, twget, tnmap, tping, tnetcat
- **Tier 3** (system): thtop, tps, tmem, tcron, twatchexec
- **Tier 4** (development): tgit, tmake, ttrace, tprofile
- **Tier 5** (infrastructure): tdocker, tkube, tterraform, tansible
- **Tier 6** (data): tsqlite, tredis, tmongo, tlocate
- **Tier 7** (media): timage, tvideo, tffmpeg, tpandoc

Each tool: ternary state + TSpeak frame + chunked streaming + NovaLang builtin.
Simple tools = direct builtins. Complex tools = .nova service on dedicated port.
All compose via tpipe: `tpipe(tcurl(url), tjq(".data"), tgrep("pattern"))` — stops on -1, streams on 0, passes on +1.

---

## Runtime Implementation (inside novalang.py)

### TFlaskRuntime class

```python
class TFlaskRuntime:
    """Ternary-native HTTP server runtime. Created by tserve() builtin."""

    def __init__(self, port, name, interpreter):
        self.port = port
        self.name = name
        self.interpreter = interpreter  # NovaInterpreter ref for calling handlers
        self.routes = {}                # {(method, path): handler_fn_name}
        self.hooks = {}                 # {hook_name: [fn_names]}
        self.stats = {"requests": 0, "ternary": {1: 0, 0: 0, -1: 0}}
        self._server = None

    def add_route(self, method, path, handler_name): ...
    def add_hook(self, hook_name, fn_name): ...
    def start(self): ...               # Creates ThreadedHTTPServer, serve_forever
    def _handle_request(self, method, path, body): ...  # Calls NovaLang fn
    def _run_hooks(self, hook_name, context): ...
```

### TFlaskHandler (inner class)

Subclasses BaseHTTPRequestHandler. do_GET/do_POST look up route in runtime.routes, call runtime._handle_request(), which calls interpreter.call_function(handler_name, args). Adds X-Ternary-State and X-TSpeak-Frame headers automatically.

### Streaming support

When handler calls tpartial(), the runtime writes a JSON line to wfile with chunked encoding and ternary state 0. tresolve() writes final line with state +1. treject() writes with state -1 and closes.

For non-streaming handlers (just return a dict), runtime auto-wraps as state +1.

---

## Files Modified

| File | Change | Lines |
|------|--------|-------|
| `C:\NovaX\novalang.py` | Add TFlaskRuntime class + 7 builtins + thook | ~250 |
| `C:\NovaX\nova_tools.nova` | First service migration (create new) | ~80 |
| `C:\NovaX\web\nova_desktop.html` | TernaryFlask status panel | ~60 |
| **Total** | | **~390** |

---

## Verification

1. `tserve(9891, "Nova Tools")` creates server, no crash
2. `troute()` registers handlers, `tstart()` binds port
3. `curl localhost:9891/health` returns `{"ok":true}` with `X-Ternary-State: 1`
4. `curl -X POST localhost:9891/tools/read` returns file content with ternary header
5. Streaming handler: `tpartial()` sends chunks, `tresolve()` sends final
6. `treject()` returns -1 state with reason
7. Middleware hooks fire in order
8. Orchestrator proxies to .nova service identically to Python service
9. Desktop panel shows TernaryFlask stats
10. Side-by-side: Python nova_tools and NovaLang nova_tools return identical results
