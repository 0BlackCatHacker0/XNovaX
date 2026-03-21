"""
NovaX Admin Elevation Helper
Runs specific NovaX operations with elevated (Administrator) privileges.

Uses Windows UAC via ShellExecuteW to self-elevate.
Called by orchestrator API when admin is required.

Usage:
  python elevate.py startup-enable     Enable NovaX startup (registry)
  python elevate.py startup-disable    Disable NovaX startup
  python elevate.py boot-task-create   Create boot scheduled task
  python elevate.py boot-task-remove   Remove boot scheduled task
  python elevate.py shell-install      Install NovaX as Windows shell
  python elevate.py shell-uninstall    Revert to explorer.exe shell
  python elevate.py status             Show current OS takeover status
"""
import sys
import os
import json
import ctypes

NOVAX_ROOT = r"C:\NovaX"
RESULT_FILE = os.path.join(NOVAX_ROOT, "memory", "elevation_result.json")

sys.path.insert(0, os.path.join(NOVAX_ROOT, "installer"))


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def request_elevation(action):
    """Re-launch this script as admin with the given action."""
    script = os.path.abspath(__file__)
    python = sys.executable
    params = f'"{script}" {action}'

    # ShellExecuteW with "runas" triggers UAC prompt
    ret = ctypes.windll.shell32.ShellExecuteW(
        None, "runas", python, params, NOVAX_ROOT, 1
    )
    # Returns >32 on success
    return ret > 32


def save_result(result):
    """Save operation result so the non-admin caller can read it."""
    os.makedirs(os.path.dirname(RESULT_FILE), exist_ok=True)
    with open(RESULT_FILE, "w") as f:
        json.dump(result, f, indent=2)


def run_action(action):
    """Execute the requested admin action."""
    if action == "startup-enable":
        from os_takeover import enable_startup
        return enable_startup()

    elif action == "startup-disable":
        from os_takeover import disable_startup
        return disable_startup()

    elif action == "boot-task-create":
        from os_takeover import create_boot_task
        return create_boot_task()

    elif action == "boot-task-remove":
        from os_takeover import remove_boot_task
        return remove_boot_task()

    elif action == "shell-install":
        from shell_replace import install_shell
        return install_shell()

    elif action == "shell-uninstall":
        from shell_replace import uninstall_shell
        return uninstall_shell()

    elif action == "status":
        from os_takeover import takeover_status
        return takeover_status()

    # ── OS Integration actions ──
    elif action == "integration-enable-all":
        from os_integration import enable_all
        return enable_all()

    elif action == "integration-disable-all":
        from os_integration import disable_all
        return disable_all()

    elif action == "theme-set":
        from os_integration import set_theme
        return set_theme()

    elif action == "theme-restore":
        from os_integration import restore_theme
        return restore_theme()

    elif action == "lockscreen-set":
        from os_integration import set_lock_screen
        return set_lock_screen()

    elif action == "lockscreen-restore":
        from os_integration import restore_lock_screen
        return restore_lock_screen()

    elif action == "file-assoc-enable":
        from os_integration import set_file_associations
        return set_file_associations()

    elif action == "file-assoc-disable":
        from os_integration import restore_file_associations
        return restore_file_associations()

    else:
        return {"ok": False, "error": f"Unknown action: {action}"}


def main():
    if len(sys.argv) < 2:
        print("Usage: python elevate.py <action>")
        print("Actions: startup-enable, startup-disable, boot-task-create,")
        print("         boot-task-remove, shell-install, shell-uninstall, status,")
        print("         integration-enable-all, integration-disable-all,")
        print("         theme-set, theme-restore, lockscreen-set, lockscreen-restore,")
        print("         file-assoc-enable, file-assoc-disable")
        return

    action = sys.argv[1]

    if not is_admin():
        print(f"[NovaX] Requesting admin elevation for: {action}")
        ok = request_elevation(action)
        if ok:
            print("[NovaX] UAC prompt shown — check elevated window for result")
            print(f"[NovaX] Result will be saved to: {RESULT_FILE}")
        else:
            print("[NovaX] Failed to request elevation")
            save_result({"ok": False, "error": "UAC elevation denied or failed"})
        return

    # We ARE admin — run the action
    print(f"[NovaX Admin] Running: {action}")
    result = run_action(action)
    save_result(result)
    print(f"[NovaX Admin] Result: {json.dumps(result, indent=2)}")
    print(f"[NovaX Admin] Saved to: {RESULT_FILE}")

    # Keep window open briefly so user can see result
    import time
    time.sleep(3)


if __name__ == "__main__":
    main()
