# ai_router.py — Intelligent task router with provider cascade
# Classifies prompts into task types, selects best model per task,
# and provides the route_with_fallback() function the orchestrator expects.
# Returns (model, task_type, mode) tuple.

import re
import json
import time
import requests

_CLOUD_ROUTER = "http://127.0.0.1:9878"

# ── Task classification patterns ──
_TASK_PATTERNS = {
    "code": [
        r"\b(code|function|class|import|def |async |const |let |var |return |bug|debug|error|traceback|exception|fix|refactor|compile|syntax)\b",
        r"\b(python|javascript|rust|java|html|css|typescript|novalang|nova)\b",
    ],
    "reasoning": [
        r"\b(explain|why|how does|analyze|compare|evaluate|think|reason|logic|proof|math|calculate)\b",
    ],
    "creative": [
        r"\b(write|story|poem|creative|generate|imagine|design|brainstorm|idea)\b",
    ],
    "search": [
        r"\b(search|find|look up|what is|who is|when did|latest|news|current)\b",
    ],
    "system": [
        r"\b(run|execute|install|start|stop|restart|kill|process|service|port|file|folder|directory)\b",
    ],
    "vision": [
        r"\b(image|picture|photo|screenshot|visual|see|look at|describe this)\b",
    ],
    "chat": [],  # default fallback
}

# ── Model preferences per task type (public alias: MODELS) ──
_TASK_MODELS = {
    "code": "anthropic",      # Claude best for code
    "reasoning": "anthropic",  # Claude best for reasoning
    "creative": "openai",      # GPT-4o good for creative
    "search": "openrouter",    # OpenRouter has search models
    "system": "executor",      # Direct system execution
    "vision": "openai",        # GPT-4o has vision
    "chat": "anthropic",       # Default to Claude for chat
}

# ── Mode mapping ──
_TASK_MODES = {
    "code": "precise",
    "reasoning": "analytical",
    "creative": "creative",
    "search": "factual",
    "system": "executor",
    "vision": "visual",
    "chat": "balanced",
}

# ── Routing memory (simple win/loss tracker) ──
_route_stats = {}


def classify_task(prompt):
    """Classify a prompt into a task type based on pattern matching."""
    prompt_lower = prompt.lower()
    scores = {}
    for task_type, patterns in _TASK_PATTERNS.items():
        score = 0
        for pattern in patterns:
            matches = re.findall(pattern, prompt_lower)
            score += len(matches)
        scores[task_type] = score

    # Find best match (minimum 1 match needed, else default to chat)
    best = max(scores, key=scores.get) if scores else "chat"
    if scores.get(best, 0) == 0:
        best = "chat"
    return best


def select_model(task_type, prompt=None):
    """Select the best model/provider for a task type."""
    preferred = _TASK_MODELS.get(task_type, "anthropic")

    # Check routing memory — if a provider keeps failing, skip it
    stats = _route_stats.get(preferred, {"wins": 0, "losses": 0})
    if stats.get("losses", 0) > 5 and stats.get("wins", 0) == 0:
        # This provider is consistently failing, use fallback
        fallback_order = ["anthropic", "openai", "openrouter", "ollama"]
        for fb in fallback_order:
            if fb != preferred:
                fb_stats = _route_stats.get(fb, {"wins": 0, "losses": 0})
                if fb_stats.get("losses", 0) < 3:
                    return fb
        return "ollama"  # ultimate fallback

    return preferred


def record(task_type, model, success, duration=0):
    """Record routing outcome for learning."""
    key = model.split(" (")[0] if " (" in model else model
    if key not in _route_stats:
        _route_stats[key] = {"wins": 0, "losses": 0, "total_ms": 0}
    if success:
        _route_stats[key]["wins"] += 1
    else:
        _route_stats[key]["losses"] += 1
    _route_stats[key]["total_ms"] += int(duration * 1000)


def route_with_fallback(prompt, models=None, context=None, **kwargs):
    """
    Route an AI request with intelligent fallback.
    Returns (model, task_type, mode) tuple as expected by orchestrator.
    """
    # Classify the task
    task_type = classify_task(prompt)

    # Select best model
    model = select_model(task_type, prompt)

    # Get mode
    mode = _TASK_MODES.get(task_type, "balanced")

    return (model, task_type, mode)


def get_routing_stats():
    """Get current routing statistics."""
    return {
        "stats": _route_stats,
        "providers_tracked": len(_route_stats),
    }


# ── Public exports for orchestrator imports ──
MODELS = _TASK_MODELS
