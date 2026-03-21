# profile_manager.py — Stub for orchestrator startup
# Original encrypted (.enc). Provides minimal no-op implementations.

_active_profile = "default"
_profiles = {"default": {"name": "default", "config": {}}}

def switch(name):
    """Switch active profile. Stub updates in-memory state."""
    global _active_profile
    _active_profile = name
    return True

def get_active():
    """Get active profile name. Stub returns in-memory value."""
    return _active_profile

def list_profiles():
    """List all profiles. Stub returns in-memory dict."""
    return list(_profiles.keys())

def export_profile(name=None):
    """Export a profile. Stub returns profile dict."""
    name = name or _active_profile
    return _profiles.get(name, {})

def import_profile(data):
    """Import a profile. Stub stores in memory."""
    name = data.get("name", "imported")
    _profiles[name] = data
    return True

def get_profile_config(name=None):
    """Get profile config. Stub returns empty dict."""
    name = name or _active_profile
    return _profiles.get(name, {}).get("config", {})
