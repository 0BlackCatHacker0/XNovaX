"""
novax-core-integration-api_gateway -- NovaX Core Script: integration.api_gateway
Auto-generated from NOVAX_MASTER_MODULE_FILE
"""

CORE_SCRIPT = "integration.api_gateway"
DOMAIN = "integration"
FUNCTION = "api_gateway"
ENABLED = True


def setup():
    print(f"[{__name__}] Core script integration.api_gateway loaded")


def teardown():
    print(f"[{__name__}] Core script integration.api_gateway unloaded")


def run(params=None):
    return {"status": "ok", "core_script": CORE_SCRIPT, "domain": DOMAIN}
