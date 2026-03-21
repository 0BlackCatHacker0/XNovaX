# novalang_debugger.py — NovaLang REPL + debugger for orchestrator
# Provides REPL evaluation, breakpoint management, code analysis,
# and syntax highlighting data for the NovaX desktop UI.

import subprocess
import platform
import os
import time

# ── Syntax highlighting data ──
NOVALANG_KEYWORDS = [
    "if3", "match3", "try3", "while3", "for3", "break3", "continue3",
    "fn", "return", "let", "set", "import", "class3", "print", "emit",
    "on", "spawn", "await3", "yield3", "throw3", "module", "export",
]
NOVALANG_TYPES = [
    "trit", "trit_array", "trit_map", "trit_set", "string", "number",
    "bool", "list", "dict", "any", "void", "result3",
]
SYNTAX_THEME = {
    "keywords": "#ff6ec7",      # neon pink
    "types": "#00ffff",         # cyan
    "strings": "#39ff14",       # neon green
    "numbers": "#ffaa00",       # amber
    "comments": "#666666",      # dim gray
    "operators": "#ff4444",     # red
    "functions": "#aa88ff",     # purple
    "background": "#0a0a12",    # deep navy
    "foreground": "#e0e0e0",    # light gray
}

_CREATE_NO_WINDOW = 0x08000000 if platform.system() == "Windows" else 0
_NOVALANG_EXE = r"C:\NovaX\novalang.exe"


class _REPLSession:
    """In-process REPL session for NovaLang code evaluation."""

    def __init__(self):
        self._history = []

    def evaluate(self, code):
        """Evaluate NovaLang code via novalang.exe and return result."""
        if not code or not code.strip():
            return {"ok": False, "error": "Empty code", "output": ""}
        try:
            si = None
            cf = 0
            if platform.system() == "Windows":
                si = subprocess.STARTUPINFO()
                si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                si.wShowWindow = 0
                cf = _CREATE_NO_WINDOW
            # Write code to temp file and execute
            tmp = os.path.join(os.environ.get("TEMP", r"C:\NovaX\tmp"), "repl_eval.nova")
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(code)
            result = subprocess.run(
                [_NOVALANG_EXE, tmp],
                capture_output=True, text=True, timeout=15,
                creationflags=cf, startupinfo=si,
                cwd=r"C:\NovaX"
            )
            output = result.stdout.strip()
            error = result.stderr.strip()
            entry = {
                "code": code[:500],
                "output": output[:2000],
                "error": error[:1000] if result.returncode != 0 else "",
                "ok": result.returncode == 0,
                "time": time.time(),
            }
            self._history.append(entry)
            return entry
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": "Execution timed out (15s)", "output": ""}
        except Exception as e:
            return {"ok": False, "error": str(e), "output": ""}

    def get_history(self, limit=50):
        return self._history[-limit:]

    def clear_history(self):
        self._history.clear()
        return {"ok": True, "cleared": True}


class NovaLangDebugger:
    """NovaLang debugger with REPL, breakpoints, and code analysis."""

    def __init__(self):
        self.breakpoints = []
        self.registered = False
        self.repl = _REPLSession()

    def register_language(self):
        self.registered = True

    def set_breakpoint(self, file=None, line=None):
        bp = {"file": file, "line": line, "id": len(self.breakpoints)}
        self.breakpoints.append(bp)
        return {"ok": True, "breakpoint": bp}

    def remove_breakpoint(self, file=None, line=None):
        """Remove a breakpoint by file+line."""
        before = len(self.breakpoints)
        self.breakpoints = [
            bp for bp in self.breakpoints
            if not (bp.get("file") == file and bp.get("line") == line)
        ]
        removed = before - len(self.breakpoints)
        return {"ok": True, "removed": removed}

    def list_breakpoints(self):
        return {"breakpoints": self.breakpoints, "count": len(self.breakpoints)}

    def clear_breakpoints(self):
        self.breakpoints.clear()
        return {"ok": True, "cleared": True}

    def step(self, **kwargs):
        return {"status": "step_not_available", "breakpoints": len(self.breakpoints)}

    def evaluate(self, expr=None, **kwargs):
        """Evaluate a NovaLang expression via the REPL."""
        return self.repl.evaluate(expr or "")

    def analyze(self, code):
        """Static analysis of NovaLang code — checks for common issues."""
        if not code:
            return {"ok": False, "issues": [], "error": "No code provided"}
        issues = []
        lines = code.split("\n")
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            # Check for common NovaLang gotchas
            if "f\"" in stripped and "(" in stripped.split("f\"")[-1]:
                issues.append({
                    "line": i, "severity": "warning",
                    "message": "f-string may contain function call — assign to variable first"
                })
            if stripped.startswith("let ") and "if3" in stripped:
                issues.append({
                    "line": i, "severity": "warning",
                    "message": "let-in-if3 pattern — if3 returns trit, not the assigned value"
                })
            if "== 1" in stripped or "== -1" in stripped or "== 0" in stripped:
                if "trit" not in stripped.lower():
                    issues.append({
                        "line": i, "severity": "info",
                        "message": "Comparing with integer — use trit constants (+1/0/-1) for clarity"
                    })
            if "dict_set" in stripped and "let " not in stripped and "set " not in stripped:
                issues.append({
                    "line": i, "severity": "warning",
                    "message": "dict_set result not assigned — use set or let to capture"
                })
        return {
            "ok": True,
            "issues": issues,
            "total_lines": len(lines),
            "total_issues": len(issues),
        }

    def status(self):
        return {
            "registered": self.registered,
            "breakpoints": len(self.breakpoints),
            "repl_history": len(self.repl._history),
            "status": "active" if self.registered else "inactive",
        }
