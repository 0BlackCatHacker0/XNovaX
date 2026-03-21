"""Context inference - understand what the user/system wants."""
from ..objects import Intent

class ContextEngine:
    def __init__(self):
        self.patterns = {
            "run": ["execute", "run", "start", "launch", "do"],
            "read": ["read", "show", "display", "get", "list", "cat"],
            "write": ["write", "create", "save", "make", "set"],
            "delete": ["delete", "remove", "kill", "stop", "rm"],
            "repair": ["fix", "repair", "recover", "heal", "restart"],
        }

    def infer(self, text: str) -> Intent:
        low = text.lower()
        for action, keywords in self.patterns.items():
            for kw in keywords:
                if kw in low:
                    return Intent(text=text, action=action, confidence=0.7)
        return Intent(text=text, action="unknown", confidence=0.1)
