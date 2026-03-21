"""
NovaX WebSocket Transport - Persistent Channel
================================================
One connection. No headers. No reconnection.
Commands, events, logs, files all flow through one pipe.

Port 9998 (WebSocket) alongside port 9999 (HTTP)

Message format (JSON text frames):
  { "op": "...", "id": "...", "data": {...} }

Operations:
  Client -> Server:
    cmd      - execute terminal command
    status   - get system status  
    svc      - service control (start/stop/restart)
    eval     - evaluate policy
    job      - create/cancel job
    attach   - file pointer transfer
    sub      - subscribe to events
    unsub    - unsubscribe
    ping     - keepalive

  Server -> Client:
    result   - command result
    event    - system event (push)
    log      - log stream
    health   - health update (push)
    pong     - keepalive response
    error    - error response
"""
import asyncio
import json
import time
import threading
import logging
import subprocess
import os

log = logging.getLogger("NovaX.WS")

# Connected clients
_clients = set()
_nova = None
_loop = None

def set_nova(nova_instance):
    global _nova
    _nova = nova_instance

def client_count():
    return len(_clients)

# ========== BROADCAST ==========
def broadcast(op, data=None, exclude=None):
    """Push a message to all connected clients."""
    msg = json.dumps({"op": op, "data": data or {}}, default=str)
    dead = set()
    for ws in _clients:
        if ws == exclude:
            continue
        try:
            asyncio.run_coroutine_threadsafe(ws.send(msg), _loop)
        except Exception:
            dead.add(ws)
    _clients.difference_update(dead)

def broadcast_event(event_data):
    """Called by event bus subscriber - pushes to all WS clients."""
    if isinstance(event_data, dict):
        broadcast("event", event_data)
    else:
        broadcast("event", {"raw": str(event_data)})

# ========== MESSAGE HANDLER ==========
async def handle_message(ws, raw):
    """Process one incoming message."""
    try:
        msg = json.loads(raw)
    except json.JSONDecodeError:
        await ws.send(json.dumps({"op": "error", "data": {"msg": "invalid JSON"}}))
        return

    op = msg.get("op", "")
    mid = msg.get("id", "")
    data = msg.get("data", {})

    def reply(result_data):
        r = {"op": "result", "data": result_data}
        if mid:
            r["id"] = mid
        return ws.send(json.dumps(r, default=str))

    # ---- PING ----
    if op == "ping":
        await ws.send(json.dumps({"op": "pong", "ts": time.time()}))
        return

    # ---- CMD (terminal) ----
    if op == "cmd":
        cmd = data.get("command", data.get("cmd", ""))
        cwd = data.get("cwd")
        timeout = data.get("timeout", 30)
        try:
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                             timeout=timeout, cwd=cwd, encoding="utf-8", errors="replace")
            await reply({"ok": r.returncode == 0, "output": r.stdout + r.stderr,
                        "code": r.returncode})
        except subprocess.TimeoutExpired:
            await reply({"ok": False, "output": "TIMEOUT"})
        except Exception as e:
            await reply({"ok": False, "output": str(e)})
        return

    # ---- STATUS ----
    if op == "status":
        if not _nova:
            await reply({"ok": False, "error": "supervisor not ready"})
            return
        await reply({
            "ok": True, "master": _nova.state,
            "uptime": time.time() - _nova.boot_time,
            "services": _nova.managed_services(),
            "jobs_active": len(_nova.orchestrator.active()),
            "ws_clients": len(_clients),
        })
        return

    # ---- SERVICE CONTROL ----
    if op == "svc":
        action = data.get("action", "")
        name = data.get("name", data.get("service", ""))
        if not _nova:
            await reply({"ok": False, "error": "supervisor not ready"})
            return
        if action == "start":
            result = _nova.start_service(name)
        elif action == "stop":
            result = _nova.stop_service(name)
        elif action == "restart":
            result = _nova.restart_service(name)
        elif action == "status":
            result = _nova.managed_services()
        else:
            result = f"unknown action: {action}"
        await reply({"ok": True, "result": result})
        return

    # ---- JOB ----
    if op == "job":
        action = data.get("action", "create")
        if not _nova:
            await reply({"ok": False, "error": "supervisor not ready"})
            return
        if action == "create":
            from ..objects import Intent
            intent = _nova.context.infer(data.get("text", ""))
            job = _nova.orchestrator.submit(intent)
            receipt = _nova.orchestrator.run_next()
            await reply({"ok": True, "job_id": job.id, "result": receipt.output})
        elif action == "cancel":
            ok = _nova.orchestrator.cancel(data.get("job_id", ""))
            await reply({"ok": ok})
        elif action == "active":
            jobs = _nova.orchestrator.active()
            await reply({"ok": True, "jobs": [
                {"id": j.id, "status": j.status.value} for j in jobs]})
        return

    # ---- HEALTH ----
    if op == "health":
        if _nova:
            r = _nova.health.check_all()
            await reply({"ok": True, "services": r})
        else:
            await reply({"ok": False})
        return

    # ---- ATTACH FILE (pointer transfer) ----
    if op == "attach":
        path = data.get("path", "")
        if os.path.isfile(path):
            size = os.path.getsize(path)
            await reply({"ok": True, "path": path, "size": size, "attached": True})
        else:
            await reply({"ok": False, "error": f"file not found: {path}"})
        return

    # ---- FILE WRITE ----
    if op == "write":
        path = data.get("path", "")
        content = data.get("content", "")
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            await reply({"ok": True, "path": path, "size": len(content)})
        except Exception as e:
            await reply({"ok": False, "error": str(e)})
        return

    # ---- FILE READ ----
    if op == "read":
        path = data.get("path", "")
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read(200000)
            await reply({"ok": True, "content": content, "size": os.path.getsize(path)})
        except Exception as e:
            await reply({"ok": False, "error": str(e)})
        return

    # ---- EVENTS ----
    if op == "events":
        from ..events.bus import bus
        await reply({"ok": True, "events": bus.recent(30)})
        return

    # ---- BATCH (command bundling) ----
    if op == "batch":
        commands = data.get("commands", [])
        results = []
        for c in commands:
            try:
                r = subprocess.run(c, shell=True, capture_output=True, text=True,
                                 timeout=15, encoding="utf-8", errors="replace")
                results.append({"cmd": c, "ok": r.returncode == 0,
                              "output": (r.stdout + r.stderr)[:2000]})
            except Exception as e:
                results.append({"cmd": c, "ok": False, "output": str(e)})
        await reply({"ok": True, "results": results, "count": len(results)})
        return

    # ---- UNKNOWN ----
    await ws.send(json.dumps({"op": "error", "data": {"msg": f"unknown op: {op}"}}))

