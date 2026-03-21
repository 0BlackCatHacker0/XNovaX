"""
NovaX Enterprise Installer
One-command setup: checks Python, installs dependencies,
initializes memory stores, validates all modules, optionally
replaces the Windows shell.

Usage:
  python novax_installer.py              (full install)
  python novax_installer.py --check      (verify only)
  python novax_installer.py --shell      (install + shell replace)
"""
import json
import os
import sys
import subprocess
import time
import shutil

NOVAX_ROOT = r"C:\NovaX"

# All required Python packages
CORE_DEPS = [
    "flask",
    "flask-cors",
    "flask-socketio",
    "requests",
]

EXTENDED_DEPS = [
    "xrpl-py",
    "SpeechRecognition",
    "pyttsx3",
    "pyaudio",
    "anthropic",
]

# Directories that must exist
REQUIRED_DIRS = [
    os.path.join(NOVAX_ROOT, "memory"),
    os.path.join(NOVAX_ROOT, "memory", "profiles"),
    os.path.join(NOVAX_ROOT, "modules"),
    os.path.join(NOVAX_ROOT, "installer"),
    os.path.join(NOVAX_ROOT, "web"),
    os.path.join(NOVAX_ROOT, "web", "assets"),
    os.path.join(NOVAX_ROOT, "core"),
    os.path.join(NOVAX_ROOT, "servers"),
]

# Core Python modules that must exist
CORE_MODULES = [
    "core/orchestrator.py",
    "core/task_classifier.py",
    "core/ai_router.py",
    "core/ai_router_memory.py",
    "core/claude_connector.py",
    "core/drivers.py",
    "core/skills_engine.py",
    "core/vcc.py",
    "core/session_memory.py",
    "core/workflows.py",
    "core/time_index.py",
    "core/profile_manager.py",
    "core/event_bus.py",
    "core/arbiter.py",
    "core/dse.py",
    "core/context_watcher.py",
    "core/environment_manager.py",
    "core/state.py",
    "core/tasks.py",
    "core/config.py",
    "core/brain_server.py",
    "core/relay_server.py",
    "core/repair_engine.py",
    "core/project_learner.py",
    "core/ui_memory.py",
    "core/xrpl_wallet.py",
    "core/voice.py",
    "core/module_manager.py",
]

WEB_FILES = [
    "web/hivemind.html",
    "web/nova_desktop.html",
]

OTHER_FILES = [
    "start_all.py",
    "novax_cli.py",
]


def banner():
    print("""
  +=============================================+
  |                                             |
  |     N O V A X                               |
  |                                             |
  |     Personal AI Operating System            |
  |     Installer v2.0                          |
  |                                             |
  +=============================================+
    """)


def step(msg, status="..."):
    """Print a formatted step."""
    icons = {"ok": "[OK]", "fail": "[!!]", "skip": "[--]", "...": "[..]", "warn": "[??]"}
    print(f"  {icons.get(status, status):>6}  {msg}")


def check_python():
    """Verify Python version."""
    v = sys.version_info
    if v.major == 3 and v.minor >= 10:
        step(f"Python {v.major}.{v.minor}.{v.micro}", "ok")
        return True
    elif v.major == 3 and v.minor >= 8:
        step(f"Python {v.major}.{v.minor}.{v.micro} (3.10+ recommended)", "warn")
        return True
    else:
        step(f"Python {v.major}.{v.minor} -- need 3.8+", "fail")
        return False


def check_directories():
    """Ensure all required directories exist."""
    created = 0
    for d in REQUIRED_DIRS:
        if not os.path.exists(d):
            os.makedirs(d, exist_ok=True)
            created += 1
    step(f"Directories verified ({created} created)", "ok")
    return True


def install_deps(core_only=False):
    """Install Python dependencies."""
    deps = CORE_DEPS if core_only else CORE_DEPS + EXTENDED_DEPS
    installed = []
    failed = []

    for pkg in deps:
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", pkg, "--quiet"],
                capture_output=True, text=True, timeout=120,
            )
            if result.returncode == 0:
                installed.append(pkg)
            else:
                failed.append(pkg)
        except subprocess.TimeoutExpired:
            failed.append(pkg + " (timeout)")
        except Exception as e:
            failed.append(pkg + f" ({e})")

    if failed:
        step(f"Dependencies: {len(installed)} installed, {len(failed)} failed", "warn")
        for f in failed:
            step(f"  Failed: {f}", "fail")
    else:
        step(f"All {len(installed)} dependencies installed", "ok")

    return {"installed": installed, "failed": failed}


