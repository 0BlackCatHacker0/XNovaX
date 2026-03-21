# ai_router_memory.py — Stub for orchestrator startup
# Original encrypted (.enc). Provides minimal no-op implementations.

DEFAULT_RULES = {
    "max_retries": 3,
    "fallback_order": ["local", "cloud"],
    "timeout": 30,
    "learning_enabled": False
}

# Fallback cascade order — orchestrator imports this
FALLBACK = ["anthropic", "openai", "openrouter", "deepseek", "groq", "ollama"]

def record(model=None, prompt=None, response=None, latency=0, success=True, **kwargs):
    """Record an AI routing event. Stub no-op."""
    return True

def get_stats():
    """Get routing statistics. Stub returns empty stats."""
    return {"total_requests": 0, "models": {}, "avg_latency": 0}

def get_history(limit=50):
    """Get routing history. Stub returns empty list."""
    return []

def get_dashboard():
    """Get dashboard data. Stub returns empty dashboard."""
    return {"stats": get_stats(), "history": [], "rules": DEFAULT_RULES}
