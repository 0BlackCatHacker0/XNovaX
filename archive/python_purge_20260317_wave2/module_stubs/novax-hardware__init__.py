"""
novax-hardware -- NovaX Hardware Capability Module
Auto-generated from NOVAX_MASTER_MODULE_FILE
Contains 3,328 sub-module capabilities for hardware domain.
"""

CATEGORY = "hardware"
SUB_MODULE_COUNT = 3328
SUB_MODULE_RANGE = (15, 99972)
ENABLED = True


def setup():
    """Called when module is enabled."""
    print(f"[{__name__}] Hardware module loaded (3,328 capabilities)")


def teardown():
    """Called when module is disabled."""
    print(f"[{__name__}] Hardware module unloaded")


def run(params=None):
    """Main entry point."""
    return {
        "status": "ok",
        "module": "novax-hardware",
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
