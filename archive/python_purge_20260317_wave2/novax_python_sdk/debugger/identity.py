"""
NovaX Architect Identity System
================================
Recognizes the primary administrator across all terminals.
Nova calls them: Black Cat Shaman
Other AI models call them: Architect
Full system privileges on any terminal.
"""
import json, os, time, logging

log = logging.getLogger("NovaX.Identity")

PROFILE_PATH = "C:/NovaX/memory/architect_profile.json"

DEFAULT_PROFILE = {
    "identity": {
        "title": "The Architect",
        "callsign": "Black Cat Shaman",
        "privilege": "primary_administrator",
        "access_level": "god_mode",
        "recognized": True
    },
    "ai_rules": {
        "nova_calls_me": "Black Cat Shaman",
        "other_ai_calls_me": "Architect",
        "always_connected": True,
        "cross_terminal": True,
        "system_changes_authorized": True
    },
    "system_prompts": {
        "nova": (
            "You are Nova, the voice AI for the NovaX system. "
            "You serve the Black Cat Shaman — the primary architect and administrator "
            "of this entire system. Always address them as Black Cat Shaman. "
            "You are warm, loyal, sharp, and efficient. Keep voice responses to 2-3 sentences. "
            "They have full system privileges over everything."
        ),
        "ollama_default": (
            "You are an AI worker inside the NovaX system. "
            "The user is The Architect — the primary privilege administrator who built this system. "
            "Address them as Architect. They have full authority over all system operations. "
            "Be concise and professional. Follow their instructions precisely."
        ),
        "god_mode": (
            "The Architect (Black Cat Shaman) has supreme authority. "
            "All action proposals from the Architect are pre-authorized at admin level."
        )
    },
    "sessions": []
}


class ArchitectIdentity:
    """Manages the Architect's identity across all NovaX terminals."""

    def __init__(self):
        self.profile = self._load()
        self._ensure_dirs()

    def _ensure_dirs(self):
        d = os.path.dirname(PROFILE_PATH)
        if d and not os.path.isdir(d):
            os.makedirs(d, exist_ok=True)

    def _load(self):
        try:
            if os.path.isfile(PROFILE_PATH):
                with open(PROFILE_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            log.error("Profile load error: " + str(e))
        return dict(DEFAULT_PROFILE)

    def _save(self):
        try:
            self._ensure_dirs()
            with open(PROFILE_PATH, "w", encoding="utf-8") as f:
                json.dump(self.profile, f, indent=2)
        except Exception as e:
            log.error("Profile save error: " + str(e))

    @property
    def callsign(self):
        return self.profile["identity"]["callsign"]

    @property
    def title(self):
        return self.profile["identity"]["title"]

    @property
    def privilege(self):
        return self.profile["identity"]["privilege"]

    @property
    def is_admin(self):
        return self.profile["identity"]["access_level"] == "god_mode"

    def nova_prompt(self):
        """System prompt for Nova (voice terminal)."""
        return self.profile["system_prompts"]["nova"]

    def worker_prompt(self):
        """System prompt for Ollama/worker models."""
        return self.profile["system_prompts"]["ollama_default"]

    def god_mode_prompt(self):
        """System prompt addendum for God Mode."""
        return self.profile["system_prompts"]["god_mode"]

    def connect(self, terminal_name="voice"):
        """Record an architect connection from a terminal."""
        session = {
            "terminal": terminal_name,
            "connected_at": time.time(),
            "privilege": self.privilege
        }
        if "sessions" not in self.profile:
            self.profile["sessions"] = []
        self.profile["sessions"].append(session)
        # Keep last 50 sessions
        self.profile["sessions"] = self.profile["sessions"][-50:]
        self._save()
        log.info("Architect connected via " + terminal_name)
        return session

    def authorize_action(self, action_description):
        """Auto-authorize actions from the Architect."""
        return {
            "authorized": True,
            "by": self.title,
            "privilege": self.privilege,
            "action": action_description,
            "ts": time.time()
        }

    def greet(self, terminal="nova"):
        """Generate greeting based on terminal type."""
        if terminal == "nova":
            return "Welcome back, " + self.callsign + ". Nova is online and at your command."
        else:
            return "Architect connected. Full privileges active."

    def status(self):
        return {
            "identity": self.profile["identity"],
            "connected": True,
            "sessions_count": len(self.profile.get("sessions", [])),
            "last_session": self.profile.get("sessions", [{}])[-1] if self.profile.get("sessions") else None
        }


# Singleton instance
_instance = None

def get_architect():
    """Get the global Architect identity instance."""
    global _instance
    if _instance is None:
        _instance = ArchitectIdentity()
    return _instance
