# device_detector.py — Stub for orchestrator startup
# Original encrypted (.enc). Provides minimal no-op implementations.

def scan_devices(**kwargs):
    return []

def device_status(**kwargs):
    return {"status": "stub_mode", "devices": 0}

def list_usb_drives(**kwargs):
    return []

def get_device_log(limit=50, **kwargs):
    return []

def add_rule(rule=None, **kwargs):
    return True

def remove_rule(rule_id=None, **kwargs):
    return True

def get_rules(**kwargs):
    return []

def start_monitor(**kwargs):
    return True

def stop_monitor(**kwargs):
    return True

def monitor_status(**kwargs):
    return {"running": False, "status": "stub_mode"}
