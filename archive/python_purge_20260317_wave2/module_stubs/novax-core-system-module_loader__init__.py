"""
novax-core-system-module_loader -- NovaX Core Script: system.module_loader
Auto-generated from NOVAX_MASTER_MODULE_FILE
"""

CORE_SCRIPT = "system.module_loader"
DOMAIN = "system"
FUNCTION = "module_loader"
ENABLED = True


def setup():
    print(f"[{__name__}] Core script system.module_loader loaded")


def teardown():
    print(f"[{__name__}] Core script system.module_loader unloaded")


def run(params=None):
    return {"status": "ok", "core_script": CORE_SCRIPT, "domain": DOMAIN}
