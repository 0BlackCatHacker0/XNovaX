"""git-sync -- Auto-commits and pushes NovaX changes to git"""
import subprocess, json, os, time

_config = {}


def setup():
    global _config
    manifest_path = os.path.join(os.path.dirname(__file__), "manifest.json")
    with open(manifest_path) as f:
        _config = json.load(f).get("config", {})
    print(f"[git-sync] Repo: {_config.get('repo_dir', 'C:\\\\NovaX')}")


def teardown():
    print("[git-sync] Stopped.")


def _git(args):
    repo = _config.get("repo_dir", r"C:\NovaX")
    r = subprocess.run(
        ["git"] + args,
        cwd=repo, capture_output=True, text=True, timeout=30
    )
    return {"ok": r.returncode == 0, "stdout": r.stdout.strip(), "stderr": r.stderr.strip()}


def run(params=None):
    params = params or {}
    message = params.get("message", f"NovaX auto-sync {time.strftime('%Y-%m-%d %H:%M')}")

    status = _git(["status", "--porcelain"])
    if not status["stdout"]:
        return {"ok": True, "message": "Nothing to commit — working tree clean"}

    changed = len(status["stdout"].strip().split("\n"))
    _git(["add", "-A"])
    commit = _git(["commit", "-m", message])

    result = {"ok": commit["ok"], "changed_files": changed, "commit": commit["stdout"][:200]}

    if _config.get("auto_push", False):
        branch = _config.get("branch", "main")
        push = _git(["push", "origin", branch])
        result["pushed"] = push["ok"]
        result["push_output"] = push["stdout"][:200] or push["stderr"][:200]

    return result
