"""
NovaX Universal Prompt Controller (UPC)
========================================
Shared runtime across all prompt bars.
All prompts are thin clients connected to one central routing system.

Every prompt input becomes a PromptPacket routed through the UPC.
Changing the model once updates every prompt everywhere.
"""
import uuid
import time
import json
import os
import threading
import logging

log = logging.getLogger("NovaX.UPC")

# ============================================================
#  PROMPT PACKET
# ============================================================
class PromptPacket:
    """Standardized prompt payload routed through UPC."""
    def __init__(self, text, attachments=None, model=None, permissions=None, session_id=None):
        self.id = str(uuid.uuid4())[:12]
        self.text = text
        self.attachments = attachments or []
        self.model = model
        self.permissions = permissions or "standard"
        self.session_id = session_id
        self.timestamp = time.time()
        self.routed = False
        self.result = None

    def to_dict(self):
        return {
            "id": self.id, "text": self.text, "attachments": self.attachments,
            "model": self.model, "permissions": self.permissions,
            "session_id": self.session_id, "timestamp": self.timestamp,
            "routed": self.routed,
        }

# ============================================================
#  SESSION STATE
# ============================================================
class SessionState:
    """Global session state shared across all prompts."""
    def __init__(self):
        self.selected_model = "auto"
        self.permission_level = "standard"   # standard, elevated, god
        self.workspace_files = []
        self.conversation_memory = []
        self.tool_availability = {}
        self.god_mode = False
        self.session_id = str(uuid.uuid4())[:16]
        self.created_at = time.time()
        self._lock = threading.Lock()

    def set_model(self, model):
        with self._lock:
            old = self.selected_model
            self.selected_model = model
            log.info(f"UPC: Model changed globally: {old} -> {model}")
            return {"old": old, "new": model}

    def elevate(self, level):
        valid = ["standard", "elevated", "god"]
        if level not in valid:
            return {"ok": False, "error": f"invalid level: {level}"}
        with self._lock:
            self.permission_level = level
            self.god_mode = (level == "god")
            log.info(f"UPC: Permission level -> {level} (god_mode={self.god_mode})")
            return {"ok": True, "level": level, "god_mode": self.god_mode}

    def add_memory(self, entry):
        with self._lock:
            self.conversation_memory.append({
                "text": entry, "ts": time.time()
            })
            if len(self.conversation_memory) > 500:
                self.conversation_memory = self.conversation_memory[-500:]

    def update_tools(self, tools_dict):
        with self._lock:
            self.tool_availability.update(tools_dict)

    def to_dict(self):
        return {
            "session_id": self.session_id,
            "selected_model": self.selected_model,
            "permission_level": self.permission_level,
            "god_mode": self.god_mode,
            "workspace_files": len(self.workspace_files),
            "memory_entries": len(self.conversation_memory),
            "tools_available": len(self.tool_availability),
            "created_at": self.created_at,
            "uptime": round(time.time() - self.created_at, 1),
        }

# ============================================================
#  UNIVERSAL PROMPT CONTROLLER
# ============================================================
class UniversalPromptController:
    """
    Central routing system for all prompt bars.
    All prompts are thin clients connected here.
    """
    def __init__(self):
        self.session = SessionState()
        self.registered_prompts = {}   # prompt_id -> metadata
        self.packet_history = []       # last N packets
        self.model_registry = {}       # model_name -> endpoint info
        self._lock = threading.Lock()

    # ---------- PROMPT REGISTRATION ----------
    def register_prompt(self, prompt_id, source="unknown"):
        """Register a prompt bar as a thin client."""
        with self._lock:
            self.registered_prompts[prompt_id] = {
                "source": source,
                "registered_at": time.time(),
                "packets_sent": 0,
            }
        log.info(f"UPC: Prompt registered: {prompt_id} ({source})")
        return {"ok": True, "session_id": self.session.session_id}

    def unregister_prompt(self, prompt_id):
        with self._lock:
            self.registered_prompts.pop(prompt_id, None)

    # ---------- MODEL REGISTRY ----------
    def register_model(self, name, endpoint=None, capabilities=None):
        """Register an AI model for routing."""
        self.model_registry[name] = {
            "name": name,
            "endpoint": endpoint,
            "capabilities": capabilities or [],
            "registered_at": time.time(),
            "calls": 0,
            "failures": 0,
        }
        log.info(f"UPC: Model registered: {name} @ {endpoint}")

    def available_models(self):
        return list(self.model_registry.keys())

    # ---------- ROUTING ----------
    def route(self, packet):
        """Route a PromptPacket to the appropriate model."""
        if not isinstance(packet, PromptPacket):
            return {"ok": False, "error": "invalid packet"}

        # Apply session state
        if not packet.model or packet.model == "auto":
            packet.model = self.session.selected_model
        packet.permissions = self.session.permission_level
        packet.session_id = self.session.session_id

        # Permission check
        if self.session.permission_level == "standard":
            # Block destructive actions without elevation
            dangerous = ["delete", "format", "kill", "rm -rf", "shutdown"]
            if any(d in packet.text.lower() for d in dangerous):
                return {
                    "ok": False, "error": "elevated permissions required",
                    "packet_id": packet.id, "requires": "elevated"
                }

        # Route to model
        model_info = self.model_registry.get(packet.model)
        if not model_info and packet.model != "auto":
            # Try fallback
            if self.model_registry:
                packet.model = list(self.model_registry.keys())[0]
                model_info = self.model_registry[packet.model]

        packet.routed = True

        # Record
        with self._lock:
            self.packet_history.append(packet.to_dict())
            if len(self.packet_history) > 200:
                self.packet_history = self.packet_history[-200:]
            if packet.model in self.registered_prompts:
                self.registered_prompts[packet.model]["packets_sent"] += 1

        # Add to conversation memory
        self.session.add_memory(packet.text)

        log.info(f"UPC: Routed packet {packet.id} -> {packet.model} [{packet.permissions}]")

        return {
            "ok": True,
            "packet_id": packet.id,
            "model": packet.model,
            "permissions": packet.permissions,
            "session_id": packet.session_id,
            "endpoint": model_info.get("endpoint") if model_info else None,
        }

    # ---------- STATE ----------
    def status(self):
        return {
            "session": self.session.to_dict(),
            "registered_prompts": len(self.registered_prompts),
            "models": self.available_models(),
            "packets_routed": len(self.packet_history),
        }

    def history(self, n=20):
        return self.packet_history[-n:]
