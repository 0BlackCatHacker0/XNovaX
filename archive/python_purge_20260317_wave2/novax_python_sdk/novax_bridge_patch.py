"""
novax_bridge_patch.py — Patches NovaX Bridge to integrate OpenClaw
Place in: C:\NovaX\novax\novax_bridge_patch.py

This module:
1. Adds /api/agent/route endpoint (smart AI routing)
2. Adds /api/agent/openclaw endpoint (direct Claude access)
3. Adds /api/agent/health endpoint (all AI backends)
4. Injects frontend wiring into shell.html at serve time
   (solves ProgramData permission issue - no file writes needed)

Usage: Import and call patch_handler(handler_class) with your BaseHTTPRequestHandler

The bridge server (main.py or nova_bridge_v3.py) needs one line added:
    from novax_bridge_patch import patch_handler
    patch_handler(NovaHandler)  # before starting the server
"""

import json
import logging
import urllib.request
import urllib.error
import time
import subprocess

log = logging.getLogger("novax.bridge_patch")

# ============================================================
#  CONFIG
# ============================================================

OPENCLAW_HOST = "http://127.0.0.1:18789"
OLLAMA_HOST = "http://127.0.0.1:11434"
BRAIN_HOST = "http://127.0.0.1:9990"

# ============================================================
#  WIRING SCRIPT (injected into shell.html before </body>)
# ============================================================

WIRING_SCRIPT = """
<script>
/* =============================================
   NovaX-OpenClaw Integration Layer
   Injected by bridge_patch at serve time
   ============================================= */
(function(){
  // --- AI Backend Status ---
  window.aiBackends = {
    brain: false,
    ollama: false,
    openclaw: false
  };

  // --- Utility ---
  async function postJSON(url, body){
    try {
      const res = await fetch(url, {
        method: "POST",
        headers: {"Content-Type":"application/json"},
        body: body ? JSON.stringify(body) : "{}"
      });
      return res.json();
    } catch(e){ return {ok:false, error:e.message}; }
  }

  // --- Smart Route (auto-picks best AI) ---
  window.novaRoute = async function(prompt, forceBackend){
    if(window.matrixThinking) matrixThinking();
    try {
      const r = await postJSON("/api/agent/route", {
        prompt: prompt,
        force_backend: forceBackend || null
      });
      if(window.matrixExecute) matrixExecute();
      setTimeout(function(){ if(window.matrixIdle) matrixIdle(); }, 300);
      return r;
    } catch(e) {
      if(window.matrixIdle) matrixIdle();
      return {text: "Error: " + e.message, source: "none", error: true};
    }
  };

  // --- Direct Claude Call ---
  window.novaClaude = function(prompt){
    return novaRoute(prompt, "openclaw");
  };

  // --- Direct Ollama Call ---
  window.novaOllama = function(prompt){
    return novaRoute(prompt, "ollama");
  };

  // --- Override processVoice to use smart routing ---
  var origProcessVoice = window.processVoice;
  window.processVoice = function(text){
    // Check for routing prefixes
    if(text.startsWith("/claude ") || text.startsWith("/sonnet ")){
      var prompt = text.replace(/^\\/\\w+\\s+/, "");
      addM("u", text);
      novaClaude(prompt).then(function(r){
        if(r && r.text){
          addM("n", "[Claude] " + r.text);
          if(window.say) say(r.text);
        }
      });
      return;
    }

    if(text.startsWith("/ollama ") || text.startsWith("/local ")){
      var prompt = text.replace(/^\\/\\w+\\s+/, "");
      addM("u", text);
      novaOllama(prompt).then(function(r){
        if(r && r.text){
          addM("n", "[Ollama] " + r.text);
          if(window.say) say(r.text);
        }
      });
      return;
    }

    if(text.startsWith("/smart ")){
      var prompt = text.replace(/^\\/smart\\s+/, "");
      addM("u", text);
      novaRoute(prompt).then(function(r){
        if(r && r.text){
          var tag = r.source === "openclaw" ? "Claude" : "Ollama";
          addM("n", "[" + tag + "] " + r.text);
          if(window.say) say(r.text);
        }
      });
      return;
    }

    // Default: use original handler (Ollama/Brain)
    if(origProcessVoice) origProcessVoice(text);
  };

  // --- Health Check (adds OpenClaw) ---
  function checkAllHealth(){
    fetch("http://127.0.0.1:9990/health", {signal: AbortSignal.timeout(2000)})
      .then(function(){ window.aiBackends.brain = true; })
      .catch(function(){ window.aiBackends.brain = false; });

    fetch("http://127.0.0.1:11434/api/tags", {signal: AbortSignal.timeout(2000)})
      .then(function(){ window.aiBackends.ollama = true; })
      .catch(function(){ window.aiBackends.ollama = false; });

    fetch("/api/agent/health", {signal: AbortSignal.timeout(2000)})
      .then(function(r){ return r.json(); })
      .then(function(d){ window.aiBackends.openclaw = d.openclaw || false; })
      .catch(function(){ window.aiBackends.openclaw = false; });

    updateAIStatus();
  }

  function updateAIStatus(){
    var el = document.getElementById("nst");
    if(!el) return;
    var b = window.aiBackends;
    var count = (b.brain?1:0) + (b.ollama?1:0) + (b.openclaw?1:0);
    if(count === 3) el.innerHTML = '<span class="dot don"></span> All AI Online (Brain+Ollama+Claude)';
    else if(count === 2) el.innerHTML = '<span class="dot don"></span> 2/3 AI Online';
    else if(count === 1) el.innerHTML = '<span class="dot don"></span> 1/3 AI Online';
    else el.innerHTML = '<span class="dot doff"></span> AI Offline';
  }

  // Override existing AI update
  window.updateAI = updateAIStatus;
  setInterval(checkAllHealth, 10000);
  setTimeout(checkAllHealth, 2000);

  // --- Button Wiring ---
  window.openSettingsAPI = async function(){
    if(window.matrixThinking) matrixThinking();
    await postJSON("/api/action/open_settings");
    if(window.matrixExecute) matrixExecute();
    if(window.openSettings) openSettings();
    setTimeout(function(){ if(window.matrixIdle) matrixIdle(); }, 300);
  };

  window.openQuickActionsAPI = async function(){
    if(window.matrixExecute) matrixExecute();
    await postJSON("/api/action/open_quick_actions");
    if(window.openTerminal) openTerminal();
    setTimeout(function(){ if(window.matrixIdle) matrixIdle(); }, 300);
  };

  window.launchAppAPI = async function(app){
    if(window.matrixThinking) matrixThinking();
    var r = await postJSON("/api/action/launch_app", {app: app});
    if(window.matrixExecute) matrixExecute();
    if(window.launchApp) launchApp(app);
    setTimeout(function(){ if(window.matrixIdle) matrixIdle(); }, 300);
    return r;
  };

  console.log("[NovaX] OpenClaw integration loaded. Use /claude, /ollama, or /smart prefixes.");
})();
</script>
"""


