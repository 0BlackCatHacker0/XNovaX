# ui_memory.py — Stub for orchestrator startup
# Original encrypted (.enc). Provides minimal no-op implementations.

def record_interaction(action=None, **kwargs):
    return True

def match_routine(query=None, **kwargs):
    return None

def list_routines(**kwargs):
    return []

def enable_auto_replay(routine_id=None, **kwargs):
    return True

def disable_auto_replay(routine_id=None, **kwargs):
    return True

def get_auto_routines(**kwargs):
    return []

def get_stats(**kwargs):
    return {"total_interactions": 0, "routines": 0, "auto_enabled": 0}
