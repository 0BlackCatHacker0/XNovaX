"""DISABLED MODULE — NovaX safety prohibition."""
_DISABLED = {"ok": False, "status": "DISABLED"}
def _noop(*a, **kw): return _DISABLED
enable_startup = disable_startup = startup_status = takeover_status = killswitch = _noop
def __getattr__(name): return _noop