def check_modules():
    """Verify all core Python modules exist."""
    missing = []
    for mod in CORE_MODULES:
        path = os.path.join(NOVAX_ROOT, mod)
        if not os.path.exists(path):
            missing.append(mod)

    if missing:
        step(f"Core modules: {len(CORE_MODULES) - len(missing)}/{len(CORE_MODULES)} present", "warn")
        for m in missing[:5]:
            step(f"  Missing: {m}", "fail")
        if len(missing) > 5:
            step(f"  ... and {len(missing) - 5} more", "fail")
    else:
        step(f"All {len(CORE_MODULES)} core modules present", "ok")

    return missing


def check_web_files():
    """Verify web UI files exist."""
    missing = []
    for f in WEB_FILES:
        path = os.path.join(NOVAX_ROOT, f)
        if not os.path.exists(path):
            missing.append(f)
    if missing:
        step(f"Web files: {len(WEB_FILES) - len(missing)}/{len(WEB_FILES)}", "warn")
    else:
        step(f"All {len(WEB_FILES)} web files present", "ok")
    return missing


def check_other_files():
    """Verify other essential files."""
    missing = []
    for f in OTHER_FILES:
        path = os.path.join(NOVAX_ROOT, f)
        if not os.path.exists(path):
            missing.append(f)
    if missing:
        step(f"Other files: {len(OTHER_FILES) - len(missing)}/{len(OTHER_FILES)}", "warn")
    else:
        step(f"All utility files present", "ok")
    return missing


def validate_imports():
    """Try importing core modules to verify they load."""
    sys.path.insert(0, os.path.join(NOVAX_ROOT, "core"))
    importable = []
    errors = []

    modules_to_test = [
        "task_classifier", "ai_router", "ai_router_memory",
        "claude_connector", "drivers", "skills_engine", "vcc",
        "session_memory", "workflows", "time_index", "profile_manager",
        "event_bus", "arbiter", "dse", "context_watcher",
        "environment_manager", "state", "tasks", "config",
        "repair_engine", "project_learner", "ui_memory",
        "xrpl_wallet", "voice", "module_manager",
    ]

    for mod in modules_to_test:
        try:
            __import__(mod)
            importable.append(mod)
        except Exception as e:
            errors.append({"module": mod, "error": str(e)})

    if errors:
        step(f"Module imports: {len(importable)}/{len(modules_to_test)} OK", "warn")
        for e in errors[:5]:
            step(f"  Import fail: {e['module']} -- {e['error'][:50]}", "fail")
    else:
        step(f"All {len(importable)} modules import successfully", "ok")

    return {"importable": importable, "errors": errors}


def check_services():
    """Check if key services can start."""
    import socket
    ports = {
        9999: "Orchestrator",
        9877: "Relay",
        9990: "Brain",
        6379: "Redis",
        7700: "Meilisearch",
        11434: "Ollama",
    }
    running = {}
    for port, name in ports.items():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            result = s.connect_ex(("127.0.0.1", port))
            running[name] = result == 0
            s.close()
        except Exception:
            running[name] = False

    online = sum(1 for v in running.values() if v)
    step(f"Services: {online}/{len(ports)} online", "ok" if online > 0 else "warn")
    for name, ok in running.items():
        if ok:
            step(f"  {name}: online", "ok")

    return running


def initialize_memory():
    """Initialize default memory files if they don't exist."""
    defaults = {
        "skills.json": [],
        "repair_log.json": [],
        "xrpl_transactions.json": [],
        "voice_log.json": [],
        "module_registry.json": {},
        "ui_patterns.json": {},
        "session_capture.json": [],
        "projects.json": {},
    }
    created = 0
    for filename, default_data in defaults.items():
        path = os.path.join(NOVAX_ROOT, "memory", filename)
        if not os.path.exists(path):
            with open(path, "w") as f:
                json.dump(default_data, f)
            created += 1

    step(f"Memory stores initialized ({created} new)", "ok")
    return created


