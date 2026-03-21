"""Tool runner - safe execution of commands and scripts."""
import subprocess, time, os, sys
from ..objects import Receipt

# Add NovaX core to path for openclaw_client
sys.path.insert(0, "C:/NovaX")

class ToolRunner:
    def __init__(self):
        self.history = []
        self.timeout = 30
        self._openclaw_enabled = None
        self._check_openclaw()

    def _check_openclaw(self):
        """Check if OpenClaw is available and enabled."""
        try:
            from core.openclaw_client import is_enabled, health
            self._openclaw_enabled = is_enabled()
            if self._openclaw_enabled:
                ok, msg = health()
                if not ok:
                    self._openclaw_enabled = False
        except:
            self._openclaw_enabled = False

    def _try_openclaw_shell(self, cmd, timeout=None):
        """Try to execute via OpenClaw if available."""
        if not self._openclaw_enabled:
            return None
        
        try:
            from core.openclaw_client import execute_actions
            result = execute_actions([{
                "type": "shell",
                "command": cmd,
                "timeout": timeout or self.timeout
            }], ask=False, timeout=(timeout or self.timeout) + 5)
            
            if result.get("ok"):
                return Receipt(
                    success=True,
                    output=result.get("output", ""),
                    duration=result.get("duration", 0),
                    metadata={"via": "openclaw"}
                )
        except Exception as e:
            # Fall back to local execution
            pass
        
        return None

    def shell(self, cmd, cwd=None, timeout=None, prefer_openclaw=True) -> Receipt:
        # Try OpenClaw first if enabled and preferred
        if prefer_openclaw and not cwd:  # OpenClaw doesn't support cwd yet
            openclaw_result = self._try_openclaw_shell(cmd, timeout)
            if openclaw_result:
                self.history.append({"cmd": cmd, "ts": time.time(), "via": "openclaw"})
                return openclaw_result
        
        # Fall back to local execution
        t = timeout or self.timeout
        start = time.time()
        try:
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                             timeout=t, cwd=cwd, encoding="utf-8", errors="replace")
            receipt = Receipt(success=r.returncode == 0,
                            output=r.stdout + r.stderr, duration=time.time()-start)
        except subprocess.TimeoutExpired:
            receipt = Receipt(success=False, output="TIMEOUT", duration=t)
        except Exception as e:
            receipt = Receipt(success=False, output=str(e), duration=time.time()-start)
        self.history.append({"cmd": cmd, "ts": time.time(), "via": "local"})
        return receipt

    def python_exec(self, code, timeout=30) -> Receipt:
        import tempfile, os
        tmp = os.path.join("C:/NovaX/temp", "exec_tmp.py")
        os.makedirs(os.path.dirname(tmp), exist_ok=True)
        with open(tmp, "w") as f: f.write(code)
        return self.shell(f'python "{tmp}"', timeout=timeout)

    def recent(self, n=10): return self.history[-n:]
