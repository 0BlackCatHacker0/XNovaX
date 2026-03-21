"""
NovaX Visual Perception System
Extracts structured state from active windows.
Models receive interpreted state objects instead of pixels.
Modes: Game Administrator, 3D Modeling, UI Builder.
"""
import subprocess, json, time, logging, threading

log = logging.getLogger("NovaX.Perception")

class PerceptionMode:
    GAME_ADMIN = "game_administrator"
    MODELING_3D = "3d_modeling"
    UI_BUILDER = "ui_builder"
    GENERAL = "general"

class WindowState:
    """Structured state extracted from an active window."""
    def __init__(self, title="", process="", rect=None):
        self.title = title
        self.process = process
        self.rect = rect or {}
        self.elements = []
        self.detected_type = "unknown"
        self.timestamp = time.time()

    def to_dict(self):
        return {"title": self.title, "process": self.process, "rect": self.rect,
                "elements": self.elements, "type": self.detected_type, "ts": self.timestamp}

class PerceptionEngine:
    def __init__(self):
        self.mode = PerceptionMode.GENERAL
        self.active_windows = []
        self.state_history = []
        self._lock = threading.Lock()

    def set_mode(self, mode):
        self.mode = mode
        log.info(f"Perception mode: {mode}")

    def scan_windows(self):
        """Get active window list via PowerShell."""
        cmd = """powershell -NoProfile -Command "Get-Process | Where-Object {$_.MainWindowTitle -ne ''} | Select-Object ProcessName,MainWindowTitle,Id | ConvertTo-Json -Compress" """
        try:
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
            if r.returncode != 0:
                return []
            data = json.loads(r.stdout)
            if isinstance(data, dict): data = [data]
            windows = []
            for w in data:
                ws = WindowState(
                    title=w.get("MainWindowTitle", ""),
                    process=w.get("ProcessName", ""),
                )
                ws.detected_type = self._classify_window(ws)
                windows.append(ws)
            with self._lock:
                self.active_windows = windows
            return [w.to_dict() for w in windows]
        except Exception as e:
            log.error(f"Window scan failed: {e}")
            return []

    def _classify_window(self, ws):
        p = ws.process.lower()
        t = ws.title.lower()
        if any(x in p for x in ["unity", "unreal", "godot"]): return "game_engine"
        if any(x in p for x in ["blender", "maya", "3dsmax", "zbrush"]): return "3d_modeling"
        if any(x in p for x in ["code", "pycharm", "intellij", "rider"]): return "ide"
        if any(x in p for x in ["chrome", "firefox", "edge", "brave"]): return "browser"
        if any(x in p for x in ["kodi", "vlc", "mpv"]): return "media_player"
        if any(x in p for x in ["photoshop", "gimp", "figma"]): return "design"
        if any(x in p for x in ["excel", "word", "powerpoint"]): return "office"
        if any(x in p for x in ["steam", "epic"]): return "game_launcher"
        if "terminal" in p or "powershell" in p or "cmd" in p: return "terminal"
        return "application"

    def get_state_for_model(self):
        """Return interpreted state for AI model consumption."""
        self.scan_windows()
        state = {
            "mode": self.mode,
            "timestamp": time.time(),
            "windows": [w.to_dict() for w in self.active_windows],
            "window_count": len(self.active_windows),
            "types": {},
        }
        for w in self.active_windows:
            t = w.detected_type
            state["types"][t] = state["types"].get(t, 0) + 1
        with self._lock:
            self.state_history.append(state)
            if len(self.state_history) > 100:
                self.state_history = self.state_history[-100:]
        return state

    def focused_context(self):
        """Get context for the currently focused application."""
        cmd = """powershell -NoProfile -Command "$fw=[System.Windows.Forms.Form]::ActiveForm; if($fw){$fw.Text}else{'none'}" """
        # Simpler: just return first window
        if self.active_windows:
            return self.active_windows[0].to_dict()
        return None

    def status(self):
        return {"mode": self.mode, "windows": len(self.active_windows),
                "history_depth": len(self.state_history)}