def create_boot_script():
    """Create the main boot script."""
    boot_path = os.path.join(NOVAX_ROOT, "boot.bat")
    content = f"""@echo off
title NovaX OS
color 0B
echo.
echo   ╔══════════════════════════════════════╗
echo   ║   NovaX Personal AI Operating System ║
echo   ║           Starting up...             ║
echo   ╚══════════════════════════════════════╝
echo.

cd /d "{NOVAX_ROOT}"

REM Start services
echo Starting NovaX services...
start /min python start_all.py --skip redis,stt 2>nul

REM Wait for orchestrator
echo Waiting for orchestrator...
:wait
timeout /t 2 /nobreak >nul
curl -s http://localhost:9999/health >nul 2>&1
if errorlevel 1 goto wait

echo.
echo   NovaX is ready!
echo   Opening NovaX Desktop...
echo.

REM Open NovaX Desktop
start "" http://localhost:9999/nova_desktop.html

echo   Access points:
echo     Desktop:  http://localhost:9999/nova_desktop.html
echo     Terminal: http://localhost:9999/hivemind.html
echo     API:      http://localhost:9999/health
echo.
echo   Press Ctrl+C to stop NovaX.
pause >nul
"""
    with open(boot_path, "w") as f:
        f.write(content)
    step("Boot script created (boot.bat)", "ok")
    return boot_path


def run_install(check_only=False, with_shell=False):
    """Run the full installation process."""
    banner()
    print("  ── System Check ──")
    results = {}

    # Step 1: Python
    results["python"] = check_python()

    # Step 2: Directories
    results["dirs"] = check_directories()

    # Step 3: Core modules
    results["missing_modules"] = check_modules()

    # Step 4: Web files
    results["missing_web"] = check_web_files()

    # Step 5: Other files
    results["missing_other"] = check_other_files()

    if check_only:
        print("\n  ── Import Validation ──")
        results["imports"] = validate_imports()
        print("\n  ── Service Check ──")
        results["services"] = check_services()
        print()
        total_issues = (
            len(results.get("missing_modules", [])) +
            len(results.get("missing_web", [])) +
            len(results.get("missing_other", [])) +
            len(results.get("imports", {}).get("errors", []))
        )
        if total_issues == 0:
            print("  [OK] NovaX installation is COMPLETE and VERIFIED.")
        else:
            print(f"  [!!] {total_issues} issue(s) found. Run installer to fix.")
        return results

    print("\n  ── Installing Dependencies ──")
    results["deps"] = install_deps()

    print("\n  ── Memory Initialization ──")
    results["memory"] = initialize_memory()

    print("\n  ── Import Validation ──")
    results["imports"] = validate_imports()

    print("\n  ── Boot Setup ──")
    results["boot"] = create_boot_script()

    if with_shell:
        print("\n  ── Shell Replacement ──")
        try:
            sys.path.insert(0, os.path.join(NOVAX_ROOT, "installer"))
            from shell_replace import install_shell, shell_status
            status = shell_status()
            step(f"Current shell: {status['current_shell']}", "ok")
            if not status["is_novax_shell"]:
                result = install_shell()
                if "error" in result:
                    step(result["error"], "fail")
                else:
                    step("Shell replacement prepared (manual activation needed)", "ok")
                    for inst in result.get("instructions", []):
                        print(f"        {inst}")
        except Exception as e:
            step(f"Shell replace error: {e}", "fail")

    print("\n  ── Service Check ──")
    results["services"] = check_services()

    # Summary
    print("\n  ==========================================")
    dep_fails = len(results.get("deps", {}).get("failed", []))
    import_fails = len(results.get("imports", {}).get("errors", []))
    svc_online = sum(1 for v in results.get("services", {}).values() if v)

    if dep_fails == 0 and import_fails == 0:
        print("  [OK] NovaX installation COMPLETE!")
    else:
        print(f"  [!!] Installed with {dep_fails} dep failures, {import_fails} import errors")

    print(f"  Services online: {svc_online}")
    print(f"  Boot: boot.bat or python start_all.py")
    print("  ==========================================\n")

    # Save install report
    report_path = os.path.join(NOVAX_ROOT, "memory", "install_report.json")
    with open(report_path, "w") as f:
        json.dump({
            "installed_at": time.time(),
            "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "dep_failures": dep_fails,
            "import_errors": import_fails,
            "services_online": svc_online,
        }, f, indent=2)

    return results


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--check" in args:
        run_install(check_only=True)
    elif "--shell" in args:
        run_install(with_shell=True)
    else:
        run_install()
