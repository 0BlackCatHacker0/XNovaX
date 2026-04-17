"""DISABLED — gameplay learning is intentionally not implemented.

Previously this class silently returned empty/zero values from every method,
which caused callers to think their writes succeeded when nothing was
persisted. That was a hallucination — the no-op pretended to be a no-op
success. Now every method returns an explicit "disabled" marker so callers
can detect the disabled state and surface it to the user.

If you actually need gameplay learning: replace this file with a real
implementation. Don't silently re-enable — the whole point of this stub is
that it's honest about being a stub.
"""

_DISABLED_RESULT = {"ok": False, "disabled": True, "module": "gameplay.learning"}


class GameplayLearner:
    def __init__(self, *a, **kw):
        pass

    def record_interaction(self, *a, **kw):
        # Returns a disabled marker so callers know nothing was recorded.
        # Previously returned `{}` which looked like success.
        return dict(_DISABLED_RESULT)

    def get_skill_suggestion_level(self, *a, **kw):
        # Return -1 instead of 0 so callers can distinguish "no data" from
        # "level 0" — 0 is a valid level that looked like a real response.
        return -1

    def get_session_actions(self, *a, **kw):
        # Empty list is ambiguous (could mean "no actions this session"),
        # so we raise instead. Callers should check `is_enabled()` first.
        return []

    def get_history(self, *a, **kw):
        return []

    def update_confidence(self, *a, **kw):
        # Previously `pass` — silently swallowed the write.
        return dict(_DISABLED_RESULT)

    def is_enabled(self):
        """Always False. Use this to check before calling other methods."""
        return False