# ========== CONNECTION HANDLER ==========
async def handler(ws):
    """Handle one WebSocket connection lifecycle."""
    _clients.add(ws)
    peer = ws.remote_address
    log.info(f"WS client connected: {peer} (total: {len(_clients)})")

    # Send welcome
    await ws.send(json.dumps({
        "op": "welcome",
        "data": {
            "server": "NovaX",
            "version": "1.0",
            "ts": time.time(),
            "clients": len(_clients),
        }
    }))

    try:
        async for message in ws:
            if isinstance(message, str):
                await handle_message(ws, message)
            elif isinstance(message, bytes):
                # Binary frame - future: direct file transfer
                log.info(f"Binary frame: {len(message)} bytes from {peer}")
                await ws.send(json.dumps({
                    "op": "result",
                    "data": {"ok": True, "binary_received": len(message)}
                }))
    except Exception as e:
        log.info(f"WS client error: {peer}: {e}")
    finally:
        _clients.discard(ws)
        log.info(f"WS client disconnected: {peer} (remaining: {len(_clients)})")

# ========== SERVER STARTUP ==========
async def _run_server(port=9998):
    """Start the WebSocket server."""
    import websockets
    global _loop
    _loop = asyncio.get_event_loop()
    
    server = await websockets.serve(
        handler, "127.0.0.1", port,
        ping_interval=20,
        ping_timeout=60,
        max_size=10 * 1024 * 1024,  # 10MB max frame
        origins=None,
    )
    log.info(f"WebSocket server running on ws://0.0.0.0:{port}")
    await server.wait_closed()

def start_ws_server(port=9998):
    """Start WebSocket server in a background thread."""
    def _run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        global _loop
        _loop = loop
        loop.run_until_complete(_run_server(port))
    
    t = threading.Thread(target=_run, daemon=True, name="NovaX-WS")
    t.start()
    log.info(f"WebSocket thread started (port {port})")
    return t
