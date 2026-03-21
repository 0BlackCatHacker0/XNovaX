"""
NovaX Orchestrator — The Complete AI OS Server
Port: 9999

Integrates ALL systems from all text files:
- Two-Phase Intent System (master_build.txt)
- Action Bus + Drivers
- AI Router with learning (ai_router_memory)
- Skills Engine (ai_skills.txt)
- VCC verification (Verified_Capability_Contract.txt)
- Session Memory & Project Learner
- Claude API direct connector (browser_extention_fix.txt)
- OpenClaw routing (The_API_call_succeeded.txt)

All 26+ endpoints implemented and working.
"""

import os, sys, json, time, threading, collections, atexit, socketserver, socket

# ── CRITICAL: Global socket timeout safety net ──
# Prevents any urllib/socket call from hanging indefinitely.
# Without this, a single dead service can block a thread forever.
socket.setdefaulttimeout(60.0)
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory

# ── FIX: Prevent multiple listeners on same port (Windows SO_REUSEADDR trap) ──
if sys.platform == 'win32':
    socketserver.TCPServer.allow_reuse_address = False

# ── Path traversal protection ─────────────────────────────────────────────────
_SAFE_ROOTS = [r"C:\NovaX", r"C:\NovaX\data", r"C:\NovaX\memory", r"C:\NovaX\web"]

def _safe_path(p):
    """Validate path stays within allowed roots. Returns True if safe."""
    real = os.path.realpath(p)
    return any(real.lower().startswith(os.path.realpath(r).lower() + os.sep) or
               real.lower() == os.path.realpath(r).lower() for r in _SAFE_ROOTS)
from flask_socketio import SocketIO, emit
from flask_cors import CORS

# Add core to path
sys.path.insert(0, str(Path(__file__).parent))

from task_classifier import classify, classify_risk
from ai_router import route_with_fallback
from ai_router_memory import record, get_stats, get_history, get_dashboard, DEFAULT_RULES
from claude_connector import ask_claude, ask_claude_with_context, NOVAX_SYSTEM_PROMPT
from nova_agent import agent_loop
from drivers import bus
from skills_engine import match_skill, load_skills, list_skills, save_skill
from vcc import get_vcc_status, vcc_summary, verify_component
from session_memory import (
    record_action, get_session_actions, analyze_for_project,
    save_project, get_projects, add_message, get_conversation, clear_conversation,
    get_session_meta, update_session_meta, save_working_context,
    load_working_context, build_resume_prompt, get_full_conversation
)
from nova_persona import (
    build_system_prompt, build_conversation_messages,
    format_response, auto_save_context
)

# Phase 1 modules (all verified working)
from workflows import save_workflow as wf_save, list_workflows as wf_list, match_workflow
from time_index import record_event, search as time_search
from profile_manager import (
    switch as profile_switch, get_active as active_profile,
    list_profiles, export_profile, import_profile, get_profile_config
)
from event_bus import bus as event_bus
from arbiter import Arbiter
from dse import (
    get_observed, get_desired, set_desired, diff as dse_diff,
    plan as dse_plan, killswitch, DSE_PROFILES
)
from context_watcher import detect_profile
from environment_manager import propose_bootstrap, execute_bootstrap, list_environments
from state import format_for_prompt, full_system_context
from skills_engine import update_confidence, get_skill_suggestion_level
import tasks
import config

# Phase 8 modules
from xrpl_wallet import (
    generate_wallet, get_wallet_info, get_balance,
    send_payment, get_transactions, get_tx_log, wallet_status,
    mint_nft, get_nfts, burn_nft, recover_wallet, export_wallet,
    list_dapps, get_dapp
)
from voice import (
    get_config as voice_get_config, update_config as voice_update_config, voice_status,
    list_voices, get_active_voice, set_voice, speak_to_bytes, speak
)
from module_manager import (
    discover as mod_discover, list_modules, get_module_info,
    enable_module, disable_module, install_module, uninstall_module,
    create_module_template, validate_module, module_stats,
    snapshot_module, rollback_module, list_snapshots,
    resolve_dependencies, get_dependency_tree,
    get_module_config, update_module_config,
    run_module_action
)
from ui_memory import (
    record_interaction, match_routine, list_routines,
    enable_auto_replay, disable_auto_replay, get_auto_routines, get_stats as ui_stats
)
from repair_engine import diagnose, diagnose_with_ai, recent_failures, get_repair_stats

# Device Detection
from device_detector import (
    scan_devices, device_status as dev_device_status, list_usb_drives,
    get_device_log, add_rule as dev_add_rule, remove_rule as dev_remove_rule,
    get_rules as dev_get_rules, start_monitor as dev_start_monitor,
    stop_monitor as dev_stop_monitor, monitor_status as dev_monitor_status
)

# Shell Replacement & OS Takeover (DISABLED per Session 34)
sys.path.insert(0, os.path.join(str(Path(__file__).parent.parent), "installer"))
try:
    from shell_replace import shell_status, install_shell, uninstall_shell, is_admin
except ImportError:
    def shell_status(): return {"status": "permanently_disabled"}
    def install_shell(): return False
    def uninstall_shell(): return False
    def is_admin(): return False
try:
    from os_takeover import (
        enable_startup, disable_startup, startup_status,
        create_boot_task, remove_boot_task, check_services as ot_check_services,
        takeover_status
    )
except ImportError:
    def enable_startup(): return False
    def disable_startup(): return False
    def startup_status(): return {"status": "permanently_disabled"}
    def create_boot_task(): return False
    def remove_boot_task(): return False
    def ot_check_services(): return {}
    def takeover_status(): return {"status": "permanently_disabled"}
from os_integration import (
    set_wallpaper, restore_wallpaper, wallpaper_status,
    set_theme, restore_theme, theme_status,
    register_protocol, unregister_protocol, protocol_status,
    add_context_menu, remove_context_menu, context_menu_status,
    set_file_associations, restore_file_associations, file_assoc_status,
    hide_taskbar, show_taskbar, taskbar_status,
    set_lock_screen, restore_lock_screen, lockscreen_status,
    scan_installed_apps, integration_status, enable_all as integration_enable_all,
    disable_all as integration_disable_all,
)

# Code Protection
from code_protector import (
    fingerprint_all, fingerprint_file, encrypt_file, decrypt_file,
    encrypt_all_source, generate_integrity_manifest, verify_integrity,
    sign_release, protection_status, get_protection_log
)

# Mode System
import mode_system

# Gameplay / AI Creativity
sys.path.insert(0, r"C:\NovaX\novax")
from gameplay.learning import GameplayLearner
gameplay_learner = GameplayLearner()

# Hive Mind — Unified AI Model Dispatch
from hive_mind import HiveMind
hive_mind = HiveMind()

# Persistence Layer
from persistence import persistence

# NovaLang Debugger
from novalang_debugger import NovaLangDebugger
novalang_debugger = NovaLangDebugger()
novalang_debugger.register_language()

# Workspace Watch — Real-Time Model Monitor
from workspace_watch import workspace_watch

# God Mode
from godmode.session import GodModeEngine
god_engine = GodModeEngine()

# Workspace Manager
from workspace_manager import activate_workspace, get_workspace, get_active as get_active_workspace, customize_workspace

# Super Archive — Full-Text Search
from super_archive import search as archive_search, build_index as archive_build_index, archive_status

# ─────────────────────────────────────────────
# APP SETUP
# ─────────────────────────────────────────────
ROOT = Path(r"C:\NovaX")
# Prefer web/ directory (has all Phase 5+ UI files)
STATIC = ROOT / "web"
if not STATIC.exists():
    STATIC = ROOT / "app" / "shell" / "static"

app = Flask(__name__, static_folder=str(STATIC))
CORS(app, origins=["http://localhost:9999", "http://127.0.0.1:9999"])
socketio = SocketIO(app, cors_allowed_origins=["http://localhost:9999", "http://127.0.0.1:9999"], async_mode="threading")

START_TIME = time.time()
VERSION = "5.1.0"  # Security-hardened

# ── Session Token Auth ─────────────────────────────────────────────────────
# Generate a random token on boot. Required for dangerous endpoints.
# Token is written to .session_token for local tools to read.
import secrets as _secrets
_SESSION_TOKEN = _secrets.token_hex(32)
_TOKEN_FILE = os.path.join(r"C:\NovaX", ".session_token")
try:
    with open(_TOKEN_FILE, "w") as _tf:
        _tf.write(_SESSION_TOKEN)
except Exception:
    pass  # best-effort

def _require_auth():
    """Check X-Nova-Token header or ?token= query param against boot token."""
    token = request.headers.get("X-Nova-Token") or request.args.get("token", "")
    if token != _SESSION_TOKEN:
        return False
    return True

# Endpoints that require auth (RCE, env, file-write)
_AUTH_REQUIRED_PREFIXES = ["/api/run", "/api/exec", "/api/execute",
                           "/api/environment", "/api/fs/write", "/api/fs/delete"]

@app.before_request
def _check_auth():
    """Gate dangerous endpoints behind token auth."""
    path = request.path
    for prefix in _AUTH_REQUIRED_PREFIXES:
        if path.startswith(prefix):
            if not _require_auth():
                return jsonify({"ok": False, "error": "auth_required",
                                "msg": "X-Nova-Token header required"}), 401
    return None

# ── Zombie Prevention: kill stale listeners on our port at startup ──────────
_ORCHESTRATOR_PORT = 9999
_CHILD_PROCS = []  # track spawned service processes for cleanup

def _kill_port_zombies(port):
    """Kill any stale process listening on our port before we bind."""
    if sys.platform != 'win32':
        return
    import subprocess as _zsp
    try:
        r = _zsp.run(['netstat', '-ano', '-p', 'TCP'], capture_output=True, text=True, timeout=5)
        my_pid = os.getpid()
        for line in r.stdout.splitlines():
            if f':{port}' in line and 'LISTENING' in line:
                pid = int(line.split()[-1])
                if pid != my_pid and pid != 0:
                    _zsp.run(['taskkill', '/F', '/PID', str(pid)], capture_output=True, timeout=5)
    except Exception:
        pass

def _cleanup_children():
    """Kill all child service processes on orchestrator exit."""
    for proc in _CHILD_PROCS:
        try:
            if proc.poll() is None:
                proc.terminate()
                proc.wait(timeout=5)
        except Exception:
            try: proc.kill()
            except Exception: pass

atexit.register(_cleanup_children)
_kill_port_zombies(_ORCHESTRATOR_PORT)

# ── 3-5-7-13 Ternary Constants ──────────────────────────────────────
H3, H5, H7, H13 = 3, 5, 7, 13
TRUE, MAYBE, FALSE_ = 1, 0, -1  # FALSE_ to avoid shadowing Python's False
BLOCK_SIZE = 3 ** H7  # 2187
RE_LAMINAR = H3 ** H3      # 27
RE_TRANSITION = H5 ** H3   # 125
RE_TURBULENT = H7 ** H3    # 343

def _trit(val):
    """Constrain any value to {-1, 0, +1}."""
    if val > 0: return 1
    if val < 0: return -1
    return 0

def _cmp3(a, b):
    """Ternary comparison: +1 if a>b, 0 if equal, -1 if a<b."""
    return 1 if a > b else (-1 if a < b else 0)

def _merge_ternary(trits):
    """Merge list of trits into consensus trit.
    All +1 → +1, all -1 → -1, mixed → 0 (MAYBE)."""
    if not trits: return 0
    s = sum(trits)
    n = len(trits)
    if s == n: return 1        # unanimous positive
    if s == -n: return -1      # unanimous negative
    ratio = s / n
    if ratio > 1.0 / 3: return 1   # H3 majority positive
    if ratio < -1.0 / 3: return -1 # H3 majority negative
    return 0                   # contested = MAYBE

def _bt_string(trits):
    """Convert list of trits to balanced ternary string."""
    return ''.join('1' if t == 1 else '0' if t == 0 else 'T' for t in trits)

def _route_trit(result):
    """Classify a route/action result as trit: +1=success, 0=partial, -1=failed."""
    if isinstance(result, dict):
        if result.get('ok') is True: return 1
        if result.get('ok') is False: return -1
        if result.get('error') or result.get('err'): return -1
        return 0
    if result is True: return 1
    if result is False: return -1
    return 0

# ── Circuit Breaker (Ternary: +1=CLOSED, 0=HALF_OPEN, -1=OPEN) ──────────
# Per-service circuit breaker with failure thresholds and recovery timeouts
_circuit_breakers = {}  # {service_name: {state, failures, last_failure, last_success, half_open_at}}
_cb_lock = threading.Lock()
_CB_FAILURE_THRESHOLD = H5       # 5 failures → open
_CB_RECOVERY_TIMEOUT = H13 * H3  # 39 seconds before half-open
_CB_HALF_OPEN_MAX = H3            # 3 test requests in half-open

def _cb_get(service):
    """Get or create circuit breaker state for a service."""
    with _cb_lock:
        if service not in _circuit_breakers:
            _circuit_breakers[service] = {
                'state': 1,  # +1=CLOSED (healthy)
                'failures': 0, 'successes': 0,
                'last_failure': 0, 'last_success': 0,
                'half_open_at': 0, 'half_open_attempts': 0,
                'total_trips': 0,
            }
        return _circuit_breakers[service]

def _cb_allow(service):
    """Check if request should be allowed through the circuit breaker.
    Returns True if allowed, False if circuit is open."""
    cb = _cb_get(service)
    now = time.time()
    if cb['state'] == 1:  # CLOSED — always allow
        return True
    if cb['state'] == -1:  # OPEN — check if recovery timeout elapsed
        if now - cb['last_failure'] >= _CB_RECOVERY_TIMEOUT:
            cb['state'] = 0  # transition to HALF-OPEN
            cb['half_open_at'] = now
            cb['half_open_attempts'] = 0
            return True
        return False
    if cb['state'] == 0:  # HALF-OPEN — allow limited test requests
        if cb['half_open_attempts'] < _CB_HALF_OPEN_MAX:
            cb['half_open_attempts'] += 1
            return True
        return False
    return True

def _cb_record_success(service):
    """Record a successful request — may close the breaker."""
    cb = _cb_get(service)
    cb['successes'] += 1
    cb['last_success'] = time.time()
    if cb['state'] == 0:  # HALF-OPEN → CLOSED on success
        cb['state'] = 1
        cb['failures'] = 0
        cb['half_open_attempts'] = 0
    elif cb['state'] == 1:  # CLOSED — reset failure count on success
        cb['failures'] = max(0, cb['failures'] - 1)

def _cb_record_failure(service):
    """Record a failed request — may open the breaker."""
    cb = _cb_get(service)
    cb['failures'] += 1
    cb['last_failure'] = time.time()
    if cb['state'] == 0:  # HALF-OPEN → OPEN on failure
        cb['state'] = -1
        cb['total_trips'] += 1
    elif cb['state'] == 1:  # CLOSED — check threshold
        if cb['failures'] >= _CB_FAILURE_THRESHOLD:
            cb['state'] = -1  # OPEN
            cb['total_trips'] += 1

def _cb_state_name(trit):
    return {1: 'CLOSED', 0: 'HALF_OPEN', -1: 'OPEN'}.get(trit, '?')


def _health_record(service_name, status, response_time=0):
    """Record a health check result in the per-service history ring buffer.
    Keeps at most _HEALTH_HISTORY_MAX (H13*H13=169) entries per service.
    Also feeds the circuit breaker: success on healthy, failure on dead."""
    trit = 1 if status == "healthy" else (0 if status == "degraded" else -1)
    if service_name not in _health_history:
        _health_history[service_name] = []
    _health_history[service_name].append({
        'timestamp': time.time(),
        'status': status,
        'response_time': round(response_time, 1),
        'trit': trit,
    })
    # Trim to ring buffer size
    if len(_health_history[service_name]) > _HEALTH_HISTORY_MAX:
        _health_history[service_name] = _health_history[service_name][-_HEALTH_HISTORY_MAX:]
    # Feed circuit breaker
    if trit == 1:
        _cb_record_success(service_name)
    elif trit == -1:
        _cb_record_failure(service_name)
    # Degraded (0) does not trip the breaker but is recorded


# ── Service Health Monitoring & Auto-Recovery (3-5-7-13 Harmonic) ─────────
# Comprehensive health tracking with ternary states and auto-recovery.
# Uses ThreadPoolExecutor for parallel checks across all known services.
HEALTH_CHECK_INTERVAL = H13 * 5       # 65 seconds between checks
HEALTH_TIMEOUT = H5                   # 5 second timeout per check
MAX_CONSECUTIVE_FAILURES = H3         # 3 failures before marking dead
RECOVERY_COOLDOWN = H7 * 60           # 7 min cooldown before retry

# Port→Name mapping for all known NovaX services
KNOWN_SERVICES = {
    9869: "NovaPrime", 9970: "TSpin",
    9850: "PhysicsEngine", 9851: "NovaXCoreEngine",
    9852: "RenderEngine", 9853: "SimEngine", 9854: "AudioEngine",
    9875: "STT", 9877: "ExecServer", 9878: "CloudRouter", 9880: "VPNCore",
    9881: "Hivemind", 9882: "Nexus", 9884: "Sentinel", 9885: "TernaryServer",
    9886: "TBuffer", 9888: "ClosedLoop", 9889: "MaxPatch",
    9890: "TShell", 9891: "NovaTools", 9892: "Vault",
    9893: "DeepStorage", 9894: "TernaryTools", 9895: "TSpeak",
    9896: "Cortex", 9897: "TFetch", 9901: "TKill",
    9903: "TSkipTrace", 9905: "TSysMon", 9906: "TNet",
    9907: "TSecurity", 9908: "TMedia", 9909: "TBuild",
    9910: "TCron", 9911: "TQuery", 9912: "TSession",
    9913: "TGit", 9914: "TDocker", 9915: "TTerraform",
    9916: "TSQLite", 9917: "TRedis", 9918: "TImage",
    9919: "THttp", 9920: "TMarkdown", 9921: "TYaml",
    9922: "TFFmpeg", 9923: "TText", 9924: "TIntelligence",
    9926: "BitnetFleet", 9927: "TCI",
    9940: "THealth", 9941: "TConfig", 9942: "TLog",
    9945: "TBus", 9948: "TResilience", 9950: "TWatch",
    9951: "TMesh", 9952: "TAuth", 9953: "TMetrics",
    9955: "TStream", 9956: "TCache", 9957: "TQueue",
    9958: "TGraph", 9959: "TScheduler", 9960: "TEmbed",
    9961: "NovaCLI", 9963: "TRouter", 9964: "TValidator",
    9965: "TSnapshot", 9966: "TPipeline", 9967: "TMatrix",
    9928: "TAlchemy", 9937: "TReplay", 9971: "TCluster",
    9972: "TCompress", 9973: "TDiff", 9974: "TAudit",
    9975: "TNotify", 9976: "TSync", 9977: "TPrompt",
    9978: "TMemory", 9979: "TGateway", 9980: "TProfile",
    9981: "TLock", 9982: "TFlow", 9983: "TDigest",
    9984: "TBalance", 9985: "TRelay", 9990: "NovaBrain",
    9932: "TConfig2", 9933: "TBenchmark", 9934: "TTest", 9935: "TDocs",
    9998: "WebSocket",
    9986: "TScale", 9987: "TShield", 9988: "THunter",
    9860: "ModelRegistry", 9936: "TMicro", 9991: "TPacman",
    11434: "Ollama", 6379: "Redis", 7700: "Meilisearch",
    9938: "ScriptVault",
    9939: "Quantizer",
    9954: "AbilityRouter",
    9968: "TernarySQL",
    9969: "HFGateway",
    9943: "Hardware",
    9949: "TRate",
}

_service_health = {}  # {port: {status, consecutive_failures, last_check, last_recovery, response_ms}}
_health_lock = threading.Lock()

# ── Health History (per-service timestamped records) ─────────────────────
_health_history = {}   # service_name -> list of {timestamp, status, response_time, trit}
_HEALTH_HISTORY_MAX = H13 * H13  # 169 entries per service

def _check_service_health(port, name):
    """Check a single service's health via HTTP GET /health.
    Returns dict with status ('healthy'|'degraded'|'dead'), trit (+1/0/-1), response_ms.
    Tracks consecutive failures and transitions between states."""
    import urllib.request as _ur
    t0 = time.time()
    # Redis uses TCP socket ping, not HTTP
    if port == 6379:
        import socket as _sock
        try:
            s = _sock.create_connection(("127.0.0.1", 6379), timeout=HEALTH_TIMEOUT)
            s.sendall(b"PING\r\n")
            resp_bytes = s.recv(64)
            s.close()
            elapsed_ms = (time.time() - t0) * 1000
            is_ok = b"+PONG" in resp_bytes
            status = "healthy" if is_ok else "dead"
            trit = 1 if is_ok else -1
            with _health_lock:
                entry = _service_health.get(port, {"status": "healthy", "consecutive_failures": 0, "last_check": 0, "last_recovery": 0, "response_ms": 0.0})
                entry["last_check"] = time.time()
                entry["response_ms"] = round(elapsed_ms, 1)
                entry["consecutive_failures"] = 0 if is_ok else entry.get("consecutive_failures", 0) + 1
                entry["status"] = status
                _service_health[port] = entry
            return {"port": port, "name": name, "status": status, "trit": trit,
                    "response_ms": round(elapsed_ms, 1), "consecutive_failures": entry["consecutive_failures"]}
        except Exception:
            elapsed_ms = (time.time() - t0) * 1000
            with _health_lock:
                entry = _service_health.get(port, {"status": "dead", "consecutive_failures": 0, "last_check": 0, "last_recovery": 0, "response_ms": 0.0})
                entry["last_check"] = time.time()
                entry["response_ms"] = round(elapsed_ms, 1)
                entry["consecutive_failures"] = entry.get("consecutive_failures", 0) + 1
                entry["status"] = "dead" if entry["consecutive_failures"] >= H3 else "degraded"
                _service_health[port] = entry
            trit = 0 if entry["status"] == "degraded" else -1
            return {"port": port, "name": name, "status": entry["status"], "trit": trit,
                    "response_ms": round(elapsed_ms, 1), "consecutive_failures": entry["consecutive_failures"]}
    try:
        health_path = "/api/tags" if port == 11434 else "/health"
        req = _ur.Request(f"http://127.0.0.1:{port}{health_path}", method="GET")
        resp = _ur.urlopen(req, timeout=HEALTH_TIMEOUT)
        elapsed_ms = (time.time() - t0) * 1000
        body = resp.read().decode("utf-8", errors="replace")
        # Parse response — check for "ok" or status field
        # A 200 response proves the service is alive even if body is null/{}
        is_ok = resp.status == 200 or '"ok"' in body or '"status":"ok"' in body or '"status": "ok"' in body
        with _health_lock:
            entry = _service_health.get(port, {
                "status": "healthy", "consecutive_failures": 0,
                "last_check": 0, "last_recovery": 0, "response_ms": 0.0,
            })
            entry["last_check"] = time.time()
            entry["response_ms"] = round(elapsed_ms, 1)
            if is_ok and resp.status == 200:
                entry["consecutive_failures"] = 0
                # Use H3^8 (6561ms) as degraded boundary — NovaLang Rust VM + heavy imports need headroom
                if elapsed_ms > H3 ** 8:
                    entry["status"] = "degraded"
                else:
                    entry["status"] = "healthy"
            else:
                # Got a response but not healthy
                entry["consecutive_failures"] += 1
                if entry["consecutive_failures"] >= MAX_CONSECUTIVE_FAILURES:
                    entry["status"] = "dead"
                else:
                    entry["status"] = "degraded"
            _service_health[port] = entry
        trit = 1 if entry["status"] == "healthy" else (0 if entry["status"] == "degraded" else -1)
        _health_record(name, entry["status"], elapsed_ms)
        return {"port": port, "name": name, "status": entry["status"],
                "trit": trit, "response_ms": round(elapsed_ms, 1),
                "consecutive_failures": entry["consecutive_failures"]}
    except Exception:
        elapsed_ms = (time.time() - t0) * 1000
        with _health_lock:
            entry = _service_health.get(port, {
                "status": "healthy", "consecutive_failures": 0,
                "last_check": 0, "last_recovery": 0, "response_ms": 0.0,
            })
            entry["last_check"] = time.time()
            entry["response_ms"] = round(elapsed_ms, 1)
            entry["consecutive_failures"] += 1
            if entry["consecutive_failures"] >= MAX_CONSECUTIVE_FAILURES:
                entry["status"] = "dead"
            else:
                entry["status"] = "degraded"
            _service_health[port] = entry
        trit = 0 if entry["status"] == "degraded" else -1
        _health_record(name, entry["status"], elapsed_ms)
        return {"port": port, "name": name, "status": entry["status"],
                "trit": trit, "response_ms": round(elapsed_ms, 1),
                "consecutive_failures": entry["consecutive_failures"]}


def _check_all_services():
    """Check all known services in parallel using ThreadPoolExecutor(max_workers=H7).
    Returns summary: total, healthy, degraded, dead, overall_trit, services list."""
    import concurrent.futures
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=H7) as pool:
        futures = {pool.submit(_check_service_health, port, name): (port, name)
                   for port, name in KNOWN_SERVICES.items()}
        for f in concurrent.futures.as_completed(futures):
            try:
                results.append(f.result())
            except Exception:
                port, name = futures[f]
                results.append({"port": port, "name": name, "status": "dead",
                                "trit": -1, "response_ms": 0, "consecutive_failures": 99})
    # Sort by port for consistent output
    results.sort(key=lambda r: r["port"])
    healthy = sum(1 for r in results if r["trit"] == 1)
    degraded = sum(1 for r in results if r["trit"] == 0)
    dead = sum(1 for r in results if r["trit"] == -1)
    overall_trit = _merge_ternary([r["trit"] for r in results]) if results else -1
    return {
        "total": len(results), "healthy": healthy, "degraded": degraded, "dead": dead,
        "overall_trit": overall_trit,
        "bt": _bt_string([r["trit"] for r in results]),
        "services": results,
    }


def _attempt_recovery(port, name):
    """Attempt to recover a dead/degraded service by restarting it.
    Respects RECOVERY_COOLDOWN. Returns trit: +1=recovered, 0=attempted, -1=failed/cooldown."""
    import socket, subprocess as _sp
    now = time.time()
    # Check cooldown
    with _health_lock:
        entry = _service_health.get(port, {})
        last_recovery = entry.get("last_recovery", 0)
        if now - last_recovery < RECOVERY_COOLDOWN:
            return {"port": port, "name": name, "trit": -1, "status": "cooldown",
                    "cooldown_remaining": round(RECOVERY_COOLDOWN - (now - last_recovery))}
    # Find the service in BOOT_ORDER
    svc = next((s for s in BOOT_ORDER if s["port"] == port), None)
    if not svc:
        return {"port": port, "name": name, "trit": -1, "status": "unknown_service"}
    # Check if port is already occupied
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1.0)
            if s.connect_ex(("127.0.0.1", port)) == 0:
                # Port is occupied — service may be hung, try kill first
                _kill_port_zombies(port)
                time.sleep(0.5)
    except Exception:
        pass
    # Attempt restart
    try:
        _cmd = list(svc["cmd"])
        if _cmd and ("python" in _cmd[0].lower()) and ("pythonw" not in _cmd[0].lower()):
            _cmd[0] = r"C:\Users\Jupit\AppData\Local\Programs\Python\Python312\python.exe"
        _si = _sp.STARTUPINFO()
        _si.dwFlags |= _sp.STARTF_USESHOWWINDOW
        _si.wShowWindow = 0
        _proc = _sp.Popen(_cmd, stdout=_sp.DEVNULL, stderr=_sp.DEVNULL,
                   stdin=_sp.DEVNULL, creationflags=_CREATE_NO_WINDOW,
                   startupinfo=_si, close_fds=True)
        _CHILD_PROCS.append(_proc)
        # Record recovery attempt
        with _health_lock:
            entry = _service_health.get(port, {
                "status": "degraded", "consecutive_failures": 0,
                "last_check": 0, "last_recovery": 0, "response_ms": 0.0,
            })
            entry["last_recovery"] = now
            entry["consecutive_failures"] = 0
            entry["status"] = "degraded"  # Will be updated on next health check
            _service_health[port] = entry
        return {"port": port, "name": name, "trit": 0, "status": "recovery_attempted",
                "pid": _proc.pid}
    except Exception as e:
        return {"port": port, "name": name, "trit": -1, "status": "recovery_failed",
                "error": str(e)[:100]}


# ── Service Restart Policies (3-5-7-13 Harmonic) ────────────────────────
# Per-service restart tracking: max retries, exponential backoff, crash history.
_restart_policy = {
    "max_retries": H5,                  # 5 attempts before giving up
    "base_cooldown": H7 * 10,           # 70s base (grows exponentially)
    "max_cooldown": H13 * H7 * 60,      # 91 minutes max backoff cap
    "history_max": H13 * H3,            # 39 crash events per service
}
_restart_tracker = {}   # {port: {attempts, last_attempt, backoff_s, crashes: deque}}
_restart_lock = threading.Lock()

def _get_restart_backoff(port):
    """Exponential backoff: base * 2^attempts, capped at max_cooldown."""
    with _restart_lock:
        t = _restart_tracker.get(port, {"attempts": 0, "last_attempt": 0, "backoff_s": 0})
    base = _restart_policy["base_cooldown"]
    backoff = min(base * (2 ** t["attempts"]), _restart_policy["max_cooldown"])
    return backoff

def _record_restart_attempt(port, success):
    """Track restart attempt. Resets on success, increments on failure."""
    now = time.time()
    with _restart_lock:
        t = _restart_tracker.setdefault(port, {
            "attempts": 0, "last_attempt": 0, "backoff_s": 0,
            "crashes": collections.deque(maxlen=_restart_policy["history_max"]),
            "total_restarts": 0, "total_failures": 0,
        })
        t["last_attempt"] = now
        if success:
            t["attempts"] = 0
            t["backoff_s"] = 0
            t["total_restarts"] += 1
        else:
            t["attempts"] += 1
            t["backoff_s"] = _get_restart_backoff(port)
            t["total_failures"] += 1
            t["crashes"].append({"time": now, "attempt": t["attempts"]})

def _can_restart(port):
    """Check if service can be restarted (within retry limit and past backoff)."""
    with _restart_lock:
        t = _restart_tracker.get(port, {"attempts": 0, "last_attempt": 0, "backoff_s": 0})
    if t["attempts"] >= _restart_policy["max_retries"]:
        return False, "max_retries_exceeded"
    elapsed = time.time() - t["last_attempt"]
    if elapsed < t["backoff_s"]:
        return False, f"backoff ({int(t['backoff_s'] - elapsed)}s remaining)"
    return True, "ok"


# ── Background Health Monitor Thread ─────────────────────────────────────
# Runs every HEALTH_CHECK_INTERVAL (65s), checks all services in parallel,
# auto-recovers dead services that pass restart policy checks.
_health_monitor_running = False

def _health_monitor_loop():
    """Background thread: periodic health check + auto-recovery for dead services.
    SAFETY: Caps auto-recovery to H3=3 services per cycle to prevent system overload.
    If more than half the fleet is dead, skip recovery entirely (likely a mass crash)."""
    global _health_monitor_running
    _health_monitor_running = True
    # Initial delay: let services boot first
    time.sleep(H13 * H3)  # 39s warmup
    _MAX_RECOVERY_PER_CYCLE = 0  # DISABLED — auto-recovery was causing zombie spawn loops with pythonw. Manual boot only.
    while _health_monitor_running:
        try:
            result = _check_all_services()
            total = result.get("total", 0)
            dead_services = [s for s in result.get("services", []) if s["trit"] == -1]
            # SAFETY: If more than half the fleet is dead, don't auto-recover.
            # This prevents the freeze loop where mass boot fails and health monitor
            # keeps respawning 80+ services every 65 seconds.
            if total > 0 and len(dead_services) > total // 2:
                time.sleep(HEALTH_CHECK_INTERVAL)
                continue
            recovered = 0
            for svc in dead_services:
                if recovered >= _MAX_RECOVERY_PER_CYCLE:
                    break  # Cap reached — wait for next cycle
                port = svc["port"]
                name = svc["name"]
                can_do, reason = _can_restart(port)
                if not can_do:
                    continue
                recovery = _attempt_recovery(port, name)
                if recovery.get("trit", -1) >= 0:
                    # Wait briefly and verify
                    time.sleep(H3)
                    recheck = _check_service_health(port, name)
                    if recheck.get("trit", -1) == 1:
                        _record_restart_attempt(port, True)
                        _cb_record_success(port)
                        recovered += 1
                    else:
                        _record_restart_attempt(port, False)
                        _cb_record_failure(port)
                else:
                    _record_restart_attempt(port, False)
        except Exception:
            pass  # Health monitor must never crash
        time.sleep(HEALTH_CHECK_INTERVAL)


def _start_health_monitor():
    """Start background health monitor as daemon thread."""
    t = threading.Thread(target=_health_monitor_loop, daemon=True, name="health-monitor")
    t.start()
    return t


# Orchestrator traffic tracking for Reynolds
_orch_stats = {'requests': 0, 'request_times': [], 'route_trits': []}
_orch_stats_lock = threading.Lock()

# ── Request Audit Log (ring buffer of last H13*H7=91 requests) ──────────
_audit_log = collections.deque(maxlen=H13 * H7)  # 91 entries
_audit_lock = threading.Lock()
_audit_enabled = True

def _audit_record(method, path, status, latency_ms, trit=None):
    """Record a request in the audit log."""
    if not _audit_enabled:
        return
    entry = {
        'ts': time.time(),
        'method': method,
        'path': path,
        'status': status,
        'latency_ms': round(latency_ms, 1),
        'trit': trit,
    }
    with _audit_lock:
        _audit_log.append(entry)

# ── Ternary Rate Limiter (H5 requests per H3 seconds per IP) ──────────
_rate_window = {}  # {ip: deque of timestamps}
_rate_lock = threading.Lock()
RATE_LIMIT = H5       # 5 requests per window
RATE_WINDOW_S = H3    # 3 second window
# Exempt internal + health routes from rate limiting
_RATE_EXEMPT = frozenset(('127.0.0.1', '::1', 'localhost'))
_RATE_EXEMPT_PATHS = ('/health', '/status', '/api/services/', '/socket.io/')

@app.before_request
def _rate_limit_check():
    ip = request.remote_addr or '127.0.0.1'
    path = request.path
    # Exempt local + health/service routes
    if ip in _RATE_EXEMPT:
        return None
    if any(path.startswith(p) for p in _RATE_EXEMPT_PATHS):
        return None
    now = time.time()
    with _rate_lock:
        if ip not in _rate_window:
            _rate_window[ip] = collections.deque()
        dq = _rate_window[ip]
        # Prune expired entries
        cutoff = now - RATE_WINDOW_S
        while dq and dq[0] < cutoff:
            dq.popleft()
        if len(dq) >= RATE_LIMIT:
            return jsonify({"ok": False, "error": "Rate limited", "trit": -1,
                            "limit": RATE_LIMIT, "window_s": RATE_WINDOW_S}), 429
        dq.append(now)
    return None

@app.before_request
def _audit_start():
    """Mark request start time for audit latency calculation."""
    request._audit_start = time.time()

@app.after_request
def _audit_log_request(response):
    """Log every request to the audit ring buffer."""
    start = getattr(request, '_audit_start', time.time())
    latency = (time.time() - start) * 1000
    trit = 1 if response.status_code < 400 else (0 if response.status_code < 500 else -1)
    _audit_record(request.method, request.path, response.status_code, latency, trit)
    return response

# Initialize Arbiter with driver bus
arbiter = Arbiter(bus)

# Register subsystems with persistence layer
persistence.register("hive_mind",
    save_fn=lambda: {"models": {uid: m.to_dict() for uid, m in hive_mind.models.items()},
                     "query_history": hive_mind.query_history[-100:]},
    load_fn=lambda d: None)  # hive_mind loads its own state
persistence.register("gameplay",
    save_fn=lambda: {k: v.to_dict() for k, v in gameplay_learner.skill_graph.items()},
    load_fn=lambda d: None)
persistence.register("workspace_watch",
    save_fn=lambda: {"feed": list(workspace_watch.activity_feed)[-100:],
                     "model_health": workspace_watch.model_health},
    load_fn=lambda d: None)
persistence.register("routing_stats",
    save_fn=lambda: get_stats(),
    load_fn=lambda d: None)
persistence.start_auto_save(interval=60)

# ─────────────────────────────────────────────
# HEALTH & STATUS
# ─────────────────────────────────────────────

@app.get("/")
def index():
    try:
        return send_from_directory(str(STATIC), "index.html")
    except Exception:
        return jsonify({"status": "NovaX Orchestrator running", "version": VERSION})


@app.get("/health")
def health():
    uptime = time.time() - START_TIME
    # Ternary self-health: +1 if stable (>60s uptime), 0 if warming up, -1 if just started
    self_trit = 1 if uptime > 60 else (0 if uptime > 5 else -1)
    # Reynolds: requests per minute
    elapsed = max(1, uptime)
    rpm = _orch_stats['requests'] / (elapsed / 60)
    regime = 'laminar' if rpm < RE_LAMINAR else ('transitional' if rpm < RE_TRANSITION else ('turbulent' if rpm < RE_TURBULENT else 'chaotic'))
    with _orch_stats_lock:
        _orch_stats['requests'] += 1
    return jsonify({
        "status": "ok",
        "version": VERSION,
        "ternary": True,
        "harmonics": {"H3": H3, "H5": H5, "H7": H7, "H13": H13},
        "uptime": round(uptime, 2),
        "uptime_human": _fmt_uptime(uptime),
        "self_trit": self_trit,
        "self_char": '1' if self_trit == 1 else '0' if self_trit == 0 else 'T',
        "reynolds": int(rpm),
        "flow_regime": regime,
    })


@app.get("/api/status")
def api_status():
    vcc = get_vcc_status()
    return jsonify({
        "version": VERSION,
        "uptime": round(time.time() - START_TIME, 2),
        "services": vcc,
        "skills_count": len(load_skills()),
    })


@app.get("/api/vcc")
def api_vcc():
    return jsonify(get_vcc_status())


@app.get("/api/vcc/summary")
def api_vcc_summary():
    return jsonify({"summary": vcc_summary()})


# ─────────────────────────────────────────────
# RAG CONTEXT BUILDER — Enriches every AI query
# ─────────────────────────────────────────────

def _build_enriched_context(text, task_type=None):
    """
    Build enriched context for ALL models in the HiveMind.
    Searches Super Archive, gathers skills, includes conversation,
    injects gameplay learner insights, and system state.
    Returns (system_prompt: str, conversation_messages: list[dict])
    """
    parts = [NOVAX_SYSTEM_PROMPT]

    # 1. System state (CPU, RAM, apps, tools)
    sys_ctx = format_for_prompt()
    parts.append(f"\n[System State]\n{sys_ctx}")
    parts.append(f"Active Profile: {active_profile()}")

    # 2. RAG — Auto-search Super Archive for relevant knowledge
    try:
        archive_results = archive_search(text, limit=5)
        hits = archive_results.get("results", [])
        if hits:
            snippets = []
            for h in hits[:5]:
                src = h.get("source", "?")
                snip = h.get("snippet", "")[:300]
                snippets.append(f"  [{src}] {snip}")
            parts.append(f"\n[Relevant Knowledge from Archive]\n" + "\n".join(snippets))
    except Exception:
        pass

    # 3. Matched skills — inject as known solutions
    try:
        skill = match_skill(text)
        if skill:
            skill_name = skill.get("name", "")
            skill_steps = skill.get("steps", [])
            steps_text = "; ".join(
                f"{s.get('driver','')}.{s.get('action','')}" for s in skill_steps[:5]
            )
            parts.append(f"\n[Known Skill: {skill_name}]\nSteps: {steps_text}")
    except Exception:
        pass

    # 4. Gameplay learner — inject best-action insight
    try:
        if task_type:
            best = gameplay_learner.best_action(task_type)
            if best:
                parts.append(
                    f"\n[Learned Strategy ({int(best['confidence']*100)}% success)]\n{best['action']}"
                )
    except Exception:
        pass

    # 5. Current mode context
    try:
        current_mode = mode_system.get_mode_config()
        if current_mode:
            mode_name = current_mode.get("name", "general")
            parts.append(f"\n[Active Mode: {mode_name}]")
    except Exception:
        pass

    # 6. Script Portal — search for relevant packages/libraries/tools
    try:
        import urllib.request, urllib.parse
        # Quick keyword extraction: take significant words from query
        code_keywords = [w for w in text.lower().split() if len(w) > 3 and w not in
                         ("what", "how", "does", "this", "that", "with", "from", "about",
                          "could", "would", "should", "make", "help", "please", "want",
                          "need", "give", "tell", "know", "think", "like", "just")]
        if code_keywords and task_type in ("code", "tool", "config", "research", None):
            search_q = " ".join(code_keywords[:3])
            # npm quick search
            npm_url = f"https://registry.npmjs.org/-/v1/search?text={urllib.parse.quote(search_q)}&size=3"
            try:
                r = urllib.request.urlopen(npm_url, timeout=4)
                npm_data = json.loads(r.read())
                npm_pkgs = []
                for obj in npm_data.get("objects", [])[:3]:
                    p = obj.get("package", {})
                    npm_pkgs.append(f"  npm: {p.get('name')} — {(p.get('description') or '')[:80]}")
                if npm_pkgs:
                    parts.append(f"\n[Script Portal — Relevant Packages]\n" + "\n".join(npm_pkgs))
            except Exception:
                pass
            # PyPI quick search
            pypi_url = f"https://pypi.org/pypi/{urllib.parse.quote(code_keywords[0])}/json"
            try:
                r = urllib.request.urlopen(pypi_url, timeout=4)
                pypi_data = json.loads(r.read())
                info = pypi_data.get("info", {})
                if info.get("name"):
                    parts.append(f"  pypi: {info['name']} v{info.get('version','')} — {(info.get('summary') or '')[:80]}")
            except Exception:
                pass
    except Exception:
        pass

    system_prompt = "\n".join(parts)

    # 6. Conversation history — format as messages list for multi-turn models
    conversation_messages = []
    try:
        raw_convo = get_conversation()
        if raw_convo and isinstance(raw_convo, list):
            # Keep last 20 messages to stay within token limits
            for msg in raw_convo[-20:]:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role in ("user", "assistant") and content:
                    conversation_messages.append({"role": role, "content": content[:2000]})
    except Exception:
        pass

    # Ensure the current user message is the last message
    if not conversation_messages or conversation_messages[-1].get("content") != text:
        conversation_messages.append({"role": "user", "content": text})

    return system_prompt, conversation_messages


# ─────────────────────────────────────────────
# CORE AI - TWO PHASE INTENT SYSTEM
# ─────────────────────────────────────────────

@app.post("/think")
def think():
    """
    Universal Prompt — ALL queries go through the Agent Loop first
    (Claude with real tools: read/write files, run commands, search code).
    Falls back to HiveMind if agent loop fails.
    Voice always responds.
    """
    data = request.get_json() or {}
    text = data.get("text", "").strip()
    req_mode = data.get("mode")  # "speed" for voice commands
    if not text:
        return jsonify({"reply": "Say something!", "actions": []})

    add_message("user", text)
    auto_save_context(current_goal=text[:200])
    start = time.time()

    # ── Voice speed mode: skip EVERYTHING, go straight to fastest model ──
    if req_mode == 'speed':
        try:
            from nova_persona import NOVA_VOICE_SYSTEM_PROMPT
            hive_result = hive_mind.fan_out(text, max_models=4, timeout=12, mode="speed", system=NOVA_VOICE_SYSTEM_PROMPT)
            reply = hive_result.get("consensus", "") if hive_result.get("ok") else ""
            if not reply:
                reply = "Sorry, I couldn't process that. Try again."
            add_message("assistant", reply)
            duration = round(time.time() - start, 2)
            return jsonify({
                "reply": reply, "model": hive_result.get("fastest_model", "hive"),
                "task": "voice", "mode": "speed", "profile": active_profile(),
                "duration": duration, "optionA": None, "optionB": None,
            })
        except Exception as e:
            return jsonify({"reply": f"Error: {e}", "model": "error", "duration": 0})
    else:
        # ── UNIVERSAL: Try agent loop FIRST (Claude with tools) ──────────
        try:
            agent_result = agent_loop(text)
            if agent_result.get("ok") and agent_result.get("reply"):
                reply = agent_result["reply"]
                add_message("assistant", reply)
                duration = round(time.time() - start, 2)
                try:
                    speak(_voice_clean(reply), blocking=False, voice_id="en-US-AvaNeural")
                except Exception:
                    pass
                return jsonify({
                    "reply": reply,
                    "optionA": None,
                    "optionB": None,
                    "model": f"nova-agent ({agent_result.get('iterations', 1)} steps)",
                    "task": "agent",
                    "mode": "agent",
                    "profile": active_profile(),
                    "duration": duration,
                    "agent": True,
                    "actions": agent_result.get("actions", []),
                })
        except Exception as e:
            print(f"[think] Agent loop failed, falling back to HiveMind: {e}")

    # 1. Classify intent
    task_type = classify(text)

    # 2. Check for matching skill → Option A
    skill = match_skill(text)
    option_a = None
    if skill:
        suggestion_level = get_skill_suggestion_level(skill["id"])
        option_a = {
            "source": "skill",
            "skill_id": skill["id"],
            "name": skill["name"],
            "actions": skill.get("steps", []),
            "confidence": skill.get("confidence", 1.0 / 3),
            "suggestion_level": suggestion_level,
        }

    # 3. Auto-switch mode based on context
    mode_system.auto_switch(text)

    # 4. Build enriched context (RAG search + skills + conversation + learner)
    enriched_system, enriched_convo = _build_enriched_context(text, task_type)

    # 5. Route to best model (for tracking/display, HiveMind queries all anyway)
    model, task, mode = route_with_fallback(text)
    workspace_watch.record_query_start(f"think-{start}", model, text[:100])

    # 6. Get AI response — HiveMind PRIMARY with enriched context
    reply = None

    if model == "executor":
        # System execution bypasses AI — direct command
        reply = json.dumps({
            "reply": f"Executing system task: {text}",
            "actions": [{"driver": "terminal", "action": "run_command",
                         "params": {"cmd": text}, "risk": classify_risk("terminal", "run_command")}]
        })
    else:
        # PRIMARY: HiveMind fan-out — speed mode for voice, synthesis for text
        hive_mode = req_mode or "synthesis"
        hive_max = 4 if hive_mode == "speed" else 15
        hive_timeout = 15 if hive_mode == "speed" else 60
        hive_result = hive_mind.fan_out(
            text, max_models=hive_max, timeout=hive_timeout,
            system=enriched_system, conversation=enriched_convo,
            mode=hive_mode
        )
        if hive_result.get("ok") and hive_result.get("consensus"):
            reply = hive_result["consensus"]
            synth = hive_result.get("synthesis_model")
            n_models = hive_result.get('models_succeeded', 0)
            hive_model = hive_result.get("fastest_model", "hive_mind")
            if synth:
                model = f"hive_mind ({n_models} models, synthesized by {synth})"
            else:
                model = f"hive_mind ({n_models} models)"
            # Feed best model back into routing learning
            record(task, hive_model, True, hive_result.get("total_time", 5.0))

        # FALLBACK 1: Direct Claude with enriched context
        if not reply:
            reply = ask_claude_with_context(
                enriched_convo, system=enriched_system, max_tokens=8192
            )
            if reply and ("[Error" in reply or "[ERROR" in reply or "[Claude" in reply):
                reply = None
            elif reply:
                model = "claude (fallback)"

        # FALLBACK 2: Cloud Router
        if not reply:
            cr_result = _proxy_post("http://127.0.0.1:9878/api/v1/query",
                {"prompt": text, "providers": ["openai"]})
            if cr_result.get("succeeded", 0) > 0:
                reply = cr_result["best"]["resp"]
                model = "gpt-4o (fallback)"

        # FALLBACK 3: Direct Ollama with enriched prompt
        if not reply:
            enriched_prompt = f"{enriched_system}\n\n{text}"
            reply = _ask_ollama(enriched_prompt, "novax-mistral")
            if reply:
                model = "novax-mistral (fallback)"

    query_ok = True
    if not reply and model != "executor":
        reply = "All AI models unavailable. Configure providers in AI & API Setup."
        query_ok = False

    add_message("assistant", reply)
    duration = time.time() - start
    record(task, model.split(" (")[0], query_ok, duration)
    workspace_watch.record_query_complete(f"think-{start}", model.split(" (")[0], query_ok, int(duration * 1000), (reply or "")[:100])

    # Parse structured AI response
    option_b_actions = []
    try:
        parsed = json.loads(reply)
        if isinstance(parsed, dict):
            reply = parsed.get("reply", reply)
            option_b_actions = parsed.get("actions", [])
    except (json.JSONDecodeError, TypeError):
        pass

    option_b = {
        "source": "ai",
        "model": model,
        "actions": option_b_actions,
    }

    # Add risk levels to all actions
    for opt in [option_a, option_b]:
        if opt:
            for act in opt.get("actions", []):
                if "risk" not in act:
                    act["risk"] = classify_risk(
                        act.get("driver", "terminal"),
                        act.get("action", "")
                    )

    # Record temporal event
    record_event(text, [task_type, model], size="small" if len(text) < 50 else "medium")

    # Voice auto-speak only for typed prompts (not voice commands — frontend handles TTS)
    if req_mode != 'speed':
        try:
            speak(_voice_clean(reply or ""), blocking=False, voice_id="en-US-AvaNeural")
        except Exception:
            pass

    return jsonify({
        "reply": reply,
        "optionA": option_a,
        "optionB": option_b,
        "model": model,
        "task": task_type,
        "mode": mode,
        "profile": active_profile(),
        "duration": round(duration, 3),
    })


@app.post("/nova/agent")
def nova_agent():
    """
    Agentic loop — Claude with real tools (read/write files, run commands).
    Same capability as Claude Code, running inside NovaX.
    """
    data = request.get_json() or {}
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"reply": "Say something!", "actions": [], "ok": False})
    add_message("user", text)
    start = time.time()
    result = agent_loop(text)
    if result.get("reply"):
        add_message("assistant", result["reply"])
        # Voice always responds
        try:
            speak(_voice_clean(result["reply"]), blocking=False, voice_id="en-US-AvaNeural")
        except Exception:
            pass
    result["duration"] = round(time.time() - start, 2)
    return jsonify(result)


# ── Claude Code → NovaX Output Relay ─────────────────────────────────
# All heavy output from Claude Code sessions flows here instead of
# filling up the CLI context window. Ternary-compressed storage.
_output_stream = []  # ring buffer of output chunks
_OUTPUT_MAX = 500    # keep last 500 chunks

@app.post("/nova/output")
def nova_output():
    """Receive output from Claude Code — display in Nova, store compressed."""
    data = request.get_json() or {}
    text = data.get("text", "")
    label = data.get("label", "claude-code")
    level = data.get("level", "info")  # info, result, error, tool
    ts = time.strftime("%H:%M:%S")
    chunk = {"text": text, "label": label, "level": level, "ts": ts,
             "id": len(_output_stream)}
    _output_stream.append(chunk)
    if len(_output_stream) > _OUTPUT_MAX:
        _output_stream.pop(0)
    # Push to connected WebSocket clients instantly
    try:
        socketio.emit("output_chunk", chunk)
    except Exception:
        pass
    # Compress to TBuffer if available
    try:
        _proxy_post("http://127.0.0.1:9886/store", {
            "prompt": f"[{label}] {ts}", "response": text[:2000],
            "channel": "CODE"
        })
    except Exception:
        pass
    return jsonify({"ok": True, "id": chunk["id"]})

@app.get("/nova/output")
def nova_output_get():
    """Get recent output stream (for UI polling)."""
    since = request.args.get("since", 0, type=int)
    chunks = [c for c in _output_stream if c["id"] > since]
    return jsonify({"chunks": chunks, "total": len(_output_stream)})

@app.delete("/nova/output")
def nova_output_clear():
    """Clear the output stream."""
    _output_stream.clear()
    return jsonify({"ok": True})


@app.post("/execute")
def execute():
    """
    Phase 2: Execute an approved action plan
    Returns results of each action
    """
    data = request.get_json() or {}
    actions = data.get("actions", [])
    
    if not actions:
        return jsonify({"ok": False, "error": "No actions provided"})
    
    results = []
    max_retries = int(data.get("retries", 1))
    for act in actions:
        driver = act.get("driver", "terminal")
        action = act.get("action", "")
        params = act.get("params", {})

        attempt = 0
        result = None
        while attempt < max_retries:
            attempt += 1
            result = bus.execute(driver, action, params)
            if result.ok:
                break
            if attempt < max_retries:
                print(f"[ORCH] Retrying {driver}.{action} (attempt {attempt+1}/{max_retries})")
                time.sleep(1.0 / 3)  # H3 harmonic retry interval
        record_action(driver, action, params, result.ok)

        results.append({
            "driver": driver,
            "action": action,
            "ok": result.ok,
            "output": result.output[:5000],  # Cap output size
            "error": result.error,
            "attempts": attempt,
        })
    
    # Check if we detected a project environment
    learn = analyze_for_project()
    
    response = {"ok": True, "results": results}
    if learn:
        response["learn_candidate"] = learn
    
    return jsonify(response)


# ─────────────────────────────────────────────
# COMMAND EXECUTION (LEGACY COMPATIBLE)
# ─────────────────────────────────────────────

@app.post("/api/run")
@app.post("/api/exec")
def api_run():
    """Direct command execution - compatible with hivemind.html"""
    data = request.get_json() or {}
    cmd = data.get("cmd") or data.get("command", "")
    code = data.get("code", "")
    
    if code:
        result = bus.execute("terminal", "run_python", {"code": code})
    elif cmd:
        result = bus.execute("terminal", "run_command", {"cmd": cmd})
    else:
        return jsonify({"ok": False, "output": "No command provided"})
    
    return jsonify({"ok": result.ok, "output": result.output, "error": result.error})


@app.post("/api/execute")
def api_execute_cmd():
    data = request.get_json() or {}
    cmd = data.get("cmd", "")
    result = bus.execute("terminal", "run_command", {"cmd": cmd})
    return jsonify({"ok": result.ok, "out": result.output, "error": result.error})


# ─────────────────────────────────────────────
# FILE SYSTEM API
# ─────────────────────────────────────────────

@app.get("/api/fs/list")
def fs_list():
    path = request.args.get("path", r"C:\NovaX")
    if not _safe_path(path):
        return jsonify({"ok": False, "error": "Path outside allowed roots"}), 403
    result = bus.execute("file", "list_dir", {"path": path})
    if result.ok:
        return jsonify({"ok": True, "files": json.loads(result.output)})
    return jsonify({"ok": False, "error": result.error})


@app.post("/api/fs/read")
def fs_read():
    data = request.get_json() or {}
    path = data.get("path", "")
    if not _safe_path(path):
        return jsonify({"ok": False, "error": "Path outside allowed roots"}), 403
    result = bus.execute("file", "read_file", {"path": path})
    return jsonify({"ok": result.ok, "content": result.output, "error": result.error})


@app.post("/api/fs/write")
def fs_write():
    data = request.get_json() or {}
    path = data.get("path", "")
    if not _safe_path(path):
        return jsonify({"ok": False, "error": "Path outside allowed roots"}), 403
    result = bus.execute("file", "write_file", {
        "path": path,
        "content": data.get("content", ""),
        "append": data.get("append", False),
    })
    return jsonify({"ok": result.ok, "output": result.output, "error": result.error})


@app.delete("/api/fs/delete")
def fs_delete():
    data = request.get_json() or {}
    path = data.get("path", "")
    if not _safe_path(path):
        return jsonify({"ok": False, "error": "Path outside allowed roots"}), 403
    result = bus.execute("file", "delete_file", {"path": path})
    return jsonify({"ok": result.ok, "output": result.output})


# ─────────────────────────────────────────────
# AI ROUTING API
# ─────────────────────────────────────────────

@app.post("/api/claude")
def api_claude():
    """Direct Claude API call - no extension, no Brave shields"""
    data = request.get_json() or {}
    text = data.get("text", data.get("prompt", ""))
    reply = ask_claude(text)
    return jsonify({"reply": reply, "model": "claude"})


@app.get("/api/routing/stats")
def routing_stats():
    return jsonify(get_stats())


@app.get("/api/routing/rules")
def routing_rules():
    return jsonify(DEFAULT_RULES)


@app.post("/api/routing/record")
def routing_record():
    data = request.get_json() or {}
    record(data.get("task", "general"), data.get("model", "claude"),
           data.get("success", True), data.get("time", 1.0))
    return jsonify({"ok": True})


@app.get("/api/routing/history")
def routing_history():
    """Recent routing decisions (time-series log)."""
    limit = int(request.args.get("limit", 30))
    return jsonify({"ok": True, "history": get_history(limit)})


@app.get("/api/routing/dashboard")
def routing_dashboard():
    """Full routing history dashboard — ranked models, task routing, trends."""
    return jsonify({"ok": True, **get_dashboard()})


@app.get("/api/circuit-breakers")
def route_circuit_breakers():
    """View all circuit breaker states. Ternary: +1=all closed, 0=some half-open, -1=any open."""
    with _cb_lock:
        breakers = []
        for name, cb in _circuit_breakers.items():
            breakers.append({
                'service': name, 'state': cb['state'],
                'state_name': _cb_state_name(cb['state']),
                'failures': cb['failures'], 'successes': cb['successes'],
                'total_trips': cb['total_trips'],
                'last_failure': cb['last_failure'], 'last_success': cb['last_success'],
            })
    states = [b['state'] for b in breakers]
    trit = _merge_ternary(states) if states else 1
    return jsonify({'ok': True, 'breakers': breakers, 'total': len(breakers),
                    'open': sum(1 for s in states if s == -1),
                    'half_open': sum(1 for s in states if s == 0),
                    'closed': sum(1 for s in states if s == 1),
                    'trit': trit})

@app.get("/api/audit")
def route_audit_log():
    """View recent request audit log. Ternary: +1=all ok, 0=some errors, -1=many errors."""
    limit = request.args.get('limit', 50, type=int)
    path_filter = request.args.get('path', '')
    with _audit_lock:
        entries = list(_audit_log)
    if path_filter:
        entries = [e for e in entries if path_filter in e['path']]
    entries = entries[-limit:]
    trits = [e.get('trit', 0) for e in entries if e.get('trit') is not None]
    errors = sum(1 for t in trits if t < 0)
    trit = 1 if errors == 0 else (0 if errors < len(trits) // 3 else -1)
    return jsonify({'ok': True, 'entries': entries, 'total': len(entries),
                    'errors': errors, 'trit': trit})

@app.post("/api/circuit-breakers/reset")
def route_circuit_breaker_reset():
    """Reset circuit breaker(s). POST {service:"name"} for one, or {} to reset all."""
    data = request.get_json(silent=True) or {}
    name = data.get('service', '')
    with _cb_lock:
        if name:
            if name in _circuit_breakers:
                _circuit_breakers[name] = {
                    'state': 1, 'failures': 0, 'successes': 0,
                    'last_failure': 0, 'last_success': 0,
                    'half_open_at': 0, 'half_open_attempts': 0,
                    'total_trips': _circuit_breakers[name].get('total_trips', 0),
                }
                return jsonify({'ok': True, 'service': name, 'state': 'CLOSED', 'trit': 1})
            return jsonify({'ok': False, 'error': f'breaker {name} not found', 'trit': -1})
        else:
            # Reset ALL circuit breakers
            count = len(_circuit_breakers)
            for svc_name, cb in _circuit_breakers.items():
                _circuit_breakers[svc_name] = {
                    'state': 1, 'failures': 0, 'successes': 0,
                    'last_failure': 0, 'last_success': 0,
                    'half_open_at': 0, 'half_open_attempts': 0,
                    'total_trips': cb.get('total_trips', 0),
                }
            return jsonify({'ok': True, 'reset': 'all', 'count': count, 'state': 'CLOSED', 'trit': 1})

@app.get("/api/routing/analytics")
def routing_analytics():
    """N-S flow analytics for query routing — per-model Re, regime, recommendations."""
    import math
    H3, H5, H7, H13 = 3, 5, 7, 13
    RE_LAM, RE_TRANS, RE_TURB = H3**3, H5**3, H7**3

    stats = get_stats()
    dashboard = get_dashboard()
    ranked = dashboard.get("models_ranked", [])

    # Compute per-model routing Reynolds number
    # Re_route = (success_rate * throughput * task_breadth) / latency_variability
    model_flows = []
    for m in ranked:
        name = m["model"]
        runs = m["runs"]
        sr = m["success_rate"]
        avg_ms = max(m["avg_ms"], 1)
        tasks = m["tasks"]
        throughput = runs / max((time.time() - START_TIME), 1)  # queries/sec lifetime
        breadth = len(tasks) / max(len(stats) - 4, 1)  # fraction of task types covered
        mu = max(avg_ms / 1000, 0.01)
        Re = (sr * throughput * 1000 * max(breadth, 0.1)) / mu
        if Re < RE_LAM:
            regime = "laminar"
        elif Re < RE_TRANS:
            regime = "transitional"
        elif Re < RE_TURB:
            regime = "turbulent"
        else:
            regime = "chaotic"
        model_flows.append({
            "model": name, "Re": round(Re, 2), "regime": regime,
            "runs": runs, "success_rate": sr, "avg_ms": avg_ms,
            "task_breadth": round(breadth, 3), "tasks": tasks,
            "trit": 1 if regime in ("turbulent", "chaotic") else (0 if regime == "transitional" else -1),
        })
    model_flows.sort(key=lambda x: x["Re"], reverse=True)

    # Regime distribution
    regimes = {"laminar": 0, "transitional": 0, "turbulent": 0, "chaotic": 0}
    for mf in model_flows:
        regimes[mf["regime"]] += 1

    # Task coverage analysis
    task_routing = dashboard.get("task_routing", {})
    covered = sum(1 for t in task_routing.values() if t.get("using_learned"))
    total_tasks = len(task_routing)

    # Recommendations
    recs = []
    cold = [mf for mf in model_flows if mf["regime"] == "laminar" and mf["runs"] > 0]
    if cold:
        recs.append(f"{len(cold)} model(s) in laminar regime — underutilized or slow")
    hot = [mf for mf in model_flows if mf["regime"] in ("turbulent", "chaotic")]
    if hot:
        recs.append(f"{len(hot)} model(s) in turbulent+ regime — high performers")
    if covered < total_tasks:
        recs.append(f"{total_tasks - covered}/{total_tasks} task types still using default routing")
    total_runs = sum(mf["runs"] for mf in model_flows)
    overall_trit = 1 if len(hot) >= H3 else (0 if total_runs > 0 else -1)

    return jsonify({
        "ok": True,
        "model_flows": model_flows,
        "regime_distribution": regimes,
        "task_coverage": {"learned": covered, "total": total_tasks},
        "total_routed": total_runs,
        "recommendations": recs,
        "trit": overall_trit,
    })


@app.get("/api/tci/viz")
def tci_pipeline_viz():
    """Pipeline dependency graph visualization — ASCII tree rendering."""
    import requests as _rq
    try:
        r = _rq.get("http://127.0.0.1:9927/tci/depgraph", timeout=5)
        data = r.json()
    except Exception as e:
        return jsonify({"ok": False, "error": f"TCI unreachable: {e}"}), 503

    pipelines = data.get("pipelines", {})
    viz = {}
    for pname, pdata in pipelines.items():
        stages = pdata.get("stages", {})
        layers = pdata.get("layers", [])
        lines = [
            f"Pipeline: {pname} ({len(stages)} stages, {len(layers)} layers)",
            "=" * 40,
        ]
        for li, layer in enumerate(layers):
            lines.append("")
            lines.append(f"Layer {li} (parallel={len(layer)})")
            for si, sname in enumerate(layer):
                sinfo = stages.get(sname, {})
                deps = sinfo.get("deps", [])
                url = sinfo.get("url", "")
                method = sinfo.get("method", "POST")
                cache = sinfo.get("cacheable", False)
                connector = "  \\-" if si == len(layer) - 1 else "  |-"
                tag = " [CACHE]" if cache else " [NO-CACHE]"
                lines.append(f"{connector} [{sname}] {method} {url}{tag}")
                dep_str = ", ".join(deps) if deps else "(root)"
                lines.append(f"  |    deps: {dep_str}")
            if li < len(layers) - 1:
                lines.extend(["  |", "  V"])
            else:
                lines.extend(["  |", "  [DONE]"])
        viz[pname] = "\n".join(lines)

    pipeline_filter = request.args.get("pipeline", "")
    if pipeline_filter and pipeline_filter in viz:
        viz = {pipeline_filter: viz[pipeline_filter]}

    return jsonify({"ok": True, "viz": viz, "total_pipelines": len(viz), "trit": 1})


# ─────────────────────────────────────────────
# SKILLS API
# ─────────────────────────────────────────────

@app.get("/api/skills")
def api_skills():
    return jsonify(list_skills())


@app.post("/api/skills/match")
def api_skills_match():
    data = request.get_json() or {}
    skill = match_skill(data.get("text", ""))
    if skill:
        return jsonify({"found": True, "skill": skill})
    return jsonify({"found": False})


@app.post("/api/skills/save")
def api_skills_save():
    data = request.get_json() or {}
    save_skill(data.get("id", f"skill_{int(time.time())}"), data.get("skill", {}))
    return jsonify({"ok": True})


# ─────────────────────────────────────────────
# PROJECTS API
# ─────────────────────────────────────────────

@app.get("/api/projects")
def api_projects():
    return jsonify(get_projects())


@app.post("/api/project/save")
def project_save():
    data = request.get_json() or {}
    save_project(data.get("name", "project"), data.get("project", {}))
    return jsonify({"ok": True, "saved": data.get("name")})


@app.post("/api/project/suggest")
def project_suggest():
    data = request.get_json() or {}
    return jsonify({
        "reply": f'Project "{data.get("name")}" detected. Prepare workspace?',
        "actions": data.get("actions", []),
    })


# ─────────────────────────────────────────────
# SYSTEM INFO
# ─────────────────────────────────────────────

@app.get("/api/system")
def api_system():
    result = bus.execute("system", "get_system_info", {})
    try:
        info = json.loads(result.output)
    except (json.JSONDecodeError, TypeError):
        info = {}
    return jsonify({"ok": result.ok, "info": info})


@app.get("/api/processes")
def api_processes():
    import psutil
    procs = []
    for p in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_info']):
        try:
            info = p.info
            procs.append({
                "pid": info['pid'],
                "name": info['name'],
                "cpu": info.get('cpu_percent', 0) or 0,
                "memory": round((info.get('memory_info').rss if info.get('memory_info') else 0) / 1048576, 1)
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    procs.sort(key=lambda x: x['memory'], reverse=True)
    return jsonify(procs[:50])


# ─────────────────────────────────────────────
# CONVERSATION MEMORY
# ─────────────────────────────────────────────

@app.get("/api/conversation")
def api_conversation():
    return jsonify({"messages": get_conversation()})


@app.post("/api/conversation/clear")
def api_clear_conversation():
    clear_conversation()
    return jsonify({"ok": True})


# ─────────────────────────────────────────────
# SESSION CONTINUITY (Claude-reset survival)
# ─────────────────────────────────────────────

@app.get("/api/session/meta")
def api_session_meta():
    """Get current session metadata — who we are, where we left off."""
    return jsonify(get_session_meta())


@app.post("/api/session/meta")
def api_update_session_meta():
    """Update session metadata (working_on, active_tasks, etc.)."""
    data = request.get_json() or {}
    for key, val in data.items():
        update_session_meta(key, val)
    return jsonify({"ok": True, "meta": get_session_meta()})


@app.get("/api/session/resume")
def api_session_resume():
    """
    Get the full resume prompt — everything an AI needs to continue
    exactly where the last session left off. Includes conversation
    history, active tasks, working context, and system state.
    """
    resume_prompt = build_resume_prompt(max_messages=20)
    meta = get_session_meta()
    ctx = load_working_context()
    return jsonify({
        "ok": True,
        "resume_prompt": resume_prompt,
        "meta": meta,
        "working_context": ctx,
        "system_prompt": build_system_prompt(include_session=False),
    })


@app.post("/api/session/context")
def api_save_context():
    """Save current working context (what we're doing right now)."""
    data = request.get_json() or {}
    save_working_context(data)
    return jsonify({"ok": True})


@app.get("/api/session/context")
def api_get_context():
    """Get saved working context."""
    return jsonify(load_working_context())


@app.get("/api/session/history")
def api_session_history():
    """Get full conversation history (for session export/resume)."""
    limit = request.args.get("limit", 100, type=int)
    messages = get_conversation(limit)
    return jsonify({"messages": messages, "count": len(messages)})


@app.post("/api/session/export")
def api_session_export():
    """Export full session state — conversations, actions, context, meta.
    Used for backup, transfer to another provider, or cold storage."""
    return jsonify({
        "ok": True,
        "meta": get_session_meta(),
        "working_context": load_working_context(),
        "conversation": get_full_conversation(),
        "actions": get_session_actions(limit=500),
        "resume_prompt": build_resume_prompt(max_messages=30),
        "exported_at": time.time(),
    })


@app.post("/api/session/new")
def api_session_new():
    """Start a new session — archives old conversation, resets meta."""
    clear_conversation()
    return jsonify({"ok": True, "meta": get_session_meta()})


def _voice_clean(text):
    """Strip markdown/code for clean voice output."""
    import re
    t = re.sub(r'```[\s\S]*?```', '', text)           # remove code blocks
    t = re.sub(r'`[^`]+`', '', t)                      # remove inline code
    t = re.sub(r'[#*_~>\-|]', '', t)                   # remove markdown chars
    t = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', t)     # links -> text
    t = re.sub(r'\n{2,}', '. ', t)                     # double newlines -> pause
    t = re.sub(r'\n', ' ', t)                          # single newlines -> space
    t = re.sub(r'\s{2,}', ' ', t)                      # collapse whitespace
    return t.strip()[:800]


@app.post("/api/session/think")
def api_session_think():
    """
    Claude-continuity /think — same as /think but explicitly uses
    the persona system prompt and saves all context for session resume.
    ALWAYS speaks the response via voice.
    """
    data = request.get_json() or {}
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"reply": "Say something!", "actions": []})

    add_message("user", text)
    start = time.time()

    # Build conversation with full history for continuity
    system = build_system_prompt(include_session=True, include_state=True)

    # Try agent loop first (has tools)
    try:
        agent_result = agent_loop(text)
        if agent_result.get("ok") and agent_result.get("reply"):
            reply = format_response(agent_result["reply"])
            add_message("assistant", reply)
            auto_save_context(current_goal=text[:200])
            # ALWAYS speak the response
            try:
                speak(_voice_clean(reply), blocking=False, voice_id="en-US-AvaNeural")
            except Exception:
                pass
            return jsonify({
                "reply": reply,
                "model": f"nova-agent ({agent_result.get('iterations', 1)} steps)",
                "mode": "session_continuity",
                "duration": round(time.time() - start, 2),
                "agent": True,
                "actions": agent_result.get("actions", []),
                "session": get_session_meta(),
            })
    except Exception:
        pass

    # Fall back to direct HiveMind query with full context — SYNTHESIS MODE
    hive_result = hive_mind.fan_out(text, max_models=4, timeout=30, system=system, mode="synthesis")
    reply = ""
    if hive_result and hive_result.get("ok"):
        reply = format_response(hive_result.get("consensus", ""))

    if not reply:
        reply = "All AI providers timed out. Retrying..."
        hive_result = hive_mind.query(text, system=system)
        if hive_result.get("response"):
            reply = format_response(hive_result["response"])

    add_message("assistant", reply)
    auto_save_context(current_goal=text[:200])

    # ALWAYS speak the response
    try:
        speak(_voice_clean(reply), blocking=False, voice_id="en-US-AvaNeural")
    except Exception:
        pass

    return jsonify({
        "reply": reply,
        "model": hive_result.get("fastest_model", "unknown") if isinstance(hive_result, dict) else "unknown",
        "mode": "session_continuity",
        "duration": round(time.time() - start, 2),
        "session": get_session_meta(),
    })


# ─────────────────────────────────────────────
# WEBSOCKET EVENTS
# ─────────────────────────────────────────────

@socketio.on("connect")
def ws_connect():
    emit("connected", {"version": VERSION, "status": "Nova online"})


@socketio.on("message")
def ws_message(data):
    text = data.get("text", "") if isinstance(data, dict) else str(data)
    
    add_message("user", text)
    model, task, mode = route_with_fallback(text)
    
    if model == "anthropic":
        reply = ask_claude_with_context(get_conversation(), system=NOVAX_SYSTEM_PROMPT)
    else:
        reply = _ask_ollama(text, model) or ask_claude(text)
    
    add_message("assistant", reply)
    emit("response", {"reply": reply, "model": model, "task": task})


@socketio.on("execute")
def ws_execute(data):
    actions = data.get("actions", []) if isinstance(data, dict) else []
    results = bus.execute_plan(actions)
    emit("execution_result", {"results": results})


# ─────────────────────────────────────────────
# TASK GRAPH API
# ─────────────────────────────────────────────

@app.post("/step")
def route_step():
    """Run one task graph step."""
    tid, task = tasks.get_active()
    if not tid:
        return jsonify({"error": "No active task"})
    steps = task.get("steps", [])
    current = task.get("current", 0)
    if current < len(steps):
        result = arbiter.execute_plan([steps[current]])
        tasks.advance(tid)
        return jsonify({"step": current, "result": result, "details": tasks.step_details(tid)})
    return jsonify({"status": "task_complete"})


@app.post("/run")
def route_run():
    """Run N task graph steps (default 5, max 20)."""
    data = request.get_json() or {}
    n = min(data.get("steps", 5), 20)
    tid, task = tasks.get_active()
    if not tid:
        return jsonify({"error": "No active task"})
    results = []
    for _ in range(n):
        task = tasks.load().get(tid, {})
        steps = task.get("steps", [])
        current = task.get("current", 0)
        if current >= len(steps):
            break
        result = arbiter.execute_plan([steps[current]])
        tasks.advance(tid)
        results.append(result)
        if result and not result[0].get("ok", True):
            break
    return jsonify({"executed": len(results), "results": results, "details": tasks.step_details(tid)})


@app.get("/task/active")
def route_task_active():
    tid, _ = tasks.get_active()
    if tid:
        return jsonify(tasks.step_details(tid))
    return jsonify({"active": None})


@app.post("/task/pause")
def route_task_pause():
    tid, _ = tasks.get_active()
    if tid:
        tasks.pause(tid)
        return jsonify({"status": "paused", "task_id": tid})
    return jsonify({"error": "No active task"})


@app.get("/task/history")
def route_task_history():
    return jsonify(tasks.get_history())


# ─────────────────────────────────────────────
# WORKFLOW API
# ─────────────────────────────────────────────

@app.post("/workflow/save")
def route_workflow_save():
    data = request.get_json() or {}
    name = wf_save(data.get("name", f"wf_{int(time.time())}"),
                   data.get("actions", []), data.get("description", ""))
    return jsonify({"status": "saved", "name": name})


@app.get("/workflow/list")
def route_workflow_list():
    return jsonify(wf_list())


# ─────────────────────────────────────────────
# PROFILE API
# ─────────────────────────────────────────────

@app.post("/profile/switch")
def route_profile_switch():
    data = request.get_json() or {}
    result = profile_switch(data.get("profile", "dev"))
    event_bus.emit("STATUS", {"profile_switched": result}, source="orchestrator")
    return jsonify(result)


@app.get("/profile/list")
def route_profile_list():
    return jsonify(list_profiles())


@app.get("/profile/active")
def route_profile_active():
    return jsonify({"profile": active_profile(), "config": get_profile_config()})


@app.get("/profile/export")
def route_profile_export():
    path = export_profile()
    return send_from_directory(str(Path(path).parent), Path(path).name, as_attachment=True)


@app.post("/profile/import")
def route_profile_import():
    if "file" in request.files:
        f = request.files["file"]
        from werkzeug.utils import secure_filename
        save_path = Path(r"C:\NovaX\profiles") / secure_filename(f.filename)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        f.save(str(save_path))
        result = import_profile(str(save_path))
        return jsonify(result)
    return jsonify({"error": "No file provided"}), 400


# ─────────────────────────────────────────────
# CONTROL PLANE (DSE)
# ─────────────────────────────────────────────

@app.get("/control/observed")
def route_control_observed():
    return jsonify(get_observed())


@app.get("/control/desired")
def route_control_desired():
    return jsonify(get_desired())


@app.get("/control/diff")
def route_control_diff():
    return jsonify(dse_diff())


@app.post("/control/request")
def route_control_request():
    data = request.get_json() or {}
    return jsonify(set_desired(data.get("profile", "IDLE")))


@app.post("/control/profile/apply")
def route_control_profile_apply():
    data = request.get_json() or {}
    return jsonify(set_desired(data.get("profile", "IDLE")))


@app.get("/control/plan")
def route_control_plan():
    p = dse_plan()
    return jsonify(p)


@app.post("/control/apply")
def route_control_apply():
    data = request.get_json() or {}
    force = data.get("force", False)
    dry_run = data.get("dry_run", False)

    # Generate plan
    p = dse_plan()
    actions = p.get("actions", [])
    if not actions and not force:
        return jsonify({"status": "converged", "convergence_trit": TRUE, "convergence_char": "1",
                        "message": "No actions needed", "actions": []})

    if dry_run:
        return jsonify({"status": "dry_run", "actions": actions, "count": len(actions)})

    # Execute through Arbiter
    event_bus.emit("STATUS", {"ncp_apply": "started", "actions": len(actions)}, source="ncp")
    results = arbiter.execute_plan(actions, source="ncp_apply")

    # Log to apply_log.jsonl
    import json as _json
    log_entry = {
        "profile": get_desired().get("profile", "IDLE"),
        "actions": len(actions),
        "results": results,
        "ok": all(r.get("ok") for r in results),
        "applied_at": time.time()
    }
    try:
        log_path = Path(r"C:\NovaX\memory\apply_log.jsonl")
        with open(str(log_path), "a") as f:
            f.write(_json.dumps(log_entry) + "\n")
    except Exception:
        pass

    succeeded = sum(1 for r in results if r.get("ok"))
    failed = len(actions) - succeeded
    # Ternary convergence: +1=full, 0=partial, -1=diverged
    result_trits = [_route_trit(r) for r in results]
    convergence_trit = _merge_ternary(result_trits)
    event_bus.emit("STATUS", {"ncp_apply": "done", "succeeded": succeeded, "total": len(actions),
                              "convergence_trit": convergence_trit}, source="ncp")

    # Persist convergence: clear stale plan if fully or partially applied
    if convergence_trit >= 0:  # TRUE or MAYBE = progress
        try:
            from pathlib import Path as _P
            plan_file = _P(r"C:\NovaX\memory\last_plan.json")
            plan_file.write_text(_json.dumps({
                "actions": [], "diffs": [], "converged": True,
                "applied_at": time.time(), "profile": get_desired().get("profile", "IDLE")
            }, indent=2))
        except Exception:
            pass

    return jsonify({
        "status": "applied",
        "profile": get_desired().get("profile", "IDLE"),
        "total": len(actions),
        "succeeded": succeeded,
        "failed": failed,
        "convergence_trit": convergence_trit,
        "convergence_char": '1' if convergence_trit == 1 else '0' if convergence_trit == 0 else 'T',
        "convergence_bt": _bt_string(result_trits),
        "results": results
    })


@app.get("/control/profile/list")
def route_control_profile_list():
    return jsonify(list(DSE_PROFILES.keys()))


@app.post("/control/killswitch/safe")
def route_killswitch_safe():
    event_bus.emit("STATUS", {"killswitch": "SAFE_MODE"}, source="orchestrator")
    return jsonify(killswitch("safe"))


@app.post("/control/killswitch/panic")
def route_killswitch_panic():
    event_bus.emit("STATUS", {"killswitch": "PANIC_OFF"}, source="orchestrator")
    return jsonify(killswitch("panic"))


# ─────────────────────────────────────────────
# METRICS API
# ─────────────────────────────────────────────

@app.get("/api/history")
def route_history():
    """Return recent session actions / think history."""
    limit = int(request.args.get("limit", 30))
    actions = get_session_actions()
    items = actions[-limit:] if isinstance(actions, list) else []
    return jsonify({"history": items, "total": len(actions)})

@app.get("/api/metrics")
def route_metrics():
    task_data = tasks.get_all()
    total = sum(len(v) for v in task_data.values())
    done = len(task_data.get("done", []))
    return jsonify({
        "uptime": _fmt_uptime(time.time() - START_TIME),
        "total_tasks": total,
        "completed_tasks": done,
        "success_rate": round(done / max(total, 1) * 100, 1),
        "active_profile": active_profile(),
        "loaded_skills": len(list_skills()),
        "version": VERSION,
    })


# ─────────────────────────────────────────────
# REPAIR API
# ─────────────────────────────────────────────

@app.post("/repair")
def route_repair():
    """Self-healing: diagnose failed step, propose repair plan."""
    data = request.get_json() or {}
    error = data.get("error", "Unknown error")
    step = data.get("step", {})
    repair_prompt = (
        f"A NovaX action failed. Error: {error}. "
        f"Failed step: {json.dumps(step)}. "
        f"Suggest a repair plan as a JSON array of actions, each with driver/action/params/risk."
    )
    response = ask_claude(repair_prompt)
    try:
        repair_plan = json.loads(response)
    except (json.JSONDecodeError, TypeError):
        repair_plan = [{"driver": "terminal", "action": "run_command",
                        "params": {"cmd": "echo Repair needed"}, "risk": "low"}]
    event_bus.emit("REPAIR_APPLIED", {"error": error}, source="orchestrator")
    return jsonify({"repair_plan": repair_plan, "original_error": error})


# ─────────────────────────────────────────────
# SKILL CONFIDENCE API
# ─────────────────────────────────────────────

@app.post("/api/skills/feedback")
def route_skill_feedback():
    """Update skill confidence after user choice."""
    data = request.get_json() or {}
    skill_id = data.get("skill_id", "")
    outcome = data.get("outcome", "execute_a")  # execute_a, execute_a_edited, cancelled, error
    new_conf = update_confidence(skill_id, outcome)
    return jsonify({"skill_id": skill_id, "confidence": new_conf, "outcome": outcome})


# ─────────────────────────────────────────────
# TIME SEARCH API
# ─────────────────────────────────────────────

@app.post("/api/search/time")
def route_time_search():
    """Search temporal memory: 'yesterday's setup', 'the python project'."""
    data = request.get_json() or {}
    results = time_search(data.get("query", ""))
    return jsonify({"results": results})


# ─────────────────────────────────────────────
# CONTEXT & ENVIRONMENT API
# ─────────────────────────────────────────────

@app.get("/api/context/detect")
def route_context_detect():
    """Detect which profile the foreground app suggests."""
    suggested = detect_profile()
    current = active_profile()
    return jsonify({"suggested": suggested, "current": current,
                    "switch_recommended": suggested and suggested != current})


@app.post("/api/environment/bootstrap")
def route_environment_bootstrap():
    """Propose workspace bootstrap for current or specified profile."""
    data = request.get_json() or {}
    profile = data.get("profile", active_profile())
    return jsonify(propose_bootstrap(profile))

@app.post("/api/environment/execute")
def route_environment_execute():
    """Execute bootstrap actions — actually launch apps for a profile."""
    data = request.get_json() or {}
    profile = data.get("profile", active_profile())
    return jsonify(execute_bootstrap(profile))

@app.get("/api/environment/list")
def route_environment_list():
    """List all configured environments."""
    return jsonify(list_environments())


# ─────────────────────────────────────────────
# EVENT STREAM API
# ─────────────────────────────────────────────

@app.get("/api/events")
def route_events():
    """Get recent events from the event bus."""
    event_type = request.args.get("type")
    limit = int(request.args.get("limit", 50))
    return jsonify(event_bus.recent(limit=limit, event_type=event_type))


# ─────────────────────────────────────────────
# XRPL WALLET
# ─────────────────────────────────────────────

@app.get("/api/wallet")
def route_wallet_info():
    return jsonify(wallet_status())

@app.post("/api/wallet/generate")
def route_wallet_generate():
    data = request.get_json() or {}
    return jsonify(generate_wallet(network=data.get("network")))

@app.get("/api/wallet/balance")
def route_wallet_balance():
    address = request.args.get("address")
    return jsonify(get_balance(address=address))

@app.post("/api/wallet/send")
def route_wallet_send():
    data = request.get_json() or {}
    dest = data.get("destination", "")
    amount = float(data.get("amount", 0))
    memo = data.get("memo")
    if not dest or amount <= 0:
        return jsonify({"error": "destination and positive amount required"}), 400
    return jsonify(send_payment(dest, amount, memo=memo))

@app.get("/api/wallet/transactions")
def route_wallet_txs():
    limit = int(request.args.get("limit", 20))
    return jsonify(get_transactions(limit=limit))

@app.get("/api/wallet/log")
def route_wallet_log():
    limit = int(request.args.get("limit", 50))
    return jsonify(get_tx_log(limit=limit))

@app.post("/api/wallet/nft/mint")
def route_nft_mint():
    data = request.get_json() or {}
    uri = data.get("uri", "")
    if not uri:
        return jsonify({"error": "uri required"}), 400
    return jsonify(mint_nft(
        uri=uri,
        name=data.get("name"),
        description=data.get("description"),
        transfer_fee=data.get("transfer_fee", 0),
    ))

@app.get("/api/wallet/nfts")
def route_nft_list():
    address = request.args.get("address")
    return jsonify(get_nfts(address=address))

@app.post("/api/wallet/nft/burn")
def route_nft_burn():
    data = request.get_json() or {}
    nft_id = data.get("nft_id", "")
    if not nft_id:
        return jsonify({"error": "nft_id required"}), 400
    return jsonify(burn_nft(nft_id))

@app.post("/api/wallet/recover")
def route_wallet_recover():
    data = request.get_json() or {}
    seed = data.get("seed", "")
    if not seed:
        return jsonify({"error": "seed required"}), 400
    return jsonify(recover_wallet(seed, network=data.get("network")))

@app.get("/api/wallet/export")
def route_wallet_export():
    return jsonify(export_wallet())

@app.get("/api/dapps")
def route_dapps_list():
    category = request.args.get("category")
    return jsonify(list_dapps(category=category))

@app.get("/api/dapps/<dapp_id>")
def route_dapp_info(dapp_id):
    return jsonify(get_dapp(dapp_id))


# ─────────────────────────────────────────────
# VOICE
# ─────────────────────────────────────────────

@app.get("/api/voice/status")
def route_voice_status():
    return jsonify(voice_status())

@app.get("/api/voice/config")
def route_voice_config():
    return jsonify(voice_get_config())

@app.post("/api/voice/config")
def route_voice_config_update():
    data = request.get_json() or {}
    return jsonify(voice_update_config(**data))

@app.get("/api/voice/log")
def route_voice_log():
    from voice import get_voice_log
    limit = int(request.args.get("limit", 50))
    return jsonify(get_voice_log(limit=limit))

@app.post("/api/voice/speak")
def route_voice_speak():
    from voice import speak
    data = request.get_json() or {}
    text = data.get("text", "")
    voice_id = data.get("voice_id")
    if not text:
        return jsonify({"error": "text required"}), 400
    import threading
    threading.Thread(target=speak, args=(text,), kwargs={"blocking": True, "voice_id": voice_id}, daemon=True).start()
    return jsonify({"status": "speaking", "text": text[:100], "voice": voice_id})

@app.get("/api/voice/voices")
def route_voice_list():
    """List all curated voices with active voice indicator."""
    active = get_active_voice()
    voices = list_voices()
    return jsonify({"voices": voices, "active": active})

@app.post("/api/voice/set")
def route_voice_set():
    """Set active TTS voice."""
    data = request.get_json() or {}
    voice_id = data.get("voice_id", "")
    if not voice_id:
        return jsonify({"error": "voice_id required"}), 400
    result = set_voice(voice_id)
    return jsonify(result)

@app.post("/api/voice/preview")
def route_voice_preview():
    """Generate TTS audio preview and stream as MP3."""
    data = request.get_json() or {}
    voice_id = data.get("voice_id", "")
    text = data.get("text", "Hello, I am your Nova X assistant.")
    if not voice_id:
        return jsonify({"error": "voice_id required"}), 400
    audio = speak_to_bytes(text[:200], voice_id)
    if audio:
        from flask import Response
        return Response(audio, mimetype="audio/mpeg",
                        headers={"Content-Disposition": "inline"})
    return jsonify({"error": "TTS generation failed"}), 500

@app.post("/api/voice/transcribe")
def route_voice_transcribe():
    """Proxy to the STT server for audio transcription."""
    import urllib.request as _ur
    try:
        audio = request.get_data()
        ct = request.content_type or "audio/webm"
        # Try real STT (9876) first, fall back to stub (9875)
        for stt_port in [9876, 9875]:
            try:
                req = _ur.Request(f"http://127.0.0.1:{stt_port}/transcribe", data=audio,
                                  headers={"Content-Type": ct})
                with _ur.urlopen(req, timeout=15) as r:
                    return jsonify(json.loads(r.read()))
            except Exception:
                continue
        return jsonify({"error": "No STT server available", "text": ""})
    except Exception as e:
        return jsonify({"error": f"STT error: {e}", "text": ""})

@app.get("/api/voice/speaking")
def route_voice_speaking():
    """Check if TTS is still playing — frontend polls this to know when to unmute mic."""
    import time as _t
    try:
        from voice import get_speak_finish_time
        finish = get_speak_finish_time()
        still_speaking = _t.time() < finish
        remaining = max(0, finish - _t.time())
        return jsonify({"speaking": still_speaking, "remaining": round(remaining, 1)})
    except Exception:
        return jsonify({"speaking": False, "remaining": 0})

@app.post("/api/relay")
def route_claude_relay():
    """Relay Claude Code output to NovaX desktop chat + TTS.
    Claude Code calls this to display and speak its responses through Nova."""
    data = request.get_json() or {}
    text = data.get("text", "")
    speak = data.get("speak", True)
    source = data.get("source", "claude-code")
    if not text:
        return jsonify({"ok": False, "error": "no text"})
    # Push to desktop via SocketIO
    try:
        socketio.emit("claude_relay", {"text": text, "source": source})
    except Exception:
        pass
    # Speak it through Nova TTS
    if speak:
        try:
            from voice import speak as tts_speak
            tts_speak(text[:800])
        except Exception:
            pass
    return jsonify({"ok": True, "displayed": True, "spoken": speak})


@app.post("/api/ai/query")
def route_ai_query():
    """Local HTTPS proxy for NovaLang HiveMind. NovaLang calls HTTP here,
    orchestrator forwards to HTTPS cloud APIs with TLS."""
    import requests as _rq
    data = request.get_json() or {}
    provider = data.get("provider", "openai")
    model = data.get("model", "gpt-4o-mini")
    messages = data.get("messages", [])
    system = data.get("system", "")
    max_tokens = data.get("max_tokens", 2048)
    timeout = data.get("timeout", 15)

    try:
        from claude_connector import _load_key
    except ImportError:
        _load_key = lambda p: ""
    try:
        with open(r"C:\NovaX\cloud_config.json", encoding="utf-8") as _f:
            import json as _j
            _cfg = _j.load(_f)
    except Exception:
        _cfg = {}

    def _get_key(prov):
        k = _cfg.get(prov, {}).get("key", "")
        if k:
            return k
        env_map = {"openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY", "openrouter": "OPENROUTER_API_KEY"}
        return os.environ.get(env_map.get(prov, ""), "")

    key = _get_key(provider)
    if not key:
        return jsonify({"ok": False, "error": f"No API key for {provider}"})

    # For OpenAI/OpenRouter: inject system prompt into messages if provided separately
    if system and provider in ("openai", "openrouter"):
        has_system = any(m.get("role") == "system" for m in messages)
        if not has_system:
            messages = [{"role": "system", "content": system}] + messages

    try:
        if provider == "openai":
            r = _rq.post("https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={"model": model, "messages": messages, "max_tokens": max_tokens},
                timeout=timeout)
            if r.status_code != 200:
                return jsonify({"ok": False, "error": f"HTTP {r.status_code}: {r.text[:200]}", "provider": provider, "model": model})
            d = r.json()
            text = d.get("choices", [{}])[0].get("message", {}).get("content", "")
            return jsonify({"ok": True, "response": text, "model": model, "provider": provider})

        elif provider == "openrouter":
            r = _rq.post("https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={"model": model, "messages": messages, "max_tokens": max_tokens},
                timeout=timeout)
            if r.status_code != 200:
                return jsonify({"ok": False, "error": f"HTTP {r.status_code}: {r.text[:200]}", "provider": provider, "model": model})
            d = r.json()
            text = d.get("choices", [{}])[0].get("message", {}).get("content", "")
            return jsonify({"ok": True, "response": text, "model": model, "provider": provider})

        elif provider == "anthropic":
            body = {"model": model, "messages": messages, "max_tokens": max_tokens}
            if system:
                body["system"] = system
            r = _rq.post("https://api.anthropic.com/v1/messages",
                headers={"x-api-key": key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"},
                json=body, timeout=timeout)
            if r.status_code != 200:
                return jsonify({"ok": False, "error": f"HTTP {r.status_code}: {r.text[:200]}", "provider": provider, "model": model})
            d = r.json()
            text = ""
            for block in d.get("content", []):
                if block.get("type") == "text":
                    text += block.get("text", "")
            return jsonify({"ok": True, "response": text, "model": model, "provider": provider})

        else:
            return jsonify({"ok": False, "error": f"Unknown provider: {provider}"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e), "provider": provider, "model": model})


@app.post("/api/voice/command")
def route_voice_command():
    """Process a voice command through the think pipeline."""
    from voice import _log_event
    data = request.get_json() or {}
    text = data.get("text", "")
    if not text:
        return jsonify({"error": "text required"}), 400
    _log_event("voice_command", {"text": text})
    # Route through the standard think pipeline
    try:
        result = think(text)
        return jsonify({"status": "ok", "input": text, "response": result})
    except Exception as e:
        return jsonify({"status": "error", "input": text, "error": str(e)})


# ─────────────────────────────────────────────
# MODULE MANAGER
# ─────────────────────────────────────────────

@app.get("/api/modules")
def route_modules_list():
    return jsonify(list_modules())

@app.get("/api/modules/stats")
def route_modules_stats():
    return jsonify(module_stats())

@app.get("/api/modules/<name>")
def route_module_info(name):
    return jsonify(get_module_info(name))

@app.post("/api/modules/<name>/enable")
def route_module_enable(name):
    return jsonify(enable_module(name))

@app.post("/api/modules/<name>/disable")
def route_module_disable(name):
    return jsonify(disable_module(name))

@app.post("/api/modules/<name>/validate")
def route_module_validate(name):
    return jsonify(validate_module(name))

@app.post("/api/modules/create")
def route_module_create():
    data = request.get_json() or {}
    name = data.get("name", "")
    desc = data.get("description", "A NovaX module")
    if not name:
        return jsonify({"error": "name required"}), 400
    return jsonify(create_module_template(name, desc))

@app.delete("/api/modules/<name>")
def route_module_uninstall(name):
    return jsonify(uninstall_module(name))

@app.post("/api/modules/<name>/snapshot")
def route_module_snapshot(name):
    return jsonify(snapshot_module(name))

@app.post("/api/modules/<name>/rollback")
def route_module_rollback(name):
    data = request.get_json() or {}
    idx = data.get("snapshot_index", -1)
    return jsonify(rollback_module(name, idx))

@app.get("/api/modules/snapshots")
def route_module_snapshots():
    return jsonify(list_snapshots())

@app.get("/api/modules/<name>/snapshots")
def route_module_snapshots_name(name):
    return jsonify(list_snapshots(name))

@app.get("/api/modules/<name>/deps")
def route_module_deps(name):
    return jsonify(resolve_dependencies(name))

@app.get("/api/modules/deps/tree")
def route_module_dep_tree():
    return jsonify(get_dependency_tree())

@app.get("/api/modules/<name>/config")
def route_module_config_get(name):
    return jsonify(get_module_config(name))

@app.post("/api/modules/<name>/config")
def route_module_config_update(name):
    data = request.get_json() or {}
    return jsonify(update_module_config(name, data))

@app.post("/api/modules/<name>/run")
def route_module_run(name):
    data = request.get_json() or {}
    action = data.get("action", "")
    params = data.get("params", {})
    if not action:
        return jsonify({"ok": False, "error": "action required"})
    return jsonify(run_module_action(name, action, params))


# ─────────────────────────────────────────────
# UI MEMORY
# ─────────────────────────────────────────────

@app.get("/api/ui/routines")
def route_ui_routines():
    return jsonify(list_routines())

@app.get("/api/ui/stats")
def route_ui_stats():
    return jsonify(ui_stats())

@app.post("/api/ui/record")
def route_ui_record():
    data = request.get_json() or {}
    actions = data.get("actions", [])
    context = data.get("context", "")
    return jsonify(record_interaction(actions, context))

@app.post("/api/ui/match")
def route_ui_match():
    data = request.get_json() or {}
    actions = data.get("actions", [])
    return jsonify(match_routine(actions) or {"match": False})

@app.post("/api/ui/auto-replay/<hash_id>/enable")
def route_ui_auto_enable(hash_id):
    return jsonify({"enabled": enable_auto_replay(hash_id)})

@app.post("/api/ui/auto-replay/<hash_id>/disable")
def route_ui_auto_disable(hash_id):
    return jsonify({"disabled": disable_auto_replay(hash_id)})

@app.get("/api/ui/auto-replay")
def route_ui_auto_routines():
    return jsonify(get_auto_routines())


# ─────────────────────────────────────────────
# REPAIR ENGINE (enhanced endpoints)
# ─────────────────────────────────────────────

@app.get("/api/repair/stats")
def route_repair_stats():
    return jsonify(get_repair_stats())

@app.get("/api/repair/failures")
def route_repair_failures():
    limit = int(request.args.get("limit", 5))
    return jsonify(recent_failures(limit=limit))

@app.post("/api/repair/diagnose")
def route_repair_diagnose():
    data = request.get_json() or {}
    error = data.get("error", "")
    context = data.get("context", "")
    use_ai = data.get("ai", False)
    if use_ai:
        return jsonify(diagnose_with_ai(error, context))
    return jsonify(diagnose(error, context))


# ─────────────────────────────────────────────
# AI & API CONFIGURATION (proxies to Cloud Router :9878)
# ─────────────────────────────────────────────

def _proxy_get(url):
    try:
        import urllib.request, gzip
        with urllib.request.urlopen(url, timeout=5) as r:
            data = r.read()
            if data[:2] == b'\x1f\x8b':
                data = gzip.decompress(data)
            return json.loads(data)
    except Exception as e:
        return {"ok": False, "error": str(e)}

def _proxy_post(url, payload):
    try:
        import urllib.request, gzip
        data = json.dumps(payload).encode()
        req = urllib.request.Request(url, data, {"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as r:
            resp = r.read()
            if resp[:2] == b'\x1f\x8b':
                resp = gzip.decompress(resp)
            return json.loads(resp)
    except Exception as e:
        return {"ok": False, "error": str(e)}

def _proxy_post_json(url, payload, timeout=30):
    try:
        import urllib.request, gzip
        data = json.dumps(payload).encode()
        req = urllib.request.Request(url, data, {"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            resp = r.read()
            if resp[:2] == b'\x1f\x8b':
                resp = gzip.decompress(resp)
            return json.loads(resp)
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.get("/api/ai/config")
def route_ai_config_get():
    raw = _proxy_get("http://127.0.0.1:9878/api/v1/providers")
    name_map = {"anthropic": "claude", "openai": "openai", "deepseek": "deepseek",
                "ollama": "ollama", "google": "google", "mistral": "mistral",
                "groq": "groq", "cohere": "cohere", "together": "together",
                "openrouter": "openrouter", "cortex": "cortex"}
    result = {}
    # Cloud-router returns {"ok":1, "providers": [...], "count": N, "enabled": N}
    providers_list = raw.get("providers", [])
    for info in providers_list:
        pid = info.get("name", "")
        key = name_map.get(pid, pid)
        has_key = info.get("has_key", False)
        enabled = info.get("enabled", False)
        # NovaLang true=1, false=-1 — normalize to Python bool
        has_key_bool = has_key == True or has_key == 1
        enabled_bool = enabled == True or enabled == 1
        # Use full model list from registry if available, else single default
        reg_models = info.get("models", [])
        model_list = reg_models if reg_models else ([info.get("model", "")] if info.get("model") else [])
        result[key] = {
            "configured": has_key_bool and enabled_bool,
            "enabled": enabled_bool,
            "has_key": has_key_bool,
            "models": model_list,
            "model_count": info.get("model_count", len(model_list)),
            "name": pid,
            "priority": info.get("priority", 99),
            "type": info.get("type", ""),
            "trit": info.get("trit", 0),
            "seal": info.get("seal", 0),
            "quality": info.get("quality", 0),
        }
    # Pass through registry metadata
    result["_total_models"] = raw.get("total_models", 0)
    result["_registry_synced"] = raw.get("registry_synced", False)
    result["_abilities"] = raw.get("abilities", {})
    return jsonify(result)

@app.post("/api/ai/config")
def route_ai_config_post():
    data = request.get_json() or {}
    name_map = {"claude": "anthropic"}
    provider = data.get("provider", "")
    data["provider"] = name_map.get(provider, provider)
    # Frontend sends "key", Cloud Router expects "api_key"
    if "key" in data and "api_key" not in data:
        data["api_key"] = data.pop("key")
    return jsonify(_proxy_post("http://127.0.0.1:9878/api/v1/bind", data))

@app.post("/api/ai/test")
def route_ai_test():
    data = request.get_json() or {}
    provider = data.get("provider", "ollama")
    name_map = {"claude": "anthropic"}
    cloud_pid = name_map.get(provider, provider)
    # Cloud-router expects {"prompt": "...", "provider": "name"} (singular)
    payload = {"prompt": "Reply with exactly: NOVAX_OK", "provider": cloud_pid}
    result = _proxy_post("http://127.0.0.1:9878/api/v1/query", payload)
    ok = result.get("ok") == True or result.get("ok") == 1
    return jsonify({"ok": ok, "provider": provider, "result": result})

@app.get("/api/ai/cloud")
def route_ai_cloud():
    return jsonify(_proxy_get("http://127.0.0.1:9878/api/v1/cloud"))

@app.get("/api/ai/health3")
def route_ai_health3():
    """Cloud Router ternary health: per-provider health3 trits."""
    return jsonify(_proxy_get("http://127.0.0.1:9878/api/v1/health3"))

@app.get("/api/ai/reynolds")
def route_ai_reynolds():
    """Cloud Router traffic flow classification."""
    return jsonify(_proxy_get("http://127.0.0.1:9878/api/v1/reynolds"))

@app.get("/api/ai/quality")
def route_ai_quality():
    """Cloud Router per-provider ternary quality fingerprints."""
    return jsonify(_proxy_get("http://127.0.0.1:9878/api/v1/quality"))

# ─────────────────────────────────────────────
# MODEL REGISTRY (proxies to :9860)
# ─────────────────────────────────────────────

@app.get("/api/ai/catalog")
def route_ai_catalog():
    """Full model catalog — 508+ models, abilities, providers, lock status."""
    return jsonify(_proxy_get("http://127.0.0.1:9860/catalog"))

@app.get("/api/ai/models")
def route_ai_models():
    """All registered models."""
    return jsonify(_proxy_get("http://127.0.0.1:9860/models"))

@app.get("/api/ai/models/free")
def route_ai_models_free():
    return jsonify(_proxy_get("http://127.0.0.1:9860/models/free"))

@app.get("/api/ai/models/locked")
def route_ai_models_locked():
    return jsonify(_proxy_get("http://127.0.0.1:9860/models/locked"))

@app.get("/api/ai/models/stats")
def route_ai_models_stats():
    return jsonify(_proxy_get("http://127.0.0.1:9860/models/stats"))

@app.get("/api/ai/abilities")
def route_ai_abilities():
    """Combined abilities matrix — code, reasoning, vision, math, chat, flagship, fast."""
    return jsonify(_proxy_get("http://127.0.0.1:9860/abilities"))

@app.post("/api/ai/models/discover")
def route_ai_models_discover():
    """Trigger full re-discovery across all providers."""
    return jsonify(_proxy_post("http://127.0.0.1:9860/models/discover", {}))

@app.post("/api/ai/models/lock-all")
def route_ai_models_lock_all():
    """Lock ALL models for full access."""
    return jsonify(_proxy_post("http://127.0.0.1:9860/models/lock-all", {}))

# ─────────────────────────────────────────────
# WIFI BRIDGE (proxies to VPN Core :9880)
# ─────────────────────────────────────────────

@app.get("/api/wifi/status")
def route_wifi_status():
    raw = _proxy_get("http://127.0.0.1:9880/n/wifi/speeds")
    adapters = raw.get("adapters", [])
    bonded = raw.get("bonded_speed_mbps", 0)
    count = raw.get("count", len(adapters))
    return jsonify({
        "ok": True, "bridged": count > 1,
        "adapter_count": count, "adapters": adapters,
        "bonded_speed_mbps": bonded,
        "download_speed": f"{bonded:.0f} Mbps" if bonded else "N/A",
        "upload_speed": f"{bonded/2:.0f} Mbps" if bonded else "N/A",
    })

@app.post("/api/wifi/bridge")
def route_wifi_bridge():
    data = request.get_json() or {}
    result = _proxy_post("http://127.0.0.1:9880/n/wifi/bridge", data)
    result["status"] = "Bridge active" if result.get("ok") else "Bridge failed"
    return jsonify(result)

@app.post("/api/wifi/unbridge")
def route_wifi_unbridge():
    return jsonify(_proxy_post("http://127.0.0.1:9880/n/wifi/unbridge", {}))

@app.get("/api/wifi/speedtest")
def route_wifi_speedtest():
    return jsonify(_proxy_get("http://127.0.0.1:9880/n/wifi/speedtest"))

@app.get("/api/wifi/adapters")
def route_wifi_adapters():
    return jsonify(_proxy_get("http://127.0.0.1:9880/n/wifi/adapters"))

@app.get("/api/wifi/scan")
def route_wifi_scan():
    return jsonify(_proxy_get("http://127.0.0.1:9880/n/wifi/scan"))

@app.post("/api/wifi/connect")
def route_wifi_connect():
    data = request.get_json() or {}
    return jsonify(_proxy_post("http://127.0.0.1:9880/n/wifi/connect", data))

@app.post("/api/wifi/disconnect")
def route_wifi_disconnect():
    data = request.get_json() or {}
    return jsonify(_proxy_post("http://127.0.0.1:9880/n/wifi/disconnect", data))

@app.get("/api/wifi/throughput")
def route_wifi_throughput():
    return jsonify(_proxy_get("http://127.0.0.1:9880/n/wifi/throughput"))

@app.get("/api/wifi/connections")
def route_wifi_connections():
    return jsonify(_proxy_get("http://127.0.0.1:9880/n/wifi/connections"))

# ─────────────────────────────────────────────
# OPENCLAW INTEGRATION
# ─────────────────────────────────────────────

@app.get("/api/openclaw/config")
def route_openclaw_config_get():
    from openclaw_client import _config, is_enabled
    cfg = _config()
    cfg["enabled"] = is_enabled()
    cfg["token"] = bool(cfg.get("token"))
    return jsonify({"ok": True, **cfg})

@app.post("/api/openclaw/config")
def route_openclaw_config_post():
    data = request.get_json() or {}
    from openclaw_client import configure
    result = configure(
        url=data.get("url"),
        token=data.get("token"),
        enabled=data.get("enabled")
    )
    return jsonify({"ok": True, **result})

@app.get("/api/openclaw/health")
def route_openclaw_health():
    from openclaw_client import health
    alive, msg = health()
    return jsonify({"ok": alive, "message": msg})

# ─────────────────────────────────────────────
# VPN / TOR / SECURITY
# ─────────────────────────────────────────────

@app.get("/api/vpn/status")
def route_vpn_status():
    return jsonify(_proxy_get("http://127.0.0.1:9880/n/status"))

@app.get("/api/vpn/servers")
def route_vpn_servers():
    return jsonify(_proxy_get("http://127.0.0.1:9880/n/servers"))

@app.get("/api/tor/status")
def route_tor_status():
    return jsonify(_proxy_get("http://127.0.0.1:9880/n/tor/status"))

@app.get("/api/sentinel/status")
def route_sentinel_status():
    return jsonify(_proxy_get("http://127.0.0.1:9884/sentinel/status"))

@app.get("/api/sentinel/events")
def route_sentinel_events():
    return jsonify(_proxy_get("http://127.0.0.1:9884/sentinel/events"))

@app.post("/api/sentinel/restart")
def route_sentinel_restart():
    svc = (request.get_json() or {}).get("service", "")
    return jsonify(_proxy_post("http://127.0.0.1:9884/sentinel/restart", {"service": svc}))

@app.post("/api/tor/start")
def route_tor_start():
    return jsonify(_proxy_post("http://127.0.0.1:9880/n/tor/start", {}))

@app.post("/api/tor/stop")
def route_tor_stop():
    return jsonify(_proxy_post("http://127.0.0.1:9880/n/tor/stop", {}))

@app.post("/api/tor/new-circuit")
def route_tor_newcircuit():
    return jsonify(_proxy_post("http://127.0.0.1:9880/n/tor/new-circuit", {}))

@app.get("/api/vpn/encryption")
def route_vpn_encryption():
    return jsonify(_proxy_get("http://127.0.0.1:9880/n/status"))

@app.post("/api/novalang/run")
def route_novalang_run():
    data = request.get_json() or {}
    code = data.get("code", "")
    if not code:
        return jsonify({"error": "code required"}), 400
    try:
        import subprocess, tempfile, os
        fd, path = tempfile.mkstemp(suffix=".nova")
        with os.fdopen(fd, 'w') as f:
            f.write(code)
        _nsi = subprocess.STARTUPINFO()
        _nsi.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        _nsi.wShowWindow = 0
        result = subprocess.run(
            [r"C:\NovaX\novalang.exe", path],
            capture_output=True, text=True, timeout=15,
            creationflags=0x08000000, startupinfo=_nsi
        )
        os.unlink(path)
        return jsonify({"ok": result.returncode == 0,
                        "output": result.stdout[-2000:],
                        "error": result.stderr[-500:] if result.returncode != 0 else ""})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

@app.post("/api/novalang/transpile")
def route_novalang_transpile():
    data = request.get_json() or {}
    code = data.get("code", "")
    target = data.get("target", "python")
    if not code:
        return jsonify({"error": "code required"}), 400
    if target not in ("python", "javascript", "rust"):
        return jsonify({"error": "target must be python, javascript, or rust"}), 400
    try:
        import subprocess, tempfile, os
        fd, path = tempfile.mkstemp(suffix=".nova")
        with os.fdopen(fd, 'w') as f:
            f.write(code)
        _nsi2 = subprocess.STARTUPINFO()
        _nsi2.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        _nsi2.wShowWindow = 0
        result = subprocess.run(
            [r"C:\Users\Jupit\AppData\Local\Programs\Python\Python312\python.exe", "C:\\NovaX\\novalang.py", path, "--transpile", target],
            capture_output=True, text=True, timeout=15,
            creationflags=0x08000000, startupinfo=_nsi2
        )
        os.unlink(path)
        return jsonify({"ok": result.returncode == 0, "target": target,
                        "output": result.stdout[-4000:],
                        "error": result.stderr[-500:] if result.returncode != 0 else ""})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

# ─────────────────────────────────────────────
# AUTO-LAUNCHER  (boot all services in order)
# CREATE_NO_WINDOW = 0x08000000 — prevents blue PowerShell popups
# ─────────────────────────────────────────────
_CREATE_NO_WINDOW = 0x08000000

_PW = r"C:\Users\Jupit\AppData\Local\Programs\Python\Python312\python.exe"  # Python 3.12 — LEGACY, only for remaining .py services
_NL = r"C:\NovaX\novalang.py"  # NovaLang Python interpreter — LEGACY fallback
_NV = r"C:\NovaX\novalang.exe"  # NovaLang Rust VM — NATIVE runtime, zero Python
BOOT_ORDER = [
    {"name": "tspin",        "cmd": [_NV, r"C:\NovaX\nova_tspin_service.nova"],                  "port": 9970},
    {"name": "tscale",       "cmd": [_NV, r"C:\NovaX\nova_tscale_service.nova"],             "port": 9986},
    {"name": "tshield",      "cmd": [_NV, r"C:\NovaX\nova_tshield_service.nova"],            "port": 9987},
    {"name": "thunter",      "cmd": [_NV, r"C:\NovaX\nova_thunter_service.nova"],            "port": 9988},
    {"name": "ollama",       "cmd": [r"C:\Users\Jupit\AppData\Local\Programs\Ollama\ollama.exe", "serve"], "port": 11434},
    {"name": "redis",        "cmd": [r"C:\Program Files\Redis\redis-server.exe", "--bind", "127.0.0.1", "--port", "6379", "--maxmemory", "128mb"],  "port": 6379},
    {"name": "meilisearch",  "cmd": [r"C:\NovaX\servers\meilisearch\meilisearch.exe", "--db-path", r"C:\NovaX\servers\meilisearch\data"], "port": 7700},
    {"name": "exec-server",  "cmd": [_NV, r"C:\NovaX\launchers\exec_server.nova"],          "port": 9877},
    {"name": "model-registry", "cmd": [_NV, r"C:\NovaX\nova_model_registry_service.nova"], "port": 9860},
    {"name": "cloud-router", "cmd": [_NV, r"C:\NovaX\nova_cloud_router_service.nova"], "port": 9878},
    {"name": "novax-prime",  "cmd": [_NV, r"C:\NovaX\nova_prime_service.nova"],          "port": 9869},
    {"name": "physics-engine",   "cmd": [_NV, r"C:\NovaX\nova_physics_engine.nova"],     "port": 9850},
    {"name": "novaxcore-engine", "cmd": [_NV, r"C:\NovaX\nova_novaxcore_engine.nova"],   "port": 9851},
    {"name": "rendering-engine", "cmd": [_NV, r"C:\NovaX\nova_rendering_engine.nova"],   "port": 9852},
    {"name": "simulation-engine","cmd": [_NV, r"C:\NovaX\nova_simulation_engine.nova"],  "port": 9853},
    {"name": "audio-engine",     "cmd": [_NV, r"C:\NovaX\nova_audio_engine.nova"],       "port": 9854},
    {"name": "brain",        "cmd": [_NV, r"C:\NovaX\core\server.nova"], "port": 9990},
    {"name": "vpn-core",     "cmd": [_NV, r"C:\NovaX\nova_vpn_core_service.nova"],    "port": 9880},
    {"name": "sentinel",     "cmd": [_NV, r"C:\NovaX\nova_sentinel_service.nova"],          "port": 9884},
    {"name": "hivemind",     "cmd": [_NV, r"C:\NovaX\nova_hivemind_service.nova"],          "port": 9881},
    {"name": "nexus",        "cmd": [_NV, r"C:\NovaX\nova_nexus_service.nova"],       "port": 9882},
    {"name": "stt",          "cmd": [_NV, r"C:\NovaX\nova_stt_service.nova"],         "port": 9875},
    {"name": "websocket",    "cmd": [_NV, r"C:\NovaX\ws_server_standalone.nova"], "port": 9998},
    {"name": "ternary-server", "cmd": [_NV, r"C:\NovaX\nova_ternary_server_service.nova"],  "port": 9885},
    {"name": "nova-cli",     "cmd": [_NV, r"C:\NovaX\nova_cli_server_service.nova"],  "port": 9961},
    {"name": "closed-loop", "cmd": [_NV, r"C:\NovaX\nova_closed_loop_service.nova"],  "port": 9888},
    {"name": "max-patch",   "cmd": [_NV, r"C:\NovaX\nova_max_patch_service.nova"],    "port": 9889},
    {"name": "tshell",      "cmd": [_NV, r"C:\NovaX\nova_tshell_service.nova"],       "port": 9890},
    {"name": "nova-cortex", "cmd": [_NV, r"C:\NovaX\nova_cortex_service.nova"],       "port": 9896},
    {"name": "nova-tfetch", "cmd": [_NV, r"C:\NovaX\nova_tfetch_service.nova"],       "port": 9897},
    {"name": "nova-tools", "cmd": [_NV, r"C:\NovaX\nova_tools_service.nova"],         "port": 9891},
    {"name": "nova-vault", "cmd": [_NV, r"C:\NovaX\nova_vault_service.nova"],         "port": 9892},
    {"name": "nova-deepstorage", "cmd": [_NV, r"C:\NovaX\nova_deepstorage_service.nova"], "port": 9893},
    {"name": "nova-ttools", "cmd": [_NV, r"C:\NovaX\nova_ternary_tools_service.nova"], "port": 9894},
    {"name": "nova-tspeak", "cmd": [_NV, r"C:\NovaX\nova_tspeak_service.nova"],       "port": 9895},
    {"name": "nova-tkill", "cmd": [_NV, r"C:\NovaX\nova_tkill_service.nova"],         "port": 9901},
    {"name": "nova-tbuffer", "cmd": [_NV, r"C:\NovaX\nova_tbuffer_service.nova"],     "port": 9886},
    {"name": "skiptrace", "cmd": [_NV, r"C:\NovaX\nova_skiptrace_service.nova"],      "port": 9903},
    {"name": "nova-tsysmon", "cmd": [_NV, r"C:\NovaX\nova_tsysmon_service.nova"],       "port": 9905},
    {"name": "nova-tnet", "cmd": [_NV, r"C:\NovaX\nova_tnet_service.nova"],             "port": 9906},
    {"name": "nova-tsecurity", "cmd": [_NV, r"C:\NovaX\nova_tsecurity_service.nova"],   "port": 9907},
    {"name": "nova-tmedia", "cmd": [_NV, r"C:\NovaX\nova_tmedia_service.nova"],         "port": 9908},
    {"name": "nova-tbuild", "cmd": [_NV, r"C:\NovaX\nova_tbuild_service.nova"],         "port": 9909},
    {"name": "nova-tcron", "cmd": [_NV, r"C:\NovaX\nova_tcron_service.nova"],           "port": 9910},
    {"name": "nova-tquery", "cmd": [_NV, r"C:\NovaX\nova_tquery_service.nova"],         "port": 9911},
    {"name": "nova-tbus",        "cmd": [_NV, r"C:\NovaX\nova_tbus_service.nova"],           "port": 9945},
    {"name": "nova-tresilience", "cmd": [_NV, r"C:\NovaX\nova_tresilience_service.nova"],    "port": 9948},
    {"name": "nova-tintelligence","cmd": [_NV, r"C:\NovaX\nova_tintelligence_service.nova"], "port": 9924},
    {"name": "nova-twatch",      "cmd": [_NV, r"C:\NovaX\nova_twatch_service.nova"],        "port": 9950},
    {"name": "nova-tmesh",       "cmd": [_NV, r"C:\NovaX\nova_tmesh_service.nova"],         "port": 9951},
    {"name": "nova-tauth",       "cmd": [_NV, r"C:\NovaX\nova_tauth_service.nova"],         "port": 9952},
    {"name": "nova-tmetrics",    "cmd": [_NV, r"C:\NovaX\nova_tmetrics_service.nova"],       "port": 9953},
    {"name": "nova-tstream",     "cmd": [_NV, r"C:\NovaX\nova_tstream_service.nova"],        "port": 9955},
    {"name": "nova-tcache",      "cmd": [_NV, r"C:\NovaX\nova_tcache_service.nova"],         "port": 9956},
    {"name": "nova-tqueue",      "cmd": [_NV, r"C:\NovaX\nova_tqueue_service.nova"],         "port": 9957},
    {"name": "nova-tgraph",      "cmd": [_NV, r"C:\NovaX\nova_tgraph_service.nova"],         "port": 9958},
    {"name": "nova-tscheduler",  "cmd": [_NV, r"C:\NovaX\nova_tscheduler_service.nova"],     "port": 9959},
    {"name": "nova-tembed",      "cmd": [_NV, r"C:\NovaX\nova_tembed_service.nova"],         "port": 9960},
    {"name": "nova-tlog",        "cmd": [_NV, r"C:\NovaX\nova_tlog.nova"],                   "port": 9942},
    {"name": "nova-tconfig",     "cmd": [_NV, r"C:\NovaX\nova_tconfig.nova"],                "port": 9941},
    {"name": "nova-trouter",     "cmd": [_NV, r"C:\NovaX\nova_trouter_service.nova"],        "port": 9963},
    {"name": "nova-tvalidator",  "cmd": [_NV, r"C:\NovaX\nova_tvalidator_service.nova"],     "port": 9964},
    {"name": "nova-tsnapshot",   "cmd": [_NV, r"C:\NovaX\nova_tsnapshot_service.nova"],      "port": 9965},
    {"name": "nova-tpipeline",   "cmd": [_NV, r"C:\NovaX\nova_tpipeline_service.nova"],      "port": 9966},
    {"name": "nova-tmatrix",     "cmd": [_NV, r"C:\NovaX\nova_tmatrix_service.nova"],        "port": 9967},
    {"name": "nova-talchemy",    "cmd": [_NV, r"C:\NovaX\nova_talchemy_service.nova"],       "port": 9928},
    {"name": "nova-thealth",     "cmd": [_NV, r"C:\NovaX\nova_thealth.nova"],                "port": 9940},
    {"name": "nova-treplay",     "cmd": [_NV, r"C:\NovaX\nova_treplay_service.nova"],        "port": 9937},
    {"name": "nova-tcluster",    "cmd": [_NV, r"C:\NovaX\nova_tcluster_service.nova"],       "port": 9971},
    {"name": "nova-tcompress",   "cmd": [_NV, r"C:\NovaX\nova_tcompress_service.nova"],      "port": 9972},
    {"name": "nova-tdiff",       "cmd": [_NV, r"C:\NovaX\nova_tdiff_service.nova"],          "port": 9973},
    {"name": "nova-taudit",      "cmd": [_NV, r"C:\NovaX\nova_taudit_service.nova"],         "port": 9974},
    {"name": "nova-tnotify",     "cmd": [_NV, r"C:\NovaX\nova_tnotify_service.nova"],        "port": 9975},
    {"name": "nova-tsync",       "cmd": [_NV, r"C:\NovaX\nova_tsync_service.nova"],          "port": 9976},
    {"name": "nova-tprompt",     "cmd": [_NV, r"C:\NovaX\nova_tprompt_service.nova"],        "port": 9977},
    {"name": "nova-tmemory",     "cmd": [_NV, r"C:\NovaX\nova_tmemory_service.nova"],        "port": 9978},
    {"name": "nova-tgarlic",     "cmd": [_NV, r"C:\NovaX\nova_tgarlic_service.nova"],        "port": 9996},
    {"name": "nova-tgateway",    "cmd": [_NV, r"C:\NovaX\nova_tgateway_service.nova"],       "port": 9979},
    {"name": "nova-tprofile",    "cmd": [_NV, r"C:\NovaX\nova_tprofile_service.nova"],       "port": 9980},
    {"name": "nova-tlock",       "cmd": [_NV, r"C:\NovaX\nova_tlock_service.nova"],          "port": 9981},
    {"name": "nova-tflow",       "cmd": [_NV, r"C:\NovaX\nova_tflow_service.nova"],          "port": 9982},
    {"name": "nova-tdigest",     "cmd": [_NV, r"C:\NovaX\nova_tdigest_service.nova"],        "port": 9983},
    {"name": "nova-tbalance",    "cmd": [_NV, r"C:\NovaX\nova_tbalance_service.nova"],       "port": 9984},
    {"name": "nova-trelay",      "cmd": [_NV, r"C:\NovaX\nova_trelay_service.nova"],         "port": 9985},
    {"name": "nova-tsession",   "cmd": [_NV, r"C:\NovaX\nova_tsession_service.nova"],      "port": 9912},
    {"name": "nova-tgit",      "cmd": [_NV, r"C:\NovaX\nova_tgit_service.nova"],         "port": 9913},
    {"name": "nova-tdocker",   "cmd": [_NV, r"C:\NovaX\nova_tdocker_service.nova"],      "port": 9914},
    {"name": "nova-tterraform","cmd": [_NV, r"C:\NovaX\nova_tterraform_service.nova"],   "port": 9915},
    {"name": "nova-tsqlite",   "cmd": [_NV, r"C:\NovaX\nova_tsqlite_service.nova"],      "port": 9916},
    {"name": "nova-tredis",    "cmd": [_NV, r"C:\NovaX\nova_tredis_service.nova"],       "port": 9917},
    {"name": "nova-timage",    "cmd": [_NV, r"C:\NovaX\nova_timage_service.nova"],       "port": 9918},
    {"name": "nova-thttp",     "cmd": [_NV, r"C:\NovaX\nova_thttp_service.nova"],       "port": 9919},
    {"name": "nova-tmarkdown", "cmd": [_NV, r"C:\NovaX\nova_tmarkdown_service.nova"],   "port": 9920},
    {"name": "nova-tyaml",     "cmd": [_NV, r"C:\NovaX\nova_tyaml_service.nova"],       "port": 9921},
    {"name": "nova-tffmpeg",   "cmd": [_NV, r"C:\NovaX\nova_tffmpeg_service.nova"],     "port": 9922},
    {"name": "nova-ttext",     "cmd": [_NV, r"C:\NovaX\nova_ttext_service.nova"],       "port": 9923},
    {"name": "nova-bitnet-fleet", "cmd": [_NV, r"C:\NovaX\nova_bitnet_fleet_service.nova"],    "port": 9926},
    {"name": "nova-tci",        "cmd": [_NV, r"C:\NovaX\nova_tci_service.nova"],       "port": 9927},
    {"name": "nova-tconfig2",   "cmd": [_NV, r"C:\NovaX\nova_tconfig_service.nova"],   "port": 9932},
    {"name": "nova-tbenchmark", "cmd": [_NV, r"C:\NovaX\nova_tbenchmark_service.nova"], "port": 9933},
    {"name": "nova-ttest",      "cmd": [_NV, r"C:\NovaX\nova_ttest_service.nova"],     "port": 9934},
    {"name": "nova-tdocs",      "cmd": [_NV, r"C:\NovaX\nova_tdocs_service.nova"],     "port": 9935},
    {"name": "nova-tmicro",     "cmd": [_NV, r"C:\NovaX\nova_tmicro_service.nova"],   "port": 9936},
    {"name": "nova-tpacman",   "cmd": [_NV, r"C:\NovaX\nova_tpacman_service.nova"],  "port": 9991},
    {"name": "script-vault",  "cmd": [_NV, r"C:\NovaX\nova_script_vault_service.nova"], "port": 9938},
    {"name": "nova-quantizer", "cmd": [_NV, r"C:\NovaX\nova_quantizer_service.nova"], "port": 9939},
    {"name": "ability-router", "cmd": [_NV, r"C:\NovaX\nova_ability_router.nova"],   "port": 9954},
    {"name": "hf-gateway",     "cmd": [_NV, r"C:\NovaX\nova_hf_gateway.nova"],       "port": 9969},
    {"name": "nova-trate",     "cmd": [_NV, r"C:\NovaX\nova_trate_service.nova"],    "port": 9949},
    {"name": "nova-hardware", "cmd": [_NV, r"C:\NovaX\nova_hardware_service.nova"],  "port": 9943},
]

@app.post("/api/services/boot")
def route_services_boot():
    """Launch all NovaX services — CREATE_NO_WINDOW, zero blue shells.
    SAFE BOOT: H3 batch size (3 services), 2s pause + health verify between batches.
    Prevents system overload from spawning 89 Python processes simultaneously.
    Ternary boot state per service: +1=started+healthy, 0=started/already_running, -1=failed."""
    import socket, subprocess as _sp, time as _time, urllib.request as _ur
    results = []
    _BATCH = H3  # H3=3 services per wave — SAFE for system resources
    _WAVE_PAUSE = 2.0  # 2 seconds between waves — let OS settle
    _launched_in_batch = 0
    for svc in BOOT_ORDER:
        _port_owned = False
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1.0)
                _port_owned = s.connect_ex(("127.0.0.1", svc["port"])) == 0
        except Exception:
            _port_owned = False
        if _port_owned:
                results.append({"name": svc["name"], "port": svc["port"], "status": "already_running",
                                "trit": TRUE, "char": "1"})
                continue
        # TResource Gate Check — ternary-server resource virtualization (primary)
        # Falls back to TSpin gate if ternary server is down
        _gate_blocked = False
        try:
            _gate_data = json.dumps({"service": svc["name"], "name": svc["name"], "port": svc["port"]}).encode()
            _gate_req = _ur.Request("http://127.0.0.1:9885/tresource/gate", data=_gate_data,
                                    headers={"Content-Type": "application/json"}, method="POST")
            _gate_resp = json.loads(_ur.urlopen(_gate_req, timeout=3).read())
            if _gate_resp.get("trit", 1) == -1:
                results.append({"name": svc["name"], "port": svc["port"], "status": "gate_blocked",
                                "reason": _gate_resp.get("reason", ""), "trit": FALSE_, "char": "T"})
                _gate_blocked = True
        except Exception:
            # TResource not available — try TSpin as fallback
            try:
                _gate_data = json.dumps({"name": svc["name"], "port": svc["port"]}).encode()
                _gate_req = _ur.Request("http://127.0.0.1:9970/spin/gate", data=_gate_data,
                                        headers={"Content-Type": "application/json"}, method="POST")
                _gate_resp = json.loads(_ur.urlopen(_gate_req, timeout=3).read())
                if _gate_resp.get("trit", 1) == -1:
                    results.append({"name": svc["name"], "port": svc["port"], "status": "gate_blocked",
                                    "reason": _gate_resp.get("reason", ""), "trit": FALSE_, "char": "T"})
                    _gate_blocked = True
            except Exception:
                pass  # Neither gate running — proceed without gate
        if _gate_blocked:
            continue
        try:
            _cmd = list(svc["cmd"])
            _si = _sp.STARTUPINFO()
            _si.dwFlags |= _sp.STARTF_USESHOWWINDOW
            _si.wShowWindow = 0
            _proc = _sp.Popen(_cmd, stdout=_sp.DEVNULL, stderr=_sp.DEVNULL,
                       stdin=_sp.DEVNULL, creationflags=_CREATE_NO_WINDOW,
                       startupinfo=_si, close_fds=True)
            _CHILD_PROCS.append(_proc)
            results.append({"name": svc["name"], "port": svc["port"], "status": "started",
                            "trit": MAYBE, "char": "0"})
            _launched_in_batch += 1
            if _launched_in_batch >= _BATCH:
                _time.sleep(_WAVE_PAUSE)  # SAFE stagger — let system breathe
                _launched_in_batch = 0
        except Exception as e:
            results.append({"name": svc["name"], "port": svc["port"], "status": "error", "error": str(e)[:100],
                            "trit": FALSE_, "char": "T"})
    # ── RETRY WAVE: health-verify started services after full fleet is up ──
    _time.sleep(H5)  # 5s settle — let all services bind ports
    _CRITICAL = {"hivemind", "ternary-server"}  # Race-condition-prone
    for _attempt in range(2):  # 2 passes: 1st=all, 2nd=critical only
        for r in results:
            if r["trit"] != MAYBE:
                continue
            if _attempt == 1 and r["name"] not in _CRITICAL:
                continue
            try:
                _hreq = _ur.Request(f"http://127.0.0.1:{r['port']}/health", method="GET")
                _hresp = json.loads(_ur.urlopen(_hreq, timeout=H5).read())
                if _hresp.get("ok") or _hresp.get("self_trit", 0) >= 0:
                    r["trit"] = TRUE
                    r["char"] = "1"
                    r["status"] = "started_healthy"
            except Exception:
                pass
        if _attempt == 0:
            _time.sleep(H3)  # 3s between retry waves
    boot_trits = [r["trit"] for r in results]
    boot_bt = _bt_string(boot_trits)
    return jsonify({"ok": True, "services": results,
                    "boot_bt": boot_bt, "boot_trit": _merge_ternary(boot_trits)})

@app.post("/api/services/start")
def route_services_start_one():
    """Start a single service by name — CREATE_NO_WINDOW. TSpin-gated. Ternary state."""
    import socket, subprocess as _sp, urllib.request as _ur
    name = request.json.get("name", "")
    svc = next((s for s in BOOT_ORDER if s["name"] == name), None)
    if not svc:
        return jsonify({"ok": False, "error": f"Unknown service: {name}", "trit": FALSE_, "char": "T"})
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1.0 / 3)
        if s.connect_ex(("127.0.0.1", svc["port"])) == 0:
            return jsonify({"ok": True, "status": "already_running", "port": svc["port"], "trit": TRUE, "char": "1"})
    # TSpin Gate Check
    try:
        _gate_data = json.dumps({"name": name, "port": svc["port"]}).encode()
        _gate_req = _ur.Request("http://127.0.0.1:9970/spin/gate", data=_gate_data,
                                headers={"Content-Type": "application/json"}, method="POST")
        _gate_resp = json.loads(_ur.urlopen(_gate_req, timeout=3).read())
        if _gate_resp.get("trit", 1) == -1:
            return jsonify({"ok": False, "status": "gate_blocked", "reason": _gate_resp.get("reason", ""),
                            "trit": FALSE_, "char": "T"})
    except Exception:
        pass  # TSpin not running — proceed without gate
    try:
        # Replace ANY python.exe with pythonw.exe — catches "python", full paths, etc.
        _cmd = list(svc["cmd"])
        if _cmd and ("python" in _cmd[0].lower()) and ("pythonw" not in _cmd[0].lower()):
            _cmd[0] = r"C:\Users\Jupit\AppData\Local\Programs\Python\Python312\python.exe"
        _si = _sp.STARTUPINFO()
        _si.dwFlags |= _sp.STARTF_USESHOWWINDOW
        _si.wShowWindow = 0
        _proc = _sp.Popen(_cmd, stdout=_sp.DEVNULL, stderr=_sp.DEVNULL,
                   stdin=_sp.DEVNULL, creationflags=_CREATE_NO_WINDOW,
                   startupinfo=_si, close_fds=True)
        _CHILD_PROCS.append(_proc)
        return jsonify({"ok": True, "status": "started", "port": svc["port"], "trit": MAYBE, "char": "0"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)[:100], "trit": FALSE_, "char": "T"})

@app.get("/api/services/status")
def route_services_status():
    """Check which services are running. Ternary: trit per service + BT string."""
    import socket
    results = []
    for svc in BOOT_ORDER:
        t0 = time.time()
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(RE_TURBULENT / 1000.0)  # 343ms boundary
            connected = s.connect_ex(("127.0.0.1", svc["port"])) == 0
        ms = (time.time() - t0) * 1000
        if not connected:
            trit = FALSE_
        elif ms < RE_TURBULENT:  # fast = healthy
            trit = TRUE
        else:
            trit = MAYBE  # slow = degraded
        results.append({"name": svc["name"], "port": svc["port"], "running": connected,
                        "trit": trit, "char": '1' if trit == 1 else '0' if trit == 0 else 'T',
                        "ms": round(ms, 1)})
    trits = [r["trit"] for r in results]
    return jsonify({"services": results,
                    "up": sum(1 for r in results if r["running"]),
                    "healthy": sum(1 for t in trits if t == 1),
                    "degraded": sum(1 for t in trits if t == 0),
                    "down": sum(1 for t in trits if t == -1),
                    "total": len(results),
                    "health_bt": _bt_string(trits),
                    "overall_trit": _merge_ternary(trits)})

@app.post("/api/services/stop")
def route_services_stop_one():
    """Stop a single service by name — kills the process occupying its port.
    Ternary: +1=stopped, 0=was_not_running, -1=kill_failed."""
    import socket, subprocess as _sp
    name = request.json.get("name", "")
    svc = next((s for s in BOOT_ORDER if s["name"] == name), None)
    if not svc:
        return jsonify({"ok": False, "error": f"Unknown service: {name}", "trit": FALSE_, "char": "T"})
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1.0 / 3)
        if s.connect_ex(("127.0.0.1", svc["port"])) != 0:
            return jsonify({"ok": True, "status": "not_running", "port": svc["port"], "trit": MAYBE, "char": "0"})
    # Find and kill the process on this port
    try:
        _ssi = _sp.STARTUPINFO()
        _ssi.dwFlags |= _sp.STARTF_USESHOWWINDOW
        _ssi.wShowWindow = 0
        out = _sp.check_output(
            ["netstat", "-ano"], creationflags=_CREATE_NO_WINDOW,
            startupinfo=_ssi
        ).decode("utf-8", errors="replace")
        pid = None
        for line in out.splitlines():
            if f":{svc['port']}" in line and "LISTENING" in line:
                parts = line.strip().split()
                pid = int(parts[-1])
                break
        if pid and pid > 0:
            _sp.run(["taskkill", "/PID", str(pid), "/F", "/T"],
                    creationflags=_CREATE_NO_WINDOW, capture_output=True,
                    startupinfo=_ssi)
            time.sleep(1.0)
            # Verify it's actually dead
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s2:
                s2.settimeout(0.5)
                if s2.connect_ex(("127.0.0.1", svc["port"])) != 0:
                    return jsonify({"ok": True, "status": "stopped", "pid": pid, "port": svc["port"],
                                    "trit": TRUE, "char": "1"})
            return jsonify({"ok": False, "status": "kill_failed", "pid": pid, "port": svc["port"],
                            "trit": FALSE_, "char": "T"})
        return jsonify({"ok": False, "error": "PID not found", "port": svc["port"], "trit": FALSE_, "char": "T"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)[:200], "trit": FALSE_, "char": "T"})


@app.post("/api/services/restart")
def route_services_restart_one():
    """Restart a single service: stop then start. Ternary state."""
    import socket, subprocess as _sp
    name = request.json.get("name", "")
    svc = next((s for s in BOOT_ORDER if s["name"] == name), None)
    if not svc:
        return jsonify({"ok": False, "error": f"Unknown service: {name}", "trit": FALSE_, "char": "T"})
    # Phase 1: Kill existing process
    kill_result = {"status": "not_running"}
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1.0 / 3)
        if s.connect_ex(("127.0.0.1", svc["port"])) == 0:
            try:
                _ksi = _sp.STARTUPINFO()
                _ksi.dwFlags |= _sp.STARTF_USESHOWWINDOW
                _ksi.wShowWindow = 0
                out = _sp.check_output(
                    ["netstat", "-ano"], creationflags=_CREATE_NO_WINDOW,
                    startupinfo=_ksi
                ).decode("utf-8", errors="replace")
                for line in out.splitlines():
                    if f":{svc['port']}" in line and "LISTENING" in line:
                        pid = int(line.strip().split()[-1])
                        _sp.run(["taskkill", "/PID", str(pid), "/F", "/T"],
                                creationflags=_CREATE_NO_WINDOW, capture_output=True,
                                startupinfo=_ksi)
                        kill_result = {"status": "killed", "pid": pid}
                        break
            except Exception as e:
                kill_result = {"status": "kill_error", "error": str(e)[:100]}
            time.sleep(1.5)  # Grace period for port release
    # Phase 2: Start fresh (pythonw.exe + STARTUPINFO, zero windows)
    try:
        _cmd = list(svc["cmd"])
        if _cmd and ("python" in _cmd[0].lower()) and ("pythonw" not in _cmd[0].lower()):
            _cmd[0] = r"C:\Users\Jupit\AppData\Local\Programs\Python\Python312\python.exe"
        _si = _sp.STARTUPINFO()
        _si.dwFlags |= _sp.STARTF_USESHOWWINDOW
        _si.wShowWindow = 0
        _sp.Popen(_cmd, stdout=_sp.DEVNULL, stderr=_sp.DEVNULL,
                   stdin=_sp.DEVNULL, creationflags=_CREATE_NO_WINDOW,
                   startupinfo=_si)
        time.sleep(2.0)  # Let it boot
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s2:
            s2.settimeout(2.0)
            healthy = s2.connect_ex(("127.0.0.1", svc["port"])) == 0
        return jsonify({"ok": True, "status": "restarted", "port": svc["port"],
                        "healthy": healthy, "kill": kill_result,
                        "trit": TRUE if healthy else MAYBE, "char": "1" if healthy else "0"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)[:100], "kill": kill_result,
                        "trit": FALSE_, "char": "T"})


@app.get("/api/services/health")
@app.get("/api/services/health3")
def route_services_health3():
    """Ternary system health: each service = one trit (+1/0/-1).
    Returns 21-trit balanced ternary string reading entire system state.
    Binary monitoring gives you up/down. Ternary gives you up/DEGRADED/down.
    The MAYBE state is the key — it catches services that respond but are slow."""
    # Use full KNOWN_SERVICES registry + orchestrator itself
    # Parallel check via _check_all_services for speed
    result = _check_all_services()
    services = result.get("services", [])
    # Add orchestrator self-check (always healthy if we're responding)
    services = [{"name": "orchestrator", "port": 9999, "trit": 1, "char": "1",
                 "status": "healthy", "response_ms": 0, "consecutive_failures": 0}] + \
               [s for s in services if s.get("port") != 9999]
    bt = ''.join({1:'1',0:'0',-1:'T'}.get(r.get('trit',-1),'T') for r in services)
    healthy = sum(1 for r in services if r.get('trit') == 1)
    degraded = sum(1 for r in services if r.get('trit') == 0)
    down = sum(1 for r in services if r.get('trit') == -1)
    overall = _merge_ternary([r.get('trit',-1) for r in services]) if services else -1
    # Fetch PRIME state from Hivemind Tripple
    prime_status = {"prime_locked": False, "hyper_locked": False, "score": 0}
    try:
        import urllib.request
        r = urllib.request.urlopen("http://127.0.0.1:9881/hive/tripple/status", timeout=2)
        tp = __import__('json').loads(r.read())
        prime_status = {
            "prime_locked": bool(tp.get("prime_locked")),
            "hyper_locked": bool(tp.get("hyper_locked")),
            "score": tp.get("resonance_score", 0),
            "ripples": tp.get("total_ripples", 0),
        }
    except:
        pass
    return jsonify({
        "services": services, "bt": bt, "overall_trit": overall,
        "healthy": healthy, "degraded": degraded, "down": down, "total": len(services),
        "prime": prime_status,
    })

# ─────────────────────────────────────────────
# SERVICE HEALTH MONITORING & AUTO-RECOVERY API
# Ternary health: +1=healthy, 0=degraded, -1=dead
# Uses 3-5-7-13 harmonic constants for intervals
# ─────────────────────────────────────────────

@app.get("/api/health/detailed")
def route_health_detailed():
    """Per-service health with response times, failure counts, and ternary states.
    Checks all KNOWN_SERVICES in parallel (ThreadPoolExecutor, max_workers=H7)."""
    result = _check_all_services()
    return jsonify({"ok": True, **result})


@app.get("/api/health/summary")
def route_health_summary():
    """Quick health summary: counts and overall trit. Uses cached state if available,
    otherwise triggers a fresh check."""
    # Check if we have cached data (lock-safe: read-only snapshot, no nested lock calls)
    has_cached = False
    with _health_lock:
        has_cached = bool(_service_health)
    if not has_cached:
        # No cached data — do a fresh check (outside lock to avoid deadlock)
        result = _check_all_services()
        return jsonify({"ok": True, "total": result["total"],
                        "healthy": result["healthy"], "degraded": result["degraded"],
                        "dead": result["dead"], "down": result["dead"],
                        "overall_trit": result["overall_trit"],
                        "bt": result["bt"], "cached": False,
                        "services": result.get("services", [])})
    # Build summary from cached state
    services = []
    with _health_lock:
        for port, name in KNOWN_SERVICES.items():
            entry = _service_health.get(port)
            if entry:
                st = entry["status"]
                trit = 1 if st == "healthy" else (0 if st == "degraded" else -1)
                services.append({"port": port, "name": name, "status": st, "trit": trit,
                                 "response_ms": entry.get("response_ms", 0),
                                 "consecutive_failures": entry.get("consecutive_failures", 0)})
            else:
                services.append({"port": port, "name": name, "status": "unknown", "trit": 0,
                                 "response_ms": 0, "consecutive_failures": 0})
    healthy = sum(1 for s in services if s["trit"] == 1)
    degraded = sum(1 for s in services if s["trit"] == 0)
    dead = sum(1 for s in services if s["trit"] == -1)
    overall_trit = _merge_ternary([s["trit"] for s in services]) if services else -1
    bt = _bt_string([s["trit"] for s in services])
    return jsonify({"ok": True, "total": len(services),
                    "healthy": healthy, "degraded": degraded, "dead": dead,
                    "down": dead,
                    "overall_trit": overall_trit, "bt": bt, "cached": True,
                    "services": services})


@app.post("/api/health/check")
def route_health_check_trigger():
    """Trigger an immediate health check of all services.
    Returns full detailed results. Use this to force a fresh check."""
    result = _check_all_services()
    # Also attempt auto-recovery for any dead services
    recoveries = []
    for svc in result["services"]:
        if svc["trit"] == -1:  # dead
            recovery = _attempt_recovery(svc["port"], svc["name"])
            recoveries.append(recovery)
    return jsonify({"ok": True, **result,
                    "auto_recoveries": recoveries,
                    "recovery_count": len(recoveries)})


@app.post("/api/health/recover/<int:port>")
def route_health_recover_port(port):
    """Trigger recovery for a specific service by port number.
    Respects RECOVERY_COOLDOWN (7 minutes). Returns trit result."""
    name = KNOWN_SERVICES.get(port)
    if not name:
        # Check BOOT_ORDER as fallback
        svc = next((s for s in BOOT_ORDER if s["port"] == port), None)
        name = svc["name"] if svc else f"port-{port}"
    result = _attempt_recovery(port, name)
    return jsonify({"ok": result["trit"] >= 0, **result})


@app.get("/api/health/restart-policy")
def route_health_restart_policy():
    """View restart policies and per-service restart tracker.
    Shows attempts, backoff, crash history for each tracked service."""
    with _restart_lock:
        tracker = {}
        for port, t in _restart_tracker.items():
            name = KNOWN_SERVICES.get(port, f"port-{port}")
            can_do, reason = _can_restart(port)
            tracker[name] = {
                "port": port,
                "attempts": t["attempts"],
                "max_retries": _restart_policy["max_retries"],
                "backoff_s": round(t.get("backoff_s", 0)),
                "total_restarts": t.get("total_restarts", 0),
                "total_failures": t.get("total_failures", 0),
                "can_restart": can_do,
                "reason": reason,
                "crash_count": len(t.get("crashes", [])),
            }
    # Trit: +1 = all services restartable, 0 = some in backoff, -1 = some maxed out
    maxed = sum(1 for v in tracker.values() if v["attempts"] >= _restart_policy["max_retries"])
    backed = sum(1 for v in tracker.values() if not v["can_restart"] and v["attempts"] < _restart_policy["max_retries"])
    trit = -1 if maxed > 0 else (0 if backed > 0 else 1)
    return jsonify({
        "ok": True, "policy": _restart_policy, "monitor_running": _health_monitor_running,
        "check_interval_s": HEALTH_CHECK_INTERVAL,
        "tracked_services": len(tracker), "maxed_out": maxed, "in_backoff": backed,
        "trit": trit, "services": tracker,
    })


@app.post("/api/health/restart-policy/reset/<int:port>")
def route_health_restart_policy_reset(port):
    """Reset restart tracker for a specific service (clear backoff + attempts)."""
    with _restart_lock:
        if port in _restart_tracker:
            _restart_tracker[port]["attempts"] = 0
            _restart_tracker[port]["backoff_s"] = 0
    name = KNOWN_SERVICES.get(port, f"port-{port}")
    return jsonify({"ok": True, "port": port, "name": name, "status": "reset", "trit": 1})


# ─────────────────────────────────────────────
# CIRCUIT BREAKER & HEALTH HISTORY API
# Ternary circuit breakers (+1=CLOSED, 0=HALF_OPEN, -1=OPEN)
# Health history: per-service timestamped ring buffers (H13*H13=169 max)
# ─────────────────────────────────────────────

@app.get("/api/health/circuit-breakers")
def route_health_circuit_breakers():
    """View all circuit breaker states via the /api/health/ namespace.
    Ternary: +1=all closed, 0=some half-open, -1=any open."""
    with _cb_lock:
        breakers = {}
        for name, cb in _circuit_breakers.items():
            breakers[name] = {
                'state': _cb_state_name(cb['state']),
                'state_trit': cb['state'],
                'failures': cb['failures'],
                'successes': cb['successes'],
                'total_trips': cb['total_trips'],
                'last_check': cb.get('last_success', 0) or cb.get('last_failure', 0),
                'trit': cb['state'],
            }
        states = [cb['state'] for cb in _circuit_breakers.values()]
    open_count = sum(1 for s in states if s == -1)
    half_open_count = sum(1 for s in states if s == 0)
    overall = _merge_ternary(states) if states else 1
    return jsonify({
        'ok': True,
        'breakers': breakers,
        'total_services': len(breakers),
        'open_count': open_count,
        'half_open_count': half_open_count,
        'closed_count': len(breakers) - open_count - half_open_count,
        'trit': overall,
    })


@app.get("/api/health/history/<service_name>")
def route_health_history(service_name):
    """Per-service health history. Returns last H13 entries by default.
    Query param ?limit=N for more (max H13*H13=169).
    Ternary: +1 if latest healthy, 0 if degraded, -1 if dead/no data."""
    history = _health_history.get(service_name, [])
    limit = min(request.args.get('limit', H13, type=int), _HEALTH_HISTORY_MAX)
    recent = history[-limit:]
    latest_trit = recent[-1]['trit'] if recent else -1
    avg_response = round(sum(e['response_time'] for e in recent) / len(recent), 1) if recent else 0
    return jsonify({
        'ok': True,
        'service': service_name,
        'history': recent,
        'total_records': len(history),
        'avg_response_ms': avg_response,
        'trit': latest_trit,
    })


@app.post("/api/health/circuit-breakers/reset")
def route_health_circuit_breaker_reset():
    """Reset circuit breaker(s). POST {service: "name"} for one, or {} for all.
    Ternary: +1=reset ok."""
    data = request.get_json(silent=True) or {}
    service = data.get('service')
    with _cb_lock:
        if service:
            if service in _circuit_breakers:
                _circuit_breakers[service]['state'] = 1  # CLOSED
                _circuit_breakers[service]['failures'] = 0
                _circuit_breakers[service]['successes'] = 0
                _circuit_breakers[service]['half_open_attempts'] = 0
                return jsonify({'ok': True, 'reset': service, 'trit': 1})
            return jsonify({'ok': False, 'error': f'breaker {service} not found', 'trit': -1})
        else:
            count = len(_circuit_breakers)
            for cb in _circuit_breakers.values():
                cb['state'] = 1  # CLOSED
                cb['failures'] = 0
                cb['successes'] = 0
                cb['half_open_attempts'] = 0
            return jsonify({'ok': True, 'reset': 'all', 'count': count, 'trit': 1})


# ─────────────────────────────────────────────
# SOFTWARE & COMPILER CHECK API
# ─────────────────────────────────────────────

@app.post("/api/software/check")
def route_software_check():
    """Check if software tools are installed via version commands."""
    import subprocess as _sp
    data = request.get_json() or {}
    checks = data.get("checks", {})  # {"name": "cmd --version"}
    results = {}
    _vsi = _sp.STARTUPINFO()
    _vsi.dwFlags |= _sp.STARTF_USESHOWWINDOW
    _vsi.wShowWindow = 0
    for name, cmd in checks.items():
        try:
            r = _sp.run(cmd.split(), capture_output=True, text=True, timeout=5,
                        creationflags=_CREATE_NO_WINDOW, startupinfo=_vsi)
            if r.returncode == 0 and r.stdout.strip():
                version = r.stdout.strip().split('\n')[0][:80]
                results[name] = {"installed": True, "version": version}
            else:
                results[name] = {"installed": False}
        except Exception:
            results[name] = {"installed": False}
    return jsonify(results)


@app.get("/api/routing/table")
def route_routing_table():
    """Return the full AI routing table with categories and models."""
    from ai_router_memory import DEFAULT_RULES, FALLBACK
    from ai_router import MODELS
    return jsonify({
        "rules": DEFAULT_RULES,
        "fallback": FALLBACK,
        "models": {k: v for k, v in MODELS.items()},
        "categories": list(DEFAULT_RULES.keys()),
    })


# ─────────────────────────────────────────────
# SCRIPT PORTAL (search npm, PyPI, GitHub)
# ─────────────────────────────────────────────

@app.get("/api/scripts/search")
def route_scripts_search():
    import urllib.request, urllib.error, urllib.parse, json as _json
    q = request.args.get("q", "").strip()
    registry = request.args.get("registry", "all")
    if not q:
        return jsonify({"error": "query required"}), 400
    results = []
    # npm
    if registry in ("all", "npm"):
        try:
            url = f"https://registry.npmjs.org/-/v1/search?text={urllib.parse.quote(q)}&size=10"
            r = urllib.request.urlopen(url, timeout=8)
            data = _json.loads(r.read())
            for obj in data.get("objects", [])[:10]:
                p = obj.get("package", {})
                results.append({"name": p.get("name"), "version": p.get("version"),
                    "description": (p.get("description") or "")[:120],
                    "registry": "npm", "url": p.get("links", {}).get("npm", ""),
                    "downloads": obj.get("score", {}).get("detail", {}).get("popularity", 0)})
        except Exception as e:
            print(f"npm search failed: {e}")
    # PyPI
    if registry in ("all", "pypi"):
        try:
            url = f"https://pypi.org/pypi/{urllib.parse.quote(q)}/json"
            r = urllib.request.urlopen(url, timeout=8)
            data = _json.loads(r.read())
            info = data.get("info", {})
            results.append({"name": info.get("name"), "version": info.get("version"),
                "description": (info.get("summary") or "")[:120],
                "registry": "pypi", "url": info.get("package_url", ""),
                "downloads": 0})
        except Exception as e:
            print(f"PyPI search failed: {e}")
    # GitHub
    if registry in ("all", "github"):
        try:
            url = f"https://api.github.com/search/repositories?q={urllib.parse.quote(q)}&sort=stars&per_page=8"
            req = urllib.request.Request(url, headers={"User-Agent": "NovaX/4.0"})
            r = urllib.request.urlopen(req, timeout=8)
            data = _json.loads(r.read())
            for repo in data.get("items", [])[:8]:
                results.append({"name": repo.get("full_name"), "version": f"{repo.get('stargazers_count', 0)} stars",
                    "description": (repo.get("description") or "")[:120],
                    "registry": "github", "url": repo.get("html_url", ""),
                    "downloads": repo.get("stargazers_count", 0)})
        except Exception as e:
            print(f"GitHub search failed: {e}")
    return jsonify({"query": q, "results": results, "total": len(results)})

@app.post("/api/scripts/install")
def route_scripts_install():
    data = request.get_json() or {}
    name = data.get("name", "")
    registry = data.get("registry", "pip")
    if not name:
        return jsonify({"error": "name required"}), 400
    # Sanitize: only allow safe package name characters (prevent command injection)
    import re as _re_mod
    if not _re_mod.match(r'^[a-zA-Z0-9@._/\-]+$', name):
        return jsonify({"error": "Invalid package name (alphanumeric, @._/- only)"}), 400
    cmds = {"pip": ["pip", "install", name], "npm": ["npm", "install", "-g", name],
            "git": ["git", "clone", f"https://github.com/{name}"]}
    cmd = cmds.get(registry, ["pip", "install", name])
    try:
        import subprocess
        _psi = subprocess.STARTUPINFO()
        _psi.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        _psi.wShowWindow = 0
        result = subprocess.run(cmd, shell=False, capture_output=True, text=True, timeout=60,
                                creationflags=0x08000000, startupinfo=_psi)
        return jsonify({"ok": result.returncode == 0, "output": result.stdout[-500:],
                        "error": result.stderr[-300:] if result.returncode != 0 else ""})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

# ─────────────────────────────────────────────
# SCRIPT VAULT PROXY (port 9938)
# ─────────────────────────────────────────────
_VAULT_PORT = 9938

@app.get("/api/vault/status")
def route_vault_status():
    return jsonify(_proxy_get(f"http://127.0.0.1:{_VAULT_PORT}/vault/status"))

@app.get("/api/vault/catalog")
def route_vault_catalog():
    return jsonify(_proxy_get(f"http://127.0.0.1:{_VAULT_PORT}/vault/catalog"))

@app.get("/api/vault/categories")
def route_vault_categories():
    return jsonify(_proxy_get(f"http://127.0.0.1:{_VAULT_PORT}/vault/categories"))

@app.get("/api/vault/popular")
def route_vault_popular():
    return jsonify(_proxy_get(f"http://127.0.0.1:{_VAULT_PORT}/vault/popular"))

@app.get("/api/vault/stats")
def route_vault_stats():
    return jsonify(_proxy_get(f"http://127.0.0.1:{_VAULT_PORT}/vault/stats"))

@app.get("/api/vault/portals")
def route_vault_portals():
    return jsonify(_proxy_get(f"http://127.0.0.1:{_VAULT_PORT}/vault/portals"))

@app.get("/api/vault/tripple")
def route_vault_tripple():
    return jsonify(_proxy_get(f"http://127.0.0.1:{_VAULT_PORT}/vault/tripple"))

@app.post("/api/vault/list")
def route_vault_list():
    return jsonify(_proxy_post(f"http://127.0.0.1:{_VAULT_PORT}/vault/list", request.get_json(force=True, silent=True) or {}))

@app.post("/api/vault/search")
def route_vault_search():
    return jsonify(_proxy_post(f"http://127.0.0.1:{_VAULT_PORT}/vault/search", request.get_json(force=True, silent=True) or {}))

@app.post("/api/vault/grep")
def route_vault_grep():
    return jsonify(_proxy_post(f"http://127.0.0.1:{_VAULT_PORT}/vault/grep", request.get_json(force=True, silent=True) or {}))

@app.post("/api/vault/get")
def route_vault_get():
    return jsonify(_proxy_post(f"http://127.0.0.1:{_VAULT_PORT}/vault/get", request.get_json(force=True, silent=True) or {}))

@app.post("/api/vault/run")
def route_vault_run():
    return jsonify(_proxy_post(f"http://127.0.0.1:{_VAULT_PORT}/vault/run", request.get_json(force=True, silent=True) or {}))

@app.post("/api/vault/portal")
def route_vault_portal():
    return jsonify(_proxy_post(f"http://127.0.0.1:{_VAULT_PORT}/vault/portal", request.get_json(force=True, silent=True) or {}))


# ─────────────────────────────────────────────
# QUANTIZER PROXY (port 9939)
# ─────────────────────────────────────────────
_QUANTIZER_PORT = 9939

@app.get("/api/quantizer/status")
def route_quantizer_status():
    return jsonify(_proxy_get(f"http://127.0.0.1:{_QUANTIZER_PORT}/quantizer/status"))

@app.post("/api/quantizer/hardware")
def route_quantizer_hardware():
    return jsonify(_proxy_post(f"http://127.0.0.1:{_QUANTIZER_PORT}/quantizer/hardware", request.get_json(force=True, silent=True) or {}))

@app.post("/api/quantizer/scan")
def route_quantizer_scan():
    return jsonify(_proxy_post(f"http://127.0.0.1:{_QUANTIZER_PORT}/quantizer/scan", request.get_json(force=True, silent=True) or {}))

@app.post("/api/quantizer/analyze")
def route_quantizer_analyze():
    return jsonify(_proxy_post(f"http://127.0.0.1:{_QUANTIZER_PORT}/quantizer/analyze", request.get_json(force=True, silent=True) or {}))

@app.post("/api/quantizer/quantize")
def route_quantizer_quantize():
    return jsonify(_proxy_post(f"http://127.0.0.1:{_QUANTIZER_PORT}/quantizer/quantize", request.get_json(force=True, silent=True) or {}))

@app.get("/api/quantizer/savings")
def route_quantizer_savings():
    return jsonify(_proxy_get(f"http://127.0.0.1:{_QUANTIZER_PORT}/quantizer/savings"))

@app.get("/api/quantizer/models")
def route_quantizer_models():
    return jsonify(_proxy_get(f"http://127.0.0.1:{_QUANTIZER_PORT}/quantizer/models"))

@app.post("/api/quantizer/estimate")
def route_quantizer_estimate():
    return jsonify(_proxy_post(f"http://127.0.0.1:{_QUANTIZER_PORT}/quantizer/estimate", request.get_json(force=True, silent=True) or {}))

@app.get("/api/quantizer/tripple")
def route_quantizer_tripple():
    return jsonify(_proxy_get(f"http://127.0.0.1:{_QUANTIZER_PORT}/quantizer/tripple"))

# ── Hardware Detection & Quantized Enhancement ──────────────────────────
_HARDWARE_PORT = 9943

@app.get("/api/hw/detect")
def route_hw_detect():
    return jsonify(_proxy_get(f"http://127.0.0.1:{_HARDWARE_PORT}/hw/detect"))

@app.get("/api/hw/quant")
def route_hw_quant():
    return jsonify(_proxy_get(f"http://127.0.0.1:{_HARDWARE_PORT}/hw/quant"))

@app.get("/api/hw/enhance")
def route_hw_enhance():
    return jsonify(_proxy_get(f"http://127.0.0.1:{_HARDWARE_PORT}/hw/enhance"))

@app.get("/api/hw/full")
def route_hw_full():
    return jsonify(_proxy_get(f"http://127.0.0.1:{_HARDWARE_PORT}/hw/full"))

@app.get("/api/hw/ollama")
def route_hw_ollama():
    return jsonify(_proxy_get(f"http://127.0.0.1:{_HARDWARE_PORT}/hw/ollama"))

@app.get("/api/hw/ternary")
def route_hw_ternary():
    return jsonify(_proxy_get(f"http://127.0.0.1:{_HARDWARE_PORT}/hw/ternary"))


# ─────────────────────────────────────────────
# STATIC FILE SERVING (hivemind.html etc.)
# ─────────────────────────────────────────────

@app.get("/api/watchdog/status")
def route_watchdog_status():
    log_file = os.path.join(str(Path(__file__).parent.parent), "memory", "watchdog_log.json")
    log_entries = []
    if os.path.exists(log_file):
        try:
            with open(log_file) as f:
                log_entries = json.load(f)
        except Exception:
            pass
    return jsonify({"running": len(log_entries) > 0, "entries": log_entries[-20:], "total_events": len(log_entries)})

@app.post("/api/watchdog/start")
def route_watchdog_start():
    # DISABLED: Watchdog removed per user request (Session 34) — was causing Edge lock-out
    return jsonify({"ok": False, "error": "Watchdog permanently disabled", "reason": "Removed Session 34 — caused Edge fullscreen lock-out"}), 403

# ─────────────────────────────────────────────
# OS INTEGRATION (wallpaper, theme, protocol, context menu, etc.)
# ─────────────────────────────────────────────

@app.get("/api/os/integration")
def route_os_integration():
    return jsonify(integration_status())

@app.post("/api/os/integration/enable-all")
def route_os_integration_enable():
    # DISABLED: OS integration enable blocked (Session 34)
    return jsonify({"ok": False, "error": "OS integration permanently disabled", "reason": "Removed Session 34"}), 403

@app.post("/api/os/integration/disable-all")
def route_os_integration_disable():
    return jsonify(integration_disable_all())

@app.post("/api/os/wallpaper/set")
def route_os_wallpaper_set():
    return jsonify(set_wallpaper())

@app.post("/api/os/wallpaper/restore")
def route_os_wallpaper_restore():
    return jsonify(restore_wallpaper())

@app.post("/api/os/theme/set")
def route_os_theme_set():
    return jsonify(set_theme())

@app.post("/api/os/theme/restore")
def route_os_theme_restore():
    return jsonify(restore_theme())

@app.post("/api/os/protocol/register")
def route_os_protocol_register():
    return jsonify(register_protocol())

@app.post("/api/os/protocol/unregister")
def route_os_protocol_unregister():
    return jsonify(unregister_protocol())

@app.post("/api/os/context-menu/add")
def route_os_ctx_menu_add():
    return jsonify(add_context_menu())

@app.post("/api/os/context-menu/remove")
def route_os_ctx_menu_remove():
    return jsonify(remove_context_menu())

@app.post("/api/os/file-assoc/set")
def route_os_file_assoc_set():
    return jsonify(set_file_associations())

@app.post("/api/os/file-assoc/restore")
def route_os_file_assoc_restore():
    return jsonify(restore_file_associations())

@app.post("/api/os/taskbar/hide")
def route_os_taskbar_hide():
    return jsonify(hide_taskbar())

@app.post("/api/os/taskbar/show")
def route_os_taskbar_show():
    return jsonify(show_taskbar())

@app.get("/api/os/apps")
def route_os_apps():
    return jsonify(scan_installed_apps())

@app.post("/api/os/revert")
def route_os_revert():
    return jsonify({"ok": True, "trit": 1, "message": "NovaX is not in OS mode — nothing to revert"})

@app.post("/api/os/tray/start")
def route_os_tray_start():
    # DISABLED: Tray removed per user request (Session 34) — was launching Edge fullscreen
    return jsonify({"ok": False, "error": "Tray permanently disabled", "reason": "Removed Session 34 — launched Edge fullscreen lock-out"}), 403

@app.get("/api/os/lockscreen")
def route_os_lockscreen_status():
    return jsonify(lockscreen_status())

@app.post("/api/os/lockscreen/set")
def route_os_lockscreen_set():
    return jsonify(set_lock_screen())

@app.post("/api/os/lockscreen/restore")
def route_os_lockscreen_restore():
    return jsonify(restore_lock_screen())

# ── Process Manager routes ──
@app.get("/api/pm/status")
def route_pm_status():
    try:
        sys.path.insert(0, str(ROOT / "installer"))
        import novax_process_manager as pm
        result = pm.status()
        result["source"] = "novax_process_manager"
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e), "source": "pm_error"})

@app.post("/api/pm/kill")
def route_pm_kill():
    try:
        sys.path.insert(0, str(ROOT / "installer"))
        import novax_process_manager as pm
        return jsonify(pm.kill_all_novax())
    except Exception as e:
        return jsonify({"error": str(e)})

# ── Route Validator endpoints (security sublayer) ──
@app.get("/api/routes/verify")
def route_routes_verify():
    """Run a smoke test NOW and return results."""
    try:
        from route_validator import get_validator
        rv = get_validator()
        smoke = rv.smoke_test_all()
        return jsonify({"smoke": smoke, "summary": rv.get_summary()})
    except Exception as e:
        return jsonify({"error": str(e)})

@app.get("/api/routes/status")
def route_routes_status():
    """Get route validator status + summary."""
    try:
        from route_validator import get_validator
        rv = get_validator()
        return jsonify(rv.status())
    except Exception as e:
        return jsonify({"error": str(e)})

@app.get("/api/routes/manifest")
def route_routes_manifest():
    """Get full route manifest."""
    try:
        from route_validator import get_validator
        rv = get_validator()
        return jsonify(rv.get_manifest())
    except Exception as e:
        return jsonify({"error": str(e)})

@app.get("/api/routes/deep")
def route_routes_deep():
    """Run Tier 2 deep validation on critical routes NOW."""
    try:
        from route_validator import get_validator
        rv = get_validator()
        deep = rv.deep_validate_critical()
        return jsonify({"deep": deep, "summary": rv.get_summary()})
    except Exception as e:
        return jsonify({"error": str(e)})

# ── Physics Strategy routes ──

@app.get("/api/hive/ns/status")
def route_ns_status():
    return jsonify(_proxy_get("http://127.0.0.1:9881/ns/unsolved"))

@app.get("/api/hive/influence")
def route_hive_influence():
    return jsonify(_proxy_get("http://127.0.0.1:9881/hive/influence"))

@app.get("/api/hive/territory")
def route_hive_territory():
    return jsonify(_proxy_get("http://127.0.0.1:9881/hive/territory"))

@app.get("/api/patch/influence")
def route_patch_influence():
    return jsonify(_proxy_get("http://127.0.0.1:9889/patch/influence"))

@app.get("/api/patch/chess/lookahead")
def route_chess_lookahead():
    return jsonify(_proxy_get("http://127.0.0.1:9889/patch/chess/lookahead"))

@app.get("/api/patch/chess/opening")
def route_chess_opening():
    qs = request.query_string.decode()
    url = "http://127.0.0.1:9889/patch/chess/opening" + ("?" + qs if qs else "")
    return jsonify(_proxy_get(url))

@app.get("/api/patch/chess/endgame")
def route_chess_endgame():
    qs = request.query_string.decode()
    url = "http://127.0.0.1:9889/patch/chess/endgame" + ("?" + qs if qs else "")
    return jsonify(_proxy_get(url))

@app.get("/api/patch/chess/status")
def route_chess_status():
    return jsonify(_proxy_get("http://127.0.0.1:9889/patch/chess/status"))

@app.post("/api/patch/chess/record")
def route_chess_record():
    return jsonify(_proxy_post_json("http://127.0.0.1:9889/patch/chess/record",
                                    request.get_json(force=True, silent=True) or {}))

@app.get("/api/patch/japanese/status")
def route_japanese_status():
    return jsonify(_proxy_get("http://127.0.0.1:9889/patch/japanese/status"))

# ── NovaX Native Tools routes ──
TOOLS_URL = "http://127.0.0.1:9891"

@app.post("/api/tools/read")
def route_tools_read():
    return jsonify(_proxy_post(f"{TOOLS_URL}/tools/read", request.get_json(force=True)))

@app.post("/api/tools/write")
def route_tools_write():
    return jsonify(_proxy_post(f"{TOOLS_URL}/tools/write", request.get_json(force=True)))

@app.post("/api/tools/grep")
def route_tools_grep():
    return jsonify(_proxy_post(f"{TOOLS_URL}/tools/grep", request.get_json(force=True)))

@app.post("/api/tools/glob")
def route_tools_glob():
    return jsonify(_proxy_post(f"{TOOLS_URL}/tools/glob", request.get_json(force=True)))

@app.post("/api/tools/run")
def route_tools_run():
    return jsonify(_proxy_post(f"{TOOLS_URL}/tools/run", request.get_json(force=True)))

@app.post("/api/tools/edit")
def route_tools_edit():
    return jsonify(_proxy_post(f"{TOOLS_URL}/tools/edit", request.get_json(force=True)))

@app.post("/api/tools/pipe")
def route_tools_pipe():
    return jsonify(_proxy_post(f"{TOOLS_URL}/tools/pipe", request.get_json(force=True)))

@app.get("/api/tools/status")
def route_tools_status():
    return jsonify(_proxy_get(f"{TOOLS_URL}/tools/status"))

@app.get("/api/tools/predict")
def route_tools_predict():
    return jsonify(_proxy_get(f"{TOOLS_URL}/tools/predict"))

# ── TMulti composition routes ──
@app.post("/api/multi")
def route_multi():
    return jsonify(_proxy_post(f"{TOOLS_URL}/multi", request.get_json(force=True)))

@app.get("/api/multi/modes")
def route_multi_modes():
    return jsonify(_proxy_get(f"{TOOLS_URL}/multi/modes"))

# ── NovaX Vault routes ──
VAULT_URL = "http://127.0.0.1:9892"

## route_vault_status already defined above (line ~3524) — removed duplicate

@app.get("/api/vault/scan")
def route_vault_scan():
    return jsonify(_proxy_get(f"{VAULT_URL}/vault/scan"))

@app.get("/api/vault/files")
def route_vault_list_files():
    return jsonify(_proxy_get(f"{VAULT_URL}/vault/list"))

@app.post("/api/vault/set-password")
def route_vault_set_password():
    return jsonify(_proxy_post(f"{VAULT_URL}/vault/set-password", request.get_json(force=True)))

@app.post("/api/vault/unlock-session")
def route_vault_unlock_session():
    return jsonify(_proxy_post(f"{VAULT_URL}/vault/unlock-session", request.get_json(force=True)))

@app.post("/api/vault/lock-session")
def route_vault_lock_session():
    return jsonify(_proxy_post(f"{VAULT_URL}/vault/lock-session", request.get_json(force=True)))

@app.post("/api/vault/lock")
def route_vault_lock_file():
    return jsonify(_proxy_post(f"{VAULT_URL}/vault/lock", request.get_json(force=True)))

@app.post("/api/vault/unlock")
def route_vault_unlock_file():
    return jsonify(_proxy_post(f"{VAULT_URL}/vault/unlock", request.get_json(force=True)))

@app.post("/api/vault/lock-dir")
def route_vault_lock_dir():
    return jsonify(_proxy_post_json(f"{VAULT_URL}/vault/lock-dir", request.get_json(force=True), timeout=120))

@app.post("/api/vault/scan-dir")
def route_vault_scan_dir():
    return jsonify(_proxy_post(f"{VAULT_URL}/vault/scan-dir", request.get_json(force=True)))

@app.post("/api/vault/shred")
def route_vault_shred():
    return jsonify(_proxy_post(f"{VAULT_URL}/vault/shred", request.get_json(force=True)))

# ── DeepStorage proxy (port 9893) ──
DEEP_URL = "http://127.0.0.1:9893"

@app.get("/api/deep/status")
def route_deep_status():
    return jsonify(_proxy_get(f"{DEEP_URL}/deep/status"))

@app.get("/api/deep/dedup")
def route_deep_dedup():
    return jsonify(_proxy_get(f"{DEEP_URL}/deep/dedup"))

@app.get("/api/deep/tiers")
def route_deep_tiers():
    return jsonify(_proxy_get(f"{DEEP_URL}/deep/tiers"))

@app.get("/api/deep/patterns")
def route_deep_patterns():
    return jsonify(_proxy_get(f"{DEEP_URL}/deep/patterns"))

@app.post("/api/deep/quantize")
def route_deep_quantize():
    return jsonify(_proxy_post_json(f"{DEEP_URL}/deep/quantize", request.get_json(force=True), timeout=300))

@app.post("/api/deep/restore")
def route_deep_restore():
    return jsonify(_proxy_post(f"{DEEP_URL}/deep/restore", request.get_json(force=True)))

@app.post("/api/deep/scan")
def route_deep_scan():
    return jsonify(_proxy_post_json(f"{DEEP_URL}/deep/scan", request.get_json(force=True), timeout=120))

@app.post("/api/deep/watch")
def route_deep_watch():
    return jsonify(_proxy_post(f"{DEEP_URL}/deep/watch", request.get_json(force=True)))

@app.post("/api/deep/unwatch")
def route_deep_unwatch():
    return jsonify(_proxy_post(f"{DEEP_URL}/deep/unwatch", request.get_json(force=True)))

@app.get("/api/deep/vdelta")
def route_deep_vdelta():
    return jsonify(_proxy_get(f"{DEEP_URL}/deep/vdelta"))

@app.post("/api/deep/vdelta/snapshot")
def route_deep_vdelta_snapshot():
    return jsonify(_proxy_post_json(f"{DEEP_URL}/deep/vdelta/snapshot", request.get_json(force=True), timeout=120))

@app.post("/api/deep/vdelta/add")
def route_deep_vdelta_add():
    return jsonify(_proxy_post(f"{DEEP_URL}/deep/vdelta/add", request.get_json(force=True)))

@app.post("/api/deep/vdelta/restore")
def route_deep_vdelta_restore():
    return jsonify(_proxy_post(f"{DEEP_URL}/deep/vdelta/restore", request.get_json(force=True)))

@app.post("/api/deep/vdelta/versions")
def route_deep_vdelta_versions():
    return jsonify(_proxy_post(f"{DEEP_URL}/deep/vdelta/versions", request.get_json(force=True)))

@app.post("/api/deep/vdelta/save")
def route_deep_vdelta_save():
    return jsonify(_proxy_post(f"{DEEP_URL}/deep/vdelta/save", request.get_json(force=True)))

@app.post("/api/deep/vdelta/load")
def route_deep_vdelta_load():
    return jsonify(_proxy_post(f"{DEEP_URL}/deep/vdelta/load", request.get_json(force=True)))

# ── TScale proxy (port 9986) ──
TSCALE_URL = "http://127.0.0.1:9986"

@app.get("/api/scale/status")
def route_scale_status():
    return jsonify(_proxy_get(f"{TSCALE_URL}/scale/status"))

@app.get("/api/scale/weigh")
def route_scale_weigh():
    return jsonify(_proxy_get(f"{TSCALE_URL}/scale/weigh"))

@app.get("/api/scale/conflicts")
def route_scale_conflicts():
    return jsonify(_proxy_get(f"{TSCALE_URL}/scale/conflicts"))

@app.get("/api/scale/continuity")
def route_scale_continuity():
    return jsonify(_proxy_get(f"{TSCALE_URL}/scale/continuity"))

@app.get("/api/scale/registry")
def route_scale_registry():
    return jsonify(_proxy_get(f"{TSCALE_URL}/scale/registry"))

@app.get("/api/scale/reservations")
def route_scale_reservations():
    return jsonify(_proxy_get(f"{TSCALE_URL}/scale/reservations"))

@app.post("/api/scale/reserve")
def route_scale_reserve():
    return jsonify(_proxy_post(f"{TSCALE_URL}/scale/reserve", request.get_json(force=True)))

@app.post("/api/scale/free")
def route_scale_free():
    return jsonify(_proxy_post(f"{TSCALE_URL}/scale/free", request.get_json(force=True)))

@app.post("/api/scale/resolve")
def route_scale_resolve():
    return jsonify(_proxy_post(f"{TSCALE_URL}/scale/resolve", request.get_json(force=True)))

@app.post("/api/scale/rebalance")
def route_scale_rebalance():
    return jsonify(_proxy_post(f"{TSCALE_URL}/scale/rebalance", request.get_json(force=True)))

@app.post("/api/scale/check")
def route_scale_check():
    return jsonify(_proxy_post(f"{TSCALE_URL}/scale/check", request.get_json(force=True)))

@app.post("/api/scale/kill_port")
def route_scale_kill_port():
    return jsonify(_proxy_post(f"{TSCALE_URL}/scale/kill_port", request.get_json(force=True)))

# ── TShield proxy (port 9987) ──
TSHIELD_URL = "http://127.0.0.1:9987"

@app.get("/api/shield/status")
def route_shield_status():
    return jsonify(_proxy_get(f"{TSHIELD_URL}/shield/status"))

@app.get("/api/shield/identity")
def route_shield_identity():
    return jsonify(_proxy_get(f"{TSHIELD_URL}/shield/identity"))

@app.get("/api/shield/threats")
def route_shield_threats():
    return jsonify(_proxy_get(f"{TSHIELD_URL}/shield/threats"))

@app.get("/api/shield/reflections")
def route_shield_reflections():
    return jsonify(_proxy_get(f"{TSHIELD_URL}/shield/reflections"))

@app.get("/api/shield/layers")
def route_shield_layers():
    return jsonify(_proxy_get(f"{TSHIELD_URL}/shield/layers"))

@app.get("/api/shield/noise")
def route_shield_noise():
    return jsonify(_proxy_get(f"{TSHIELD_URL}/shield/noise"))

@app.post("/api/shield/analyze")
def route_shield_analyze():
    return jsonify(_proxy_post(f"{TSHIELD_URL}/shield/analyze", request.get_json(force=True)))

@app.post("/api/shield/reflect")
def route_shield_reflect():
    return jsonify(_proxy_post(f"{TSHIELD_URL}/shield/reflect", request.get_json(force=True)))

@app.post("/api/shield/block")
def route_shield_block():
    return jsonify(_proxy_post(f"{TSHIELD_URL}/shield/block", request.get_json(force=True)))

@app.post("/api/shield/unblock")
def route_shield_unblock():
    return jsonify(_proxy_post(f"{TSHIELD_URL}/shield/unblock", request.get_json(force=True)))

@app.post("/api/shield/rotate")
def route_shield_rotate():
    return jsonify(_proxy_post(f"{TSHIELD_URL}/shield/rotate", request.get_json(force=True)))

@app.post("/api/shield/layer")
def route_shield_layer():
    return jsonify(_proxy_post(f"{TSHIELD_URL}/shield/layer", request.get_json(force=True)))

@app.post("/api/shield/lockdown")
def route_shield_lockdown():
    return jsonify(_proxy_post(f"{TSHIELD_URL}/shield/lockdown", request.get_json(force=True)))

# ── THunter proxy (port 9988) ──
THUNTER_URL = "http://127.0.0.1:9988"

@app.get("/api/hunter/health")
def route_hunter_health():
    return jsonify(_proxy_get(f"{THUNTER_URL}/health"))

@app.get("/api/hunter/status")
def route_hunter_status():
    return jsonify(_proxy_get(f"{THUNTER_URL}/hunt/status"))

@app.get("/api/hunter/scan")
def route_hunter_scan():
    return jsonify(_proxy_get(f"{THUNTER_URL}/hunt/scan"))

@app.get("/api/hunter/allowlist")
def route_hunter_allowlist():
    return jsonify(_proxy_get(f"{THUNTER_URL}/hunt/allowlist"))

@app.post("/api/hunter/add")
def route_hunter_add():
    return jsonify(_proxy_post(f"{THUNTER_URL}/hunt/add", request.get_json(force=True)))

@app.post("/api/hunter/remove")
def route_hunter_remove():
    return jsonify(_proxy_post(f"{THUNTER_URL}/hunt/remove", request.get_json(force=True)))

@app.post("/api/hunter/kill")
def route_hunter_kill():
    return jsonify(_proxy_post(f"{THUNTER_URL}/hunt/kill", request.get_json(force=True)))

@app.get("/api/hunter/triad")
def route_hunter_triad():
    return jsonify(_proxy_get(f"{THUNTER_URL}/triad"))

# ── Ternary Tools proxy (port 9894) ──
TTOOLS_URL = "http://127.0.0.1:9894"

@app.get("/api/ttools/status")
def route_ttools_status():
    return jsonify(_proxy_get(f"{TTOOLS_URL}/ttools/status"))

@app.get("/api/ttools/cache/status")
def route_ttools_cache_status():
    return jsonify(_proxy_get(f"{TTOOLS_URL}/ttools/cache/status"))

@app.get("/api/ttools/cache/get")
def route_ttools_cache_get():
    key = request.args.get("key", "")
    return jsonify(_proxy_get(f"{TTOOLS_URL}/ttools/cache/get?key={key}"))

@app.get("/api/ttools/stream/read")
def route_ttools_stream_read():
    name = request.args.get("name", "")
    count = request.args.get("count", "13")
    return jsonify(_proxy_get(f"{TTOOLS_URL}/ttools/stream/read?name={name}&count={count}"))

@app.post("/api/ttools/diff")
def route_ttools_diff():
    return jsonify(_proxy_post_json(f"{TTOOLS_URL}/ttools/diff", request.get_json(force=True), timeout=60))

@app.post("/api/ttools/diff/apply")
def route_ttools_diff_apply():
    return jsonify(_proxy_post_json(f"{TTOOLS_URL}/ttools/diff/apply", request.get_json(force=True), timeout=60))

@app.post("/api/ttools/cache/set")
def route_ttools_cache_set():
    return jsonify(_proxy_post(f"{TTOOLS_URL}/ttools/cache/set", request.get_json(force=True)))

@app.post("/api/ttools/sync")
def route_ttools_sync():
    return jsonify(_proxy_post_json(f"{TTOOLS_URL}/ttools/sync", request.get_json(force=True), timeout=120))

@app.post("/api/ttools/index")
def route_ttools_index():
    return jsonify(_proxy_post_json(f"{TTOOLS_URL}/ttools/index", request.get_json(force=True), timeout=120))

@app.post("/api/ttools/search")
def route_ttools_search():
    return jsonify(_proxy_post_json(f"{TTOOLS_URL}/ttools/search", request.get_json(force=True), timeout=60))

@app.post("/api/ttools/mesh")
def route_ttools_mesh():
    return jsonify(_proxy_post(f"{TTOOLS_URL}/ttools/mesh", request.get_json(force=True)))

@app.post("/api/ttools/stream/start")
def route_ttools_stream_start():
    return jsonify(_proxy_post(f"{TTOOLS_URL}/ttools/stream/start", request.get_json(force=True)))

@app.post("/api/ttools/stream/write")
def route_ttools_stream_write():
    return jsonify(_proxy_post(f"{TTOOLS_URL}/ttools/stream/write", request.get_json(force=True)))

@app.post("/api/ttools/forge")
def route_ttools_forge():
    return jsonify(_proxy_post_json(f"{TTOOLS_URL}/ttools/forge", request.get_json(force=True), timeout=60))

@app.post("/api/ttools/filter")
def route_ttools_filter():
    return jsonify(_proxy_post_json(f"{TTOOLS_URL}/ttools/filter", request.get_json(force=True), timeout=30))

# ── TFlow — N-S Pipe Flow Routing (memory + downloads) ──
@app.post("/api/ttools/flow/message")
def route_tflow_message():
    return jsonify(_proxy_post_json(f"{TTOOLS_URL}/ttools/flow/message", request.get_json(force=True), timeout=30))

@app.post("/api/ttools/flow/recall")
def route_tflow_recall():
    return jsonify(_proxy_post_json(f"{TTOOLS_URL}/ttools/flow/recall", request.get_json(force=True), timeout=30))

@app.post("/api/ttools/flow/download")
def route_tflow_download():
    return jsonify(_proxy_post_json(f"{TTOOLS_URL}/ttools/flow/download", request.get_json(force=True), timeout=30))

@app.get("/api/ttools/flow/status")
def route_tflow_status():
    return jsonify(_proxy_get(f"{TTOOLS_URL}/ttools/flow/status"))

# ── TTools Layer endpoints (Layers 2-6) ──
@app.get("/api/ttools/weave/status")
def route_ttools_weave_status():
    return jsonify(_proxy_get(f"{TTOOLS_URL}/ttools/weave/status"))

@app.get("/api/ttools/forge/alerts")
def route_ttools_forge_alerts():
    return jsonify(_proxy_get(f"{TTOOLS_URL}/ttools/forge/alerts"))

@app.get("/api/ttools/timeline/status")
def route_ttools_timeline_status():
    return jsonify(_proxy_get(f"{TTOOLS_URL}/ttools/timeline/status"))

@app.get("/api/ttools/mesh/heartbeats")
def route_ttools_mesh_heartbeats():
    return jsonify(_proxy_get(f"{TTOOLS_URL}/ttools/mesh/heartbeats"))

@app.post("/api/ttools/weave/channel")
def route_ttools_weave_channel():
    return jsonify(_proxy_post(f"{TTOOLS_URL}/ttools/weave/channel", request.get_json(force=True)))

@app.post("/api/ttools/weave/send")
def route_ttools_weave_send():
    return jsonify(_proxy_post(f"{TTOOLS_URL}/ttools/weave/send", request.get_json(force=True)))

@app.post("/api/ttools/timeline/track")
def route_ttools_timeline_track():
    return jsonify(_proxy_post(f"{TTOOLS_URL}/ttools/timeline/track", request.get_json(force=True)))

@app.post("/api/ttools/timeline/restore")
def route_ttools_timeline_restore():
    return jsonify(_proxy_post_json(f"{TTOOLS_URL}/ttools/timeline/restore", request.get_json(force=True), timeout=60))

@app.post("/api/ttools/shield/record")
def route_ttools_shield_record():
    return jsonify(_proxy_post(f"{TTOOLS_URL}/ttools/shield/record", request.get_json(force=True)))

@app.post("/api/ttools/shield/analyze")
def route_ttools_shield_analyze():
    return jsonify(_proxy_post_json(f"{TTOOLS_URL}/ttools/shield/analyze", request.get_json(force=True) or {}, timeout=30))

# ── TImmune Layer 7 proxy routes ──
@app.get("/api/ttools/immune/status")
def route_ttools_immune_status():
    return jsonify(_proxy_get(f"{TTOOLS_URL}/ttools/immune/status"))

@app.get("/api/ttools/immune/history")
def route_ttools_immune_history():
    return jsonify(_proxy_get(f"{TTOOLS_URL}/ttools/immune/history"))

@app.post("/api/ttools/immune/heal")
def route_ttools_immune_heal():
    return jsonify(_proxy_post_json(f"{TTOOLS_URL}/ttools/immune/heal", request.get_json(force=True), timeout=30))

@app.post("/api/ttools/immune/port_guard")
def route_ttools_immune_port_guard():
    return jsonify(_proxy_post_json(f"{TTOOLS_URL}/ttools/immune/port_guard", request.get_json(force=True), timeout=10))

@app.post("/api/ttools/immune/bind_check")
def route_ttools_immune_bind_check():
    return jsonify(_proxy_post_json(f"{TTOOLS_URL}/ttools/immune/bind_check", request.get_json(force=True), timeout=10))

@app.post("/api/ttools/immune/self_heal")
def route_ttools_immune_self_heal():
    return jsonify(_proxy_post_json(f"{TTOOLS_URL}/ttools/immune/self_heal", request.get_json(force=True), timeout=30))

@app.get("/api/ttools/zombie/scan")
def route_ttools_zombie_scan():
    return jsonify(_proxy_get(f"{TTOOLS_URL}/ttools/zombie/scan"))

@app.get("/api/ttools/zombie/status")
def route_ttools_zombie_status():
    return jsonify(_proxy_get(f"{TTOOLS_URL}/ttools/zombie/status"))

@app.post("/api/ttools/zombie/kill")
def route_ttools_zombie_kill():
    return jsonify(_proxy_post_json(f"{TTOOLS_URL}/ttools/zombie/kill", request.get_json(force=True), timeout=30))

@app.post("/api/ttools/zombie/sweep")
def route_ttools_zombie_sweep():
    return jsonify(_proxy_post_json(f"{TTOOLS_URL}/ttools/zombie/sweep", request.get_json(force=True), timeout=30))

# ── TSpeak proxy (port 9895) ──
TSPEAK_URL = "http://127.0.0.1:9895"

@app.get("/api/tspeak/status")
def route_tspeak_status():
    return jsonify(_proxy_get(f"{TSPEAK_URL}/tspeak/status"))

@app.post("/api/tspeak/encode")
def route_tspeak_encode():
    return jsonify(_proxy_post_json(f"{TSPEAK_URL}/tspeak/encode", request.get_json(force=True), timeout=30))

@app.post("/api/tspeak/decode")
def route_tspeak_decode():
    return jsonify(_proxy_post_json(f"{TSPEAK_URL}/tspeak/decode", request.get_json(force=True), timeout=30))

@app.post("/api/tspeak/deliberate")
def route_tspeak_deliberate():
    return jsonify(_proxy_post_json(f"{TSPEAK_URL}/tspeak/deliberate", request.get_json(force=True), timeout=60))

@app.post("/api/tspeak/classify")
def route_tspeak_classify():
    return jsonify(_proxy_post(f"{TSPEAK_URL}/tspeak/classify", request.get_json(force=True)))

@app.post("/api/tspeak/merge")
def route_tspeak_merge():
    return jsonify(_proxy_post_json(f"{TSPEAK_URL}/tspeak/merge", request.get_json(force=True), timeout=30))

@app.post("/api/tspeak/carry")
def route_tspeak_carry():
    return jsonify(_proxy_post_json(f"{TSPEAK_URL}/tspeak/carry", request.get_json(force=True), timeout=30))

@app.post("/api/tspeak/math")
def route_tspeak_math():
    return jsonify(_proxy_post_json(f"{TSPEAK_URL}/tspeak/math", request.get_json(force=True), timeout=10))

# ── TBUFFER (Ternary Response Membrane, port 9883) ──────────
TBUFFER_URL = "http://127.0.0.1:9886"

@app.get("/api/tbuffer/status")
def route_tbuffer_status():
    return jsonify(_proxy_get(f"{TBUFFER_URL}/tbuffer/status"))

@app.post("/api/tbuffer/query")
def route_tbuffer_query():
    return jsonify(_proxy_post_json(f"{TBUFFER_URL}/tbuffer/query", request.get_json(force=True), timeout=15))

@app.post("/api/tbuffer/store")
def route_tbuffer_store():
    return jsonify(_proxy_post_json(f"{TBUFFER_URL}/tbuffer/store", request.get_json(force=True), timeout=30))

@app.post("/api/tbuffer/write")
def route_tbuffer_write():
    return jsonify(_proxy_post_json(f"{TBUFFER_URL}/tbuffer/write", request.get_json(force=True), timeout=30))

@app.get("/api/tbuffer/lookup")
def route_tbuffer_lookup_get():
    eid = request.args.get("id", "")
    return jsonify(_proxy_get(f"{TBUFFER_URL}/tbuffer/lookup?id={eid}"))

@app.post("/api/tbuffer/lookup")
def route_tbuffer_lookup_post():
    return jsonify(_proxy_post(f"{TBUFFER_URL}/tbuffer/lookup", request.get_json(force=True)))

@app.post("/api/tbuffer/invalidate")
def route_tbuffer_invalidate():
    return jsonify(_proxy_post(f"{TBUFFER_URL}/tbuffer/invalidate", request.get_json(force=True)))

# ── TBUS (Message Bus, port 9945) ──────────────────────────
TBUS_URL = "http://127.0.0.1:9945"

@app.get("/api/tbus/topics")
def route_tbus_topics():
    return jsonify(_proxy_get(f"{TBUS_URL}/tbus/topics"))

@app.post("/api/tbus/publish")
def route_tbus_publish():
    return jsonify(_proxy_post_json(f"{TBUS_URL}/tbus/publish", request.get_json(force=True)))

@app.post("/api/tbus/subscribe")
def route_tbus_subscribe():
    return jsonify(_proxy_post_json(f"{TBUS_URL}/tbus/subscribe", request.get_json(force=True)))

@app.post("/api/tbus/unsubscribe")
def route_tbus_unsubscribe():
    return jsonify(_proxy_post_json(f"{TBUS_URL}/tbus/unsubscribe", request.get_json(force=True)))

@app.post("/api/tbus/replay")
def route_tbus_replay():
    return jsonify(_proxy_post_json(f"{TBUS_URL}/tbus/replay", request.get_json(force=True)))

# ── TCIRCUIT (Circuit Breaker, port 9948) ──────────────────
TCIRCUIT_URL = "http://127.0.0.1:9948"

@app.get("/api/tcircuit/states")
def route_tcircuit_states():
    return jsonify(_proxy_get(f"{TCIRCUIT_URL}/tcircuit/states"))

@app.post("/api/tcircuit/check")
def route_tcircuit_check():
    return jsonify(_proxy_post_json(f"{TCIRCUIT_URL}/tcircuit/check", request.get_json(force=True)))

@app.post("/api/tcircuit/report")
def route_tcircuit_report():
    return jsonify(_proxy_post_json(f"{TCIRCUIT_URL}/tcircuit/report", request.get_json(force=True)))

# ── TRATE (Rate Limiter, port 9949) ────────────────────────
TRATE_URL = "http://127.0.0.1:9949"

@app.get("/api/trate/stats")
def route_trate_stats():
    return jsonify(_proxy_get(f"{TRATE_URL}/trate/stats"))

@app.post("/api/trate/check")
def route_trate_check():
    return jsonify(_proxy_post_json(f"{TRATE_URL}/trate/check", request.get_json(force=True)))

@app.post("/api/trate/config")
def route_trate_config():
    return jsonify(_proxy_post_json(f"{TRATE_URL}/trate/config", request.get_json(force=True)))

# ── TEMBED (Embedding Service, port 9924) ──────────────────
TEMBED_URL = "http://127.0.0.1:9924"

@app.post("/api/tembed/encode")
def route_tembed_encode():
    return jsonify(_proxy_post_json(f"{TEMBED_URL}/tembed/encode", request.get_json(force=True)))

@app.post("/api/tembed/similar")
def route_tembed_similar():
    return jsonify(_proxy_post_json(f"{TEMBED_URL}/tembed/similar", request.get_json(force=True)))

@app.post("/api/tembed/cluster")
def route_tembed_cluster():
    return jsonify(_proxy_post_json(f"{TEMBED_URL}/tembed/cluster", request.get_json(force=True), timeout=30))

# ── TCLASSIFY (Text Classifier, port 9921) ─────────────────
TCLASSIFY_URL = "http://127.0.0.1:9921"

@app.post("/api/tclass/intent")
def route_tclass_intent():
    return jsonify(_proxy_post_json(f"{TCLASSIFY_URL}/tclass/intent", request.get_json(force=True)))

@app.post("/api/tclass/topic")
def route_tclass_topic():
    return jsonify(_proxy_post_json(f"{TCLASSIFY_URL}/tclass/topic", request.get_json(force=True)))

@app.post("/api/tclass/sentiment")
def route_tclass_sentiment():
    return jsonify(_proxy_post_json(f"{TCLASSIFY_URL}/tclass/sentiment", request.get_json(force=True)))

# ── TWatch (watchdog auto-restart) ──────────────────────────
TWATCH_URL = "http://127.0.0.1:9950"

@app.get("/api/twatch/status")
def route_twatch_status():
    return jsonify(_proxy_get(f"{TWATCH_URL}/twatch/status"))

@app.post("/api/twatch/check")
def route_twatch_check():
    return jsonify(_proxy_post_json(f"{TWATCH_URL}/twatch/check", request.get_json(force=True)))

@app.post("/api/twatch/sweep")
def route_twatch_sweep():
    return jsonify(_proxy_post_json(f"{TWATCH_URL}/twatch/sweep", request.get_json(force=True)))

@app.post("/api/twatch/restart")
def route_twatch_restart():
    return jsonify(_proxy_post_json(f"{TWATCH_URL}/twatch/restart", request.get_json(force=True)))

@app.post("/api/twatch/register")
def route_twatch_register():
    return jsonify(_proxy_post_json(f"{TWATCH_URL}/twatch/register", request.get_json(force=True)))

# ── TMesh (master service mesh) ─────────────────────────────
TMESH_URL = "http://127.0.0.1:9951"

@app.get("/api/tmesh/health")
def route_tmesh_health():
    return jsonify(_proxy_get(f"{TMESH_URL}/tmesh/health"))

@app.get("/api/tmesh/events")
def route_tmesh_events():
    return jsonify(_proxy_get(f"{TMESH_URL}/tmesh/events"))

@app.get("/api/tmesh/topology")
def route_tmesh_topology():
    return jsonify(_proxy_get(f"{TMESH_URL}/tmesh/topology"))

@app.post("/api/tmesh/query")
def route_tmesh_query():
    return jsonify(_proxy_post_json(f"{TMESH_URL}/tmesh/query", request.get_json(force=True), timeout=120))

@app.post("/api/tmesh/collaborate")
def route_tmesh_collaborate():
    return jsonify(_proxy_post_json(f"{TMESH_URL}/tmesh/collaborate", request.get_json(force=True), timeout=60))

# ── TConfig2 (config management, port 9932) ─────────────────
TCONFIG2_URL = "http://127.0.0.1:9932"

@app.post("/api/tconfig2/set")
def route_tconfig2_set():
    return jsonify(_proxy_post_json(f"{TCONFIG2_URL}/tconfig/set", request.get_json(force=True)))

@app.get("/api/tconfig2/get")
def route_tconfig2_get():
    return jsonify(_proxy_get(f"{TCONFIG2_URL}/tconfig/get?key={request.args.get('key','')}"))

@app.get("/api/tconfig2/list")
def route_tconfig2_list():
    return jsonify(_proxy_get(f"{TCONFIG2_URL}/tconfig/list"))

@app.get("/api/tconfig2/stats")
def route_tconfig2_stats():
    return jsonify(_proxy_get(f"{TCONFIG2_URL}/tconfig/stats"))

# ── TBenchmark (performance benchmarks, port 9933) ─────────
TBENCHMARK_URL = "http://127.0.0.1:9933"

@app.post("/api/tbenchmark/latency")
def route_tbenchmark_latency():
    return jsonify(_proxy_post_json(f"{TBENCHMARK_URL}/tbenchmark/latency", request.get_json(force=True)))

@app.post("/api/tbenchmark/suite")
def route_tbenchmark_suite():
    return jsonify(_proxy_post_json(f"{TBENCHMARK_URL}/tbenchmark/suite", request.get_json(force=True), timeout=60))

@app.get("/api/tbenchmark/results")
def route_tbenchmark_results():
    return jsonify(_proxy_get(f"{TBENCHMARK_URL}/tbenchmark/results"))

@app.get("/api/tbenchmark/history")
def route_tbenchmark_history():
    return jsonify(_proxy_get(f"{TBENCHMARK_URL}/tbenchmark/history"))

# ── TTest (automated test runner, port 9934) ────────────────
TTEST_URL = "http://127.0.0.1:9934"

@app.post("/api/ttest/run")
def route_ttest_run():
    return jsonify(_proxy_post_json(f"{TTEST_URL}/ttest/run", request.get_json(force=True), timeout=60))

@app.post("/api/ttest/run-all")
def route_ttest_runall():
    return jsonify(_proxy_post_json(f"{TTEST_URL}/ttest/run-all", request.get_json(force=True), timeout=120))

@app.get("/api/ttest/list")
def route_ttest_list():
    return jsonify(_proxy_get(f"{TTEST_URL}/ttest/list"))

@app.get("/api/ttest/results")
def route_ttest_results():
    return jsonify(_proxy_get(f"{TTEST_URL}/ttest/results"))

@app.get("/api/ttest/report")
def route_ttest_report():
    return jsonify(_proxy_get(f"{TTEST_URL}/ttest/report"))

# ── TDocs (API documentation, port 9935) ────────────────────
TDOCS_URL = "http://127.0.0.1:9935"

@app.post("/api/tdocs/register")
def route_tdocs_register():
    return jsonify(_proxy_post_json(f"{TDOCS_URL}/tdocs/register", request.get_json(force=True)))

@app.get("/api/tdocs/list")
def route_tdocs_list():
    return jsonify(_proxy_get(f"{TDOCS_URL}/tdocs/list"))

@app.get("/api/tdocs/search")
def route_tdocs_search():
    return jsonify(_proxy_get(f"{TDOCS_URL}/tdocs/search?query={request.args.get('query','')}"))

@app.get("/api/tdocs/stats")
def route_tdocs_stats():
    return jsonify(_proxy_get(f"{TDOCS_URL}/tdocs/stats"))

@app.post("/api/tdocs/auto-register")
def route_tdocs_auto():
    return jsonify(_proxy_post_json(f"{TDOCS_URL}/tdocs/auto-register", request.get_json(force=True)))

# ── TFLASK (ternary-native HTTP from NovaLang) ──────────────
TFLASK_PORTS = [19891]  # Known TFlask server ports — grows as services migrate

@app.get("/api/tflask/status")
def route_tflask_status():
    """Aggregate status from all known TFlask servers."""
    servers = []
    total_ternary = {1: 0, 0: 0, -1: 0}
    for port in TFLASK_PORTS:
        try:
            r = urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=3)
            health = json.loads(r.read())
            # Try to get tstatus if available
            stats = {}
            try:
                r2 = urllib.request.urlopen(f"http://127.0.0.1:{port}/__tflask_status", timeout=3)
                stats = json.loads(r2.read())
            except Exception:
                pass
            t = stats.get("ternary", {1: 0, 0: 0, -1: 0})
            srv = {
                "name": health.get("service", f"tflask-{port}"),
                "port": port,
                "healthy": True,
                "routes": stats.get("routes", 0),
                "requests": stats.get("requests", 0),
                "hooks": stats.get("hooks", 0),
                "ternary": t,
                "uptime": stats.get("uptime", 0)
            }
            servers.append(srv)
            for k in [1, 0, -1]:
                total_ternary[k] += t.get(k, 0)
        except Exception:
            servers.append({"name": f"tflask-{port}", "port": port, "healthy": False})
    return jsonify({"servers": servers, "ternary": total_ternary, "total_ports": len(TFLASK_PORTS)})

@app.post("/api/tflask/start")
def route_tflask_start():
    """Start a TFlask .nova server script via exec server."""
    data = request.get_json(force=True)
    script = data.get("script", "")
    if not script:
        return jsonify({"error": "No script specified"}), 400
    try:
        payload = {"command": f"C:\\NovaX\\novalang.exe {script}"}
        r = urllib.request.Request("http://127.0.0.1:9877/run", json.dumps(payload).encode(),
                                  {"Content-Type": "application/json"})
        resp = urllib.request.urlopen(r, timeout=5)
        return jsonify({"ok": True, "message": f"Started {script}", "result": json.loads(resp.read())})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.post("/api/tflask/stop")
def route_tflask_stop():
    """Stop all TFlask servers (kill processes on known ports)."""
    stopped = []
    for port in TFLASK_PORTS:
        try:
            import subprocess
            _tfsi = subprocess.STARTUPINFO()
            _tfsi.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            _tfsi.wShowWindow = 0
            result = subprocess.run(
                ["powershell", "-NoProfile", "-NoLogo", "-Command", f"Get-NetTCPConnection -LocalPort {port} -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess | ForEach-Object {{ Stop-Process -Id $_ -Force }}"],
                capture_output=True, text=True, timeout=10,
                creationflags=0x08000000, startupinfo=_tfsi
            )
            stopped.append(port)
        except Exception:
            pass
    return jsonify({"ok": True, "stopped": stopped})

# ── NOVA CORTEX PROXY (port 9896) ──
CORTEX_URL = "http://127.0.0.1:9896"

@app.get("/api/cortex/status")
def route_cortex_status():
    import urllib.request as _ur
    try:
        r = _ur.urlopen(f"{CORTEX_URL}/cortex/status", timeout=5)
        return jsonify(json.loads(r.read()))
    except Exception as e:
        return jsonify({"error": str(e)}), 502

@app.post("/api/cortex/claude")
def route_cortex_claude():
    import urllib.request as _ur
    try:
        data = json.dumps(request.json or {}).encode()
        req = _ur.Request(f"{CORTEX_URL}/cortex/claude", data=data,
                          headers={"Content-Type": "application/json"})
        r = _ur.urlopen(req, timeout=120)
        return jsonify(json.loads(r.read()))
    except Exception as e:
        return jsonify({"error": str(e)}), 502

@app.post("/api/cortex/gpt")
def route_cortex_gpt():
    import urllib.request as _ur
    try:
        data = json.dumps(request.json or {}).encode()
        req = _ur.Request(f"{CORTEX_URL}/cortex/gpt", data=data,
                          headers={"Content-Type": "application/json"})
        r = _ur.urlopen(req, timeout=120)
        return jsonify(json.loads(r.read()))
    except Exception as e:
        return jsonify({"error": str(e)}), 502

@app.post("/api/cortex/both")
def route_cortex_both():
    import urllib.request as _ur
    try:
        data = json.dumps(request.json or {}).encode()
        req = _ur.Request(f"{CORTEX_URL}/cortex/both", data=data,
                          headers={"Content-Type": "application/json"})
        r = _ur.urlopen(req, timeout=120)
        return jsonify(json.loads(r.read()))
    except Exception as e:
        return jsonify({"error": str(e)}), 502

@app.post("/api/cortex/chain")
def route_cortex_chain():
    import urllib.request as _ur
    try:
        data = json.dumps(request.json or {}).encode()
        req = _ur.Request(f"{CORTEX_URL}/cortex/chain", data=data,
                          headers={"Content-Type": "application/json"})
        r = _ur.urlopen(req, timeout=180)
        return jsonify(json.loads(r.read()))
    except Exception as e:
        return jsonify({"error": str(e)}), 502

@app.post("/api/cortex/fuse")
def route_cortex_fuse():
    import urllib.request as _ur
    try:
        data = json.dumps(request.json or {}).encode()
        req = _ur.Request(f"{CORTEX_URL}/cortex/fuse", data=data,
                          headers={"Content-Type": "application/json"})
        r = _ur.urlopen(req, timeout=120)
        return jsonify(json.loads(r.read()))
    except Exception as e:
        return jsonify({"error": str(e)}), 502

@app.post("/api/cortex/arrange")
def route_cortex_arrange():
    import urllib.request as _ur
    try:
        data = json.dumps(request.json or {}).encode()
        req = _ur.Request(f"{CORTEX_URL}/cortex/arrange", data=data,
                          headers={"Content-Type": "application/json"})
        r = _ur.urlopen(req, timeout=10)
        return jsonify(json.loads(r.read()))
    except Exception as e:
        return jsonify({"error": str(e)}), 502

@app.get("/api/cortex/services")
def route_cortex_services():
    import urllib.request as _ur
    try:
        req = _ur.Request(f"{CORTEX_URL}/cortex/services")
        r = _ur.urlopen(req, timeout=10)
        return jsonify(json.loads(r.read()))
    except Exception as e:
        return jsonify({"error": str(e)}), 502

@app.post("/api/cortex/proxy")
def route_cortex_proxy():
    import urllib.request as _ur
    try:
        data = json.dumps(request.json or {}).encode()
        req = _ur.Request(f"{CORTEX_URL}/cortex/proxy", data=data,
                          headers={"Content-Type": "application/json"})
        r = _ur.urlopen(req, timeout=300)
        return jsonify(json.loads(r.read()))
    except Exception as e:
        return jsonify({"error": str(e)}), 502

@app.get("/api/cortex/live/claude")
def route_cortex_live_claude():
    import urllib.request as _ur
    try:
        r = _ur.urlopen(f"{CORTEX_URL}/cortex/live/claude", timeout=10)
        return jsonify(json.loads(r.read()))
    except Exception as e:
        return jsonify({"ok": False, "error": str(e), "elements": [], "messages": []}), 502

@app.get("/api/cortex/live/gpt")
def route_cortex_live_gpt():
    import urllib.request as _ur
    try:
        r = _ur.urlopen(f"{CORTEX_URL}/cortex/live/gpt", timeout=10)
        return jsonify(json.loads(r.read()))
    except Exception as e:
        return jsonify({"ok": False, "error": str(e), "elements": [], "messages": []}), 502

@app.get("/api/cortex/uia/status")
def route_cortex_uia_status():
    import urllib.request as _ur
    try:
        r = _ur.urlopen(f"{CORTEX_URL}/cortex/uia/status", timeout=5)
        return jsonify(json.loads(r.read()))
    except Exception as e:
        return jsonify({"error": str(e)}), 502

@app.post("/api/cortex/uia/tree")
def route_cortex_uia_tree():
    import urllib.request as _ur
    try:
        data = json.dumps(request.json or {}).encode()
        req = _ur.Request(f"{CORTEX_URL}/cortex/uia/tree", data=data,
                          headers={"Content-Type": "application/json"})
        r = _ur.urlopen(req, timeout=15)
        return jsonify(json.loads(r.read()))
    except Exception as e:
        return jsonify({"error": str(e)}), 502

@app.get("/api/cortex/app-state/claude")
def route_cortex_appstate_claude():
    import urllib.request as _ur
    try:
        r = _ur.urlopen(f"{CORTEX_URL}/cortex/app-state/claude", timeout=10)
        return jsonify(json.loads(r.read()))
    except Exception as e:
        return jsonify({"ok": False, "error": str(e), "model": "", "sessions": [], "buttons": []}), 502

@app.get("/api/cortex/app-state/gpt")
def route_cortex_appstate_gpt():
    import urllib.request as _ur
    try:
        r = _ur.urlopen(f"{CORTEX_URL}/cortex/app-state/gpt", timeout=10)
        return jsonify(json.loads(r.read()))
    except Exception as e:
        return jsonify({"ok": False, "error": str(e), "model": "", "sessions": [], "buttons": []}), 502

@app.post("/api/cortex/action")
def route_cortex_action():
    import urllib.request as _ur
    try:
        data = json.dumps(request.json or {}).encode()
        req = _ur.Request(f"{CORTEX_URL}/cortex/action", data=data,
                          headers={"Content-Type": "application/json"})
        r = _ur.urlopen(req, timeout=15)
        return jsonify(json.loads(r.read()))
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 502

@app.post("/api/cortex/hint")
def route_cortex_hint():
    """Forward window handle hints to Cortex for desktop app discovery."""
    import urllib.request as _ur
    try:
        data = json.dumps(request.json or {}).encode()
        req = _ur.Request(f"{CORTEX_URL}/cortex/hint", data=data,
                          headers={"Content-Type": "application/json"})
        r = _ur.urlopen(req, timeout=10)
        return jsonify(json.loads(r.read()))
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 502

# ── UIA BRIDGE (session-1 element access + command relay) ──

BRIDGE_URL = "http://127.0.0.1:9902"

@app.get("/api/bridge/status")
def route_bridge_status():
    """UIA bridge health (port 9902) + Cortex bridge cache status."""
    import urllib.request as _ur
    out = {"bridge_running": False, "cortex_bridge": {}}
    try:
        r = _ur.urlopen(f"{BRIDGE_URL}/health", timeout=3)
        out.update(json.loads(r.read()))
        out["bridge_running"] = True
    except Exception:
        pass
    try:
        r = _ur.urlopen(f"{CORTEX_URL}/cortex/bridge/status", timeout=3)
        out["cortex_bridge"] = json.loads(r.read())
    except Exception:
        pass
    return jsonify(out)

@app.post("/api/cortex/command")
def route_cortex_command():
    """Queue a command for the UIA bridge via Cortex."""
    return jsonify(_proxy_post_json(f"{CORTEX_URL}/cortex/command",
                                     request.json or {}, timeout=H13 * H3))

@app.post("/api/cortex/bridge/interact")
def route_cortex_bridge_interact():
    """Type prompt + submit via bridge (async)."""
    return jsonify(_proxy_post_json(f"{CORTEX_URL}/cortex/bridge/interact",
                                     request.json or {}, timeout=H7))

@app.post("/api/cortex/hivemind/task")
def route_cortex_hivemind_task():
    """Autonomous hivemind task: new chat -> prompt -> wait -> capture."""
    return jsonify(_proxy_post_json(f"{CORTEX_URL}/cortex/hivemind/task",
                                     request.json or {}, timeout=120))

@app.get("/api/cortex/hivemind/status")
def route_cortex_hivemind_status():
    import urllib.request as _ur
    try:
        r = _ur.urlopen(f"{CORTEX_URL}/cortex/hivemind/status", timeout=5)
        return jsonify(json.loads(r.read()))
    except Exception as e:
        return jsonify({"error": str(e)}), 502

@app.post("/api/cortex/hivemind/open_sidebar")
def route_cortex_hivemind_open_sidebar():
    """Open sidebar to show chat history."""
    return jsonify(_proxy_post_json(f"{CORTEX_URL}/cortex/hivemind/open_sidebar",
                                     request.json or {}, timeout=15))

@app.get("/api/cortex/bridge/status")
def route_cortex_bridge_cached():
    import urllib.request as _ur
    try:
        r = _ur.urlopen(f"{CORTEX_URL}/cortex/bridge/status", timeout=5)
        return jsonify(json.loads(r.read()))
    except Exception as e:
        return jsonify({"error": str(e)}), 502


# ── APP LAUNCHER (native application management) ──

_app_running = {}  # {app_name: {pid, hwnd, started, exe}}
_APP_MAX = 5  # Max concurrent applications
_ICON_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web", "icons")
os.makedirs(_ICON_DIR, exist_ok=True)

def _extract_icons_batch(apps_list):
    """Batch extract icons from exe files using PowerShell .NET (hidden window)."""
    import subprocess as _sp, re as _re
    missing = []
    for a in apps_list:
        exe = a.get("exe", "")
        if not exe or not os.path.isfile(exe):
            continue
        safe = _re.sub(r'[^a-z0-9_\-]', '_', a["name"].lower())
        png = os.path.join(_ICON_DIR, safe + ".png")
        if os.path.exists(png):
            a["icon"] = "/icons/" + safe + ".png"
            continue
        missing.append((safe, exe, png))
    if not missing:
        return
    # Build batch PowerShell: one ExtractAssociatedIcon per exe
    lines = ["Add-Type -AssemblyName System.Drawing"]
    for safe, exe, png in missing:
        exe_e = exe.replace("'", "''")
        png_e = png.replace("\\", "/").replace("'", "''")
        lines.append(
            "try { $i=[System.Drawing.Icon]::ExtractAssociatedIcon('%s');"
            " if($i){ $b=$i.ToBitmap();"
            " $b.Save('%s',[System.Drawing.Imaging.ImageFormat]::Png);"
            " $b.Dispose(); $i.Dispose() } } catch {}" % (exe_e, png_e)
        )
    script = "\n".join(lines)
    try:
        _isi = _sp.STARTUPINFO()
        _isi.dwFlags |= _sp.STARTF_USESHOWWINDOW
        _isi.wShowWindow = 0
        _sp.run(["powershell", "-NoProfile", "-NoLogo", "-Command", script],
                creationflags=0x08000000, timeout=45,
                stdout=_sp.DEVNULL, stderr=_sp.DEVNULL, stdin=_sp.DEVNULL,
                startupinfo=_isi)
    except Exception:
        pass
    # Assign icon paths for newly extracted
    for safe, exe, png in missing:
        if os.path.exists(png):
            for a in apps_list:
                if a.get("exe") == exe:
                    a["icon"] = "/icons/" + safe + ".png"


@app.get("/api/apps/icon/<path:name>")
def route_app_icon(name):
    """Serve extracted app icon."""
    import re as _re
    safe = _re.sub(r'[^a-z0-9_\-]', '_', name.lower()) + ".png"
    fpath = os.path.join(_ICON_DIR, safe)
    if os.path.isfile(fpath):
        return send_from_directory(_ICON_DIR, safe, mimetype="image/png")
    return "", 404


@app.get("/api/apps/discover")
def route_apps_discover():
    """Discover installed applications on the system."""
    import glob as _glob
    apps = []
    seen = set()
    locations = [
        "C:/Program Files",
        "C:/Program Files (x86)",
        os.path.expanduser("~/AppData/Local/Programs"),
    ]
    # Category mapping — keywords matched against app name (case-insensitive)
    categories = {
        "Creative": ["blender", "krita", "lmms", "kdenlive", "openshot", "audacity",
                      "handbrake", "obs-studio", "obs studio", "draw.io", "gimp",
                      "inkscape", "davinci", "premiere", "photoshop", "figma"],
        "Development": ["visual studio", "vs code", "vscode", "cursor", "git",
                         "github", "postman", "dbeaver", "jetbrains", "unity",
                         "notepad++", "sublime", "atom", "vim", "neovim", "rider",
                         "intellij", "pycharm", "webstorm", "android studio"],
        "Browser": ["firefox", "brave", "chrome", "edge", "opera", "vivaldi", "tor"],
        "Gaming": ["steam", "pcsx2", "ppsspp", "sidequest", "kodi", "epic games",
                    "discord", "retroarch", "dolphin", "rpcs3"],
        "System": ["everything", "winrar", "7-zip", "putty", "winscp", "keepass",
                    "wireguard", "rustdesk", "wireshark", "powershell", "terminal",
                    "winmerge", "beyond compare", "filezilla", "process explorer"],
        "AI/ML": ["ollama", "novax", "stable diffusion", "comfyui", "lm studio"],
        "Runtime": ["python", "node", "rust", "go ", "dotnet", "java", "ruby"],
    }
    cat_map = {}
    for cat, keywords in categories.items():
        for k in keywords:
            cat_map[k] = cat

    for loc in locations:
        if not os.path.isdir(loc):
            continue
        try:
            for d in os.listdir(loc):
                full = os.path.join(loc, d)
                if not os.path.isdir(full):
                    continue
                try:
                    # Check current dir and one level deep for .exe files
                    exes = _glob.glob(os.path.join(full, "*.exe"))
                    if not exes:
                        exes = _glob.glob(os.path.join(full, "*", "*.exe"))
                    if exes and d not in seen:
                        seen.add(d)
                        # Find category
                        cat = "Other"
                        for key, c in cat_map.items():
                            if key in d.lower():
                                cat = c
                                break
                        apps.append({
                            "name": d,
                            "exe": exes[0].replace("\\", "/"),
                            "path": full.replace("\\", "/"),
                            "category": cat,
                            "running": d in _app_running,
                        })
                except PermissionError:
                    pass
        except PermissionError:
            pass

    # Start Menu shortcuts
    start = os.path.expanduser("~/AppData/Roaming/Microsoft/Windows/Start Menu/Programs")
    if os.path.isdir(start):
        for item in _glob.glob(start + "/**/*.lnk", recursive=True):
            name = os.path.splitext(os.path.basename(item))[0]
            if len(name) > 2 and name not in seen:
                seen.add(name)
                cat = "Other"
                for key, c in cat_map.items():
                    if key in name.lower():
                        cat = c
                        break
                apps.append({"name": name, "exe": "", "path": item.replace("\\", "/"),
                             "category": cat, "running": name in _app_running})

    apps.sort(key=lambda x: x["name"].lower())
    # Extract real icons from exe files (cached on disk)
    _extract_icons_batch(apps)
    return jsonify({"ok": True, "apps": apps, "total": len(apps),
                    "running": len(_app_running), "max": _APP_MAX})


@app.post("/api/apps/launch")
def route_apps_launch():
    """Launch a native application via AppControl bridge (Session 1 = user desktop).
    The bridge launches apps in the user's session so windows are visible and controllable.
    """
    name = request.json.get("name", "")
    exe = request.json.get("exe", "")
    path = request.json.get("path", "")

    if len(_app_running) >= _APP_MAX:
        return jsonify({"ok": False, "error": f"Max {_APP_MAX} apps running. Close one first.",
                        "running": len(_app_running)})

    if name in _app_running:
        return jsonify({"ok": True, "status": "already_running", "app": _app_running[name]})

    target = exe or path
    # Proxy launch to AppControl bridge (runs in Session 1)
    result = _appcontrol_req("POST", "/launch", {"name": name, "exe": target})
    if result.get("ok"):
        _app_running[name] = {
            "pid": result.get("pid", 0),
            "exe": target,
            "started": time.time(),
            "name": name,
        }
        return jsonify({"ok": True, "status": result.get("status", "launched"),
                        "pid": result.get("pid"), "name": name,
                        "running": len(_app_running), "trit": 1})
    return jsonify(result)


@app.post("/api/apps/close")
def route_apps_close():
    """Close a running application via bridge + local cleanup."""
    name = request.json.get("name", "")
    if name not in _app_running:
        return jsonify({"ok": False, "error": f"{name} not tracked"})
    # Ask bridge to close (it has the real PID in Session 1)
    _appcontrol_req("POST", "/close", {"name": name})
    # Also kill by PID as fallback
    import subprocess as _sp
    try:
        _csi = _sp.STARTUPINFO()
        _csi.dwFlags |= _sp.STARTF_USESHOWWINDOW
        _csi.wShowWindow = 0
        _sp.run(["taskkill", "/PID", str(_app_running[name]["pid"]), "/F", "/T"],
                creationflags=_CREATE_NO_WINDOW, capture_output=True, startupinfo=_csi)
    except Exception:
        pass
    del _app_running[name]
    return jsonify({"ok": True, "closed": name, "running": len(_app_running), "trit": 1})


@app.get("/api/apps/running")
def route_apps_running():
    """List currently running tracked applications."""
    return jsonify({"ok": True, "apps": list(_app_running.values()),
                    "count": len(_app_running), "max": _APP_MAX})


# ── APP WINDOW CONTROL (proxied to AppControl bridge in Session 1, port 9887) ──
APPCONTROL_URL = "http://127.0.0.1:9887"


def _appcontrol_req(method, path, data=None):
    """Send request to AppControl bridge (Session 1)."""
    import urllib.request as _ur
    try:
        url = f"{APPCONTROL_URL}{path}"
        if method == "GET":
            r = _ur.urlopen(url, timeout=H5)
        else:
            payload = json.dumps(data or {}).encode()
            req = _ur.Request(url, data=payload, headers={"Content-Type": "application/json"})
            r = _ur.urlopen(req, timeout=H5)
        return json.loads(r.read())
    except Exception as e:
        return {"ok": False, "trit": -1, "error": f"AppControl bridge: {str(e)[:150]}"}


@app.get("/api/apps/windows")
def route_apps_windows():
    """List all visible windows (from Session 1 bridge)."""
    return jsonify(_appcontrol_req("GET", "/windows"))


@app.post("/api/apps/embed")
def route_apps_embed():
    """Position an app window to overlay the NovaX content area."""
    name = request.json.get("name", "")
    if name not in _app_running:
        return jsonify({"ok": False, "error": f"{name} not tracked"})
    result = _appcontrol_req("POST", "/embed", {
        "search": name, "x": request.json.get("x", 0),
        "y": request.json.get("y", 0), "w": request.json.get("w", 800),
        "h": request.json.get("h", 600),
    })
    if result.get("ok"):
        _app_running[name]["embedded"] = True
        _app_running[name]["hwnd"] = result.get("hwnd")
    return jsonify(result)


@app.post("/api/apps/unembed")
def route_apps_unembed():
    """Restore an embedded app window to normal windowed mode."""
    name = request.json.get("name", "")
    if name not in _app_running:
        return jsonify({"ok": False, "error": f"{name} not tracked"})
    result = _appcontrol_req("POST", "/unembed", {"search": name})
    if result.get("ok"):
        _app_running[name].pop("embedded", None)
        _app_running[name].pop("bounds", None)
    return jsonify(result)


@app.post("/api/apps/focus")
def route_apps_focus():
    """Bring a running app window to the foreground via Session 1 bridge."""
    name = request.json.get("name", "")
    if name not in _app_running:
        return jsonify({"ok": False, "error": f"{name} not tracked"})
    result = _appcontrol_req("POST", "/focus", {
        "search": name, "pid": _app_running[name].get("pid"),
    })
    if result.get("hwnd"):
        _app_running[name]["hwnd"] = result["hwnd"]
    return jsonify(result)


@app.post("/api/apps/input")
def route_apps_input():
    """Send keyboard/mouse input to a running app for autonomous control.
    Body: {name, action: 'key'|'type'|'click'|'hotkey', key, text, x, y, keys}
    Proxied to AppControl bridge in user's desktop session.
    """
    name = request.json.get("name", "")
    action = request.json.get("action", "")
    if name not in _app_running:
        return jsonify({"ok": False, "error": f"{name} not tracked"})
    # Get HWND from tracked app (if bridge found it before)
    hwnd = _app_running[name].get("hwnd")
    if not hwnd:
        # Try to find it via bridge
        found = _appcontrol_req("POST", "/focus", {"search": name})
        hwnd = found.get("hwnd")
        if hwnd:
            _app_running[name]["hwnd"] = hwnd

    if action == "click":
        return jsonify(_appcontrol_req("POST", "/click", {
            "hwnd": hwnd, "x": request.json.get("x", 0), "y": request.json.get("y", 0),
            "button": request.json.get("button", "left"),
        }))
    elif action == "type":
        return jsonify(_appcontrol_req("POST", "/type", {
            "hwnd": hwnd, "text": request.json.get("text", ""),
        }))
    elif action == "key":
        return jsonify(_appcontrol_req("POST", "/key", {
            "hwnd": hwnd, "key": request.json.get("key", ""),
            "vk": request.json.get("vk", 0),
        }))
    elif action == "hotkey":
        return jsonify(_appcontrol_req("POST", "/hotkey", {
            "hwnd": hwnd, "keys": request.json.get("keys", []),
        }))
    else:
        return jsonify({"ok": False, "error": f"Unknown action: {action}"})


@app.post("/api/apps/script")
def route_apps_script():
    """Execute a multi-step script sequence on the desktop.
    Body: {actions: [{action, search, key, x, y, ms, ...}, ...]}
    All actions run in one request — no per-step approval needed."""
    return jsonify(_appcontrol_req("POST", "/script", request.json))


@app.get("/api/apps/screenshot")
def route_apps_screenshot():
    """Capture a window screenshot. ?target=Blender|ChatGPT|Claude|active"""
    import urllib.request as _ur
    target = request.args.get("target", "active")
    try:
        url = f"{APPCONTROL_URL}/screenshot?target={target}"
        r = _ur.urlopen(url, timeout=10)
        from flask import Response
        return Response(r.read(), mimetype="image/png",
                       headers={"Cache-Control": "no-cache",
                                "Access-Control-Allow-Origin": "http://localhost:9999"})
    except Exception as e:
        return jsonify({"ok": False, "trit": -1, "error": str(e)[:150]})


@app.get("/api/apps/live")
def route_apps_live():
    """Serve the NovaX Live Preview page."""
    import urllib.request as _ur
    try:
        r = _ur.urlopen(f"{APPCONTROL_URL}/live", timeout=H5)
        return r.read().decode(), 200, {"Content-Type": "text/html"}
    except Exception as e:
        return jsonify({"ok": False, "trit": -1, "error": str(e)[:150]})


@app.post("/api/apps/minimize")
def route_apps_minimize():
    """Minimize a window by search string."""
    return jsonify(_appcontrol_req("POST", "/minimize", request.json))


@app.post("/api/apps/maximize")
def route_apps_maximize():
    """Maximize a window by search string."""
    return jsonify(_appcontrol_req("POST", "/maximize", request.json))


@app.post("/api/apps/restore")
def route_apps_restore():
    """Restore a minimized/maximized window."""
    return jsonify(_appcontrol_req("POST", "/restore", request.json))


@app.post("/api/apps/move")
def route_apps_move():
    """Move/resize a window. Body: {search, x, y, w, h}"""
    return jsonify(_appcontrol_req("POST", "/move", request.json))


# ── v3.0: Advanced Desktop Control (relative coords, scroll, drag, etc.) ──

@app.post("/api/apps/click")
def route_apps_click():
    """Click at absolute (x,y) or window-relative (rx,ry 0-1) coords.
    Body: {x,y} or {rx,ry,window} with optional button."""
    return jsonify(_appcontrol_req("POST", "/click", request.json))


@app.post("/api/apps/doubleclick")
def route_apps_doubleclick():
    """Double-click at coords. Supports rx,ry relative coords."""
    return jsonify(_appcontrol_req("POST", "/doubleclick", request.json))


@app.post("/api/apps/scroll")
def route_apps_scroll():
    """Scroll at coords. Body: {x,y,delta,direction} or {rx,ry,window,...}"""
    return jsonify(_appcontrol_req("POST", "/scroll", request.json))


@app.post("/api/apps/drag")
def route_apps_drag():
    """Drag from A to B. Body: {x1,y1,x2,y2} or {rx1,ry1,rx2,ry2,window}"""
    return jsonify(_appcontrol_req("POST", "/drag", request.json))


@app.post("/api/apps/clicktext")
def route_apps_clicktext():
    """Find UI control by text and click it. Body: {search,text}"""
    return jsonify(_appcontrol_req("POST", "/clicktext", request.json))


@app.post("/api/apps/filedialog")
def route_apps_filedialog():
    """Type path into an open file dialog. Body: {path}"""
    return jsonify(_appcontrol_req("POST", "/filedialog", request.json))


@app.get("/api/apps/elements")
def route_apps_elements():
    """Get child controls/elements of a window. ?target=Blender"""
    target = request.args.get("target", "")
    return jsonify(_appcontrol_req("GET", f"/elements?target={target}"))


@app.get("/api/apps/state")
def route_apps_state():
    """Get current screen state for AI decision-making.
    Returns active window, cursor, all windows, desktop size."""
    target = request.args.get("target", "")
    return jsonify(_appcontrol_req("GET", f"/state?target={target}"))


# ── v3.0: Blender Python Injection (via file-based bridge addon) ──

@app.post("/api/blender/exec")
def route_blender_exec():
    """Execute Python code in the running Blender instance.
    Requires NovaX Bridge addon active in Blender.
    Body: {code, timeout?}"""
    return jsonify(_appcontrol_req("POST", "/blender/exec", request.json))


@app.get("/api/blender/status")
def route_blender_status():
    """Check if Blender bridge addon is active and responding."""
    return jsonify(_appcontrol_req("POST", "/blender/status", {}))


# ── v3.0: Autonomous Task Queue (multi-AI task dispatch) ──

@app.post("/api/tasks/create")
def route_tasks_create():
    """Create a new task for AI agents. Body: {goal, agent_id?, priority?, context?}"""
    return jsonify(_appcontrol_req("POST", "/task/create", request.json))


@app.post("/api/tasks/claim")
def route_tasks_claim():
    """Claim the next available task. Body: {agent_id, task_id?}"""
    return jsonify(_appcontrol_req("POST", "/task/claim", request.json))


@app.post("/api/tasks/update")
def route_tasks_update():
    """Update task status/result. Body: {task_id, status?, result?, error?}"""
    return jsonify(_appcontrol_req("POST", "/task/update", request.json))


@app.post("/api/tasks/batch")
def route_tasks_batch():
    """Create multiple tasks at once. Body: {goals: [...], agent_id?}"""
    return jsonify(_appcontrol_req("POST", "/task/batch", request.json))


@app.get("/api/tasks")
def route_tasks_list():
    """List all tasks: pending, active, and recent history."""
    return jsonify(_appcontrol_req("GET", "/tasks"))


# ── NOVA TFETCH PROXY (port 9897) ──
TFETCH_URL = "http://127.0.0.1:9897"

@app.get("/api/tfetch/status")
def route_tfetch_status():
    import urllib.request as _ur
    try:
        r = _ur.urlopen(f"{TFETCH_URL}/tfetch/status", timeout=10)
        return jsonify(json.loads(r.read()))
    except Exception as e:
        return jsonify({"error": str(e)}), 502

@app.get("/api/tfetch/session/<sid>")
def route_tfetch_session(sid):
    import urllib.request as _ur
    try:
        r = _ur.urlopen(f"{TFETCH_URL}/tfetch/session/{sid}", timeout=10)
        return jsonify(json.loads(r.read()))
    except Exception as e:
        return jsonify({"error": str(e)}), 502

@app.post("/api/tfetch/download")
def route_tfetch_download():
    import urllib.request as _ur
    try:
        data = json.dumps(request.json or {}).encode()
        req = _ur.Request(f"{TFETCH_URL}/tfetch/download", data=data,
                          headers={"Content-Type": "application/json"})
        r = _ur.urlopen(req, timeout=600)
        return jsonify(json.loads(r.read()))
    except Exception as e:
        return jsonify({"error": str(e)}), 502

@app.post("/api/tfetch/pause")
def route_tfetch_pause():
    import urllib.request as _ur
    try:
        data = json.dumps(request.json or {}).encode()
        req = _ur.Request(f"{TFETCH_URL}/tfetch/pause", data=data,
                          headers={"Content-Type": "application/json"})
        r = _ur.urlopen(req, timeout=10)
        return jsonify(json.loads(r.read()))
    except Exception as e:
        return jsonify({"error": str(e)}), 502

@app.post("/api/tfetch/resume")
def route_tfetch_resume():
    import urllib.request as _ur
    try:
        data = json.dumps(request.json or {}).encode()
        req = _ur.Request(f"{TFETCH_URL}/tfetch/resume", data=data,
                          headers={"Content-Type": "application/json"})
        r = _ur.urlopen(req, timeout=10)
        return jsonify(json.loads(r.read()))
    except Exception as e:
        return jsonify({"error": str(e)}), 502

@app.post("/api/tfetch/cancel")
def route_tfetch_cancel():
    import urllib.request as _ur
    try:
        data = json.dumps(request.json or {}).encode()
        req = _ur.Request(f"{TFETCH_URL}/tfetch/cancel", data=data,
                          headers={"Content-Type": "application/json"})
        r = _ur.urlopen(req, timeout=10)
        return jsonify(json.loads(r.read()))
    except Exception as e:
        return jsonify({"error": str(e)}), 502

@app.post("/api/tfetch/git")
def route_tfetch_git():
    import urllib.request as _ur
    try:
        data = json.dumps(request.json or {}).encode()
        req = _ur.Request(f"{TFETCH_URL}/tfetch/git", data=data,
                          headers={"Content-Type": "application/json"})
        r = _ur.urlopen(req, timeout=600)
        return jsonify(json.loads(r.read()))
    except Exception as e:
        return jsonify({"error": str(e)}), 502

@app.post("/api/tfetch/proxy/enable")
def route_tfetch_proxy_enable():
    import urllib.request as _ur
    try:
        req = _ur.Request(f"{TFETCH_URL}/tfetch/proxy/enable", data=b"{}",
                          headers={"Content-Type": "application/json"})
        r = _ur.urlopen(req, timeout=15)
        return jsonify(json.loads(r.read()))
    except Exception as e:
        return jsonify({"error": str(e)}), 502

@app.post("/api/tfetch/proxy/disable")
def route_tfetch_proxy_disable():
    import urllib.request as _ur
    try:
        req = _ur.Request(f"{TFETCH_URL}/tfetch/proxy/disable", data=b"{}",
                          headers={"Content-Type": "application/json"})
        r = _ur.urlopen(req, timeout=15)
        return jsonify(json.loads(r.read()))
    except Exception as e:
        return jsonify({"error": str(e)}), 502

@app.get("/api/tfetch/proxy/status")
def route_tfetch_proxy_status():
    import urllib.request as _ur
    try:
        r = _ur.urlopen(f"{TFETCH_URL}/tfetch/proxy/status", timeout=5)
        return jsonify(json.loads(r.read()))
    except Exception as e:
        return jsonify({"error": str(e)}), 502

@app.get("/api/tfetch/speedtest")
def route_tfetch_speedtest():
    import urllib.request as _ur
    try:
        r = _ur.urlopen(f"{TFETCH_URL}/tfetch/speedtest", timeout=120)
        return jsonify(json.loads(r.read()))
    except Exception as e:
        return jsonify({"error": str(e)}), 502

# ── TSkipTrace proxy (port 9903) ──
SKIP_URL = "http://127.0.0.1:9903"

@app.post("/api/skip/search")
def route_skip_search():
    return jsonify(_proxy_post_json(f"{SKIP_URL}/skip/search", request.get_json(force=True), timeout=30))

@app.post("/api/skip/matrix")
def route_skip_matrix():
    return jsonify(_proxy_post_json(f"{SKIP_URL}/skip/matrix", request.get_json(force=True), timeout=30))

@app.post("/api/skip/harmonic")
def route_skip_harmonic():
    return jsonify(_proxy_post_json(f"{SKIP_URL}/skip/harmonic", request.get_json(force=True), timeout=30))

@app.post("/api/skip/correlate")
def route_skip_correlate():
    return jsonify(_proxy_post_json(f"{SKIP_URL}/skip/correlate", request.get_json(force=True), timeout=30))

@app.post("/api/skip/japan/multiply")
def route_skip_japan_multiply():
    return jsonify(_proxy_post_json(f"{SKIP_URL}/skip/japan/multiply", request.get_json(force=True), timeout=15))

@app.post("/api/skip/japan/divide")
def route_skip_japan_divide():
    return jsonify(_proxy_post_json(f"{SKIP_URL}/skip/japan/divide", request.get_json(force=True), timeout=15))

@app.get("/api/skip/status")
def route_skip_status():
    return jsonify(_proxy_get(f"{SKIP_URL}/skip/status"))

# ── TSysmon proxy (port 9905) ──
SYSMON_URL = "http://127.0.0.1:9905"

@app.post("/api/sysmon/procs")
def route_sysmon_procs():
    return jsonify(_proxy_post_json(f"{SYSMON_URL}/sysmon/procs", request.get_json(force=True), timeout=15))

@app.post("/api/sysmon/resources")
def route_sysmon_resources():
    return jsonify(_proxy_post_json(f"{SYSMON_URL}/sysmon/resources", request.get_json(force=True), timeout=15))

@app.post("/api/sysmon/bench")
def route_sysmon_bench():
    return jsonify(_proxy_post_json(f"{SYSMON_URL}/sysmon/bench", request.get_json(force=True), timeout=60))

@app.post("/api/sysmon/trace")
def route_sysmon_trace():
    return jsonify(_proxy_post_json(f"{SYSMON_URL}/sysmon/trace", request.get_json(force=True), timeout=15))

@app.post("/api/sysmon/network")
def route_sysmon_network():
    return jsonify(_proxy_post_json(f"{SYSMON_URL}/sysmon/network", request.get_json(force=True), timeout=15))

@app.post("/api/sysmon/iowatch")
def route_sysmon_iowatch():
    return jsonify(_proxy_post_json(f"{SYSMON_URL}/sysmon/iowatch", request.get_json(force=True), timeout=15))

@app.post("/api/sysmon/stress")
def route_sysmon_stress():
    return jsonify(_proxy_post_json(f"{SYSMON_URL}/sysmon/stress", request.get_json(force=True), timeout=30))

@app.get("/api/sysmon/status")
def route_sysmon_status():
    return jsonify(_proxy_get(f"{SYSMON_URL}/sysmon/status"))

# ── TNet proxy (port 9906) ──
TNET_URL = "http://127.0.0.1:9906"

@app.post("/api/tnet/probe")
def route_tnet_probe():
    return jsonify(_proxy_post_json(f"{TNET_URL}/tnet/probe", request.get_json(force=True), timeout=30))

@app.post("/api/tnet/fetch")
def route_tnet_fetch():
    return jsonify(_proxy_post_json(f"{TNET_URL}/tnet/fetch", request.get_json(force=True), timeout=30))

@app.post("/api/tnet/scan")
def route_tnet_scan():
    return jsonify(_proxy_post_json(f"{TNET_URL}/tnet/scan", request.get_json(force=True), timeout=60))

@app.post("/api/tnet/trace")
def route_tnet_trace():
    return jsonify(_proxy_post_json(f"{TNET_URL}/tnet/trace", request.get_json(force=True), timeout=60))

@app.post("/api/tnet/bandwidth")
def route_tnet_bandwidth():
    return jsonify(_proxy_post_json(f"{TNET_URL}/tnet/bandwidth", request.get_json(force=True), timeout=30))

@app.post("/api/tnet/dns")
def route_tnet_dns():
    return jsonify(_proxy_post_json(f"{TNET_URL}/tnet/dns", request.get_json(force=True), timeout=15))

@app.post("/api/tnet/health")
def route_tnet_health_check():
    return jsonify(_proxy_post_json(f"{TNET_URL}/tnet/health", request.get_json(force=True), timeout=30))

@app.get("/api/tnet/status")
def route_tnet_status():
    return jsonify(_proxy_get(f"{TNET_URL}/tnet/status"))

# ── TSecurity proxy (port 9907) ──
TSEC_URL = "http://127.0.0.1:9907"

@app.post("/api/tsec/scan-file")
def route_tsec_scan_file():
    return jsonify(_proxy_post_json(f"{TSEC_URL}/tsec/scan-file", request.get_json(force=True), timeout=15))

@app.post("/api/tsec/scan-dir")
def route_tsec_scan_dir():
    return jsonify(_proxy_post_json(f"{TSEC_URL}/tsec/scan-dir", request.get_json(force=True), timeout=30))

@app.post("/api/tsec/ports")
def route_tsec_ports():
    return jsonify(_proxy_post_json(f"{TSEC_URL}/tsec/ports", request.get_json(force=True), timeout=15))

@app.post("/api/tsec/entropy")
def route_tsec_entropy():
    return jsonify(_proxy_post_json(f"{TSEC_URL}/tsec/entropy", request.get_json(force=True), timeout=15))

@app.post("/api/tsec/hash")
def route_tsec_hash():
    return jsonify(_proxy_post_json(f"{TSEC_URL}/tsec/hash", request.get_json(force=True), timeout=15))

@app.post("/api/tsec/permissions")
def route_tsec_permissions():
    return jsonify(_proxy_post_json(f"{TSEC_URL}/tsec/permissions", request.get_json(force=True), timeout=15))

@app.post("/api/tsec/audit")
def route_tsec_audit():
    return jsonify(_proxy_post_json(f"{TSEC_URL}/tsec/audit", request.get_json(force=True), timeout=30))

@app.get("/api/tsec/status")
def route_tsec_status():
    return jsonify(_proxy_get(f"{TSEC_URL}/tsec/status"))

# ── TMedia proxy (port 9908) ──
TMEDIA_URL = "http://127.0.0.1:9908"

@app.post("/api/tmedia/info")
def route_tmedia_info():
    return jsonify(_proxy_post_json(f"{TMEDIA_URL}/tmedia/info", request.get_json(force=True), timeout=15))

@app.post("/api/tmedia/convert")
def route_tmedia_convert():
    return jsonify(_proxy_post_json(f"{TMEDIA_URL}/tmedia/convert", request.get_json(force=True), timeout=15))

@app.post("/api/tmedia/thumbnail")
def route_tmedia_thumbnail():
    return jsonify(_proxy_post_json(f"{TMEDIA_URL}/tmedia/thumbnail", request.get_json(force=True), timeout=15))

@app.post("/api/tmedia/audio-info")
def route_tmedia_audio_info():
    return jsonify(_proxy_post_json(f"{TMEDIA_URL}/tmedia/audio-info", request.get_json(force=True), timeout=15))

@app.post("/api/tmedia/doc-gen")
def route_tmedia_doc_gen():
    return jsonify(_proxy_post_json(f"{TMEDIA_URL}/tmedia/doc-gen", request.get_json(force=True), timeout=15))

@app.post("/api/tmedia/cheat")
def route_tmedia_cheat():
    return jsonify(_proxy_post_json(f"{TMEDIA_URL}/tmedia/cheat", request.get_json(force=True), timeout=15))

@app.post("/api/tmedia/manifest")
def route_tmedia_manifest():
    return jsonify(_proxy_post_json(f"{TMEDIA_URL}/tmedia/manifest", request.get_json(force=True), timeout=30))

@app.get("/api/tmedia/status")
def route_tmedia_status():
    return jsonify(_proxy_get(f"{TMEDIA_URL}/tmedia/status"))

# ── TBuild proxy (port 9909) ──
TBUILD_URL = "http://127.0.0.1:9909"

@app.post("/api/tbuild/deps")
def route_tbuild_deps():
    return jsonify(_proxy_post_json(f"{TBUILD_URL}/tbuild/deps", request.get_json(force=True), timeout=15))

@app.post("/api/tbuild/order")
def route_tbuild_order():
    return jsonify(_proxy_post_json(f"{TBUILD_URL}/tbuild/order", request.get_json(force=True), timeout=15))

@app.post("/api/tbuild/diff")
def route_tbuild_diff():
    return jsonify(_proxy_post_json(f"{TBUILD_URL}/tbuild/diff", request.get_json(force=True), timeout=15))

@app.post("/api/tbuild/project-status")
def route_tbuild_project_status():
    return jsonify(_proxy_post_json(f"{TBUILD_URL}/tbuild/status", request.get_json(force=True), timeout=15))

@app.post("/api/tbuild/lint")
def route_tbuild_lint():
    return jsonify(_proxy_post_json(f"{TBUILD_URL}/tbuild/lint", request.get_json(force=True), timeout=30))

@app.post("/api/tbuild/vcs")
def route_tbuild_vcs():
    return jsonify(_proxy_post_json(f"{TBUILD_URL}/tbuild/vcs", request.get_json(force=True), timeout=15))

@app.post("/api/tbuild/compile")
def route_tbuild_compile():
    return jsonify(_proxy_post_json(f"{TBUILD_URL}/tbuild/compile", request.get_json(force=True), timeout=30))

@app.get("/api/tbuild/service-status")
def route_tbuild_service_status():
    return jsonify(_proxy_get(f"{TBUILD_URL}/tbuild/status"))

# ── TCron proxy (port 9910) ──
TCRON_URL = "http://127.0.0.1:9910"

@app.post("/api/tcron/schedule")
def route_tcron_schedule():
    return jsonify(_proxy_post_json(f"{TCRON_URL}/tcron/schedule", request.get_json(force=True), timeout=15))

@app.post("/api/tcron/list")
def route_tcron_list():
    return jsonify(_proxy_post_json(f"{TCRON_URL}/tcron/list", request.get_json(force=True), timeout=15))

@app.post("/api/tcron/cancel")
def route_tcron_cancel():
    return jsonify(_proxy_post_json(f"{TCRON_URL}/tcron/cancel", request.get_json(force=True), timeout=15))

@app.post("/api/tcron/watch")
def route_tcron_watch():
    return jsonify(_proxy_post_json(f"{TCRON_URL}/tcron/watch", request.get_json(force=True), timeout=15))

@app.post("/api/tcron/task")
def route_tcron_task():
    return jsonify(_proxy_post_json(f"{TCRON_URL}/tcron/task", request.get_json(force=True), timeout=15))

@app.post("/api/tcron/run-once")
def route_tcron_run_once():
    return jsonify(_proxy_post_json(f"{TCRON_URL}/tcron/run-once", request.get_json(force=True), timeout=30))

@app.post("/api/tcron/chain")
def route_tcron_chain():
    return jsonify(_proxy_post_json(f"{TCRON_URL}/tcron/chain", request.get_json(force=True), timeout=60))

@app.get("/api/tcron/status")
def route_tcron_status():
    return jsonify(_proxy_get(f"{TCRON_URL}/tcron/status"))

# ── TQuery proxy (port 9911) ──
TQUERY_URL = "http://127.0.0.1:9911"

@app.post("/api/tquery/sql")
def route_tquery_sql():
    return jsonify(_proxy_post_json(f"{TQUERY_URL}/tquery/sql", request.get_json(force=True), timeout=30))

@app.post("/api/tquery/kv")
def route_tquery_kv():
    return jsonify(_proxy_post_json(f"{TQUERY_URL}/tquery/kv", request.get_json(force=True), timeout=15))

@app.post("/api/tquery/aggregate")
def route_tquery_aggregate():
    return jsonify(_proxy_post_json(f"{TQUERY_URL}/tquery/aggregate", request.get_json(force=True), timeout=30))

@app.post("/api/tquery/analyze")
def route_tquery_analyze():
    return jsonify(_proxy_post_json(f"{TQUERY_URL}/tquery/analyze", request.get_json(force=True), timeout=15))

@app.post("/api/tquery/csv")
def route_tquery_csv():
    return jsonify(_proxy_post_json(f"{TQUERY_URL}/tquery/csv", request.get_json(force=True), timeout=30))

@app.post("/api/tquery/json-query")
def route_tquery_json_query():
    return jsonify(_proxy_post_json(f"{TQUERY_URL}/tquery/json-query", request.get_json(force=True), timeout=15))

@app.post("/api/tquery/pivot")
def route_tquery_pivot():
    return jsonify(_proxy_post_json(f"{TQUERY_URL}/tquery/pivot", request.get_json(force=True), timeout=30))

@app.get("/api/tquery/status")
def route_tquery_status():
    return jsonify(_proxy_get(f"{TQUERY_URL}/tquery/status"))

# ── TKill Routes (beacon-aware: auto-discovers actual port) ──
_tkill_beacon_cache = {"port": 9901, "ts": 0}

def _tkill_url():
    """Read beacon file to find TKill's actual port (cached H13=13s)."""
    import time as _t
    if _t.time() - _tkill_beacon_cache["ts"] < 13:
        return f"http://127.0.0.1:{_tkill_beacon_cache['port']}"
    try:
        with open(r"C:\NovaX\memory\tkill_beacon.json", "r") as f:
            beacon = json.loads(f.read())
            _tkill_beacon_cache["port"] = beacon.get("port", 9901)
            _tkill_beacon_cache["ts"] = _t.time()
    except Exception:
        pass
    return f"http://127.0.0.1:{_tkill_beacon_cache['port']}"

TKILL_URL = "http://127.0.0.1:9901"  # fallback, _tkill_url() preferred

@app.get("/api/tkill/status")
def route_tkill_status():
    import urllib.request as _ur
    try:
        r = _ur.urlopen(f"{_tkill_url()}/tkill/status", timeout=10)
        return jsonify(json.loads(r.read()))
    except Exception as e:
        return jsonify({"error": str(e)}), 502

@app.post("/api/tkill/flush")
def route_tkill_flush():
    import urllib.request as _ur
    try:
        req = _ur.Request(f"{_tkill_url()}/tkill/flush", data=b"{}",
                          headers={"Content-Type": "application/json"})
        r = _ur.urlopen(req, timeout=60)
        return jsonify(json.loads(r.read()))
    except Exception as e:
        return jsonify({"error": str(e)}), 502

@app.post("/api/tkill/flush-one")
def route_tkill_flush_one():
    import urllib.request as _ur
    data = request.get_data()
    try:
        req = _ur.Request(f"{_tkill_url()}/tkill/flush-one", data=data,
                          headers={"Content-Type": "application/json"})
        r = _ur.urlopen(req, timeout=30)
        return jsonify(json.loads(r.read()))
    except Exception as e:
        return jsonify({"error": str(e)}), 502

@app.post("/api/tkill/flush-and-boot")
def route_tkill_flush_and_boot():
    import urllib.request as _ur
    try:
        req = _ur.Request(f"{_tkill_url()}/tkill/flush-and-boot", data=b"{}",
                          headers={"Content-Type": "application/json"})
        r = _ur.urlopen(req, timeout=120)
        return jsonify(json.loads(r.read()))
    except Exception as e:
        return jsonify({"error": str(e)}), 502

@app.post("/api/tkill/verify")
def route_tkill_verify():
    import urllib.request as _ur
    try:
        r = _ur.urlopen(f"{_tkill_url()}/tkill/verify", timeout=30)
        return jsonify(json.loads(r.read()))
    except Exception as e:
        return jsonify({"error": str(e)}), 502

@app.get("/api/tkill/snapshot")
def route_tkill_snapshot():
    return jsonify(_proxy_get(f"{_tkill_url()}/tkill/snapshot"))

@app.get("/api/tkill/beacon")
def route_tkill_beacon():
    return jsonify(_proxy_get(f"{_tkill_url()}/tkill/beacon"))

@app.get("/api/tkill/beacons")
def route_tkill_beacons():
    return jsonify(_proxy_get(f"{_tkill_url()}/tkill/beacons"))

@app.get("/api/tkill/zombies")
def route_tkill_zombies():
    return jsonify(_proxy_get(f"{_tkill_url()}/tkill/zombies"))

@app.post("/api/tkill/zombie-kill")
def route_tkill_zombie_kill():
    return jsonify(_proxy_post(f"{_tkill_url()}/tkill/zombie-kill", request.get_json(silent=True) or {}))

@app.post("/api/tkill/zombie-scan-kill")
def route_tkill_zombie_scan_kill():
    return jsonify(_proxy_post(f"{_tkill_url()}/tkill/zombie-scan-kill", {}))

@app.post("/api/tkill/boot-one")
def route_tkill_boot_one():
    return jsonify(_proxy_post(f"{_tkill_url()}/tkill/boot-one", request.get_json(silent=True) or {}))

# ── TResource Routes (proxy to Ternary Server :9885) ──
_TRES_URL = "http://127.0.0.1:9885"

@app.get("/api/tresource/status")
def route_tresource_status():
    return jsonify(_proxy_get(f"{_TRES_URL}/tresource/status"))

@app.get("/api/tresource/predict")
def route_tresource_predict():
    return jsonify(_proxy_get(f"{_TRES_URL}/tresource/predict"))

@app.get("/api/tresource/service/<name>")
def route_tresource_service(name):
    return jsonify(_proxy_get(f"{_TRES_URL}/tresource/service/{name}"))

@app.post("/api/tresource/materialize")
def route_tresource_materialize():
    return jsonify(_proxy_post(f"{_TRES_URL}/tresource/materialize", request.get_json(silent=True) or {}))

@app.post("/api/tresource/dematerialize")
def route_tresource_dematerialize():
    return jsonify(_proxy_post(f"{_TRES_URL}/tresource/dematerialize", request.get_json(silent=True) or {}))

@app.post("/api/tresource/sweep")
def route_tresource_sweep():
    return jsonify(_proxy_post(f"{_TRES_URL}/tresource/sweep", {}))

# ── TernaryBridge Routes (proxy to VPN :9880) ──
VPN_URL = "http://127.0.0.1:9880"

@app.get("/api/tbridge/status")
def route_tbridge_status():
    import urllib.request as _ur
    try:
        r = _ur.urlopen(f"{VPN_URL}/n/tbridge/status", timeout=5)
        return jsonify(json.loads(r.read()))
    except Exception as e:
        return jsonify({"error": str(e)}), 502

@app.post("/api/tbridge/configure")
def route_tbridge_configure():
    import urllib.request as _ur
    try:
        data = request.get_data()
        req = _ur.Request(f"{VPN_URL}/n/tbridge/configure", data=data,
                          headers={"Content-Type": "application/json"})
        r = _ur.urlopen(req, timeout=10)
        return jsonify(json.loads(r.read()))
    except Exception as e:
        return jsonify({"error": str(e)}), 502

@app.post("/api/tbridge/start")
def route_tbridge_start():
    import urllib.request as _ur
    try:
        req = _ur.Request(f"{VPN_URL}/n/tbridge/start", data=b"{}",
                          headers={"Content-Type": "application/json"})
        r = _ur.urlopen(req, timeout=20)
        return jsonify(json.loads(r.read()))
    except Exception as e:
        return jsonify({"error": str(e)}), 502

@app.post("/api/tbridge/stop")
def route_tbridge_stop():
    import urllib.request as _ur
    try:
        req = _ur.Request(f"{VPN_URL}/n/tbridge/stop", data=b"{}",
                          headers={"Content-Type": "application/json"})
        r = _ur.urlopen(req, timeout=10)
        return jsonify(json.loads(r.read()))
    except Exception as e:
        return jsonify({"error": str(e)}), 502

@app.post("/api/tbridge/switch")
def route_tbridge_switch():
    import urllib.request as _ur
    try:
        req = _ur.Request(f"{VPN_URL}/n/tbridge/switch", data=b"{}",
                          headers={"Content-Type": "application/json"})
        r = _ur.urlopen(req, timeout=20)
        return jsonify(json.loads(r.read()))
    except Exception as e:
        return jsonify({"error": str(e)}), 502

@app.post("/api/tbridge/probe")
def route_tbridge_probe():
    import urllib.request as _ur
    try:
        req = _ur.Request(f"{VPN_URL}/n/tbridge/probe", data=b"{}",
                          headers={"Content-Type": "application/json"})
        r = _ur.urlopen(req, timeout=60)
        return jsonify(json.loads(r.read()))
    except Exception as e:
        return jsonify({"error": str(e)}), 502

@app.get("/api/tbridge/schedule")
def route_tbridge_schedule():
    import urllib.request as _ur
    try:
        segs = request.args.get("segments", "7")
        r = _ur.urlopen(f"{VPN_URL}/n/tbridge/schedule?segments={segs}", timeout=5)
        return jsonify(json.loads(r.read()))
    except Exception as e:
        return jsonify({"error": str(e)}), 502

# ── GENERIC TERNARY SERVICE PROXY (75-tool architecture) ──
# Single gateway route: /api/t<service>/<action> → localhost:<port>/<prefix>/<action>
# Handles GET and POST for all Wave 1-5 ternary micro-tools.
_TERNARY_PROXY = {
    "thealth":    9940, "tconfig":    9941, "tlog":       9942,
    "tauth":      9952, "tmetrics":   9953, "tstream":    9955,
    "tcache":     9956, "tqueue":     9957, "tgraph":     9958,
    "tscheduler": 9959, "tembed":     9960, "trouter":    9963,
    "tvalidator": 9964, "tsnapshot":  9965, "tpipeline":  9966,
    "tmatrix":    9967, "talchemy":   9928, "treplay":    9937,
    "tcluster":   9971, "tcompress":  9972, "tdiff":      9973,
    "taudit":     9974, "tnotify":    9975, "tsync":      9976,
    "tprompt":    9977, "tmemory":    9978, "tgateway":   9979,
    "tprofile":   9980, "tlock":      9981, "tflow":      9982,
    "tdigest":    9983, "tbalance":   9984,
    "tscale":     9986,
    "tshield":    9987, "tgarlic":    9996,
    "thunter":    9988,
    "fleet":      9926,
}

@app.route("/api/<service>/<path:action>", methods=["GET", "POST"])
def route_ternary_proxy(service, action):
    """Generic proxy for all ternary micro-tools.
    GET  /api/tauth/status → GET  localhost:9952/tauth/status
    POST /api/tcache/set   → POST localhost:9956/tcache/set
    """
    port = _TERNARY_PROXY.get(service)
    if port is None:
        return jsonify({"error": f"Unknown ternary service: {service}"}), 404
    url = f"http://127.0.0.1:{port}/{service}/{action}"
    if request.method == "GET":
        return jsonify(_proxy_get(url))
    else:
        body = request.get_json(force=True, silent=True) or {}
        # Fleet scatter needs longer timeout (N-S parallel inference)
        timeout = 120 if service == "fleet" else 30
        return jsonify(_proxy_post_json(url, body, timeout=timeout))

# Health endpoint for all ternary proxied services
@app.get("/api/ternary/health")
def route_ternary_health():
    """Quick health check across all 33 ternary micro-tools."""
    import concurrent.futures
    results = {}
    def _check(name, port):
        try:
            import urllib.request
            urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=3).read()
            return name, {"port": port, "status": "up", "trit": 1}
        except Exception:
            return name, {"port": port, "status": "down", "trit": -1}
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
        futures = [pool.submit(_check, n, p) for n, p in _TERNARY_PROXY.items()]
        for f in concurrent.futures.as_completed(futures):
            name, status = f.result()
            results[name] = status
    up = sum(1 for v in results.values() if v["trit"] == 1)
    total = len(results)
    return jsonify({"ok": True, "up": up, "total": total, "pct": round(up/total*100, 1), "services": results})

# ── STATIC FILE CATCH-ALL (must be LAST) ──
@app.get("/<path:filename>")
def serve_static(filename):
    if filename.startswith("api/"):
        return jsonify({"error": f"Unknown API route: /{filename}"}), 404
    try:
        return send_from_directory(str(STATIC), filename)
    except Exception:
        return jsonify({"error": f"File not found: {filename}"}), 404


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def _fmt_uptime(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h}h {m}m {s}s"


_ollama_alive = None  # cached health state
_ollama_checked = 0

def _check_ollama() -> bool:
    """Quick Ollama health check with 30s cache."""
    global _ollama_alive, _ollama_checked
    now = time.time()
    if _ollama_alive is not None and (now - _ollama_checked) < 30:
        return _ollama_alive
    try:
        import requests
        r = requests.get("http://127.0.0.1:11434/api/tags", timeout=3)
        _ollama_alive = r.ok
    except Exception:
        _ollama_alive = False
    _ollama_checked = now
    return _ollama_alive


def _ask_ollama(text: str, model: str) -> str | None:
    """Ask a local Ollama model (with health pre-check)."""
    if not _check_ollama():
        print(f"Ollama offline, skipping {model}")
        return None
    try:
        import requests
        r = requests.post(
            "http://127.0.0.1:11434/api/generate",
            json={"model": model, "prompt": text, "stream": False},
            timeout=30
        )
        if r.ok:
            return r.json().get("response", "")
    except Exception as e:
        print(f"Ollama query failed ({model}): {e}")
    return None


# ─────────────────────────────────────────────
# GOD MODE  (multi-model orchestration)
# ─────────────────────────────────────────────

@app.get("/api/godmode/status")
def godmode_status():
    return jsonify(god_engine.status())

@app.post("/api/godmode/create")
def godmode_create():
    d = request.json or {}
    name = d.get("name", "Untitled Session")
    desc = d.get("description", "")
    ws = d.get("workspace")
    return jsonify(god_engine.create_session(name, desc, ws))

@app.post("/api/godmode/activate")
def godmode_activate():
    return jsonify(god_engine.activate())

@app.post("/api/godmode/pause")
def godmode_pause():
    return jsonify(god_engine.pause())

@app.post("/api/godmode/resume")
def godmode_resume():
    return jsonify(god_engine.resume())

@app.post("/api/godmode/complete")
def godmode_complete():
    return jsonify(god_engine.complete())

@app.post("/api/godmode/model")
def godmode_register_model():
    d = request.json or {}
    return jsonify(god_engine.register_model(
        d.get("model_id", ""), d.get("role", "builder"),
        d.get("capabilities")))

@app.post("/api/godmode/job")
def godmode_create_job():
    d = request.json or {}
    return jsonify(god_engine.create_job(
        d.get("title", ""), d.get("description", ""),
        d.get("assigned_model", ""), d.get("role", ""),
        d.get("dependencies")))

@app.post("/api/godmode/job/<job_id>/assign")
def godmode_assign_job(job_id):
    d = request.json or {}
    return jsonify(god_engine.assign_job(job_id, d.get("model_id", ""), d.get("role", "")))

@app.post("/api/godmode/job/<job_id>/start")
def godmode_start_job(job_id):
    result = god_engine.start_job(job_id)
    if result.get("error"):
        return jsonify(result)
    # Dispatch to assigned model if prompt is provided
    job_data = result
    model_id = job_data.get("assigned_model", "")
    prompt = job_data.get("description", "")
    if model_id and prompt:
        import threading
        def _dispatch():
            try:
                import requests as rq
                # Try Ollama first (local models)
                r = rq.post("http://127.0.0.1:11434/api/generate",
                    json={"model": model_id, "prompt": prompt, "stream": False}, timeout=60)
                if r.ok:
                    resp = r.json().get("response", "")
                    god_engine.complete_job(job_id, output=resp)
                    return
            except Exception:
                pass
            try:
                import requests as rq
                # Fallback: route through Cloud Router
                r = rq.post("http://127.0.0.1:9878/api/v1/query",
                    json={"prompt": prompt, "providers": [model_id]}, timeout=60)
                if r.ok:
                    results = r.json().get("results", [])
                    resp = results[0].get("resp", "") if results else ""
                    god_engine.complete_job(job_id, output=resp)
                    return
            except Exception as e:
                god_engine.fail_job(job_id, error=str(e))
        threading.Thread(target=_dispatch, daemon=True).start()
    return jsonify(result)

@app.post("/api/godmode/job/<job_id>/complete")
def godmode_complete_job(job_id):
    d = request.json or {}
    return jsonify(god_engine.complete_job(
        job_id, d.get("output", ""),
        d.get("files_created"), d.get("files_modified")))

@app.post("/api/godmode/job/<job_id>/fail")
def godmode_fail_job(job_id):
    d = request.json or {}
    return jsonify(god_engine.fail_job(job_id, d.get("error", "")))

@app.post("/api/godmode/memory")
def godmode_update_memory():
    d = request.json or {}
    return jsonify(god_engine.update_memory(d.get("key", ""), d.get("value")))

@app.get("/api/godmode/memory")
def godmode_read_memory():
    key = request.args.get("key")
    return jsonify({"memory": god_engine.read_memory(key)})

@app.post("/api/godmode/execute")
def godmode_execute():
    """Execute a prompt across multiple models with role assignment."""
    d = request.json or {}
    prompt = d.get("prompt", "")
    models = d.get("models")
    task_type = d.get("task_type", "general")
    if not prompt:
        return jsonify({"error": "prompt required"})
    import requests as rq
    results = []
    # Fan-out to Cloud Router (all cloud providers)
    try:
        cr = rq.post("http://127.0.0.1:9878/api/v1/query",
            json={"prompt": prompt, "providers": models}, timeout=40)
        if cr.ok:
            crd = cr.json()
            results.extend(crd.get("results", []))
    except Exception as e:
        print(f"God Mode cloud router failed: {e}")
        results.append({"prov": "cloud_router", "error": str(e), "ok": False})
    # Also query Hivemind (local swarm)
    try:
        hm = rq.post("http://127.0.0.1:9881/hive/query",
            json={"prompt": prompt, "task_type": task_type, "model_count": d.get("model_count", 3)}, timeout=40)
        if hm.ok:
            hmd = hm.json()
            if hmd.get("individual_results"):
                for r in hmd["individual_results"]:
                    results.append({
                        "prov": "ollama", "model": r.get("model", "local"),
                        "resp": r.get("response", ""), "ok": r.get("ok", True),
                        "ms": r.get("ms", 0), "source": "hivemind"
                    })
            if hmd.get("merged_response"):
                results.append({
                    "prov": "hivemind_merged", "model": "swarm",
                    "resp": hmd["merged_response"], "ok": True, "source": "hivemind_merge"
                })
    except Exception as e:
        print(f"God Mode hivemind failed: {e}")
        results.append({"prov": "hivemind", "error": str(e), "ok": False, "source": "hivemind"})
    return jsonify({
        "ok": True, "prompt": prompt[:100],
        "results": results, "total_models": len(results),
        "cloud_count": len([r for r in results if r.get("source") != "hivemind"]),
        "local_count": len([r for r in results if r.get("source") == "hivemind"]),
    })


# ─────────────────────────────────────────────
# UNIFIED LOG QUERY
# ─────────────────────────────────────────────

@app.get("/api/logs")
def route_unified_logs():
    """Query logs from all services in one call."""
    limit = int(request.args.get("limit", 50))
    source = request.args.get("source", "all")
    entries = []

    # Orchestrator's own logs
    if source in ("all", "orchestrator"):
        try:
            log_path = Path(r"C:\NovaX\logs\orchestrator.log")
            if log_path.exists():
                lines = log_path.read_text(errors="replace").strip().split("\n")
                for line in lines[-limit:]:
                    entries.append({"source": "orchestrator", "line": line[:300]})
        except Exception:
            pass

    # Sentinel events
    if source in ("all", "sentinel"):
        try:
            import requests as _rq
            r = _rq.get("http://127.0.0.1:9877/events", timeout=3)
            if r.ok:
                for ev in r.json()[-limit:]:
                    entries.append({"source": "sentinel", **ev})
        except Exception:
            pass

    # Apply log
    if source in ("all", "apply"):
        try:
            log_path = Path(r"C:\NovaX\memory\apply_log.jsonl")
            if log_path.exists():
                import json as _json
                for line in log_path.read_text().strip().split("\n")[-limit:]:
                    try:
                        entries.append({"source": "apply", **_json.loads(line)})
                    except Exception:
                        pass
        except Exception:
            pass

    # Voice log
    if source in ("all", "voice"):
        try:
            from voice import get_voice_log
            for ev in get_voice_log(limit):
                entries.append({"source": "voice", **ev})
        except Exception:
            pass

    # Sort by timestamp if available
    entries.sort(key=lambda e: e.get("ts", e.get("timestamp", e.get("time", 0))), reverse=True)
    return jsonify({"entries": entries[:limit], "total": len(entries)})


# ─────────────────────────────────────────────
# SERVICE PRE-FLIGHT CHECK
# ─────────────────────────────────────────────

def _preflight():
    """Run pre-flight checks before startup."""
    checks = []
    # Check critical directories
    for d in [r"C:\NovaX\memory", r"C:\NovaX\logs", r"C:\NovaX\config",
              r"C:\NovaX\modules", r"C:\NovaX\projects"]:
        os.makedirs(d, exist_ok=True)
        checks.append({"check": f"dir:{d}", "ok": os.path.isdir(d)})

    # Check Ollama
    try:
        import requests as _rq
        r = _rq.get("http://127.0.0.1:11434/api/tags", timeout=3)
        checks.append({"check": "ollama", "ok": r.ok, "models": len(r.json().get("models", []))})
    except Exception:
        checks.append({"check": "ollama", "ok": False, "note": "offline"})

    # Check config files
    for cfg in [r"C:\NovaX\cloud_config.json", r"C:\NovaX\config\openclaw.json"]:
        exists = os.path.exists(cfg)
        checks.append({"check": f"config:{os.path.basename(cfg)}", "ok": exists})

    ok_count = sum(1 for c in checks if c["ok"])
    print(f"  Pre-flight: {ok_count}/{len(checks)} checks passed")
    for c in checks:
        if not c["ok"]:
            print(f"    [WARN] {c['check']}: {c.get('note', 'missing')}")
    return checks


@app.get("/api/preflight")
def route_preflight():
    return jsonify(_preflight())


# ─────────────────────────────────────────────
# DEVICE DETECTION
# ─────────────────────────────────────────────

@app.get("/api/devices/scan")
def route_devices_scan():
    return jsonify(scan_devices())

@app.get("/api/devices/status")
def route_devices_status():
    return jsonify(dev_device_status())

@app.get("/api/devices/usb")
def route_devices_usb():
    return jsonify({"drives": list_usb_drives()})

@app.get("/api/devices/log")
def route_devices_log():
    limit = request.args.get("limit", 50, type=int)
    return jsonify({"events": get_device_log(limit)})

@app.get("/api/devices/rules")
def route_devices_rules():
    return jsonify({"rules": dev_get_rules()})

@app.post("/api/devices/rules")
def route_devices_add_rule():
    d = request.get_json() or {}
    rule = dev_add_rule(d.get("device_type", ""), d.get("name_pattern", "*"),
                        d.get("action", "notify"), d.get("params"))
    return jsonify(rule)

@app.delete("/api/devices/rules/<rule_id>")
def route_devices_del_rule(rule_id):
    return jsonify(dev_remove_rule(rule_id))

@app.post("/api/devices/monitor/start")
def route_devices_monitor_start():
    d = request.get_json() or {}
    interval = d.get("interval", 10)
    return jsonify(dev_start_monitor(interval=interval))

@app.post("/api/devices/monitor/stop")
def route_devices_monitor_stop():
    return jsonify(dev_stop_monitor())

@app.get("/api/devices/monitor")
def route_devices_monitor_status():
    return jsonify(dev_monitor_status())


# ─────────────────────────────────────────────
# SHELL REPLACEMENT / OS INTEGRATION
# ─────────────────────────────────────────────

@app.get("/api/shell/status")
def route_shell_status():
    return jsonify(shell_status())

@app.post("/api/shell/install")
def route_shell_install():
    return jsonify(install_shell())

@app.post("/api/shell/uninstall")
def route_shell_uninstall():
    return jsonify(uninstall_shell())

@app.get("/api/os/takeover")
def route_os_takeover_status():
    return jsonify(takeover_status())

@app.post("/api/os/startup/enable")
def route_os_startup_enable():
    return jsonify(enable_startup())

@app.post("/api/os/startup/disable")
def route_os_startup_disable():
    return jsonify(disable_startup())

@app.get("/api/os/startup")
def route_os_startup_status():
    return jsonify(startup_status())

@app.post("/api/os/boot-task/create")
def route_os_boot_task():
    return jsonify(create_boot_task())

@app.post("/api/os/boot-task/remove")
def route_os_boot_task_remove():
    return jsonify(remove_boot_task())

@app.get("/api/os/services")
def route_os_services():
    return jsonify({"services": ot_check_services()})

@app.post("/api/os/elevate")
def route_os_elevate():
    """Run an OS takeover action with admin elevation (triggers UAC)."""
    data = request.get_json() or {}
    action = data.get("action", "")
    valid = ["startup-enable", "startup-disable", "boot-task-create",
             "boot-task-remove", "shell-install", "shell-uninstall", "status",
             "integration-enable-all", "integration-disable-all",
             "theme-set", "theme-restore", "lockscreen-set", "lockscreen-restore",
             "file-assoc-enable", "file-assoc-disable"]
    if action not in valid:
        return jsonify({"ok": False, "error": f"Invalid action. Valid: {valid}"}), 400
    elevate_script = os.path.join(str(Path(__file__).parent.parent), "installer", "elevate.py")
    result_file = os.path.join(str(Path(__file__).parent.parent), "memory", "elevation_result.json")
    # Clear stale result so polling detects the new one
    try:
        if os.path.exists(result_file):
            os.remove(result_file)
    except Exception:
        pass
    try:
        import subprocess as sp
        sp.Popen([sys.executable, elevate_script, action],
                 cwd=str(Path(__file__).parent.parent),
                 creationflags=getattr(sp, "CREATE_NO_WINDOW", 0))
        return jsonify({"ok": True, "action": action,
                        "message": f"Elevation requested for '{action}'. Check UAC prompt.",
                        "result_file": result_file})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.get("/api/os/elevate/result")
def route_os_elevate_result():
    """Read the result of the last elevated operation."""
    result_file = os.path.join(str(Path(__file__).parent.parent), "memory", "elevation_result.json")
    if os.path.exists(result_file):
        try:
            with open(result_file) as f:
                return jsonify(json.load(f))
        except Exception:
            pass
    return jsonify({"pending": True, "message": "No elevation result yet"})


# ─────────────────────────────────────────────
# CODE PROTECTION
# ─────────────────────────────────────────────

@app.get("/api/protection/status")
def route_protection_status():
    return jsonify(protection_status())

@app.post("/api/protection/fingerprint")
def route_protection_fingerprint():
    return jsonify(fingerprint_all())

@app.post("/api/protection/integrity/generate")
def route_protection_integrity_gen():
    return jsonify(generate_integrity_manifest())

@app.get("/api/protection/integrity/verify")
def route_protection_integrity_verify():
    return jsonify(verify_integrity())

@app.post("/api/protection/encrypt-all")
def route_protection_encrypt_all():
    return jsonify(encrypt_all_source())

@app.post("/api/protection/sign")
def route_protection_sign():
    d = request.get_json() or {}
    version = d.get("version", "4.0.0")
    return jsonify(sign_release(version))

@app.get("/api/protection/log")
def route_protection_log():
    limit = request.args.get("limit", 30, type=int)
    return jsonify({"events": get_protection_log(limit)})


# ─────────────────────────────────────────────
# MODE SYSTEM
# ─────────────────────────────────────────────

@app.get("/api/mode")
def route_mode():
    return jsonify(mode_system.get_mode_config())

@app.get("/api/mode/list")
def route_mode_list():
    return jsonify(mode_system.list_modes())

@app.post("/api/mode/set")
def route_mode_set():
    d = request.get_json() or {}
    mode = d.get("mode", "general")
    result = mode_system.set_mode(mode)
    if result is None:
        return jsonify({"error": f"Unknown mode: {mode}"}), 400
    return jsonify(result)

@app.post("/api/mode/auto")
def route_mode_auto():
    d = request.get_json() or {}
    text = d.get("text", "")
    apps = d.get("active_apps", None)
    result = mode_system.auto_switch(text, apps)
    if result:
        return jsonify({"switched": True, "config": result})
    return jsonify({"switched": False, "current": mode_system.get_mode()})

@app.get("/api/mode/detect")
def route_mode_detect():
    text = request.args.get("text", "")
    return jsonify({"detected": mode_system.detect_mode(text)})


# ─────────────────────────────────────────────
# GAMEPLAY / AI CREATIVITY ENGINE
# ─────────────────────────────────────────────

@app.get("/api/gameplay/status")
def route_gameplay_status():
    return jsonify(gameplay_learner.status())

@app.get("/api/gameplay/skills")
def route_gameplay_skills():
    top = request.args.get("top", 20, type=int)
    return jsonify({"skills": gameplay_learner.skill_summary(top)})

@app.post("/api/gameplay/game")
def route_gameplay_set_game():
    d = request.get_json() or {}
    gameplay_learner.set_game(d.get("game", "unknown"))
    return jsonify({"ok": True, "game": gameplay_learner.active_game})

@app.post("/api/gameplay/role")
def route_gameplay_assign_role():
    d = request.get_json() or {}
    gameplay_learner.assign_role(d.get("model", ""), d.get("role", ""))
    return jsonify({"ok": True, "roles": gameplay_learner.model_roles})

@app.post("/api/gameplay/observe")
def route_gameplay_observe():
    d = request.get_json() or {}
    state = d.get("state", {})
    gs = gameplay_learner.observe(state)
    return jsonify(gs.to_dict())

@app.post("/api/gameplay/propose")
def route_gameplay_propose():
    d = request.get_json() or {}
    gameplay_learner.propose_action(d.get("model", ""), d.get("action", ""),
                                    d.get("confidence", 1.0))
    return jsonify({"ok": True, "buffer_size": len(gameplay_learner.decision_buffer)})

@app.post("/api/gameplay/merge")
def route_gameplay_merge():
    result = gameplay_learner.merge_decisions()
    if result is None:
        return jsonify({"error": "No pending decisions"}), 400
    return jsonify(result)

@app.post("/api/gameplay/outcome")
def route_gameplay_outcome():
    d = request.get_json() or {}
    gameplay_learner.record_outcome(d.get("situation", ""),
                                    d.get("action", ""),
                                    d.get("success", False))
    return jsonify({"ok": True})

@app.get("/api/gameplay/best")
def route_gameplay_best():
    situation = request.args.get("situation", "")
    result = gameplay_learner.best_action(situation)
    return jsonify(result or {"action": None, "confidence": 0})

@app.post("/api/gameplay/save")
def route_gameplay_save():
    gameplay_learner.save()
    return jsonify({"ok": True, "skills": len(gameplay_learner.skill_graph)})


# ─────────────────────────────────────────────
# HIVE MIND — Unified AI Model Dispatch
# ─────────────────────────────────────────────

@app.get("/api/hive/status")
def route_hive_status():
    return jsonify(hive_mind.status())

@app.get("/api/hive/models")
def route_hive_models():
    return jsonify(hive_mind.model_list())

@app.get("/api/hive/leaderboard")
def route_hive_leaderboard():
    top = request.args.get("top", 10, type=int)
    return jsonify({"leaderboard": hive_mind.model_leaderboard(top)})

@app.post("/api/hive/discover")
def route_hive_discover():
    return jsonify(hive_mind.discover_models())

@app.post("/api/hive/query")
def route_hive_query():
    d = request.get_json() or {}
    uid = d.get("model_uid", "")
    prompt = d.get("prompt", "")
    if not uid or not prompt:
        return jsonify({"error": "model_uid and prompt required"}), 400
    return jsonify(hive_mind.query_model(uid, prompt))

@app.post("/api/hive/fan-out")
def route_hive_fanout():
    d = request.get_json() or {}
    prompt = d.get("prompt", "")
    if not prompt:
        return jsonify({"error": "prompt required"}), 400
    providers = d.get("providers")
    max_models = d.get("max_models", 15)
    mode = d.get("mode", "synthesis")
    result = hive_mind.fan_out(prompt, providers=providers, max_models=max_models, mode=mode)
    workspace_watch.record_event("fan_out", "hive_mind",
        f"Queried {result.get('models_queried', 0)} models, {result.get('models_succeeded', 0)} succeeded")
    return jsonify(result)

@app.post("/api/hive/handoff")
def route_hive_handoff():
    d = request.get_json() or {}
    prompt = d.get("prompt", "")
    failed = d.get("failed_model", "")
    if not prompt or not failed:
        return jsonify({"error": "prompt and failed_model required"}), 400
    result = hive_mind.handoff_task(prompt, failed)
    workspace_watch.record_handoff(failed, result.get("model_uid", ""), "rate_limit_or_error")
    return jsonify(result)

@app.post("/api/hive/save")
def route_hive_save():
    hive_mind.save_state()
    return jsonify({"ok": True})

@app.post("/api/hive/deepseek")
def route_hive_deepseek():
    """Proxy to Hivemind DeepSeek swarm — fans out to cloud + local DeepSeek models."""
    import requests as _rq
    d = request.get_json() or {}
    prompt = d.get("prompt", d.get("q", ""))
    if not prompt:
        return jsonify({"error": "prompt required"}), 400
    try:
        r = _rq.post("http://127.0.0.1:9881/hive/deepseek",
                      json={"prompt": prompt, "system": d.get("system")}, timeout=60)
        return jsonify(r.json())
    except Exception as e:
        return jsonify({"error": f"Hivemind unreachable: {e}"}), 502

@app.post("/api/hive/swarm")
def route_hive_full_swarm():
    """FULL SWARM — fans out to ALL 29+ cloud models + all local models simultaneously."""
    import requests as _rq
    d = request.get_json() or {}
    prompt = d.get("prompt", d.get("q", ""))
    if not prompt:
        return jsonify({"error": "prompt required"}), 400
    try:
        r = _rq.post("http://127.0.0.1:9881/hive/swarm",
                      json={"prompt": prompt, "system": d.get("system")}, timeout=90)
        return jsonify(r.json())
    except Exception as e:
        return jsonify({"error": f"Hivemind unreachable: {e}"}), 502

@app.get("/api/hive/nova")
def route_hive_nova_status():
    """Execute NovaLang unified model registry (config check, no swarm)."""
    import requests as _rq
    try:
        r = _rq.get("http://127.0.0.1:9881/hive/nova", timeout=15)
        return jsonify(r.json())
    except Exception as e:
        return jsonify({"error": f"NovaLang execution failed: {e}"}), 502

@app.post("/api/hive/nova/dispatch")
def route_hive_nova_dispatch():
    """Execute NovaLang hive dispatch — full swarm through NovaLang unifier."""
    import requests as _rq
    d = request.get_json() or {}
    prompt = d.get("prompt", d.get("q", ""))
    if not prompt:
        return jsonify({"error": "prompt required"}), 400
    try:
        r = _rq.post("http://127.0.0.1:9881/hive/nova/dispatch",
                      json={"prompt": prompt}, timeout=330)
        return jsonify(r.json())
    except Exception as e:
        return jsonify({"error": f"NovaLang dispatch failed: {e}"}), 502


# ─────────────────────────────────────────────
# BENCHMARK CLUSTER — Navier-Stokes Flow Routes
# ─────────────────────────────────────────────

@app.get("/api/hive/cluster/status")
def route_hive_cluster_status():
    return jsonify(_proxy_get("http://127.0.0.1:9881/hive/cluster/status"))

@app.get("/api/hive/cluster/channels")
def route_hive_cluster_channels():
    return jsonify(_proxy_get("http://127.0.0.1:9881/hive/cluster/channels"))

@app.post("/api/hive/cluster/query")
def route_hive_cluster_query():
    """Cluster query — needs long timeout for multi-model deliberation."""
    import urllib.request as _ur
    d = request.get_json() or {}
    try:
        data = json.dumps(d).encode()
        req = _ur.Request("http://127.0.0.1:9881/hive/cluster/query",
                          data, {"Content-Type": "application/json"})
        with _ur.urlopen(req, timeout=330) as r:  # 5.5 min for full deliberation
            return jsonify(json.loads(r.read()))
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 502

@app.post("/api/hive/cluster/classify")
def route_hive_cluster_classify():
    d = request.get_json() or {}
    return jsonify(_proxy_post("http://127.0.0.1:9881/hive/cluster/classify", d))

@app.post("/api/hive/ternary/math")
def route_hive_ternary_math():
    d = request.get_json() or {}
    return jsonify(_proxy_post("http://127.0.0.1:9881/hive/ternary/math", d))

@app.post("/api/hive/pipeline")
def route_hive_pipeline():
    """Pipeline query — needs 600s timeout for multi-channel mesh."""
    import urllib.request as _ur
    d = request.get_json() or {}
    try:
        data = json.dumps(d).encode()
        req = _ur.Request("http://127.0.0.1:9881/hive/pipeline",
                          data, {"Content-Type": "application/json"})
        with _ur.urlopen(req, timeout=600) as r:
            return jsonify(json.loads(r.read()))
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 502

@app.get("/api/hive/modulation/status")
def route_hive_modulation_status():
    return jsonify(_proxy_get("http://127.0.0.1:9881/hive/modulation/status"))

@app.get("/api/hive/modulation/schemes")
def route_hive_modulation_schemes():
    return jsonify(_proxy_get("http://127.0.0.1:9881/hive/modulation/schemes"))

# ── Hivemind Cache (agent-added, port 9881) ─────────────────
@app.get("/api/hive/cache/stats")
def route_hive_cache_stats():
    return jsonify(_proxy_get("http://127.0.0.1:9881/hive/cache/stats"))

@app.post("/api/hive/cache/flush")
def route_hive_cache_flush():
    return jsonify(_proxy_post_json("http://127.0.0.1:9881/hive/cache/flush", {}))

# ── Fleet Auto-Scaling (agent-added, port 9926) ────────────
@app.get("/api/fleet/scaling/status")
def route_fleet_scaling_status():
    return jsonify(_proxy_get("http://127.0.0.1:9926/fleet/scaling"))

@app.get("/api/fleet/scaling/rules")
def route_fleet_scaling_rules():
    return jsonify(_proxy_get("http://127.0.0.1:9926/fleet/scaling/rules"))

@app.get("/api/fleet/scaling/history")
def route_fleet_scaling_history():
    return jsonify(_proxy_get("http://127.0.0.1:9926/fleet/scaling/history"))

@app.post("/api/fleet/scaling/rules")
def route_fleet_scaling_rules_update():
    return jsonify(_proxy_post_json("http://127.0.0.1:9926/fleet/scaling/rules", request.get_json(force=True)))

@app.post("/api/fleet/scaling/execute")
def route_fleet_scaling_execute():
    return jsonify(_proxy_post_json("http://127.0.0.1:9926/fleet/scaling/execute", request.get_json(force=True)))

@app.post("/api/fleet/scaling/evaluate")
def route_fleet_scaling_evaluate():
    return jsonify(_proxy_post_json("http://127.0.0.1:9926/fleet/scaling/evaluate", request.get_json(force=True)))

# ── TShell Error Recovery (agent-added, port 9890) ─────────
TSHELL_RECOVERY_URL = "http://127.0.0.1:9890"

@app.get("/api/tshell/recovery/errors")
def route_tshell_recovery_errors():
    return jsonify(_proxy_get(f"{TSHELL_RECOVERY_URL}/recovery/errors"))

@app.get("/api/tshell/recovery/patterns")
def route_tshell_recovery_patterns():
    return jsonify(_proxy_get(f"{TSHELL_RECOVERY_URL}/recovery/patterns"))

@app.get("/api/tshell/recovery/stats")
def route_tshell_recovery_stats():
    return jsonify(_proxy_get(f"{TSHELL_RECOVERY_URL}/recovery/stats"))

@app.post("/api/tshell/recovery/report")
def route_tshell_recovery_report():
    return jsonify(_proxy_post_json(f"{TSHELL_RECOVERY_URL}/recovery/report", request.get_json(force=True)))

@app.post("/api/tshell/recovery/clear")
def route_tshell_recovery_clear():
    return jsonify(_proxy_post_json(f"{TSHELL_RECOVERY_URL}/recovery/clear", {}))

# ── TAlchemy Validation (agent-added, port 9928) ───────────
@app.post("/api/talchemy/validate/rows")
def route_talchemy_validate_rows():
    return jsonify(_proxy_post_json("http://127.0.0.1:9928/talchemy/validate/rows", request.get_json(force=True), timeout=30))

@app.post("/api/talchemy/schema")
def route_talchemy_schema():
    return jsonify(_proxy_post_json("http://127.0.0.1:9928/talchemy/schema", request.get_json(force=True)))

@app.post("/api/talchemy/quality")
def route_talchemy_quality():
    return jsonify(_proxy_post_json("http://127.0.0.1:9928/talchemy/quality", request.get_json(force=True)))

# ─────────────────────────────────────────────
# TERNARY SERVER (:9885) — unified ternary + REPL
# ─────────────────────────────────────────────

@app.get("/api/ternary/status")
def route_ternary_status():
    return jsonify(_proxy_get("http://127.0.0.1:9885/ternary/status"))

@app.post("/api/ternary/route")
def route_ternary_route():
    return jsonify(_proxy_post_json("http://127.0.0.1:9885/ternary/route",
                                     request.get_json(silent=True) or {}))

@app.post("/api/ternary/quantize")
def route_ternary_quantize():
    return jsonify(_proxy_post_json("http://127.0.0.1:9885/ternary/quantize",
                                     request.get_json(silent=True) or {}))

@app.get("/api/ternary/adjacency")
def route_ternary_adjacency():
    return jsonify(_proxy_get("http://127.0.0.1:9885/ternary/adjacency"))

@app.get("/api/ternary/stream")
def route_ternary_stream():
    return jsonify(_proxy_get("http://127.0.0.1:9885/ternary/stream"))

# ── Ability Router (port 9954) ──────────────────────────────────
@app.post("/api/ability")
def route_ability():
    return jsonify(_proxy_post_json("http://127.0.0.1:9954/ability",
                                     request.get_json(silent=True) or {}, timeout=60))

@app.post("/api/ability/code")
def route_ability_code():
    return jsonify(_proxy_post_json("http://127.0.0.1:9954/ability/code",
                                     request.get_json(silent=True) or {}, timeout=60))

@app.post("/api/ability/reason")
def route_ability_reason():
    return jsonify(_proxy_post_json("http://127.0.0.1:9954/ability/reason",
                                     request.get_json(silent=True) or {}, timeout=60))

@app.post("/api/ability/vision")
def route_ability_vision():
    return jsonify(_proxy_post_json("http://127.0.0.1:9954/ability/vision",
                                     request.get_json(silent=True) or {}, timeout=60))

@app.post("/api/ability/math")
def route_ability_math():
    return jsonify(_proxy_post_json("http://127.0.0.1:9954/ability/math",
                                     request.get_json(silent=True) or {}, timeout=60))

@app.post("/api/ability/sql")
def route_ability_sql():
    return jsonify(_proxy_post_json("http://127.0.0.1:9954/ability/sql",
                                     request.get_json(silent=True) or {}, timeout=60))

@app.post("/api/ability/embed")
def route_ability_embed():
    return jsonify(_proxy_post_json("http://127.0.0.1:9954/ability/embed",
                                     request.get_json(silent=True) or {}, timeout=30))

@app.post("/api/ability/translate")
def route_ability_translate():
    return jsonify(_proxy_post_json("http://127.0.0.1:9954/ability/translate",
                                     request.get_json(silent=True) or {}, timeout=60))

@app.post("/api/ability/swarm")
def route_ability_swarm():
    return jsonify(_proxy_post_json("http://127.0.0.1:9954/ability/swarm",
                                     request.get_json(silent=True) or {}, timeout=60))

@app.get("/api/abilities")
def route_abilities_list():
    return jsonify(_proxy_get("http://127.0.0.1:9954/abilities"))

# ── Ternary SQL (port 9968) ─────────────────────────────────────
@app.post("/api/tsql")
def route_tsql():
    return jsonify(_proxy_post_json("http://127.0.0.1:9968/tsql",
                                     request.get_json(silent=True) or {}, timeout=10))

@app.post("/api/tsql/batch")
def route_tsql_batch():
    return jsonify(_proxy_post_json("http://127.0.0.1:9968/tsql/batch",
                                     request.get_json(silent=True) or {}, timeout=30))

# ── Unsolved N-S Models (via Hivemind) ──────────────────────────
@app.get("/api/ns/unsolved")
def route_ns_unsolved():
    return jsonify(_proxy_get("http://127.0.0.1:9881/ns/unsolved"))

# ── HuggingFace Gateway (509,882 models) ─────────────────────────
@app.post("/api/hf/call")
def route_hf_call():
    return jsonify(_proxy_post_json("http://127.0.0.1:9969/hf/call",
                                     request.get_json(silent=True) or {}, timeout=30))

@app.post("/api/hf/generate")
def route_hf_generate():
    return jsonify(_proxy_post_json("http://127.0.0.1:9969/hf/generate",
                                     request.get_json(silent=True) or {}, timeout=30))

@app.post("/api/hf/classify")
def route_hf_classify():
    return jsonify(_proxy_post_json("http://127.0.0.1:9969/hf/classify",
                                     request.get_json(silent=True) or {}, timeout=30))

@app.post("/api/hf/summarize")
def route_hf_summarize():
    return jsonify(_proxy_post_json("http://127.0.0.1:9969/hf/summarize",
                                     request.get_json(silent=True) or {}, timeout=30))

@app.post("/api/hf/translate")
def route_hf_translate():
    return jsonify(_proxy_post_json("http://127.0.0.1:9969/hf/translate",
                                     request.get_json(silent=True) or {}, timeout=30))

@app.post("/api/hf/embed")
def route_hf_embed():
    return jsonify(_proxy_post_json("http://127.0.0.1:9969/hf/embed",
                                     request.get_json(silent=True) or {}, timeout=30))

@app.post("/api/hf/qa")
def route_hf_qa():
    return jsonify(_proxy_post_json("http://127.0.0.1:9969/hf/qa",
                                     request.get_json(silent=True) or {}, timeout=30))

@app.post("/api/hf/swarm")
def route_hf_swarm():
    return jsonify(_proxy_post_json("http://127.0.0.1:9969/hf/swarm",
                                     request.get_json(silent=True) or {}, timeout=60))

@app.post("/api/hf/discover")
def route_hf_discover():
    return jsonify(_proxy_post_json("http://127.0.0.1:9969/hf/discover",
                                     request.get_json(silent=True) or {}, timeout=15))

@app.get("/api/hf/stats")
def route_hf_stats():
    return jsonify(_proxy_get("http://127.0.0.1:9969/hf/stats"))

@app.get("/api/hf/pipelines")
def route_hf_pipelines():
    return jsonify(_proxy_get("http://127.0.0.1:9969/hf/pipelines"))

# ── Hivemind HF endpoints (via hivemind :9881) ──
@app.post("/api/hivemind/hf/swarm")
def route_hivemind_hf_swarm():
    return jsonify(_proxy_post_json("http://127.0.0.1:9881/hf/swarm",
                                     request.get_json(silent=True) or {}, timeout=60))

@app.post("/api/hivemind/hf/discover")
def route_hivemind_hf_discover():
    return jsonify(_proxy_post_json("http://127.0.0.1:9881/hf/discover",
                                     request.get_json(silent=True) or {}, timeout=15))

@app.get("/api/hivemind/hf/stats")
def route_hivemind_hf_stats():
    return jsonify(_proxy_get("http://127.0.0.1:9881/hf/stats"))

@app.get("/api/hivemind/hf/pipelines")
def route_hivemind_hf_pipelines():
    return jsonify(_proxy_get("http://127.0.0.1:9881/hf/pipelines"))

@app.post("/api/nova/exec")
def route_nova_exec():
    return jsonify(_proxy_post_json("http://127.0.0.1:9885/nova/exec",
                                     request.get_json(silent=True) or {}, timeout=120))

@app.post("/api/nova/reset")
def route_nova_reset():
    return jsonify(_proxy_post_json("http://127.0.0.1:9885/nova/reset",
                                     request.get_json(silent=True) or {}))

@app.get("/api/nova/sessions")
def route_nova_sessions():
    return jsonify(_proxy_get("http://127.0.0.1:9885/nova/sessions"))

# ── Ternary Code Layer routes (via ternary server :9885) ──

@app.get("/api/ternary/trace")
def route_ternary_trace():
    return jsonify(_proxy_get("http://127.0.0.1:9885/ternary/trace"))

@app.post("/api/ternary/classify")
def route_ternary_classify():
    return jsonify(_proxy_post_json("http://127.0.0.1:9885/ternary/classify",
                                     request.get_json(silent=True) or {}))

@app.get("/api/ternary/layer/status")
def route_ternary_layer_status():
    return jsonify(_proxy_get("http://127.0.0.1:9885/ternary/layer/status"))

# ── Compiler routes (via ternary server :9885) ──

@app.post("/api/nova/compile")
def route_nova_compile():
    return jsonify(_proxy_post_json("http://127.0.0.1:9885/nova/compile",
                                     request.get_json(silent=True) or {}, timeout=30))

@app.post("/api/nova/ast")
def route_nova_ast():
    return jsonify(_proxy_post_json("http://127.0.0.1:9885/nova/ast",
                                     request.get_json(silent=True) or {}))

@app.post("/api/nova/run-bytecode")
def route_nova_run_bytecode():
    return jsonify(_proxy_post_json("http://127.0.0.1:9885/nova/run-bytecode",
                                     request.get_json(silent=True) or {}, timeout=30))

# ── Universal Debugger routes (merged into TKill, beacon-aware) ──

@app.get("/api/liud/status")
def route_liud_status():
    return jsonify(_proxy_get(f"{_tkill_url()}/liud/status"))

@app.post("/api/liud/start")
def route_liud_start():
    return jsonify(_proxy_post_json(f"{_tkill_url()}/liud/start",
                                     request.get_json(silent=True) or {}, timeout=30))

@app.post("/api/liud/step")
def route_liud_step():
    return jsonify(_proxy_post_json(f"{_tkill_url()}/liud/step",
                                     request.get_json(silent=True) or {}))

@app.post("/api/liud/next")
def route_liud_next():
    return jsonify(_proxy_post_json(f"{_tkill_url()}/liud/next",
                                     request.get_json(silent=True) or {}))

@app.post("/api/liud/continue")
def route_liud_continue():
    return jsonify(_proxy_post_json(f"{_tkill_url()}/liud/continue",
                                     request.get_json(silent=True) or {}))

@app.post("/api/liud/stop")
def route_liud_stop():
    return jsonify(_proxy_post_json(f"{_tkill_url()}/liud/stop",
                                     request.get_json(silent=True) or {}))

@app.get("/api/liud/frame")
def route_liud_frame():
    return jsonify(_proxy_get(f"{_tkill_url()}/liud/frame"))

@app.get("/api/liud/vars")
def route_liud_vars():
    return jsonify(_proxy_get(f"{_tkill_url()}/liud/vars"))

@app.get("/api/liud/ternary")
def route_liud_ternary():
    return jsonify(_proxy_get(f"{_tkill_url()}/liud/ternary"))

@app.post("/api/liud/breakpoint")
def route_liud_breakpoint():
    return jsonify(_proxy_post_json(f"{_tkill_url()}/liud/breakpoint",
                                     request.get_json(silent=True) or {}))

@app.get("/api/liud/anomalies")
def route_liud_anomalies():
    return jsonify(_proxy_get(f"{_tkill_url()}/liud/anomalies"))

@app.get("/api/liud/output")
def route_liud_output():
    return jsonify(_proxy_get(f"{_tkill_url()}/liud/output"))

@app.get("/api/liud/frames")
def route_liud_frames():
    return jsonify(_proxy_get(f"{_tkill_url()}/liud/frames"))

@app.get("/api/liud/callstack")
def route_liud_callstack():
    return jsonify(_proxy_get(f"{_tkill_url()}/liud/callstack"))

@app.get("/api/liud/breakpoints")
def route_liud_breakpoints():
    return jsonify(_proxy_get(f"{_tkill_url()}/liud/breakpoints"))

@app.get("/api/liud/live-status")
def route_liud_live_status():
    return jsonify(_proxy_get(f"{_tkill_url()}/liud/live-status"))

@app.post("/api/liud/watch")
def route_liud_watch():
    return jsonify(_proxy_post_json(f"{_tkill_url()}/liud/watch",
                                     request.get_json(silent=True) or {}))

@app.post("/api/liud/live-monitor/start")
def route_liud_live_monitor_start():
    return jsonify(_proxy_post_json(f"{_tkill_url()}/liud/live-monitor/start",
                                     request.get_json(silent=True) or {}))

@app.post("/api/liud/live-monitor/stop")
def route_liud_live_monitor_stop():
    return jsonify(_proxy_post_json(f"{_tkill_url()}/liud/live-monitor/stop",
                                     request.get_json(silent=True) or {}))

# ── NovaCLI routes (port 9961) ──

@app.get("/api/cli/health")
def route_cli_health():
    return jsonify(_proxy_get("http://127.0.0.1:9961/cli/health"))

@app.post("/api/cli/exec")
def route_cli_exec():
    return jsonify(_proxy_post_json("http://127.0.0.1:9961/cli/exec",
                                     request.get_json(silent=True) or {}, timeout=30))

@app.post("/api/cli/complete")
def route_cli_complete():
    return jsonify(_proxy_post_json("http://127.0.0.1:9961/cli/complete",
                                     request.get_json(silent=True) or {}))

@app.get("/api/cli/sessions")
def route_cli_sessions():
    return jsonify(_proxy_get("http://127.0.0.1:9961/cli/sessions"))

@app.post("/api/cli/run-file")
def route_cli_run_file():
    return jsonify(_proxy_post_json("http://127.0.0.1:9961/cli/run-file",
                                     request.get_json(silent=True) or {}, timeout=30))

@app.get("/api/cli/commands")
def route_cli_commands():
    return jsonify(_proxy_get("http://127.0.0.1:9961/cli/commands"))

@app.get("/api/cli/history")
def route_cli_history():
    return jsonify(_proxy_get("http://127.0.0.1:9961/cli/history"))


# ── Closed Loop Engine routes (port 9888) ──

@app.get("/api/loop/status")
def route_loop_status():
    return jsonify(_proxy_get("http://127.0.0.1:9888/loop/status"))

@app.get("/api/loop/agents")
def route_loop_agents():
    return jsonify(_proxy_get("http://127.0.0.1:9888/loop/agents"))

@app.get("/api/loop/deliberations")
def route_loop_deliberations():
    return jsonify(_proxy_get("http://127.0.0.1:9888/loop/deliberations"))

@app.get("/api/loop/tasks")
def route_loop_tasks():
    return jsonify(_proxy_get("http://127.0.0.1:9888/loop/tasks"))

@app.get("/api/loop/self-heal")
def route_loop_selfheal():
    return jsonify(_proxy_get("http://127.0.0.1:9888/loop/self-heal"))

@app.get("/api/loop/optimizer")
def route_loop_optimizer():
    return jsonify(_proxy_get("http://127.0.0.1:9888/loop/optimizer"))

@app.post("/api/loop/dispatch")
def route_loop_dispatch():
    return jsonify(_proxy_post_json("http://127.0.0.1:9888/loop/dispatch",
                                    request.get_json(force=True, silent=True) or {}))

@app.post("/api/loop/deliberate")
def route_loop_deliberate():
    return jsonify(_proxy_post_json("http://127.0.0.1:9888/loop/deliberate",
                                    request.get_json(force=True, silent=True) or {}))

@app.post("/api/loop/heal")
def route_loop_heal():
    return jsonify(_proxy_post_json("http://127.0.0.1:9888/loop/heal",
                                    request.get_json(force=True, silent=True) or {}))

@app.post("/api/loop/optimize")
def route_loop_optimize():
    return jsonify(_proxy_post_json("http://127.0.0.1:9888/loop/optimize",
                                    request.get_json(force=True, silent=True) or {}))

@app.post("/api/loop/toggle")
def route_loop_toggle():
    return jsonify(_proxy_post_json("http://127.0.0.1:9888/loop/toggle",
                                    request.get_json(force=True, silent=True) or {}))


# ─────────────────────────────────────────────
# MAX PATCH — Ternary Max Limit Patch Layer
# ─────────────────────────────────────────────

@app.get("/api/patch/status")
def route_patch_status():
    return jsonify(_proxy_get("http://127.0.0.1:9889/patch/status"))

@app.get("/api/patch/fingerprints")
def route_patch_fingerprints():
    return jsonify(_proxy_get("http://127.0.0.1:9889/patch/fingerprints"))

@app.get("/api/patch/ensembles")
def route_patch_ensembles():
    return jsonify(_proxy_get("http://127.0.0.1:9889/patch/ensembles"))

@app.get("/api/patch/limits")
def route_patch_limits():
    return jsonify(_proxy_get("http://127.0.0.1:9889/patch/limits"))

@app.get("/api/patch/patches")
def route_patch_patches():
    return jsonify(_proxy_get("http://127.0.0.1:9889/patch/patches"))

@app.get("/api/patch/matrix")
def route_patch_matrix():
    return jsonify(_proxy_get("http://127.0.0.1:9889/patch/matrix"))

@app.get("/api/patch/fingerprint/<path:model_id>")
def route_patch_fingerprint(model_id):
    return jsonify(_proxy_get(f"http://127.0.0.1:9889/patch/fingerprint/{model_id}"))

@app.post("/api/patch/probe")
def route_patch_probe():
    return jsonify(_proxy_post_json("http://127.0.0.1:9889/patch/probe",
                                    request.get_json(force=True, silent=True) or {}))

@app.post("/api/patch/probe-all")
def route_patch_probe_all():
    return jsonify(_proxy_post_json("http://127.0.0.1:9889/patch/probe-all",
                                    request.get_json(force=True, silent=True) or {}))

@app.post("/api/patch/optimize")
def route_patch_optimize():
    return jsonify(_proxy_post_json("http://127.0.0.1:9889/patch/optimize",
                                    request.get_json(force=True, silent=True) or {}))

@app.post("/api/patch/route")
def route_patch_route():
    return jsonify(_proxy_post_json("http://127.0.0.1:9889/patch/route",
                                    request.get_json(force=True, silent=True) or {}))

@app.post("/api/patch/toggle")
def route_patch_toggle():
    return jsonify(_proxy_post_json("http://127.0.0.1:9889/patch/toggle",
                                    request.get_json(force=True, silent=True) or {}))

@app.get("/api/patch/services")
def route_patch_services():
    return jsonify(_proxy_get("http://127.0.0.1:9889/patch/services"))

@app.get("/api/patch/seal-log")
def route_patch_seal_log():
    return jsonify(_proxy_get("http://127.0.0.1:9889/patch/seal-log"))

@app.post("/api/patch/seal")
def route_patch_seal():
    return jsonify(_proxy_post_json("http://127.0.0.1:9889/patch/seal",
                                    request.get_json(force=True, silent=True) or {}))

@app.post("/api/maxpatch/feedback")
@app.post("/api/patch/feedback")
def route_patch_feedback():
    return jsonify(_proxy_post_json("http://127.0.0.1:9889/patch/feedback",
                                    request.get_json(force=True, silent=True) or {}))

# -- MaxPatch ternary additions: rank, influence, chess --
@app.get("/api/patch/rank")
def route_patch_rank():
    qs = request.query_string.decode()
    return jsonify(_proxy_get(f"http://127.0.0.1:9889/patch/rank?{qs}"))

# ── SuperPatch routes (port 9889 /super/*) ──
PATCH_URL = "http://127.0.0.1:9889"

@app.get("/api/super/status")
def route_super_status():
    return jsonify(_proxy_get(f"{PATCH_URL}/super/status"))

@app.get("/api/super/fingerprints")
def route_super_fingerprints():
    return jsonify(_proxy_get(f"{PATCH_URL}/super/fingerprints"))

@app.get("/api/super/fingerprint/<path:model_id>")
def route_super_fingerprint(model_id):
    return jsonify(_proxy_get(f"{PATCH_URL}/super/fingerprint/{model_id}"))

@app.get("/api/super/hidden")
def route_super_hidden():
    return jsonify(_proxy_get(f"{PATCH_URL}/super/hidden"))

@app.get("/api/super/matrix")
def route_super_matrix():
    return jsonify(_proxy_get(f"{PATCH_URL}/super/matrix"))

@app.post("/api/super/probe")
def route_super_probe():
    return jsonify(_proxy_post_json(f"{PATCH_URL}/super/probe",
                                    request.get_json(force=True, silent=True) or {}, timeout=300))

@app.post("/api/super/probe-all")
def route_super_probe_all():
    return jsonify(_proxy_post_json(f"{PATCH_URL}/super/probe-all",
                                    request.get_json(force=True, silent=True) or {}))

@app.post("/api/super/toggle")
def route_super_toggle():
    return jsonify(_proxy_post_json(f"{PATCH_URL}/super/toggle",
                                    request.get_json(force=True, silent=True) or {}))

# ── Brain routes (port 9990) ──
@app.get("/api/brain/status")
def route_brain_status():
    return jsonify(_proxy_get("http://127.0.0.1:9990/health"))

@app.get("/api/brain/models")
def route_brain_models():
    return jsonify(_proxy_get("http://127.0.0.1:9990/models"))

@app.post("/api/brain/generate")
def route_brain_generate():
    return jsonify(_proxy_post_json("http://127.0.0.1:9990/generate",
                                    request.get_json(force=True, silent=True) or {}))

@app.post("/api/brain/chat")
def route_brain_chat():
    return jsonify(_proxy_post_json("http://127.0.0.1:9990/chat",
                                    request.get_json(force=True, silent=True) or {}))

# ── TShell routes (port 9890) ──

@app.get("/api/tshell/status")
def route_tshell_status():
    return jsonify(_proxy_get("http://127.0.0.1:9890/tshell/status"))

@app.get("/api/tshell/index")
def route_tshell_index():
    qs = request.query_string.decode()
    url = "http://127.0.0.1:9890/tshell/index" + ("?" + qs if qs else "")
    return jsonify(_proxy_get(url))

@app.get("/api/tshell/system")
def route_tshell_system():
    return jsonify(_proxy_get("http://127.0.0.1:9890/tshell/system"))

@app.get("/api/tshell/channels")
def route_tshell_channels():
    return jsonify(_proxy_get("http://127.0.0.1:9890/tshell/channels"))

@app.get("/api/tshell/config")
def route_tshell_config_get():
    return jsonify(_proxy_get("http://127.0.0.1:9890/tshell/config"))

@app.post("/api/tshell/scan")
def route_tshell_scan():
    return jsonify(_proxy_post_json("http://127.0.0.1:9890/tshell/scan",
                                    request.get_json(force=True, silent=True) or {}))

@app.post("/api/tshell/compress")
def route_tshell_compress():
    return jsonify(_proxy_post_json("http://127.0.0.1:9890/tshell/compress",
                                    request.get_json(force=True, silent=True) or {}))

@app.post("/api/tshell/decompress")
def route_tshell_decompress():
    return jsonify(_proxy_post_json("http://127.0.0.1:9890/tshell/decompress",
                                    request.get_json(force=True, silent=True) or {}))

@app.post("/api/tshell/watch")
def route_tshell_watch():
    return jsonify(_proxy_post_json("http://127.0.0.1:9890/tshell/watch",
                                    request.get_json(force=True, silent=True) or {}))

@app.post("/api/tshell/toggle")
def route_tshell_toggle():
    return jsonify(_proxy_post_json("http://127.0.0.1:9890/tshell/toggle",
                                    request.get_json(force=True, silent=True) or {}))

@app.post("/api/tshell/toggle-compress")
def route_tshell_toggle_compress():
    return jsonify(_proxy_post_json("http://127.0.0.1:9890/tshell/toggle-compress",
                                    request.get_json(force=True, silent=True) or {}))

@app.post("/api/tshell/config")
def route_tshell_config_post():
    return jsonify(_proxy_post_json("http://127.0.0.1:9890/tshell/config",
                                    request.get_json(force=True, silent=True) or {}))


# Process manager routes removed — moved inline above tshell routes


# ── NovaXCore routes (replaces OpenClaw, on TShell port 9890) ──

CORE_URL = "http://127.0.0.1:9890"

@app.get("/api/core/status")
def route_core_status():
    return jsonify(_proxy_get(f"{CORE_URL}/core/status"))

@app.get("/api/core/history")
def route_core_history():
    qs = request.query_string.decode()
    url = f"{CORE_URL}/core/history" + ("?" + qs if qs else "")
    return jsonify(_proxy_get(url))

@app.post("/api/core/exec")
def route_core_exec():
    return jsonify(_proxy_post_json(f"{CORE_URL}/core/exec",
                                    request.get_json(force=True, silent=True) or {}, timeout=60))

@app.post("/api/core/route")
def route_core_route():
    return jsonify(_proxy_post_json(f"{CORE_URL}/core/route",
                                    request.get_json(force=True, silent=True) or {}))

@app.post("/api/core/query")
def route_core_query():
    return jsonify(_proxy_post_json(f"{CORE_URL}/core/query",
                                    request.get_json(force=True, silent=True) or {}, timeout=200))

@app.post("/api/core/consensus")
def route_core_consensus():
    return jsonify(_proxy_post_json(f"{CORE_URL}/core/consensus",
                                    request.get_json(force=True, silent=True) or {}, timeout=120))

@app.post("/api/core/pipe")
def route_core_pipe():
    return jsonify(_proxy_post_json(f"{CORE_URL}/core/pipe",
                                    request.get_json(force=True, silent=True) or {}, timeout=120))

@app.post("/api/core/env")
def route_core_env():
    return jsonify(_proxy_post_json(f"{CORE_URL}/core/env",
                                    request.get_json(force=True, silent=True) or {}))

@app.post("/api/core/proc")
def route_core_proc():
    return jsonify(_proxy_post_json(f"{CORE_URL}/core/proc",
                                    request.get_json(force=True, silent=True) or {}))

@app.post("/api/core/net")
def route_core_net():
    return jsonify(_proxy_post_json(f"{CORE_URL}/core/net",
                                    request.get_json(force=True, silent=True) or {}, timeout=30))

# ── NovaXCore Tripple Resonance Sensor routes ──
@app.get("/api/core/tripple/status")
def route_core_tripple_status():
    return jsonify(_proxy_get(f"{CORE_URL}/core/tripple/status"))

@app.get("/api/core/tripple/wave")
def route_core_tripple_wave():
    return jsonify(_proxy_get(f"{CORE_URL}/core/tripple/wave"))

@app.get("/api/core/tripple/mirror")
def route_core_tripple_mirror():
    return jsonify(_proxy_get(f"{CORE_URL}/core/tripple/mirror"))

@app.post("/api/core/tripple/ripple")
def route_core_tripple_ripple():
    return jsonify(_proxy_post_json(f"{CORE_URL}/core/tripple/ripple",
                                    request.get_json(force=True, silent=True) or {}))

# ── Hivemind Tripple Resonance Sensor routes ──
HIVE_URL = "http://127.0.0.1:9881"

@app.get("/api/hive/tripple/status")
def route_hive_tripple_status():
    return jsonify(_proxy_get(f"{HIVE_URL}/hive/tripple/status"))

@app.get("/api/hive/tripple/wave")
def route_hive_tripple_wave():
    return jsonify(_proxy_get(f"{HIVE_URL}/hive/tripple/wave"))

@app.get("/api/hive/tripple/mirror")
def route_hive_tripple_mirror():
    return jsonify(_proxy_get(f"{HIVE_URL}/hive/tripple/mirror"))

@app.post("/api/hive/tripple/ripple")
def route_hive_tripple_ripple():
    return jsonify(_proxy_post_json(f"{HIVE_URL}/hive/tripple/ripple",
                                    request.get_json(force=True, silent=True) or {}))


# ─────────────────────────────────────────────
# WORKSPACE WATCH — Real-Time Model Monitor
# ─────────────────────────────────────────────

@app.get("/api/watch/status")
def route_watch_status():
    return jsonify(workspace_watch.status())

@app.get("/api/watch/active")
def route_watch_active():
    return jsonify({"tasks": workspace_watch.get_active()})

@app.get("/api/watch/feed")
def route_watch_feed():
    limit = request.args.get("limit", 50, type=int)
    event_type = request.args.get("type")
    return jsonify({"feed": workspace_watch.get_feed(limit, event_type)})

@app.get("/api/watch/health")
def route_watch_health():
    return jsonify({"models": workspace_watch.get_health()})

@app.get("/api/watch/throughput")
def route_watch_throughput():
    window = request.args.get("window", 300, type=int)
    return jsonify(workspace_watch.get_throughput(window))


# ─────────────────────────────────────────────
# NOVALANG DEBUGGER — 58th Language
# ─────────────────────────────────────────────

@app.get("/api/novalang/status")
def route_novalang_status():
    return jsonify(novalang_debugger.status())

@app.post("/api/novalang/repl")
def route_novalang_repl():
    d = request.get_json() or {}
    code = d.get("code", "")
    if not code:
        return jsonify({"error": "code required"}), 400
    return jsonify(novalang_debugger.repl.evaluate(code))

@app.get("/api/novalang/repl/history")
def route_novalang_repl_history():
    limit = request.args.get("limit", 50, type=int)
    return jsonify({"history": novalang_debugger.repl.get_history(limit)})

@app.post("/api/novalang/repl/clear")
def route_novalang_repl_clear():
    return jsonify(novalang_debugger.repl.clear_history())

@app.post("/api/novalang/analyze")
def route_novalang_analyze():
    d = request.get_json() or {}
    code = d.get("code", "")
    if not code:
        return jsonify({"error": "code required"}), 400
    return jsonify(novalang_debugger.analyze(code))

@app.post("/api/novalang/breakpoint")
def route_novalang_breakpoint():
    d = request.get_json() or {}
    return jsonify(novalang_debugger.set_breakpoint(d.get("file", ""), d.get("line", 0)))

@app.delete("/api/novalang/breakpoint")
def route_novalang_breakpoint_remove():
    d = request.get_json() or {}
    return jsonify(novalang_debugger.remove_breakpoint(d.get("file", ""), d.get("line", 0)))

@app.get("/api/novalang/breakpoints")
def route_novalang_breakpoints():
    return jsonify(novalang_debugger.list_breakpoints())

@app.get("/api/novalang/syntax")
def route_novalang_syntax():
    from novalang_debugger import SYNTAX_THEME, NOVALANG_KEYWORDS, NOVALANG_TYPES
    return jsonify({"theme": SYNTAX_THEME, "keywords": NOVALANG_KEYWORDS, "types": NOVALANG_TYPES})


# ─────────────────────────────────────────────
# PERSISTENCE LAYER
# ─────────────────────────────────────────────

@app.get("/api/persistence/status")
def route_persistence_status():
    return jsonify(persistence.status())

@app.post("/api/persistence/save")
def route_persistence_save():
    return jsonify(persistence.save_all())

@app.post("/api/persistence/save/<name>")
def route_persistence_save_one(name):
    return jsonify(persistence.save_one(name))

@app.post("/api/persistence/restore")
def route_persistence_restore():
    return jsonify(persistence.restore_all())


# ─────────────────────────────────────────────
# WORKSPACE MANAGER
# ─────────────────────────────────────────────

@app.get("/api/workspace")
def route_workspace_active():
    ws = get_active_workspace()
    return jsonify(ws or {"active": None})

@app.post("/api/workspace/activate")
def route_workspace_activate():
    d = request.get_json() or {}
    mode = d.get("mode", "general")
    return jsonify(activate_workspace(mode))

@app.post("/api/workspace/customize")
def route_workspace_customize():
    d = request.get_json() or {}
    mode = d.get("mode", "general")
    updates = d.get("updates", {})
    return jsonify(customize_workspace(mode, updates))

@app.get("/api/workspace/<mode>")
def route_workspace_get(mode):
    return jsonify(get_workspace(mode))


# ─────────────────────────────────────────────
# SUPER ARCHIVE — FULL-TEXT SEARCH
# ─────────────────────────────────────────────

@app.get("/api/archive/status")
def route_archive_status():
    return jsonify(archive_status())

@app.post("/api/archive/index")
def route_archive_index():
    return jsonify(archive_build_index())

@app.get("/api/archive/search")
def route_archive_search():
    q = request.args.get("q", "")
    limit = int(request.args.get("limit", "20"))
    return jsonify(archive_search(q, limit=limit))

@app.post("/api/archive/search")
def route_archive_search_post():
    d = request.get_json() or {}
    return jsonify(archive_search(d.get("query", ""), limit=d.get("limit", 20)))


# ─────────────────────────────────────────────
# NOVAXCORE ENGINE PROXY (:9851)
# ─────────────────────────────────────────────
@app.post("/api/novaxcore/<tool_name>")
def route_novaxcore_tool(tool_name):
    valid = ["windows", "registry", "process", "system", "theme", "clipboard", "notify"]
    if tool_name not in valid:
        return jsonify({"ok": False, "error": f"invalid_tool: {tool_name}", "valid": valid}), 400
    d = request.get_json() or {}
    return jsonify(_proxy_post(f"http://127.0.0.1:9851/novaxcore/{tool_name}", d))

@app.post("/api/microsoft/<tool_name>")
def route_microsoft_tool(tool_name):
    """Legacy route — redirects to novaxcore"""
    valid = ["windows", "registry", "process", "system", "theme", "clipboard", "notify"]
    if tool_name not in valid:
        return jsonify({"ok": False, "error": f"invalid_tool: {tool_name}", "valid": valid}), 400
    d = request.get_json() or {}
    return jsonify(_proxy_post(f"http://127.0.0.1:9851/novaxcore/{tool_name}", d))

@app.get("/api/novaxcore/status")
def route_novaxcore_status():
    return jsonify(_proxy_get("http://127.0.0.1:9851/status"))

@app.get("/api/novaxcore/health")
def route_novaxcore_health():
    return jsonify(_proxy_get("http://127.0.0.1:9851/health"))

@app.get("/api/microsoft/status")
def route_microsoft_status():
    return jsonify(_proxy_get("http://127.0.0.1:9851/status"))

@app.get("/api/microsoft/health")
def route_microsoft_health():
    return jsonify(_proxy_get("http://127.0.0.1:9851/health"))


# ── Pacman Purification Engine Proxy ─────────────────────────────
@app.get("/api/pacman/purity/scan")
def route_purity_scan():
    return jsonify(_proxy_get("http://127.0.0.1:9991/pacman/purity/scan"))

@app.get("/api/pacman/purity/status")
def route_purity_status():
    return jsonify(_proxy_get("http://127.0.0.1:9991/pacman/purity/status"))

@app.get("/api/pacman/purity/locks")
def route_purity_locks():
    return jsonify(_proxy_get("http://127.0.0.1:9991/pacman/purity/locks"))

@app.post("/api/pacman/purity/check")
def route_purity_check():
    d = request.get_json() or {}
    return jsonify(_proxy_post("http://127.0.0.1:9991/pacman/purity/check", d))

@app.post("/api/pacman/purity/convert")
def route_purity_convert():
    d = request.get_json() or {}
    return jsonify(_proxy_post("http://127.0.0.1:9991/pacman/purity/convert", d))

@app.post("/api/pacman/purity/lock")
def route_purity_lock():
    d = request.get_json() or {}
    return jsonify(_proxy_post("http://127.0.0.1:9991/pacman/purity/lock", d))


# ─────────────────────────────────────────────
# STARTUP
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print(f"\n  NovaX Orchestrator v{VERSION}")
    print(f"  Port: 9999 | Profile: {active_profile()}")
    print(f"  Drivers: 6 | Endpoints: 80+")
    print(f"  Two-Phase Intent: Option A/B active")
    _preflight()

    # ── Route Validator: boot-time catalog + continuous monitoring ──
    try:
        sys.path.insert(0, str(ROOT / "core"))
        from route_validator import get_validator
        rv = get_validator()
        manifest = rv.build_manifest(app)
        total = manifest["summary"]["total"]
        critical = sum(1 for r in manifest["routes"].values() if r["tier"] == "critical")
        print(f"  Route Validator: {total} routes cataloged ({critical} critical)")
        rv.start_continuous(smoke_interval=30, deep_interval=300)
        print(f"  Route Validator: continuous monitoring active (30s smoke / 5m deep)")
    except Exception as e:
        print(f"  Route Validator: FAILED to start — {e}")

    # ── Background Health Monitor with auto-recovery ──
    _start_health_monitor()
    print(f"  Health Monitor: active (every {HEALTH_CHECK_INTERVAL}s, {_restart_policy['max_retries']} max retries)")

    print(f"  Welcome to NovaX. System is initializing.\n")
    event_bus.emit("STATUS", {"event": "orchestrator_started", "version": VERSION}, source="orchestrator")
    socketio.run(app, host="127.0.0.1", port=9999, debug=False,
                 use_reloader=False, allow_unsafe_werkzeug=True)
