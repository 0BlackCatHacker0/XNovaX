"""DISABLED MODULE — NovaX safety prohibition."""
_DISABLED = {"ok": False, "status": "DISABLED"}
def _noop(*a, **kw): return _DISABLED
install_shell = uninstall_shell = shell_status = _noop
def __getattr__(name): return _noop
