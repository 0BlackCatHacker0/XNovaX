# mode_system.py — Mode system with auto-switch intelligence
# Modes: standard, dev, stealth, creative, analytical

_current_mode = "standard"
_modes = {
    "standard": {"name": "standard", "features": []},
    "dev": {"name": "dev", "features": ["debug"]},
    "stealth": {"name": "stealth", "features": ["minimal_ui"]},
    "creative": {"name": "creative", "features": ["high_temp"]},
    "analytical": {"name": "analytical", "features": ["low_temp", "step_by_step"]},
}

_AUTO_PATTERNS = {
    "dev": ["code", "debug", "error", "fix", "function", "class", "import", "traceback"],
    "creative": ["write", "story", "poem", "creative", "design", "imagine"],
    "analytical": ["analyze", "explain", "compare", "evaluate", "why", "how"],
    "stealth": ["stealth", "quiet", "minimal"],
}


def get_mode():
    return _current_mode


def set_mode(mode):
    global _current_mode
    _current_mode = mode
    return True


def auto_switch(text):
    """Auto-detect best mode from prompt text."""
    global _current_mode
    if not text:
        return _current_mode
    text_lower = text.lower()
    for mode, keywords in _AUTO_PATTERNS.items():
        if any(kw in text_lower for kw in keywords):
            _current_mode = mode
            return mode
    _current_mode = "standard"
    return "standard"


def list_modes():
    return list(_modes.keys())


def get_mode_config(mode=None):
    return _modes.get(mode or _current_mode, {})