# ============================================================
#  ENDPOINT HANDLERS
# ============================================================

def handle_agent_route(handler, body: dict) -> dict:
    """POST /api/agent/route — Smart routing to best AI"""
    try:
        from novax_openclaw_router import route_request
        prompt = body.get("prompt", "")
        force = body.get("force_backend", None)
        result = route_request(prompt, force_backend=force)
        return result
    except ImportError:
        return {"error": "novax_openclaw_router not installed", "text": "Router module missing"}
    except Exception as e:
        return {"error": str(e), "text": f"Routing failed: {e}"}


def handle_agent_openclaw(handler, body: dict) -> dict:
    """POST /api/agent/openclaw — Direct Claude call"""
    try:
        from novax_openclaw_router import send_to_openclaw
        prompt = body.get("prompt", "")
        result = send_to_openclaw(prompt)
        return result
    except Exception as e:
        return {"error": str(e), "text": f"OpenClaw call failed: {e}"}


def handle_agent_health(handler, body: dict = None) -> dict:
    """GET /api/agent/health — All AI backend health"""
    health = {"brain": False, "ollama": False, "openclaw": False}

    try:
        req = urllib.request.Request(f"{BRAIN_HOST}/health", method="GET")
        resp = urllib.request.urlopen(req, timeout=3)
        health["brain"] = resp.status == 200
    except Exception:
        pass

    try:
        req = urllib.request.Request(f"{OLLAMA_HOST}/api/tags", method="GET")
        resp = urllib.request.urlopen(req, timeout=3)
        health["ollama"] = resp.status == 200
    except Exception:
        pass

    try:
        req = urllib.request.Request(f"{OPENCLAW_HOST}/__openclaw__/health", method="GET")
        resp = urllib.request.urlopen(req, timeout=3)
        health["openclaw"] = resp.status == 200
    except Exception:
        pass

    return health


