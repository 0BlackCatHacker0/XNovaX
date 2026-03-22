"""NovaX Orchestrator Bootstrap — loads all core .pyc modules in dependency order"""
import sys, os, importlib, importlib.util, types

CORE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'core')
PYC_DIR = os.path.join(CORE, '__pycache__')
sys.path.insert(0, CORE)

def load_pyc(name):
    pyc = os.path.join(PYC_DIR, f'{name}.cpython-314.pyc')
    if not os.path.exists(pyc):
        return False
    spec = importlib.util.spec_from_file_location(name, pyc, submodule_search_locations=[])
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return True

# Discover all core .pyc modules
pyc_files = [f for f in os.listdir(PYC_DIR) if f.endswith('.cpython-314.pyc')]
core_names = sorted(set(f.replace('.cpython-314.pyc', '') for f in pyc_files))

# Load order: leaf modules first, then modules that import them
# Phase 1: Register stubs for all modules (handles circular imports)
for name in core_names:
    if name not in sys.modules:
        sys.modules[name] = types.ModuleType(name)

# Phase 2: Load in dependency order — task_classifier and other leaves first
PRIORITY = ['config', 'state', 'task_classifier', 'vcc', 'session_memory',
            'drivers', 'skills_engine', 'workflows', 'ai_router_memory',
            'ai_router', 'claude_connector', 'nova_agent', 'router_engine']
loaded = set()

for name in PRIORITY:
    if name in core_names:
        try:
            load_pyc(name)
            loaded.add(name)
        except Exception as e:
            print(f"  Phase 2 warning [{name}]: {e}")

# Phase 3: Load everything else except orchestrator
for name in core_names:
    if name not in loaded and name != 'orchestrator':
        try:
            load_pyc(name)
            loaded.add(name)
        except Exception as e:
            print(f"  Phase 3 warning [{name}]: {e}")

# Phase 4: Load orchestrator last (it imports from everything)
try:
    load_pyc('orchestrator')
    print(f"NovaX Orchestrator booted — {len(loaded)+1} core modules loaded")
except Exception as e:
    print(f"Orchestrator failed: {e}")
    sys.exit(1)

# Phase 5: Start the Flask/SocketIO server
import orchestrator as orch

# Phase 5.5: Apply health check patch (fixes false "dead" reports)
# Must happen after orchestrator is imported but before server starts
try:
    import health_patch
    health_patch.apply_patch()
    print("  Health patch: applied")
except Exception as e:
    print(f"  Health patch: FAILED - {e}")

if hasattr(orch, 'socketio') and hasattr(orch, 'app'):
    print("Starting SocketIO server on 127.0.0.1:9999 (threaded)...")
    orch.socketio.run(orch.app, host='127.0.0.1', port=9999, allow_unsafe_werkzeug=True)
elif hasattr(orch, 'app'):
    print("Starting Flask server on 127.0.0.1:9999 (threaded)...")
    orch.app.run(host='127.0.0.1', port=9999, threaded=True)
else:
    print("ERROR: No app or socketio found in orchestrator module")
    sys.exit(1)
