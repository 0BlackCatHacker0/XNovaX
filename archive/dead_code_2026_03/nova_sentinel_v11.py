#!/usr/bin/env python3
"""Nova Sentinel v1.1 - Auto-Recovery Watchdog
Monitors all NovaX services, auto-restarts on failure, live dashboard.
Port: 9883
"""
import json, os, time, threading, subprocess, datetime, socket
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from collections import deque

PORT = 9883
SERVICES = {
    "bridge":      {"name":"Nova Bridge",     "port":9999, "cmd":"python C:\\NovaX\\novax\\main.py"},
    "brain":       {"name":"Nova Brain",      "port":9990, "cmd":None},
    "relay":       {"name":"Nova Relay",      "port":9877, "cmd":"python C:\\NovaX\\nova_relay.py"},
    "ollama":      {"name":"Ollama",          "port":11434,"cmd":"ollama serve"},
    "hivemind":    {"name":"Hive Mind",       "port":9881, "cmd":"python C:\\NovaX\\nova_hivemind.py"},
    "vpncore":     {"name":"VPN Core",        "port":9880, "cmd":"python C:\\NovaX\\nova_vpn_core.py"},
    "cloudrouter": {"name":"Cloud Router",    "port":9878, "cmd":"python C:\\NovaX\\nova_cloud_router.py"},
    "nexus":       {"name":"Nova Nexus",      "port":9882, "cmd":"python C:\\NovaX\\nova_nexus.py"},
}

health = {k: {"status":"unknown","down_since":0,"restarts":0,"last_restart":0} for k in SERVICES}
events = deque(maxlen=200)
stats = {"checks":0,"restarts":0,"start_time":time.time(),"auto_recovery":True}
lock = threading.Lock()

def log_event(level, msg):
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    with lock:
        events.append({"time":ts,"level":level,"msg":msg})
    print(f"  [{level}] {ts} {msg}")

def check_port(port):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1.5)
        s.connect(("127.0.0.1", port))
        s.close()
        return True
    except:
        return False

def restart_service(key, info):
    if not info.get("cmd"):
        return False
    try:
        log_event("FIX", f"Restarting {info['name']} on :{info['port']}")
        cmd = info["cmd"]
        if "python" in cmd:
            script = cmd.split("python ")[-1]
            full = f'start /MIN /B python {script}'
        else:
            full = f'start /MIN /B {cmd}'
        subprocess.Popen(f'cmd /c "{full}"', shell=True, cwd="C:\\NovaX",
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        with lock:
            health[key]["restarts"] += 1
            health[key]["last_restart"] = time.time()
            stats["restarts"] += 1
        log_event("OK", f"{info['name']} restart initiated")
        return True
    except Exception as e:
        log_event("ERR", f"Restart failed: {e}")
        return False
