"""DISABLED MODULE — NovaX safety prohibition. All functions return no-op/DISABLED."""

_DISABLED = {"ok": False, "status": "DISABLED"}

def _noop(*a, **kw): return _DISABLED

# Explicit exports for known imports
enable_startup = disable_startup = startup_status = _noop
is_admin = lambda: False
set_wallpaper = wallpaper_status = restore_wallpaper = _noop
set_theme = theme_status = restore_theme = _noop
set_lock_screen = lockscreen_status = restore_lock_screen = _noop
set_file_associations = file_assoc_status = restore_file_associations = _noop
add_context_menu = remove_context_menu = context_menu_status = _noop
register_protocol = unregister_protocol = protocol_status = _noop
integration_status = _noop
hide_taskbar = show_taskbar = taskbar_status = _noop
scan_installed_apps = lambda: []
scan_devices = lambda: []
list_usb_drives = lambda: []

# Catch-all for any other attribute
def __getattr__(name):
    return _noop
