# config.py — Stub for orchestrator startup
# Original encrypted (.enc). Provides minimal no-op implementations.

import os
from pathlib import Path

ROOT = Path(r"C:\NovaX")
DATA_DIR = ROOT / "data"
MEMORY_DIR = ROOT / "memory"
CORE_DIR = ROOT / "core"

# Default config values
PORT = 9999
DEBUG = False
VERSION = "5.0.0-stub"
HOST = "0.0.0.0"

def get(key, default=None):
    """Get a config value. Stub checks env then returns default."""
    return os.environ.get(f"NOVAX_{key.upper()}", default)

def set(key, value):
    """Set a config value. Stub no-op."""
    return True

def load(path=None):
    """Load config from file. Stub returns defaults."""
    return {"port": PORT, "debug": DEBUG, "version": VERSION}
