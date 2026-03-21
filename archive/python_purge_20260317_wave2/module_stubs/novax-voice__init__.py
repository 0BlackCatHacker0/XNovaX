"""
novax-voice -- NovaX Voice Capability Module
Auto-generated from NOVAX_MASTER_MODULE_FILE
Contains 3,286 sub-module capabilities for voice domain.
"""

CATEGORY = "voice"
SUB_MODULE_COUNT = 3286
SUB_MODULE_RANGE = (105, 99981)
ENABLED = True


def setup():
    """Called when module is enabled."""
    print(f"[{__name__}] Voice module loaded (3,286 capabilities)")


def teardown():
    """Called when module is disabled."""
    print(f"[{__name__}] Voice module unloaded")


def run(params=None):
    """Main entry point."""
    return {
        "status": "ok",
        "module": "novax-voice",
        "category": CATEGORY,
        "capabilities": SUB_MODULE_COUNT,
        "range": SUB_MODULE_RANGE,
    }


def get_capabilities():
    """Return capability summary."""
    return {
        "category": CATEGORY,
        "count": SUB_MODULE_COUNT,
        "range": SUB_MODULE_RANGE,
        "enabled": ENABLED,
    }