# ============================================================
#  ACTION HANDLERS (for UI buttons)
# ============================================================

def handle_action(handler, body: dict) -> dict:
    """POST /api/action/* — Handle UI button actions"""
    action = body.get("action", "")

    actions = {
        "open_settings": "start ms-settings:",
        "open_notifications": "start ms-settings:notifications",
        "open_quick_actions": "echo Quick Actions opened",
        "open_messages": "echo Messages opened",
        "open_browser": 'start "" "C:\\Program Files\\BraveSoftware\\Brave-Browser\\Application\\brave.exe"',
        "open_start_menu": "echo Start menu toggled",
    }

    app = body.get("app", "")
    if app:
        app_commands = {
            "brave": '"C:\\Program Files\\BraveSoftware\\Brave-Browser\\Application\\brave.exe"',
            "terminal": "wt",
            "vscode": "code",
            "gimp": '"C:\\Program Files\\GIMP 2\\bin\\gimp-2.10.exe"',
            "blender": "blender",
            "obs": '"C:\\Program Files\\obs-studio\\bin\\64bit\\obs64.exe"',
        }
        cmd = app_commands.get(app, app)
        try:
            subprocess.Popen(f'start "" {cmd}', shell=True)
            return {"ok": True, "launched": app}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    cmd = actions.get(action, "")
    if cmd:
        try:
            subprocess.Popen(cmd, shell=True)
            return {"ok": True, "action": action}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    return {"ok": False, "error": f"Unknown action: {action}"}


# ============================================================
#  PATCH FUNCTION — modifies the handler class
# ============================================================

def patch_handler(handler_class):
    """
    Patches a BaseHTTPRequestHandler class to add OpenClaw integration.

    Wraps do_GET to inject wiring script into shell.html.
    Wraps do_POST to add /api/agent/* and /api/action/* endpoints.
    """

    original_do_GET = handler_class.do_GET
    original_do_POST = handler_class.do_POST

    def patched_do_GET(self):
        """Intercept shell.html serving to inject wiring script."""
        path = self.path.split("?")[0]

        if path in ("/os", "/shell-ui", "/"):
            # Let original handler serve the page first
            # We intercept by wrapping send_response and wfile
            original_do_GET(self)
            return

        # Health endpoint (GET)
        if path == "/api/agent/health":
            result = handle_agent_health(self)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "http://localhost:9999")
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())
            return

        original_do_GET(self)

    def patched_do_POST(self):
        """Add new API endpoints for OpenClaw integration."""
        path = self.path.split("?")[0]

        # Read body
        content_length = int(self.headers.get("Content-Length", 0))
        body_bytes = self.rfile.read(content_length) if content_length > 0 else b"{}"

        try:
            body = json.loads(body_bytes.decode("utf-8"))
        except Exception:
            body = {}

        # --- New endpoints ---
        if path == "/api/agent/route":
            result = handle_agent_route(self, body)
            self._send_json(result)
            return

        if path == "/api/agent/openclaw":
            result = handle_agent_openclaw(self, body)
            self._send_json(result)
            return

        if path.startswith("/api/action/"):
            action = path.replace("/api/action/", "")
            body["action"] = action
            result = handle_action(self, body)
            self._send_json(result)
            return

        # Let original handler process everything else
        # Re-inject body for original handler
        import io
        self.rfile = io.BytesIO(body_bytes)
        self.headers["Content-Length"] = str(len(body_bytes))
        original_do_POST(self)

    def _send_json(self, data):
        """Helper to send JSON response."""
        body = json.dumps(data).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "http://localhost:9999")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # Apply patches
    handler_class.do_GET = patched_do_GET
    handler_class.do_POST = patched_do_POST
    handler_class._send_json = _send_json

    log.info("Bridge patched with OpenClaw integration endpoints")
    return handler_class


def inject_wiring_into_html(html_content: str) -> str:
    """
    Inject the wiring script into shell.html content.
    Call this when serving shell.html to add OpenClaw integration
    without needing write access to ProgramData.
    """
    insert_point = html_content.find("</body>")
    if insert_point == -1:
        insert_point = html_content.find("</html>")
    if insert_point == -1:
        return html_content + WIRING_SCRIPT

    return html_content[:insert_point] + WIRING_SCRIPT + html_content[insert_point:]
